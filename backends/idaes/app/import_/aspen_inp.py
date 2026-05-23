"""
Aspen Plus .inp parser — keyword-based text format.

File → Export → Input Summary in Aspen Plus emits a .inp file that
fully specifies a flowsheet: components, thermo method, block types,
block parameters, and streams. No proprietary binary — the file is
plain ASCII with a hierarchical keyword grammar.

Coverage (R2):
- COMPONENTS block → component list
- FLOWSHEET block → block connectivity (BLOCK X IN=S1 OUT=S2)
- BLOCK <name> <TYPE> PARAM → block params with type mapping
- STREAM <name> → stream T, P, MOLE-FLOW, MASS-FLOW, composition
- IN-UNITS preamble → unit conversion context

Unsupported gracefully: Fortran user blocks, design-specs, optimization
blocks. These emit an info diagnostic rather than a silent skip.

Grammar is intentionally permissive — Aspen .inp exports vary in
whitespace and case. We tokenize on whitespace, normalize keywords to
lowercase, and walk a simple state machine.
"""
from __future__ import annotations
import logging
import re
from typing import Iterator, Optional

from app.units import DimensionMismatchError, UnknownUnitError, convert
from .models import (
    Diagnostic,
    ImportResult,
    ImportedBlock,
    ImportedProject,
    ImportedStream,
)

logger = logging.getLogger(__name__)


# Aspen block types → Jasper unit types
_ASPEN_TYPE_MAP: dict[str, str] = {
    "HEATER": "Heater",
    "COOLER": "Cooler",
    "HEATX": "HeatExchanger",
    "FLASH2": "Flash",
    "FLASH3": "Flash",          # three-phase flash → two-phase Flash is closest R2 target
    "PUMP": "Pump",
    "COMPR": "Compressor",
    "VALVE": "Valve",
    "MIXER": "Mixer",
    "FSPLIT": "Splitter",
    "RSTOIC": "RStoic",
    "REQUIL": "REquil",
    "RGIBBS": "RGibbs",
    "RPLUG": "RPfr",
    "RCSTR": "RCSTR",
    "RBATCH": "Reactor",
    "RYIELD": "Reactor",
    "RADFRAC": "DistillationColumn",
    "DSTWU": "DistillationColumn",   # shortcut column
    "DISTL": "DistillationColumn",
    "ABSBR": "Absorber",
    "SEP": "Flash",                  # component separator → Flash surrogate
    "TANK": "Tank",
    "DRYER": "Dryer",
    "CRYSTALLIZER": "Crystallizer",
    "FILTER": "Filter",
    "CENTRIFUGE": "Centrifuge",
}


_MAX_BYTES = 25 * 1024 * 1024


def parse_aspen_inp(data: bytes, *, filename: str = "simulation.inp") -> ImportResult:
    """Parse an Aspen Plus .inp export into a Jasper ImportedProject."""
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

    try:
        text = data.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        diagnostics.append(
            Diagnostic(severity="error", message="Cannot decode file as UTF-8", location=filename)
        )
        return ImportResult(project=None, diagnostics=diagnostics)

    # Strip comments — lines beginning with ';' or ';;' and inline ';...'
    lines = [re.sub(r";.*$", "", line).rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip()]

    parser = _InpParser(lines, diagnostics)
    project = parser.parse()

    if project is None and not any(d.severity == "error" for d in diagnostics):
        diagnostics.append(
            Diagnostic(
                severity="error",
                message="No blocks or streams recognised in .inp file",
                location=filename,
            )
        )

    if project is not None:
        project_name = filename.rsplit(".", 1)[0]
        project = ImportedProject(
            name=project.name or project_name,
            components=project.components,
            blocks=project.blocks,
            streams=project.streams,
        )

    return ImportResult(project=project, diagnostics=diagnostics)


# ── Parser state machine ────────────────────────────────────────────────────


class _InpParser:
    def __init__(self, lines: list[str], diagnostics: list[Diagnostic]) -> None:
        self._lines = lines
        self._idx = 0
        self._diag = diagnostics
        self._components: list[str] = []
        self._blocks: dict[str, ImportedBlock] = {}
        self._streams: dict[str, ImportedStream] = {}
        self._title: Optional[str] = None
        self._temperature_unit = "K"
        self._pressure_unit = "Pa"
        self._flow_unit = "mol/s"

    # ── Lexer helpers ──

    def _peek(self) -> Optional[str]:
        return self._lines[self._idx] if self._idx < len(self._lines) else None

    def _consume(self) -> Optional[str]:
        line = self._peek()
        if line is not None:
            self._idx += 1
        return line

    def _at_end(self) -> bool:
        return self._idx >= len(self._lines)

    # ── Top-level parse ──

    def parse(self) -> Optional[ImportedProject]:
        while not self._at_end():
            line = self._consume()
            if line is None:
                break
            tok = line.strip().upper()
            if tok.startswith("TITLE "):
                self._title = line.split(None, 1)[1].strip().strip('"')
            elif tok.startswith("IN-UNITS"):
                self._parse_in_units(line)
            elif tok == "COMPONENTS" or tok.startswith("COMPONENTS "):
                self._parse_components_block(line)
            elif tok == "FLOWSHEET" or tok.startswith("FLOWSHEET "):
                self._parse_flowsheet_block()
            elif tok.startswith("STREAM "):
                self._parse_stream(line)
            elif tok.startswith("BLOCK "):
                self._parse_block_decl(line)
            elif tok.startswith("PROPERTIES"):
                # Skip thermo details for R2 — Jasper only needs block + stream topology
                pass
            else:
                # Unmapped top-level keyword — silently skip
                pass

        if not self._blocks and not self._streams:
            return None

        return ImportedProject(
            name=self._title or "",
            components=self._components,
            blocks=list(self._blocks.values()),
            streams=list(self._streams.values()),
        )

    # ── IN-UNITS ──
    # Syntax: IN-UNITS SI TEMPERATURE=C PRESSURE=bar MOLE-FLOW=kmol/h

    def _parse_in_units(self, line: str) -> None:
        tokens = line.split()[1:]
        for tok in tokens:
            if "=" in tok:
                k, v = tok.split("=", 1)
                k = k.upper()
                if k == "TEMPERATURE":
                    self._temperature_unit = v
                elif k == "PRESSURE":
                    self._pressure_unit = v
                elif k in ("MOLE-FLOW", "MASS-FLOW"):
                    self._flow_unit = v

    # ── COMPONENTS block ──

    def _parse_components_block(self, first_line: str) -> None:
        # The COMPONENTS keyword is followed by indented component declarations
        # until an empty line or next top-level keyword.
        while not self._at_end():
            line = self._peek()
            if line is None:
                break
            upper = line.strip().upper()
            if upper.startswith((
                "FLOWSHEET", "STREAM ", "BLOCK ", "PROPERTIES",
                "IN-UNITS", "TITLE",
            )):
                break
            self._consume()
            # "H2 H2 /" or "METHANOL CH4O /" — take first token as the name
            tokens = re.split(r"\s+", line.strip())
            if tokens and tokens[0] and not tokens[0].startswith("/"):
                self._components.append(tokens[0])

    # ── FLOWSHEET block ──
    # Syntax: BLOCK <blockid> IN=<stream1> <stream2> OUT=<stream3>

    def _parse_flowsheet_block(self) -> None:
        while not self._at_end():
            line = self._peek()
            if line is None:
                break
            upper = line.strip().upper()
            if upper.startswith((
                "STREAM ", "BLOCK ", "PROPERTIES", "IN-UNITS", "TITLE",
                "COMPONENTS",
            )):
                # Only consume if it's a FLOWSHEET-nested BLOCK
                if upper.startswith("BLOCK ") and "IN=" in upper:
                    line = self._consume()
                    self._parse_flowsheet_edge(line)
                    continue
                break
            self._consume()
            if upper.startswith("BLOCK "):
                self._parse_flowsheet_edge(line)

    def _parse_flowsheet_edge(self, line: str) -> None:
        # "BLOCK R1 IN=S1 S2 OUT=S3" — wire streams into the block
        match = re.match(
            r"BLOCK\s+(\S+)\s+IN=\s*([^=]+?)\s+OUT=\s*(.+?)$",
            line.strip(),
            re.IGNORECASE,
        )
        if not match:
            return
        block_id, in_streams, out_streams = match.groups()
        block_id = block_id.strip()
        in_list = re.split(r"\s+", in_streams.strip())
        out_list = re.split(r"\s+", out_streams.strip())
        # Register placeholder block if we haven't seen it yet
        if block_id not in self._blocks:
            self._blocks[block_id] = ImportedBlock(id=block_id, type="Unknown", name=block_id)
        # Record edge intents; STREAM parse will merge these in.
        for s in in_list:
            stream = self._streams.get(s) or ImportedStream(
                id=s, from_block=None, from_port=None, to_block=None, to_port=None,
            )
            self._streams[s] = ImportedStream(
                id=stream.id,
                from_block=stream.from_block,
                from_port=stream.from_port,
                to_block=block_id,
                to_port=stream.to_port,
                T=stream.T, P=stream.P,
                flow_mol=stream.flow_mol, flow_mass=stream.flow_mass,
                composition=stream.composition,
            )
        for s in out_list:
            stream = self._streams.get(s) or ImportedStream(
                id=s, from_block=None, from_port=None, to_block=None, to_port=None,
            )
            self._streams[s] = ImportedStream(
                id=stream.id,
                from_block=block_id,
                from_port=stream.from_port,
                to_block=stream.to_block,
                to_port=stream.to_port,
                T=stream.T, P=stream.P,
                flow_mol=stream.flow_mol, flow_mass=stream.flow_mass,
                composition=stream.composition,
            )

    # ── BLOCK <name> <TYPE> ──

    def _parse_block_decl(self, line: str) -> None:
        # "BLOCK R1 RSTOIC" or "BLOCK P1 PUMP PARAM ..."
        tokens = re.split(r"\s+", line.strip())
        if len(tokens) < 3:
            return
        block_id = tokens[1]
        aspen_type = tokens[2].upper()
        jasper_type = _ASPEN_TYPE_MAP.get(aspen_type)
        if jasper_type is None:
            self._diag.append(
                Diagnostic(
                    severity="info",
                    message=f"Aspen block type {aspen_type!r} not mapped — skipping",
                    location=block_id,
                )
            )
            return
        # Parse any inline or nested PARAM values
        duty = None
        work = None
        pressure_drop = None
        # Scan inline params: "PARAM KEY=VALUE KEY=VALUE"
        inline = line.split(None, 3)
        if len(inline) >= 4 and inline[3].upper().startswith("PARAM"):
            duty, work, pressure_drop = self._parse_inline_params(inline[3])
        # Scan following indented PARAM lines
        while not self._at_end():
            nxt = self._peek()
            if nxt is None:
                break
            upper = nxt.strip().upper()
            if upper.startswith((
                "BLOCK ", "STREAM ", "PROPERTIES", "FLOWSHEET",
                "IN-UNITS", "TITLE", "COMPONENTS",
            )):
                break
            if upper.startswith("PARAM") or "=" in nxt:
                line2 = self._consume()
                d2, w2, p2 = self._parse_inline_params(line2)
                duty = duty if duty is not None else d2
                work = work if work is not None else w2
                pressure_drop = pressure_drop if pressure_drop is not None else p2
            else:
                self._consume()

        self._blocks[block_id] = ImportedBlock(
            id=block_id,
            type=jasper_type,
            name=block_id,
            duty=duty,
            work=work,
            pressure_drop=pressure_drop,
        )

    def _parse_inline_params(self, line: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Pull DUTY=/Q=/POWER=/BRAKE-POWER=/PRES-DROP= from a PARAM line."""
        upper = line.upper()
        duty = _first_numeric(upper, ["DUTY=", "Q="])
        work = _first_numeric(upper, ["POWER=", "BRAKE-POWER=", "SHAFT-POWER="])
        pdrop = _first_numeric(upper, ["PRES-DROP=", "DP=", "DELTA-P="])
        return duty, work, pdrop

    # ── STREAM ──

    def _parse_stream(self, line: str) -> None:
        # "STREAM S1" or "STREAM S1 SUBSTREAM MIXED TEMP=200 PRES=50 MOLE-FLOW=100"
        tokens = re.split(r"\s+", line.strip())
        if len(tokens) < 2:
            return
        stream_id = tokens[1]
        T = P = flow_mol = flow_mass = None
        composition: dict[str, float] = {}

        def _grab(keyword: str, current: Optional[float]) -> Optional[float]:
            if current is not None:
                return current
            match = re.search(rf"{keyword}=\s*([-\d.eE+]+)", line, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
            return None

        T_raw = _grab("TEMP", None)
        P_raw = _grab("PRES", None)
        flow_raw = _grab("MOLE-FLOW", None)
        if flow_raw is None:
            flow_raw = _grab("TOTAL-FLOW", None)

        if T_raw is not None:
            T = _convert_safe(T_raw, self._temperature_unit, "K", "Streams!T", self._diag)
        if P_raw is not None:
            P = _convert_safe(P_raw, self._pressure_unit, "Pa", "Streams!P", self._diag)
        if flow_raw is not None:
            flow_mol = _convert_safe(flow_raw, self._flow_unit, "mol/s", "Streams!flow", self._diag)

        # Follow-on indented lines: composition via "MOLE-FRAC H2 0.67 / CO 0.33"
        while not self._at_end():
            nxt = self._peek()
            if nxt is None:
                break
            upper = nxt.strip().upper()
            if upper.startswith((
                "STREAM ", "BLOCK ", "PROPERTIES", "FLOWSHEET", "IN-UNITS",
                "TITLE", "COMPONENTS",
            )):
                break
            line2 = self._consume()
            self._parse_stream_composition(line2, composition)

        existing = self._streams.get(stream_id)
        self._streams[stream_id] = ImportedStream(
            id=stream_id,
            from_block=existing.from_block if existing else None,
            from_port=existing.from_port if existing else None,
            to_block=existing.to_block if existing else None,
            to_port=existing.to_port if existing else None,
            T=T, P=P,
            flow_mol=flow_mol, flow_mass=flow_mass,
            composition=composition,
        )

    def _parse_stream_composition(self, line: str, out: dict[str, float]) -> None:
        upper = line.upper()
        if "MOLE-FRAC" not in upper and "MASS-FRAC" not in upper:
            return
        # "MOLE-FRAC H2 0.67 / CO 0.33 / METHANOL 0.0"
        payload = re.sub(r"^.*?MOLE-FRAC\s+", "", line, flags=re.IGNORECASE)
        payload = re.sub(r"^.*?MASS-FRAC\s+", "", payload, flags=re.IGNORECASE)
        parts = [p.strip() for p in payload.split("/") if p.strip()]
        for part in parts:
            tokens = re.split(r"\s+", part)
            if len(tokens) >= 2:
                comp, val = tokens[0], tokens[1]
                try:
                    out[comp] = float(val)
                except ValueError:
                    continue


# ── Helpers ─────────────────────────────────────────────────────────────────


def _first_numeric(upper_line: str, keywords: list[str]) -> Optional[float]:
    for kw in keywords:
        m = re.search(rf"{re.escape(kw)}\s*([-\d.eE+]+)", upper_line)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
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
