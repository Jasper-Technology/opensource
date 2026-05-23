"""
Jasper TEA engine — Turton module-costing, ported from GilvanNYU/TEA.

The heavy math lives in ``costing.py`` (pure functions, no state). Coefficient
data lives in ``catalog.py`` (loads ``railway/tea-catalog.json``). Higher-level
NPV / IRR / cash-flow math will land in ``economics.py`` (forthcoming).
"""
from .catalog import Catalog, load_catalog, get_catalog
from .costing import (
    purchased_cost,
    bare_module_cost,
    total_module_cost,
    pressure_factor,
    CostResult,
    CostingError,
    SizeOutOfRangeWarning,
)
from .sizing import (
    Stream,
    BlockInput,
    SizingResult,
    SizingDefaults,
    DEFAULTS,
    size,
    cost_ready,
    lmtd,
    heat_exchanger_area,
)
from .economics import (
    npv,
    irr,
    payback_period,
    annualized_capex,
    tac,
    lcop,
    LCOPInputs,
    SimpleProject,
    EconomicsError,
)

__all__ = [
    "Catalog",
    "load_catalog",
    "get_catalog",
    "purchased_cost",
    "bare_module_cost",
    "total_module_cost",
    "pressure_factor",
    "CostResult",
    "CostingError",
    "SizeOutOfRangeWarning",
    "Stream",
    "BlockInput",
    "SizingResult",
    "SizingDefaults",
    "DEFAULTS",
    "size",
    "cost_ready",
    "lmtd",
    "heat_exchanger_area",
    "npv",
    "irr",
    "payback_period",
    "annualized_capex",
    "tac",
    "lcop",
    "LCOPInputs",
    "SimpleProject",
    "EconomicsError",
]
