"""
Aspen Plus .rep parser — the Results Summary report.

Where ``.inp`` defines a flowsheet pre-solve, ``.rep`` is what Aspen emits
after a converged run. It's a text report with two tabular sections we
care about:

1. **BLOCK results** — one sub-section per block with duty/work/pressure-drop.
2. **STREAM results** — stream-property table with T, P, molar flow and
   component mole fractions across rows vs. streams across columns.

We lean on the column-aligned structure: Aspen prints with fixed-width
padding, so we detect headers via stream-name tokens on the right and
anchor row parsing to the label in the leftmost column.

Coverage is intentionally narrow — enough to back-fill the converged
data onto an existing flowsheet that was imported from ``.inp`` first.
If the user uploads the ``.rep`` alone, we still emit a
best-effort project with streams and T/P/flow, but blocks will be
"Unknown" because block types live in ``.inp``, not ``.rep``.
"""
from __future__ import annotations

import re
from typing import Optional

from app.units import DimensionMismatchError, UnknownUnitError, convert
from .models import (
    Diagnostic,
    ImportResult,
    ImportedBlock,
    ImportedProject,
    ImportedStream,
)

_MAX_BYTES = 25 * 1024 * 1024

# Aspen uppercases every unit in .rep output. Map to the canonical form our
# pint-backed converter understands.
_UNIT_NORMALIZE = {
    "PA": "Pa",
    "KPA": "kPa",
    "BAR": "bar",
    "BARA": "bar",
    "BARG": "barg",
    "ATM": "atm",
    "PSI": "psi",
    "PSIA": "psi",
    "PSIG": "psig",
    "K": "K",
    "C": "degC",
    "F": "degF",
    "R": "degR",
    "MOL/S": "mol/s",
    "MOL/SEC": "mol/s",
    "KMOL/HR": "kmol/h",
    "KMOL/H": "kmol/h",
    "KMOL/SEC": "kmol/s",
    "KG/HR": "kg/h",
    "KG/H": "kg/h",
    "KG/S": "kg/s",
    "KG/SEC": "kg/s",
    "LB/HR": "lb/h",
    "W": "W",
    "KW": "kW",
    "MW": "MW",
    "MMBTU/HR": "MMBtu/h",
}


def _norm_unit(u: Optional[str]) -> Optional[str]:
    if u is None:
        return None
    key = u.upper()
    return _UNIT_NORMALIZE.get(key, u)

# Known Aspen row labels → canonical key
_ROW_LABELS = {
    "TEMPERATURE": "T",
    "TEMP": "T",
    "PRESSURE": "P",
    "PRES": "P",
    "MOLE FLOW": "flow_mol",
    "TOTAL MOLE FLOW": "flow_mol",
    "MASS FLOW": "flow_mass",
    "TOTAL MASS FLOW": "flow_mass",
}


def parse_aspen_report(data: bytes, *, filename: str = "simulation.rep") -> ImportResult:
    """Parse an Aspen Plus .rep Results Summary into a Jasper ImportedProject."""
    diagnostics: list[Diagnostic] = []

    if len(data) > _MAX_BYTES:
        diagnostics.append(
            Diagnostic(
                severity="error",
                message=f"File exceeds {_MAX_BYTES // 1024 // 1024} MB limit",
                location=filename,
            )
        )
        return ImportResult(project=None, diagnostics=diagnostics)

    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()

    streams = _parse_stream_section(lines, diagnostics)
    blocks = _parse_block_section(lines, diagnostics)

    if not streams and not blocks:
        diagnostics.append(
            Diagnostic(
                severity="error",
                message="No stream or block tables recognised in .rep file",
                location=filename,
            )
        )
        return ImportResult(project=None, diagnostics=diagnostics)

    project = ImportedProject(
        name=filename.rsplit(".", 1)[0],
        components=sorted({c for s in streams.values() for c in s.composition}),
        blocks=list(blocks.values()),
        streams=list(streams.values()),
    )
    return ImportResult(project=project, diagnostics=diagnostics)


# ── Stream section ──────────────────────────────────────────────────────────


def _parse_stream_section(
    lines: list[str],
    diagnostics: list[Diagnostic],
) -> dict[str, ImportedStream]:
    """
    Scan for blocks beginning with 'STREAM SECTION' or 'STREAM ID'.

    Aspen reports stream property tables in horizontal chunks:

        STREAM ID               S1          S2          S3
        TEMPERATURE     K      300.0       400.0       298.15
        PRESSURE        BAR    50.00       50.00       1.00
        MOLE FLOW       KMOL/HR 100.0      100.0       3.6
        MOLE FRAC
          H2                  0.67        0.00        0.00
          CO                  0.33        0.00        0.00
          METHANOL            0.00        1.00        0.00

    We slice on the STREAM ID header rows and parse downward.
    """
    streams: dict[str, ImportedStream] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        tokens = _split_ws(line)
        if tokens and tokens[0].upper() == "STREAM" and len(tokens) > 1 and tokens[1].upper() in {"ID", "NAME"}:
            header_streams = tokens[2:]
            block_data: dict[str, dict[str, float]] = {s: {} for s in header_streams}
            block_comp: dict[str, dict[str, float]] = {s: {} for s in header_streams}
            i += 1
            in_mole_frac = False
            while i < len(lines):
                row = lines[i]
                upper = row.upper().rstrip()
                if not upper.strip():
                    # Blank line might separate sub-table but we keep reading
                    i += 1
                    # Stop if next non-blank starts a new STREAM header or plain text
                    j = i
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        next_tokens = _split_ws(lines[j])
                        if (
                            next_tokens
                            and next_tokens[0].upper() == "STREAM"
                            and len(next_tokens) > 1
                            and next_tokens[1].upper() in {"ID", "NAME"}
                        ):
                            break
                    continue

                # Row label match (longest-prefix wins)
                label_match = _match_row_label(upper)
                if label_match is not None:
                    label, unit = label_match
                    unit = _norm_unit(unit)
                    values_tokens = _split_ws(row)
                    # Values are the last N tokens
                    numeric = [_to_float(t) for t in values_tokens[-len(header_streams):]]
                    for s, v in zip(header_streams, numeric):
                        if v is None:
                            continue
                        if label == "T":
                            converted = _convert_safe(v, unit or "K", "K", "Streams!T", diagnostics)
                            if converted is not None:
                                block_data[s]["T"] = converted
                        elif label == "P":
                            converted = _convert_safe(v, unit or "Pa", "Pa", "Streams!P", diagnostics)
                            if converted is not None:
                                block_data[s]["P"] = converted
                        elif label == "flow_mol":
                            converted = _convert_safe(v, unit or "mol/s", "mol/s", "Streams!flow", diagnostics)
                            if converted is not None:
                                block_data[s]["flow_mol"] = converted
                        elif label == "flow_mass":
                            converted = _convert_safe(v, unit or "kg/s", "kg/s", "Streams!flow", diagnostics)
                            if converted is not None:
                                block_data[s]["flow_mass"] = converted
                    in_mole_frac = False
                elif upper.strip().startswith("MOLE FRAC") or upper.strip().startswith("MASS FRAC"):
                    in_mole_frac = True
                elif in_mole_frac:
                    comp_tokens = _split_ws(row)
                    if len(comp_tokens) >= 1 + len(header_streams):
                        name = comp_tokens[0]
                        numeric = [_to_float(t) for t in comp_tokens[-len(header_streams):]]
                        for s, v in zip(header_streams, numeric):
                            if v is not None:
                                block_comp[s][name] = v
                i += 1
                # Stop condition: a new "STREAM ID" header OR a blank → non-stream section
                if i < len(lines):
                    look_tokens = _split_ws(lines[i])
                    if (
                        look_tokens
                        and look_tokens[0].upper() == "STREAM"
                        and len(look_tokens) > 1
                        and look_tokens[1].upper() in {"ID", "NAME"}
                    ):
                        break
                    # End of section: a line starting with 'BLOCK' or form-feed
                    if look_tokens and look_tokens[0].upper() in {"BLOCK", "ASPEN"}:
                        break
                    if lines[i].startswith("\f"):
                        break
            # Materialize
            for s in header_streams:
                existing = streams.get(s)
                data = block_data[s]
                comp = block_comp[s]
                streams[s] = ImportedStream(
                    id=s,
                    from_block=existing.from_block if existing else None,
                    from_port=existing.from_port if existing else None,
                    to_block=existing.to_block if existing else None,
                    to_port=existing.to_port if existing else None,
                    T=data.get("T", existing.T if existing else None),
                    P=data.get("P", existing.P if existing else None),
                    flow_mol=data.get("flow_mol", existing.flow_mol if existing else None),
                    flow_mass=data.get("flow_mass", existing.flow_mass if existing else None),
                    composition=comp or (existing.composition if existing else {}),
                )
        else:
            i += 1
    return streams


# ── Block section ──────────────────────────────────────────────────────────


def _parse_block_section(
    lines: list[str],
    diagnostics: list[Diagnostic],
) -> dict[str, ImportedBlock]:
    """
    Aspen prints each block's summary in a 'BLOCK: <id>   MODEL: <TYPE>' header
    followed by key=value rows like 'HEAT DUTY    KW    1234.5'.

    We capture the block type and pull DUTY/WORK/ΔP when present.
    """
    blocks: dict[str, ImportedBlock] = {}
    for i, line in enumerate(lines):
        m = re.match(
            r"^\s*BLOCK\s*:?\s*(\S+)\s+MODEL\s*:?\s*(\S+)",
            line,
            flags=re.IGNORECASE,
        )
        if not m:
            continue
        block_id, model = m.group(1), m.group(2).upper()
        # Scan the next 40 lines for duty/work/ΔP
        duty = work = pressure_drop = None
        for nxt in lines[i + 1 : i + 40]:
            upper = nxt.upper()
            if duty is None:
                d = _scan_numeric(upper, ["HEAT DUTY", "DUTY"])
                if d is not None:
                    duty = d
            if work is None:
                w = _scan_numeric(upper, ["NET WORK REQUIRED", "BRAKE HORSEPOWER", "POWER"])
                if w is not None:
                    work = w
            if pressure_drop is None:
                p = _scan_numeric(upper, ["PRESSURE DROP", "PRES-DROP"])
                if p is not None:
                    pressure_drop = p
        from .aspen_inp import _ASPEN_TYPE_MAP

        jasper_type = _ASPEN_TYPE_MAP.get(model, "Unknown")
        if jasper_type == "Unknown":
            diagnostics.append(
                Diagnostic(
                    severity="info",
                    message=f"Aspen block MODEL {model!r} not mapped — block left as Unknown",
                    location=block_id,
                )
            )
        blocks[block_id] = ImportedBlock(
            id=block_id,
            type=jasper_type,
            name=block_id,
            duty=duty,
            work=work,
            pressure_drop=pressure_drop,
        )
    return blocks


# ── Helpers ────────────────────────────────────────────────────────────────


def _split_ws(line: str) -> list[str]:
    return [t for t in re.split(r"\s+", line.strip()) if t]


def _to_float(tok: str) -> Optional[float]:
    try:
        return float(tok)
    except (TypeError, ValueError):
        return None


def _match_row_label(upper: str) -> Optional[tuple[str, Optional[str]]]:
    """Return (canonical_key, unit_string) if the row starts with a known label."""
    stripped = upper.lstrip()
    for label, key in _ROW_LABELS.items():
        if stripped.startswith(label):
            rest = stripped[len(label):].strip()
            # Next token is often a unit: "TEMPERATURE K ..." or "PRESSURE BAR ..."
            tokens = _split_ws(rest)
            unit = None
            if tokens and not _looks_numeric(tokens[0]):
                unit = tokens[0]
            return key, unit
    return None


def _looks_numeric(tok: str) -> bool:
    return bool(re.match(r"^[-+]?\d", tok))


def _scan_numeric(upper: str, keys: list[str]) -> Optional[float]:
    for key in keys:
        if key in upper:
            # Find a trailing number on the same line
            tail = upper.split(key, 1)[1]
            m = re.search(r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", tail)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    return None


def _convert_safe(
    value: float, from_unit: str, to_unit: str,
    where: str, diagnostics: list[Diagnostic],
) -> Optional[float]:
    if not from_unit:
        return value
    try:
        return convert(value, from_unit, to_unit)
    except (UnknownUnitError, DimensionMismatchError) as exc:
        diagnostics.append(
            Diagnostic(severity="warning", message=str(exc), location=where)
        )
        return None
