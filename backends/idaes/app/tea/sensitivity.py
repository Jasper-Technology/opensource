"""
Sensitivity — deterministic tornado + Monte Carlo.

Tornado: ±pct on revenue/feedstock/CEPCI/discount + top-3 material swaps.
Ranked by absolute NPV swing; each driver is one re-evaluation of the
simple-project cash-flow model.

Monte Carlo: sample N scenarios from triangular distributions over the
same price + utility drivers. Returns the NPV distribution with P10 /
P50 / P90 markers. Vectorized over samples — 1000 samples runs in
milliseconds on typical hardware (well inside the 10 s budget from the
plan).
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .catalog import get_catalog
from .economics import SimpleProject, npv as npv_fn, irr as irr_fn, payback_period


@dataclass(frozen=True)
class SensitivityDriver:
    """One row in the tornado."""

    label: str            # e.g. "Revenue", "Feedstock cost", "Pump P1 material"
    category: str         # "price" | "material" | "cepci" | "discount" | "ops"
    low_npv: float
    high_npv: float
    low_label: str        # e.g. "-20%", "CarbonSteel → SS"
    high_label: str
    base_npv: float

    @property
    def swing(self) -> float:
        return abs(self.high_npv - self.low_npv)


@dataclass
class SensitivityResult:
    base_npv: float
    drivers: list[SensitivityDriver] = field(default_factory=list)

    def sorted_by_swing(self) -> list[SensitivityDriver]:
        return sorted(self.drivers, key=lambda d: d.swing, reverse=True)


# ── Cash-flow model used by every perturbation ──────────────────────────────


def _npv_from_totals(
    capex_total_module: float,
    annual_opex: float,
    annual_revenue: float,
    discount_rate: float,
    project_life_years: int,
) -> float:
    """NPV with the SimpleProject shape: CAPEX year 0, constant net CF thereafter."""
    net_cf = annual_revenue - annual_opex
    p = SimpleProject(
        capex=capex_total_module,
        annual_net_cash_flow=net_cf,
        lifetime_years=project_life_years,
    )
    return p.npv(discount_rate)


# ── Top-level driver builder ────────────────────────────────────────────────


def build_tornado(
    *,
    base_result: dict,              # TEAResult.dict() shape
    base_scenario: dict,            # ScenarioConfig.dict() shape
    recost_with_material: Callable[[str, str], dict],
    perturbation: float = 0.20,
) -> SensitivityResult:
    """
    Build a tornado from a base TEA result and a recost callback.

    ``recost_with_material(block_id, material)`` is a callback that returns
    a fresh TEAResult-shaped dict after swapping the given block's material.
    The caller owns it because it has access to the block + stream context.
    """
    base_npv = float(base_result["economics"]["npv_usd"])
    capex = float(base_result["totals"]["capex_total_module_usd"])
    opex = float(base_result["totals"]["opex_annual_usd"])
    revenue = float(base_result["totals"]["revenue_annual_usd"])
    feedstock = float(base_result["totals"].get("opex_feedstock_usd", 0.0))
    discount = float(base_scenario.get("discount_rate", 0.10))
    life = int(base_scenario.get("project_life_years", 20))

    drivers: list[SensitivityDriver] = []

    # Price drivers — deterministic ±pct on revenue and feedstock
    if revenue > 0:
        low = _npv_from_totals(
            capex, opex, revenue * (1 - perturbation), discount, life
        )
        high = _npv_from_totals(
            capex, opex, revenue * (1 + perturbation), discount, life
        )
        drivers.append(
            SensitivityDriver(
                label="Product revenue",
                category="price",
                low_npv=low,
                high_npv=high,
                low_label=f"-{int(perturbation*100)}%",
                high_label=f"+{int(perturbation*100)}%",
                base_npv=base_npv,
            )
        )

    if feedstock > 0:
        # Higher feedstock cost → lower NPV (OPEX goes up)
        low_opex = opex + feedstock * perturbation        # costlier feedstock
        high_opex = opex - feedstock * perturbation       # cheaper feedstock
        low = _npv_from_totals(capex, low_opex, revenue, discount, life)
        high = _npv_from_totals(capex, high_opex, revenue, discount, life)
        drivers.append(
            SensitivityDriver(
                label="Feedstock cost",
                category="price",
                low_npv=low,
                high_npv=high,
                low_label=f"+{int(perturbation*100)}%",
                high_label=f"-{int(perturbation*100)}%",
                base_npv=base_npv,
            )
        )

    # Operational drivers
    # CEPCI: ±10% (construction-year cost index)
    cepci = float(base_scenario.get("cepci", 800))
    cepci_low_capex = capex * (1 - 0.10)
    cepci_high_capex = capex * (1 + 0.10)
    drivers.append(
        SensitivityDriver(
            label="CEPCI (cost index)",
            category="cepci",
            low_npv=_npv_from_totals(cepci_high_capex, opex, revenue, discount, life),
            high_npv=_npv_from_totals(cepci_low_capex, opex, revenue, discount, life),
            low_label=f"{cepci * 1.10:.0f}",
            high_label=f"{cepci * 0.90:.0f}",
            base_npv=base_npv,
        )
    )

    # Discount rate: ±2 percentage points
    delta = 0.02
    drivers.append(
        SensitivityDriver(
            label="Discount rate",
            category="discount",
            low_npv=_npv_from_totals(capex, opex, revenue, discount + delta, life),
            high_npv=_npv_from_totals(capex, opex, revenue, max(0.001, discount - delta), life),
            low_label=f"{(discount + delta) * 100:.0f}%",
            high_label=f"{(discount - delta) * 100:.0f}%",
            base_npv=base_npv,
        )
    )

    # Material drivers for top-3 CAPEX-contributing blocks
    blocks = sorted(
        [b for b in base_result["blocks"] if b.get("total_module_usd")],
        key=lambda b: b.get("total_module_usd", 0),
        reverse=True,
    )[:3]

    for b in blocks:
        klass = b.get("equipment_class")
        if not klass:
            continue
        try:
            cat_class = get_catalog().klass(klass)
        except KeyError:
            continue
        current_material = b.get("material") or base_scenario.get(
            "default_material", "CarbonSteel"
        )
        available = sorted(cat_class.material_factors.keys())
        if len(available) < 2:
            continue

        # Swap to the next-cheapest and next-most-expensive material for the
        # block's current subtype.
        by_factor = []
        for mat in available:
            try:
                f = cat_class.material_factor(mat, b.get("subtype") or available[0])
            except KeyError:
                continue
            by_factor.append((mat, f))
        if len(by_factor) < 2:
            continue
        by_factor.sort(key=lambda x: x[1])
        cheapest_mat = by_factor[0][0]
        priciest_mat = by_factor[-1][0]

        if cheapest_mat == current_material and priciest_mat == current_material:
            continue

        low_result = recost_with_material(b["id"], priciest_mat)
        high_result = recost_with_material(b["id"], cheapest_mat)

        drivers.append(
            SensitivityDriver(
                label=f"{b['id']} material",
                category="material",
                low_npv=float(low_result["economics"]["npv_usd"]),
                high_npv=float(high_result["economics"]["npv_usd"]),
                low_label=priciest_mat,
                high_label=cheapest_mat,
                base_npv=base_npv,
            )
        )

    return SensitivityResult(base_npv=base_npv, drivers=drivers)


# ── Monte Carlo ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MonteCarloResult:
    samples: int
    npv_samples: tuple[float, ...]   # full distribution (sorted ascending)
    p10: float
    p50: float
    p90: float
    mean: float
    std: float
    probability_positive: float      # share of samples with NPV > 0

    def histogram(self, bins: int = 20) -> list[dict]:
        """Pre-computed bin counts for the frontend histogram."""
        if not self.npv_samples:
            return []
        lo = self.npv_samples[0]
        hi = self.npv_samples[-1]
        if hi - lo < 1e-9:
            return [{"low": lo, "high": hi, "count": len(self.npv_samples)}]
        step = (hi - lo) / bins
        buckets = [0] * bins
        for v in self.npv_samples:
            idx = min(bins - 1, int((v - lo) / step))
            buckets[idx] += 1
        return [
            {
                "low": lo + i * step,
                "high": lo + (i + 1) * step,
                "count": c,
            }
            for i, c in enumerate(buckets)
        ]


def run_monte_carlo(
    *,
    base_result: dict,
    base_scenario: dict,
    samples: int = 1000,
    price_spread: float = 0.20,
    capex_spread: float = 0.15,
    rate_spread_pp: float = 0.02,
    seed: Optional[int] = None,
) -> MonteCarloResult:
    """
    Run N Monte Carlo samples over the simple-project cash flow model.

    Sampling distributions (all triangular — symmetric, min/mode/max):
    - revenue        ±``price_spread`` around base
    - feedstock cost ±``price_spread`` around base
    - CAPEX          ±``capex_spread`` (CEPCI-ish swing)
    - discount rate  ±``rate_spread_pp`` percentage points around base

    Triangular chosen (not normal) because revenue/cost ranges are
    bounded by operational reality; users can pin them directly. Fast
    sampling via stdlib ``random.triangular`` — no numpy dep.

    When ``seed`` is provided, results are reproducible — required for
    CI and for stable "Re-run" with the same inputs producing identical
    output.
    """
    if samples < 10:
        raise ValueError("samples must be >= 10")
    if samples > 100_000:
        raise ValueError("samples capped at 100_000")

    rng = random.Random(seed)

    capex_base = float(base_result["totals"]["capex_total_module_usd"])
    opex_base = float(base_result["totals"]["opex_annual_usd"])
    revenue_base = float(base_result["totals"]["revenue_annual_usd"])
    feedstock_base = float(base_result["totals"].get("opex_feedstock_usd", 0.0))
    rate_base = float(base_scenario.get("discount_rate", 0.10))
    life = int(base_scenario.get("project_life_years", 20))

    # Non-feedstock portion of OPEX — stays fixed across the sample
    opex_other = opex_base - feedstock_base

    npv_samples: list[float] = []
    positive = 0

    for _ in range(samples):
        rev = rng.triangular(
            revenue_base * (1 - price_spread),
            revenue_base * (1 + price_spread),
            revenue_base,
        )
        fs = rng.triangular(
            feedstock_base * (1 - price_spread),
            feedstock_base * (1 + price_spread),
            feedstock_base,
        )
        cap = rng.triangular(
            capex_base * (1 - capex_spread),
            capex_base * (1 + capex_spread),
            capex_base,
        )
        rate = rng.triangular(
            max(0.001, rate_base - rate_spread_pp),
            rate_base + rate_spread_pp,
            rate_base,
        )
        # Simple-project NPV: CAPEX year 0, constant net CF thereafter
        net = rev - (opex_other + fs)
        if rate > 0:
            ann_factor = (1 - (1 + rate) ** (-life)) / rate
        else:
            ann_factor = float(life)
        npv = -cap + net * ann_factor
        npv_samples.append(npv)
        if npv > 0:
            positive += 1

    npv_samples.sort()
    n = len(npv_samples)

    def _pct(p: float) -> float:
        # Percentile via nearest-rank (no numpy dependency)
        idx = min(n - 1, max(0, int(round(p / 100 * (n - 1)))))
        return npv_samples[idx]

    mean = sum(npv_samples) / n
    var = sum((v - mean) ** 2 for v in npv_samples) / n
    std = math.sqrt(var)

    return MonteCarloResult(
        samples=n,
        npv_samples=tuple(npv_samples),
        p10=_pct(10),
        p50=_pct(50),
        p90=_pct(90),
        mean=mean,
        std=std,
        probability_positive=positive / n,
    )


# ── 2D heatmap ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HeatmapAxis:
    variable: str          # 'revenue' | 'opex' | 'capex' | 'discount'
    min_fraction: float    # -0.5 means -50% from base
    max_fraction: float
    steps: int = 11


@dataclass(frozen=True)
class HeatmapResult:
    x_variable: str
    y_variable: str
    x_labels: tuple[float, ...]       # fractions
    y_labels: tuple[float, ...]
    npv_grid: tuple[tuple[float, ...], ...]    # npv_grid[y][x]
    base_npv: float
    min_npv: float
    max_npv: float


def _apply_axis(
    var: str,
    frac: float,
    *,
    capex: float,
    opex: float,
    revenue: float,
    rate: float,
) -> tuple[float, float, float, float]:
    if var == "revenue":
        return capex, opex, revenue * (1 + frac), rate
    if var == "opex":
        return capex, opex * (1 + frac), revenue, rate
    if var == "capex":
        return capex * (1 + frac), opex, revenue, rate
    if var == "discount":
        return capex, opex, revenue, rate + frac
    raise ValueError(f"Unknown sensitivity variable {var!r}")


def run_heatmap(
    *,
    base_result: dict,
    base_scenario: dict,
    x_axis: HeatmapAxis,
    y_axis: HeatmapAxis,
) -> HeatmapResult:
    """Build an (x_steps × y_steps) NPV grid."""
    if x_axis.steps < 3 or y_axis.steps < 3:
        raise ValueError("Each axis needs at least 3 steps")
    if x_axis.steps > 51 or y_axis.steps > 51:
        raise ValueError("Axis steps capped at 51")

    capex = float(base_result["totals"]["capex_total_module_usd"])
    opex = float(base_result["totals"]["opex_annual_usd"])
    revenue = float(base_result["totals"]["revenue_annual_usd"])
    rate = float(base_scenario.get("discount_rate", 0.10))
    life = int(base_scenario.get("project_life_years", 20))

    x_steps = _linspace(x_axis.min_fraction, x_axis.max_fraction, x_axis.steps)
    y_steps = _linspace(y_axis.min_fraction, y_axis.max_fraction, y_axis.steps)

    grid: list[list[float]] = []
    min_npv = float("inf")
    max_npv = float("-inf")
    for y_frac in y_steps:
        row: list[float] = []
        for x_frac in x_steps:
            cap, op, rev, r = _apply_axis(
                x_axis.variable, x_frac,
                capex=capex, opex=opex, revenue=revenue, rate=rate,
            )
            cap, op, rev, r = _apply_axis(
                y_axis.variable, y_frac,
                capex=cap, opex=op, revenue=rev, rate=r,
            )
            npv = _npv_from_totals(cap, op, rev, max(0.001, r), life)
            row.append(npv)
            min_npv = min(min_npv, npv)
            max_npv = max(max_npv, npv)
        grid.append(row)

    base_npv = _npv_from_totals(capex, opex, revenue, rate, life)

    return HeatmapResult(
        x_variable=x_axis.variable,
        y_variable=y_axis.variable,
        x_labels=tuple(x_steps),
        y_labels=tuple(y_steps),
        npv_grid=tuple(tuple(row) for row in grid),
        base_npv=base_npv,
        min_npv=min_npv,
        max_npv=max_npv,
    )


def _linspace(lo: float, hi: float, steps: int) -> list[float]:
    if steps <= 1:
        return [lo]
    step = (hi - lo) / (steps - 1)
    return [lo + i * step for i in range(steps)]
