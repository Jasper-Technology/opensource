"""
Depreciation + corporate tax + production/investment tax credits.

Closes the gap between the R1 SimpleProject model (CAPEX year 0, flat
net CF) and what a real TEA cash-flow sheet looks like:

    net_cf[t] = (revenue - opex) · (1 - τ) + depreciation[t] · τ
              + production_tax_credit[t] - 0                 (year 0: -CAPEX·(1-ITC))

References:
- Turton 4th ed. Ch.10 for depreciation schedules
- IRS Pub 946 for MACRS percentages (5-yr and 7-yr)
- IRA §45V (hydrogen PTC), §45Q (CCS PTC), §48 (ITC) for credit structures

Kept intentionally small — no AMT, no carryforwards, no state taxes.
Users who need those levels can layer them on top of the per-year cash
flow this module emits.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class MacrsClass(str, Enum):
    """MACRS depreciation classes Jasper supports. Chemical plants are
    usually 5 or 7 year; pipelines and buildings use longer schedules."""

    FIVE_YEAR = "5-year"
    SEVEN_YEAR = "7-year"
    TEN_YEAR = "10-year"
    FIFTEEN_YEAR = "15-year"
    STRAIGHT_LINE_20 = "straight-line-20"


# IRS Pub 946 half-year convention percentages (first year is half).
# Each list sums to 1.0 across the full recovery period.
_MACRS_RATES: dict[MacrsClass, list[float]] = {
    MacrsClass.FIVE_YEAR:   [0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576],
    MacrsClass.SEVEN_YEAR:  [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
    MacrsClass.TEN_YEAR:    [
        0.10, 0.18, 0.144, 0.1152, 0.0922, 0.0737, 0.0655, 0.0655, 0.0656, 0.0655, 0.0328,
    ],
    MacrsClass.FIFTEEN_YEAR: [
        0.05, 0.095, 0.0855, 0.077, 0.0693, 0.0623, 0.059, 0.059,
        0.0591, 0.059, 0.0591, 0.059, 0.0591, 0.059, 0.0591, 0.0295,
    ],
    # Straight-line for long-lived (e.g. buildings)
    MacrsClass.STRAIGHT_LINE_20: [1 / 20] * 20,
}


@dataclass(frozen=True)
class ProductionTaxCredit:
    """45V (hydrogen), 45Q (CCS), or a generic per-unit-output credit.

    Credit = ``usd_per_unit`` × annual production units, for ``years``
    starting at ``start_year`` (1 = first operating year).
    """

    usd_per_unit: float
    units_per_year: float           # e.g. 1_000_000 kg H2/yr
    start_year: int = 1
    years: int = 10                  # 45V/45Q default
    name: str = "PTC"


@dataclass(frozen=True)
class TaxConfig:
    """Top-level tax + credit settings applied to a SimpleProject-shaped
    cash flow. Everything optional; sensible defaults for the US."""

    corporate_tax_rate: float = 0.21           # federal flat rate
    state_tax_rate: float = 0.05               # weighted-average state estimate
    macrs_class: MacrsClass = MacrsClass.SEVEN_YEAR
    itc_fraction: float = 0.0                  # Investment Tax Credit (§48)
    production_credits: tuple[ProductionTaxCredit, ...] = ()
    carbon_price_usd_per_ton: float = 0.0
    carbon_emissions_ton_per_year: float = 0.0
    # Escalation — applied multiplicatively year-over-year
    revenue_escalation: float = 0.02
    opex_escalation: float = 0.025

    @property
    def combined_tax_rate(self) -> float:
        # Federal + state, with state deductible against federal
        return self.corporate_tax_rate + self.state_tax_rate * (1 - self.corporate_tax_rate)


@dataclass(frozen=True)
class YearlyCashFlow:
    year: int
    revenue: float
    opex: float
    depreciation: float
    ebit: float                 # revenue - opex - depreciation
    tax: float
    ptc: float                  # production tax credits (non-taxable for 45V)
    carbon_cost: float          # positive cost (reduces NPV)
    net_cf: float               # after-tax cash flow

    def summary(self) -> dict:
        return {
            "year": self.year,
            "revenue": self.revenue,
            "opex": self.opex,
            "depreciation": self.depreciation,
            "ebit": self.ebit,
            "tax": self.tax,
            "ptc": self.ptc,
            "carbon_cost": self.carbon_cost,
            "net_cf": self.net_cf,
        }


def macrs_schedule(capex: float, klass: MacrsClass, project_life_years: int) -> list[float]:
    """Return per-year depreciation dollars for ``project_life_years`` years.

    Unused depreciation (if schedule is shorter than project life) becomes
    zero. Depreciation beyond project life is dropped (should never trigger
    for sane inputs since MACRS schedules are ≤ 20 yr).
    """
    rates = _MACRS_RATES[klass]
    schedule: list[float] = []
    for t in range(project_life_years):
        if t < len(rates):
            schedule.append(capex * rates[t])
        else:
            schedule.append(0.0)
    return schedule


def ptc_schedule(
    credits: tuple[ProductionTaxCredit, ...],
    project_life_years: int,
) -> list[float]:
    """Aggregate all declared production credits into a per-year total."""
    out = [0.0] * project_life_years
    for c in credits:
        for t in range(project_life_years):
            year = t + 1
            if c.start_year <= year < c.start_year + c.years:
                out[t] += c.usd_per_unit * c.units_per_year
    return out


def cash_flow_with_taxes(
    *,
    capex: float,
    annual_revenue: float,
    annual_opex: float,
    project_life_years: int,
    tax_config: TaxConfig,
) -> list[YearlyCashFlow]:
    """
    Build year-0..N cash-flow with depreciation, taxes, credits, and
    escalation. Year 0 is -CAPEX × (1 - ITC); years 1..N are the
    operating years.
    """
    flows: list[YearlyCashFlow] = []
    effective_capex = capex * (1 - tax_config.itc_fraction)
    flows.append(
        YearlyCashFlow(
            year=0,
            revenue=0.0,
            opex=0.0,
            depreciation=0.0,
            ebit=0.0,
            tax=0.0,
            ptc=0.0,
            carbon_cost=0.0,
            net_cf=-effective_capex,
        )
    )

    dep = macrs_schedule(capex, tax_config.macrs_class, project_life_years)
    ptc = ptc_schedule(tax_config.production_credits, project_life_years)
    tax_rate = tax_config.combined_tax_rate
    carbon_per_year = (
        tax_config.carbon_price_usd_per_ton * tax_config.carbon_emissions_ton_per_year
    )

    for t in range(1, project_life_years + 1):
        idx = t - 1
        rev = annual_revenue * ((1 + tax_config.revenue_escalation) ** (t - 1))
        opex = annual_opex * ((1 + tax_config.opex_escalation) ** (t - 1))
        d = dep[idx]
        ebit = rev - opex - d - carbon_per_year
        # Tax is paid on positive EBIT; negative EBIT carries no cash benefit
        # in this simplified model (no loss carryforward).
        tax = max(0.0, ebit * tax_rate)
        credit = ptc[idx]
        # Net CF: (EBIT - tax) + depreciation (non-cash) + credits - carbon cost
        # carbon_cost already baked into ebit; add it back explicitly so the
        # row summary shows it as a separate line.
        net_cf = (ebit - tax) + d + credit
        flows.append(
            YearlyCashFlow(
                year=t,
                revenue=rev,
                opex=opex,
                depreciation=d,
                ebit=ebit,
                tax=tax,
                ptc=credit,
                carbon_cost=carbon_per_year,
                net_cf=net_cf,
            )
        )

    return flows


def npv_of(flows: list[YearlyCashFlow], discount_rate: float) -> float:
    return sum(
        f.net_cf / ((1 + discount_rate) ** f.year) for f in flows
    )


def irr_of(flows: list[YearlyCashFlow], guess: float = 0.1, max_iter: int = 200) -> float:
    """Newton-Raphson IRR on the post-tax cash-flow series."""
    import math

    def f(r: float) -> float:
        try:
            return sum(row.net_cf / ((1 + r) ** row.year) for row in flows)
        except (OverflowError, ZeroDivisionError):
            return float("inf")

    def df(r: float) -> float:
        try:
            return sum(
                -row.year * row.net_cf / ((1 + r) ** (row.year + 1)) for row in flows
            )
        except (OverflowError, ZeroDivisionError):
            return 0.0

    r = guess
    for _ in range(max_iter):
        y = f(r)
        if abs(y) < 1e-9:
            return r
        d = df(r)
        if d == 0:
            break
        r -= y / d
        if r <= -0.999999:
            break

    # Bracket fallback
    lo, hi = -0.99, 10.0
    y_lo, y_hi = f(lo), f(hi)
    if y_lo * y_hi > 0:
        return float("nan")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        y_mid = f(mid)
        if abs(y_mid) < 1e-9:
            return mid
        if y_lo * y_mid < 0:
            hi, y_hi = mid, y_mid
        else:
            lo, y_lo = mid, y_mid
    return (lo + hi) / 2


def payback_years_after_tax(flows: list[YearlyCashFlow]) -> float:
    """Undiscounted payback on the cash-flow series."""
    import math

    cum = 0.0
    prev = 0.0
    for row in flows:
        prev = cum
        cum += row.net_cf
        if cum >= 0 and prev < 0:
            return (row.year - 1) + (-prev / row.net_cf)
    return math.inf
