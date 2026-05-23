"""
Plain-English → structured ImportedProject via Claude.

When ANTHROPIC_API_KEY is set, user types "syngas to methanol, 2 reactors
in series, flash, distillation to 99% purity" and Claude generates a
complete ImportedProject shaped just like what the Excel/DWSIM parsers
produce. Falls back to a rule-based template when the key is absent so
the feature still works offline.

The Claude call uses a single tool-use turn with a strict JSON schema,
so output is deterministic-ish and never free-form prose. No prompt
injection surface since block/stream ids are quoted strings we re-emit,
not code we execute.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional

from .models import (
    Diagnostic,
    ImportResult,
    ImportedBlock,
    ImportedProject,
    ImportedStream,
)

logger = logging.getLogger(__name__)


# The schema we ask Claude to fill. Kept small on purpose — fills the
# minimum TEA needs, users refine from there.
_SCHEMA = {
    "name": "generate_process_flowsheet",
    "description": (
        "Emit a Jasper process flowsheet matching the user's description. "
        "Use canonical SI units: K for temperature, Pa for pressure, mol/s "
        "or kg/s for flow. Omit values you're not confident about rather "
        "than fabricating; downstream sizing uses sensible defaults."
    ),
    "input_schema": {
        "type": "object",
        "required": ["name", "components", "blocks", "streams"],
        "properties": {
            "name": {"type": "string", "description": "Process name"},
            "components": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Component names present in the process (e.g. H2, CO, Methanol)",
            },
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "type", "name"],
                    "properties": {
                        "id": {"type": "string"},
                        "type": {
                            "type": "string",
                            "description": (
                                "One of: Feed, Sink, Mixer, Splitter, Pump, Compressor, "
                                "Valve, Heater, Cooler, HeatExchanger, Flash, Tank, "
                                "DistillationColumn, Absorber, Stripper, RCSTR, RPfr, "
                                "REquil, RGibbs, RStoic, Reactor"
                            ),
                        },
                        "name": {"type": "string"},
                        "duty": {"type": "number", "description": "Watts (positive = heating)"},
                        "work": {"type": "number", "description": "Shaft power in watts"},
                    },
                },
            },
            "streams": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "from_block", "to_block"],
                    "properties": {
                        "id": {"type": "string"},
                        "from_block": {"type": "string"},
                        "from_port": {"type": "string"},
                        "to_block": {"type": "string"},
                        "to_port": {"type": "string"},
                        "T": {"type": "number", "description": "Temperature in K"},
                        "P": {"type": "number", "description": "Pressure in Pa"},
                        "flow_mol": {"type": "number", "description": "mol/s"},
                        "composition": {
                            "type": "object",
                            "additionalProperties": {"type": "number"},
                            "description": "component name → mole fraction",
                        },
                    },
                },
            },
        },
    },
}


_SYSTEM_PROMPT = (
    "You are a chemical engineering assistant building a starter flowsheet "
    "for a techno-economic analysis (TEA). The user describes a process in "
    "plain English; you emit a structured flowsheet via the "
    "generate_process_flowsheet tool. Guidance:\n"
    "- Prefer the minimum set of blocks that captures the process intent.\n"
    "- Always include at least one Feed and one Sink/Product block.\n"
    "- Give every block a unique id like F1, C1, R1, X1, P1.\n"
    "- Give every stream a unique id S1, S2, ...\n"
    "- Composition values are mole fractions and must sum to ~1.0 per stream.\n"
    "- Use canonical SI units: K / Pa / mol/s. No barg, no C, no kmol/h.\n"
    "- Omit fields you can't estimate confidently rather than fabricating.\n"
    "- If the user mentions specific temperatures/pressures, convert to K/Pa "
    "  yourself and include them. Otherwise leave blank."
)


# Max prompt length for safety (also caps Anthropic input-token bill).
_MAX_DESCRIPTION_CHARS = 4000


def describe_to_project(description: str) -> ImportResult:
    """
    Turn a plain-English description into an ImportedProject.

    Uses Claude when ANTHROPIC_API_KEY is available; falls back to a
    tiny rule-based generator otherwise so the endpoint never 500s.
    """
    if not isinstance(description, str) or not description.strip():
        return ImportResult(
            project=None,
            diagnostics=[Diagnostic(severity="error", message="Empty description")],
        )
    if len(description) > _MAX_DESCRIPTION_CHARS:
        return ImportResult(
            project=None,
            diagnostics=[
                Diagnostic(
                    severity="error",
                    message=f"Description exceeds {_MAX_DESCRIPTION_CHARS}-char limit",
                )
            ],
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            return _claude_describe(description.strip(), api_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Claude describe failed")
            return ImportResult(
                project=None,
                diagnostics=[
                    Diagnostic(severity="error", message=f"Claude request failed: {exc}")
                ],
            )

    return _fallback_describe(description.strip())


# ── Claude path ─────────────────────────────────────────────────────────────


def _claude_describe(description: str, api_key: str) -> ImportResult:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    diagnostics: list[Diagnostic] = []

    # Sanitize the description: length cap + strip control characters
    # (basic prompt-injection hardening).
    clean = "".join(c for c in description if c.isprintable() or c in "\n\r\t")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[_SCHEMA],
        tool_choice={"type": "tool", "name": "generate_process_flowsheet"},
        messages=[{"role": "user", "content": clean}],
    )

    tool_block = next(
        (b for b in response.content if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_block is None:
        return ImportResult(
            project=None,
            diagnostics=[
                Diagnostic(
                    severity="error",
                    message="Claude did not emit the expected tool call",
                )
            ],
        )

    try:
        payload = tool_block.input
    except AttributeError:
        return ImportResult(
            project=None,
            diagnostics=[
                Diagnostic(severity="error", message="Claude tool call missing input")
            ],
        )

    return _payload_to_project(payload, diagnostics)


# ── Fallback path (no Claude key) ───────────────────────────────────────────


def _fallback_describe(description: str) -> ImportResult:
    """
    Minimal rule-based template. If the user's description contains
    reactor/column keywords, scaffold a Feed → unit → Sink chain.
    """
    diagnostics: list[Diagnostic] = [
        Diagnostic(
            severity="info",
            message=(
                "ANTHROPIC_API_KEY not configured — returning a generic 3-block "
                "starter template. Edit to match your process."
            ),
        )
    ]

    lowered = description.lower()
    has_reactor = any(kw in lowered for kw in ("reactor", "cstr", "pfr", "synthesis"))
    has_column = any(kw in lowered for kw in ("distillation", "column", "tower"))

    blocks: list[ImportedBlock] = [
        ImportedBlock(id="F1", type="Feed", name="Feed"),
    ]
    streams: list[ImportedStream] = []

    current_out = "F1"

    if has_reactor:
        blocks.append(ImportedBlock(id="R1", type="Reactor", name="Reactor"))
        streams.append(
            ImportedStream(
                id=f"S{len(streams) + 1}",
                from_block=current_out, from_port="out",
                to_block="R1", to_port="in",
                T=300.0, P=1e5, flow_mol=10.0,
            )
        )
        current_out = "R1"

    if has_column:
        blocks.append(
            ImportedBlock(id="C1", type="DistillationColumn", name="Distillation")
        )
        streams.append(
            ImportedStream(
                id=f"S{len(streams) + 1}",
                from_block=current_out, from_port="out",
                to_block="C1", to_port="feed",
                T=350.0, P=1e5, flow_mol=10.0,
            )
        )
        current_out = "C1"

    blocks.append(ImportedBlock(id="P1", type="Product", name="Product"))
    streams.append(
        ImportedStream(
            id=f"S{len(streams) + 1}",
            from_block=current_out,
            from_port="overhead" if current_out == "C1" else "out",
            to_block="P1", to_port="in",
            T=300.0, P=1e5, flow_mol=10.0,
        )
    )

    project = ImportedProject(
        name="Starter flowsheet",
        components=[],
        blocks=blocks,
        streams=streams,
    )
    return ImportResult(project=project, diagnostics=diagnostics)


# ── Payload → dataclasses ───────────────────────────────────────────────────


def _payload_to_project(payload: dict, diagnostics: list[Diagnostic]) -> ImportResult:
    try:
        blocks = [
            ImportedBlock(
                id=str(b["id"]),
                type=str(b["type"]),
                name=str(b.get("name", b["id"])),
                duty=_opt_float(b.get("duty")),
                work=_opt_float(b.get("work")),
            )
            for b in payload.get("blocks", [])
        ]
        streams = [
            ImportedStream(
                id=str(s["id"]),
                from_block=_opt_str(s.get("from_block")),
                from_port=_opt_str(s.get("from_port")),
                to_block=_opt_str(s.get("to_block")),
                to_port=_opt_str(s.get("to_port")),
                T=_opt_float(s.get("T")),
                P=_opt_float(s.get("P")),
                flow_mol=_opt_float(s.get("flow_mol")),
                flow_mass=_opt_float(s.get("flow_mass")),
                composition=s.get("composition", {}) or {},
            )
            for s in payload.get("streams", [])
        ]
    except (KeyError, TypeError, ValueError) as exc:
        return ImportResult(
            project=None,
            diagnostics=[
                *diagnostics,
                Diagnostic(severity="error", message=f"Malformed Claude payload: {exc}"),
            ],
        )

    project = ImportedProject(
        name=str(payload.get("name", "Described process")),
        components=[str(c) for c in payload.get("components", []) if c],
        blocks=blocks,
        streams=streams,
    )
    return ImportResult(project=project, diagnostics=diagnostics)


def _opt_str(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _opt_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
