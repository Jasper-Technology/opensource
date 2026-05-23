"""
Heuristic flowsheet comprehension.

Infers:
- Which block is the product sink (biggest mass-out with highest purity)
- Which block is the feed source
- Role label per block (e.g. "Methanol synthesis", "Syngas compression")
- Flags for unusual patterns (no recycle, feed with no composition, etc.)

No LLM. Pure graph traversal + pattern matching. The R2 comprehension
layer will wrap this and fall back to it when Claude is unavailable.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from app.components_registry import get_default_registry
from app.import_.models import ImportedBlock, ImportedProject, ImportedStream


@dataclass(frozen=True)
class BlockAnnotation:
    block_id: str
    role: str
    notes: Optional[str] = None


@dataclass
class Annotations:
    process_name: str = "Imported process"
    product_block_id: Optional[str] = None
    product_stream_id: Optional[str] = None
    feedstock_block_id: Optional[str] = None
    feedstock_stream_id: Optional[str] = None
    block_annotations: dict[str, BlockAnnotation] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


# ── Role templates ──────────────────────────────────────────────────────────

_ROLES: dict[str, str] = {
    "Feed": "Feed source",
    "Sink": "Product sink",
    "Product": "Product sink",
    "Pump": "Liquid pressurization",
    "Compressor": "Gas compression",
    "Valve": "Throttling / pressure let-down",
    "Heater": "Stream heating",
    "Cooler": "Stream cooling",
    "HeatExchanger": "Process-to-process heat integration",
    "Flash": "Vapor/liquid separation",
    "Mixer": "Stream mixing",
    "Splitter": "Stream splitting",
    "Tank": "Intermediate storage",
    "DistillationColumn": "Distillation",
    "Absorber": "Gas absorption",
    "Stripper": "Gas stripping",
    "RCSTR": "CSTR reaction",
    "RPfr": "Plug-flow reaction",
    "REquil": "Equilibrium reaction",
    "RGibbs": "Gibbs-minimization reaction",
    "RStoic": "Stoichiometric reaction",
    "Reactor": "Reaction",
}


# ── Annotation passes ───────────────────────────────────────────────────────


def annotate(project: ImportedProject) -> Annotations:
    """Run every heuristic pass and return consolidated annotations."""
    ann = Annotations(process_name=project.name or "Imported process")

    # Role label per block
    for b in project.blocks:
        ann.block_annotations[b.id] = BlockAnnotation(
            block_id=b.id,
            role=_ROLES.get(b.type, f"{b.type} unit"),
        )

    # Product + feedstock
    product = infer_product(project)
    if product:
        ann.product_block_id, ann.product_stream_id = product
    feed = infer_feedstock(project)
    if feed:
        ann.feedstock_block_id, ann.feedstock_stream_id = feed

    # Refine role notes for reactor types using stream composition
    _refine_reactor_roles(project, ann)

    # Flags
    ann.flags.extend(_detect_flags(project, ann))

    return ann


def infer_product(project: ImportedProject) -> Optional[tuple[str, str]]:
    """Return (block_id, stream_id) of the most-likely product sink."""
    reg = get_default_registry()
    candidates: list[tuple[str, str, float]] = []

    # Look for streams terminating at a Sink/Product block with highest-purity composition.
    sink_blocks = {b.id for b in project.blocks if b.type in ("Sink", "Product")}
    for s in project.streams:
        if s.to_block not in sink_blocks:
            continue
        if not s.composition:
            continue
        top_component, top_frac = max(s.composition.items(), key=lambda kv: kv[1])
        # Boost when the component is a known valuable chemical (not a common feed gas)
        if top_component in ("H2", "N2", "O2", "H2O", "CH4", "CO", "CO2", "Air"):
            continue
        if reg.lookup(top_component):
            candidates.append((s.to_block, s.id, top_frac))

    if not candidates:
        return None
    # Pick the highest-purity product stream
    candidates.sort(key=lambda c: c[2], reverse=True)
    best = candidates[0]
    return best[0], best[1]


def infer_feedstock(project: ImportedProject) -> Optional[tuple[str, str]]:
    """Return (block_id, stream_id) of the feed source — the Feed block
    whose outgoing stream has the highest mass flow."""
    feed_blocks = {b.id for b in project.blocks if b.type == "Feed"}
    if not feed_blocks:
        return None
    # Find the outgoing stream with the largest flow
    best: Optional[tuple[str, str, float]] = None
    for s in project.streams:
        if s.from_block not in feed_blocks:
            continue
        flow = s.flow_mol or s.flow_mass or 0.0
        if best is None or flow > best[2]:
            best = (s.from_block, s.id, flow)
    if best is None:
        return None
    return best[0], best[1]


def _refine_reactor_roles(project: ImportedProject, ann: Annotations) -> None:
    """Tag reactor blocks with their apparent product (from outlet composition)."""
    reg = get_default_registry()
    by_id = {b.id: b for b in project.blocks}
    for s in project.streams:
        if s.from_block is None or not s.composition:
            continue
        block = by_id.get(s.from_block)
        if block is None:
            continue
        if block.type not in ("RCSTR", "RPfr", "REquil", "RGibbs", "RStoic", "Reactor"):
            continue
        # Find the highest-fraction component that isn't a common feed gas
        for name, frac in sorted(s.composition.items(), key=lambda kv: kv[1], reverse=True):
            if name in ("H2", "N2", "O2", "H2O", "CH4", "CO", "CO2", "Air"):
                continue
            c = reg.lookup(name)
            if c is None:
                continue
            existing = ann.block_annotations[block.id]
            ann.block_annotations[block.id] = BlockAnnotation(
                block_id=block.id,
                role=f"{c.name} synthesis",
                notes=f"outlet composition dominated by {c.name} ({frac:.2f})",
            )
            break


def _detect_flags(project: ImportedProject, ann: Annotations) -> list[str]:
    flags: list[str] = []

    # No recycle: look for any stream whose from_block is downstream of its to_block.
    # Simple heuristic: if every stream is topologically forward, assume no recycle.
    # A single cycle is flagged unusual for processes with reactions.
    has_reactor = any(b.type in ("RCSTR", "RPfr", "REquil", "RGibbs", "RStoic", "Reactor") for b in project.blocks)
    if has_reactor:
        seen_pairs = {(s.from_block, s.to_block) for s in project.streams}
        reverse_exists = any((b, a) in seen_pairs for (a, b) in seen_pairs)
        if not reverse_exists:
            flags.append("No recycle stream detected — unusual for reactor-containing processes; verify")

    # Feed with no composition
    feed_ids = {b.id for b in project.blocks if b.type == "Feed"}
    for s in project.streams:
        if s.from_block in feed_ids and not s.composition:
            flags.append(f"Feed stream {s.id!r} has no composition — TEA falls back to MW 50 g/mol")

    # Unknown components in streams
    reg = get_default_registry()
    unknowns: set[str] = set()
    for s in project.streams:
        for name in s.composition:
            if reg.lookup(name) is None:
                unknowns.add(name)
    if unknowns:
        flags.append(f"Unknown components: {', '.join(sorted(unknowns))}")

    return flags
