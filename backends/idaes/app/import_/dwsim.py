"""
DWSIM .dwxml parser.

DWSIM files are plain XML — no proprietary binary — so the parser is
grammar-free. We extract the minimum a TEA run needs:
- Simulation object list (blocks) with type + operating conditions
- Material streams with T, P, molar flow, composition
- Energy streams (duty / work) attached to their consuming block

The mapping from DWSIM object types to Jasper block types lives in
``_DWSIM_TYPE_MAP`` — any type outside the map produces an ``info``
diagnostic rather than a silent skip so the UI can surface it.

Security: uses defusedxml.ElementTree to block external-entity /
billion-laughs attacks.
"""
from __future__ import annotations
import logging
from io import BytesIO
from typing import Optional

from defusedxml import ElementTree as DET

from .models import (
    Diagnostic,
    ImportResult,
    ImportedBlock,
    ImportedProject,
    ImportedStream,
)

logger = logging.getLogger(__name__)

# DWSIM object types → Jasper unit types
_DWSIM_TYPE_MAP: dict[str, str] = {
    "Pump": "Pump",
    "Compressor": "Compressor",
    "Heater": "Heater",
    "Cooler": "Cooler",
    "HeatExchanger": "HeatExchanger",
    "Valve": "Valve",
    "NodeIn": "Feed",
    "NodeOut": "Sink",
    "Mixer": "Mixer",
    "Splitter": "Splitter",
    "Flash": "Flash",
    "Tank": "Tank",
    "DistillationColumn": "DistillationColumn",
    "AbsorptionColumn": "Absorber",
    "CSTR": "RCSTR",
    "PFR": "RPfr",
    "EquilibriumReactor": "REquil",
    "GibbsReactor": "RGibbs",
    "ConversionReactor": "RStoic",
}

_MAX_BYTES = 20 * 1024 * 1024  # DWSIM XML can be larger than Excel


def parse_dwxml(data: bytes, *, filename: str = "simulation.dwxml") -> ImportResult:
    """Parse a DWSIM ``.dwxml`` export into an ImportedProject."""
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
        root = DET.parse(BytesIO(data)).getroot()
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(
            Diagnostic(severity="error", message=f"Cannot parse XML: {exc}", location=filename)
        )
        return ImportResult(project=None, diagnostics=diagnostics)

    blocks = _parse_blocks(root, diagnostics)
    streams = _parse_streams(root, diagnostics)
    _attach_energy(root, blocks, diagnostics)

    if not blocks and not streams:
        diagnostics.append(
            Diagnostic(
                severity="error",
                message="Empty or unrecognised DWSIM XML (no SimulationObjects / MaterialStreams).",
                location=filename,
            )
        )
        return ImportResult(project=None, diagnostics=diagnostics)

    components = _parse_components(root)
    project_name = filename.rsplit(".", 1)[0]
    return ImportResult(
        project=ImportedProject(
            name=project_name,
            components=components,
            blocks=blocks,
            streams=streams,
        ),
        diagnostics=diagnostics,
    )


# ── Individual parsers ──────────────────────────────────────────────────────


def _parse_components(root) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    # DWSIM stores compounds under CompoundCollection/Compound or similar
    for tag in ("Compound", "ChemicalCompound"):
        for el in root.iter(tag):
            name = el.get("Name") or (el.findtext("Name") or "").strip()
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    return names


def _parse_blocks(root, diagnostics: list[Diagnostic]) -> list[ImportedBlock]:
    blocks: list[ImportedBlock] = []
    # DWSIM SimulationObjects wrapper holds every unit op. Object type lives in
    # an element (e.g. "ObjectType") and the display name in "Tag"/"Name".
    for obj in root.iter("SimulationObject"):
        obj_type = (obj.findtext("ObjectType") or "").strip()
        if obj_type in ("MaterialStream", "EnergyStream"):
            continue
        mapped = _DWSIM_TYPE_MAP.get(obj_type)
        if mapped is None:
            diagnostics.append(
                Diagnostic(
                    severity="info",
                    message=f"DWSIM object type {obj_type!r} not mapped — skipping",
                    location=obj.findtext("Name") or obj.get("Name") or "(unknown)",
                )
            )
            continue
        obj_id = obj.findtext("Name") or obj.get("Name") or obj_type
        name = obj.findtext("Tag") or obj_id
        pressure_drop = _float(obj.findtext("DeltaP"))
        blocks.append(
            ImportedBlock(
                id=str(obj_id),
                type=mapped,
                name=str(name),
                pressure_drop=pressure_drop,
            )
        )
    return blocks


def _parse_streams(root, diagnostics: list[Diagnostic]) -> list[ImportedStream]:
    streams: list[ImportedStream] = []
    for obj in root.iter("SimulationObject"):
        if (obj.findtext("ObjectType") or "").strip() != "MaterialStream":
            continue
        stream_id = obj.findtext("Name") or obj.get("Name") or ""
        # DWSIM typically stores upstream/downstream links under Inputs/Outputs
        from_block = obj.findtext("UpstreamObject") or None
        to_block = obj.findtext("DownstreamObject") or None
        # DWSIM persists .dwxml with SI internal units regardless of UI
        # display choice: Temperature in K, Pressure in Pa, MolarFlow in
        # mol/s, MassFlow in kg/s. No conversion needed here — but if
        # this ever becomes false, switch to app.units.convert at the
        # boundary rather than after the fact.
        T = _float(obj.findtext("Phase/Temperature"))
        P = _float(obj.findtext("Phase/Pressure"))
        flow_mol = _float(obj.findtext("Phase/MolarFlow"))
        flow_mass = _float(obj.findtext("Phase/MassFlow"))

        # Composition: <Composition><Compound Name="H2">0.67</Compound></Composition>
        comp: dict[str, float] = {}
        comp_el = obj.find("Composition")
        if comp_el is not None:
            for child in comp_el.findall("Compound"):
                name = child.get("Name") or child.findtext("Name")
                val = _float(child.text) or _float(child.findtext("MoleFraction"))
                if name and val is not None:
                    comp[name] = val

        streams.append(
            ImportedStream(
                id=stream_id,
                from_block=from_block,
                from_port=None,  # DWSIM doesn't name ports explicitly — filled in by block graph
                to_block=to_block,
                to_port=None,
                T=T,
                P=P,
                flow_mol=flow_mol,
                flow_mass=flow_mass,
                composition=comp,
            )
        )
    return streams


def _attach_energy(root, blocks: list[ImportedBlock], diagnostics: list[Diagnostic]) -> None:
    """Attach EnergyStream duty/work values to the blocks that consume them."""
    by_id = {b.id: b for b in blocks}
    for obj in root.iter("SimulationObject"):
        if (obj.findtext("ObjectType") or "").strip() != "EnergyStream":
            continue
        target = obj.findtext("DownstreamObject") or obj.findtext("ConnectedTo")
        energy = _float(obj.findtext("EnergyFlow"))
        if target and energy is not None:
            block = by_id.get(target)
            if block is None:
                continue
            # Heuristic: pump/compressor take shaft work; everything else is duty
            if block.type in ("Pump", "Compressor"):
                block.work = energy
            else:
                block.duty = energy


# ── Helpers ─────────────────────────────────────────────────────────────────


def _float(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None
