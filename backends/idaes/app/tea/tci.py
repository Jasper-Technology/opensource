"""
Total Capital Investment — ISBL + OSBL + indirects with Lang factor.

The simple-project cash flow in R1 treated the TEA's total-module cost
as "the CAPEX". Real projects need more: everything costed so far is
ISBL (Inside Battery Limits — the process itself), plus a separate
OSBL bucket for utility plants, tank farms, piperacks, flare systems,
control buildings, site prep. Then an indirects layer (engineering,
construction fee, contingency) scales the whole thing.

References:
- Turton 4th ed. §7.7 "Grass-roots and total-module costs"
- AACE RP 18R-97 for cost-estimate class definitions
- NREL H2A costing methodology for H2 projects

Classification defaults:
  Process block types (Pump, Compressor, Reactor, …) → ISBL
  Utility / storage types (Tank, Boiler, CoolingTower, …) → OSBL
Users can override per-block via the block.category field.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BlockCategory(str, Enum):
    ISBL = "isbl"          # Inside battery limits — core process
    OSBL = "osbl"          # Outside battery limits — utilities, storage
    UNKNOWN = "unknown"    # Default pre-classification


# Heuristic mapping from Jasper block type → default category.
# Users can override per block via the inspector.
_DEFAULT_CATEGORY: dict[str, BlockCategory] = {
    # Process units → ISBL
    "Heater": BlockCategory.ISBL,
    "Cooler": BlockCategory.ISBL,
    "HeatExchanger": BlockCategory.ISBL,
    "Pump": BlockCategory.ISBL,
    "Compressor": BlockCategory.ISBL,
    "Valve": BlockCategory.ISBL,
    "Flash": BlockCategory.ISBL,
    "Mixer": BlockCategory.ISBL,
    "Splitter": BlockCategory.ISBL,
    "Reactor": BlockCategory.ISBL,
    "RCSTR": BlockCategory.ISBL,
    "RPfr": BlockCategory.ISBL,
    "REquil": BlockCategory.ISBL,
    "RGibbs": BlockCategory.ISBL,
    "RStoic": BlockCategory.ISBL,
    "DistillationColumn": BlockCategory.ISBL,
    "Absorber": BlockCategory.ISBL,
    "Stripper": BlockCategory.ISBL,
    "Centrifuge": BlockCategory.ISBL,
    "Filter": BlockCategory.ISBL,
    "Dryer": BlockCategory.ISBL,
    "Evaporator": BlockCategory.ISBL,
    "Fan": BlockCategory.ISBL,
    # Utility / storage → OSBL
    "Tank": BlockCategory.OSBL,
    # Feed / Sink have no cost so category doesn't matter
    "Feed": BlockCategory.UNKNOWN,
    "Sink": BlockCategory.UNKNOWN,
    "Product": BlockCategory.UNKNOWN,
    "TextBox": BlockCategory.UNKNOWN,
}


def classify(block_type: str) -> BlockCategory:
    return _DEFAULT_CATEGORY.get(block_type, BlockCategory.ISBL)


# Lang-factor-style indirect multipliers, applied on top of equipment CAPEX.
# Values from Turton Table 7.9 (fluid-processing plant) defaults.
@dataclass(frozen=True)
class LangFactorBreakdown:
    """Indirect-cost multipliers on top of (ISBL + OSBL) equipment costs."""

    # Direct costs (Turton Table 7.9 fluid-processing averages)
    piping: float = 0.31       # % of equipment (fluid handling)
    instrumentation: float = 0.26  # DCS, analyzers, control valves
    electrical: float = 0.11
    insulation: float = 0.08
    paint: float = 0.02
    civil: float = 0.15        # Foundations, structures
    service_facilities: float = 0.12  # Utilities, fire water, roads
    buildings: float = 0.10    # Control room, MCC, admin
    # Indirect costs
    engineering: float = 0.32  # % of direct costs
    construction_fee: float = 0.15
    contingency: float = 0.18

    @property
    def total_direct_multiplier(self) -> float:
        return (
            1.0
            + self.piping
            + self.instrumentation
            + self.electrical
            + self.insulation
            + self.paint
            + self.civil
            + self.service_facilities
            + self.buildings
        )

    @property
    def indirects_multiplier(self) -> float:
        return 1 + self.engineering + self.construction_fee + self.contingency


_FLUID_PROCESSING = LangFactorBreakdown()

# Solids processing has higher structural/civil and lower piping.
_SOLIDS_PROCESSING = LangFactorBreakdown(
    piping=0.10,
    instrumentation=0.10,
    electrical=0.11,
    insulation=0.03,
    paint=0.02,
    civil=0.30,
    service_facilities=0.08,
    buildings=0.10,
)


@dataclass(frozen=True)
class TciConfig:
    """Top-level TCI settings."""

    plant_type: str = "fluid"           # "fluid" | "solids"
    # Overhead buckets layered on top of ISBL+OSBL equipment cost.
    # OSBL multiplier shortcut: if no per-block OSBL data is provided,
    # total OSBL = osbl_ratio × ISBL (typical 0.2-0.4 for grassroots).
    osbl_ratio: float = 0.30
    startup_fraction: float = 0.10       # one-time expense (fraction of fixed capital)
    working_capital_fraction: float = 0.15  # fraction of annual revenue
    land_cost_usd: float = 0.0           # flat addition
    permitting_cost_usd: float = 0.0

    def lang(self) -> LangFactorBreakdown:
        return _SOLIDS_PROCESSING if self.plant_type == "solids" else _FLUID_PROCESSING


@dataclass(frozen=True)
class TciBreakdown:
    """Result of a TCI computation — every bucket exposed for reporting."""

    isbl_equipment: float       # Σ block.total_module_usd for ISBL blocks
    osbl_equipment: float       # Σ for OSBL blocks (or osbl_ratio × ISBL)
    direct_costs: float         # ISBL + OSBL + piping + instr + elec + ...
    indirect_costs: float       # engineering + construction fee + contingency
    fixed_capital: float        # direct + indirect
    working_capital: float
    startup_costs: float
    land_plus_permits: float
    total_capital_investment: float

    def to_dict(self) -> dict:
        return {
            "isbl_equipment": self.isbl_equipment,
            "osbl_equipment": self.osbl_equipment,
            "direct_costs": self.direct_costs,
            "indirect_costs": self.indirect_costs,
            "fixed_capital": self.fixed_capital,
            "working_capital": self.working_capital,
            "startup_costs": self.startup_costs,
            "land_plus_permits": self.land_plus_permits,
            "total_capital_investment": self.total_capital_investment,
        }


def compute_tci(
    *,
    blocks: list[dict],
    annual_revenue: float,
    config: TciConfig = TciConfig(),
    category_overrides: Optional[dict[str, BlockCategory]] = None,
) -> TciBreakdown:
    """
    Sum equipment costs by category, layer Lang factors, add working
    capital, startup, land, permits.

    ``blocks`` is the TEAResult.blocks shape (dicts with id, type,
    total_module_usd, optionally a category string). Per-block
    category overrides via ``category_overrides[block_id]``.
    """
    overrides = category_overrides or {}
    isbl_sum = 0.0
    osbl_sum = 0.0
    for b in blocks:
        cost = b.get("total_module_usd")
        if cost is None or cost <= 0:
            continue
        block_id = str(b.get("id", ""))
        override = overrides.get(block_id)
        if override is not None:
            category = override
        elif b.get("category"):
            try:
                category = BlockCategory(b["category"])
            except ValueError:
                category = classify(str(b.get("type", "")))
        else:
            category = classify(str(b.get("type", "")))
        if category == BlockCategory.OSBL:
            osbl_sum += cost
        elif category == BlockCategory.ISBL:
            isbl_sum += cost
        # UNKNOWN → skip

    # If no blocks were classified as OSBL, fall back to the ratio shortcut
    if osbl_sum == 0 and config.osbl_ratio > 0 and isbl_sum > 0:
        osbl_sum = isbl_sum * config.osbl_ratio

    lang = config.lang()
    equipment = isbl_sum + osbl_sum
    direct_costs = equipment * lang.total_direct_multiplier
    indirect_costs = direct_costs * (lang.indirects_multiplier - 1)
    fixed_capital = direct_costs + indirect_costs

    working_capital = max(0.0, annual_revenue * config.working_capital_fraction)
    startup = fixed_capital * config.startup_fraction
    land_plus_permits = config.land_cost_usd + config.permitting_cost_usd

    tci = fixed_capital + working_capital + startup + land_plus_permits

    return TciBreakdown(
        isbl_equipment=isbl_sum,
        osbl_equipment=osbl_sum,
        direct_costs=direct_costs,
        indirect_costs=indirect_costs,
        fixed_capital=fixed_capital,
        working_capital=working_capital,
        startup_costs=startup,
        land_plus_permits=land_plus_permits,
        total_capital_investment=tci,
    )
