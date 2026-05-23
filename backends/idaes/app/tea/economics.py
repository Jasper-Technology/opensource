"""
Economic endpoints — NPV, IRR, Payback, LCOP, TAC.

All functions are pure and take plain floats. Currency is USD by convention
(conversion to other currencies is a display-layer concern).

Conventions
-----------
- ``annual_cash_flow`` is a list where index 0 is year 0 (typically the
  capex outflow, negative), index 1 is year 1, etc.
- ``discount_rate`` is expressed as a fraction (0.10 for 10%).
- Internal rate of return uses Newton-Raphson with a safe bracket fallback.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable, Optional


class EconomicsError(ValueError):
    """Inputs violate contract (negative life, empty flow, etc.)."""


# ── Net present value ───────────────────────────────────────────────────────


def npv(cash_flows: Iterable[float], discount_rate: float) -> float:
    """
    Net present value.

    NPV = sum_{t=0..N} CF_t / (1 + r)^t

    Rate must be > -1. By convention ``cash_flows[0]`` is year 0.
    """
    if discount_rate <= -1.0:
        raise EconomicsError(f"discount_rate must be > -1; got {discount_rate}")
    flows = list(cash_flows)
    if not flows:
        raise EconomicsError("cash_flows must be non-empty")
    total = 0.0
    for t, cf in enumerate(flows):
        total += cf / ((1.0 + discount_rate) ** t)
    return total


# ── Internal rate of return ─────────────────────────────────────────────────


def irr(cash_flows: Iterable[float], guess: float = 0.1, tol: float = 1e-9, max_iter: int = 200) -> float:
    """
    Internal rate of return — rate that makes NPV == 0.

    Uses Newton-Raphson with a 10-bracket fallback for ill-conditioned series.
    Returns NaN when no real IRR exists in (-0.99, 10).
    """
    flows = list(cash_flows)
    if len(flows) < 2:
        raise EconomicsError("IRR requires at least 2 cash flows")

    def f(r: float) -> float:
        try:
            return sum(cf / (1 + r) ** t for t, cf in enumerate(flows))
        except (OverflowError, ZeroDivisionError):
            return float("inf") if flows[0] < 0 else float("-inf")

    def df(r: float) -> float:
        try:
            return sum(-t * cf / (1 + r) ** (t + 1) for t, cf in enumerate(flows))
        except (OverflowError, ZeroDivisionError):
            return 0.0

    # Newton-Raphson
    r = guess
    for _ in range(max_iter):
        y = f(r)
        if abs(y) < tol:
            return r
        d = df(r)
        if d == 0:
            break
        r -= y / d
        if r <= -0.999999:
            break

    # Bracket search as safety net
    lo, hi = -0.99, 10.0
    y_lo = f(lo)
    y_hi = f(hi)
    if y_lo * y_hi > 0:
        return float("nan")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        y_mid = f(mid)
        if abs(y_mid) < tol:
            return mid
        if y_lo * y_mid < 0:
            hi = mid
            y_hi = y_mid
        else:
            lo = mid
            y_lo = y_mid
    return (lo + hi) / 2


# ── Payback period ──────────────────────────────────────────────────────────


def payback_period(cash_flows: Iterable[float]) -> float:
    """
    Simple payback period in years — year at which cumulative cash flow
    crosses zero. Linear interpolation between the last negative and first
    non-negative year. Returns ``math.inf`` when the investment never pays back.
    """
    flows = list(cash_flows)
    if not flows:
        raise EconomicsError("cash_flows must be non-empty")

    cum = 0.0
    prev_cum = 0.0
    for t, cf in enumerate(flows):
        prev_cum = cum
        cum += cf
        if cum >= 0 and prev_cum < 0:
            # Linear interpolation inside year t
            return (t - 1) + (-prev_cum / cf)
        if cum >= 0 and t == 0:
            return 0.0
    return math.inf


# ── Total annual cost ───────────────────────────────────────────────────────


def annualized_capex(capex: float, lifetime_years: int, discount_rate: float) -> float:
    """
    Capital recovery factor approach.

    A = CAPEX · r / (1 - (1 + r)^(-N))

    When discount_rate is 0, falls back to straight-line CAPEX / N.
    """
    if lifetime_years <= 0:
        raise EconomicsError("lifetime_years must be positive")
    if discount_rate == 0:
        return capex / lifetime_years
    r = discount_rate
    n = lifetime_years
    crf = r / (1 - (1 + r) ** (-n))
    return capex * crf


def tac(
    capex: float,
    annual_opex: float,
    lifetime_years: int,
    discount_rate: float = 0.10,
) -> float:
    """
    Total annual cost = annualized CAPEX + OPEX.
    """
    return annualized_capex(capex, lifetime_years, discount_rate) + annual_opex


# ── Levelized cost of product ───────────────────────────────────────────────


@dataclass(frozen=True)
class LCOPInputs:
    capex: float                 # Total installed CAPEX (USD)
    annual_opex: float           # USD/yr (utilities, labor, maintenance, feed)
    annual_production: float     # product units / yr (kg, MWh, etc.)
    lifetime_years: int
    discount_rate: float = 0.10


def lcop(inputs: LCOPInputs) -> float:
    """
    Levelized cost of product — the price per unit that makes NPV = 0 if
    all production is sold at that price.

    LCOP = (annualized_CAPEX + annual_OPEX) / annual_production
    """
    if inputs.annual_production <= 0:
        raise EconomicsError("annual_production must be positive")
    total_annual = tac(inputs.capex, inputs.annual_opex, inputs.lifetime_years, inputs.discount_rate)
    return total_annual / inputs.annual_production


# ── Cash-flow construction helpers ──────────────────────────────────────────


@dataclass(frozen=True)
class SimpleProject:
    """
    Minimal cash-flow shape for the R1 MVC scope: upfront CAPEX in year 0,
    constant net annual cash flow thereafter. Richer forms (MACRS
    depreciation, escalation, tax holidays, credits) come in R2.
    """

    capex: float
    annual_net_cash_flow: float
    lifetime_years: int

    def cash_flows(self) -> list[float]:
        flows = [-self.capex]
        flows.extend([self.annual_net_cash_flow] * self.lifetime_years)
        return flows

    def npv(self, discount_rate: float = 0.10) -> float:
        return npv(self.cash_flows(), discount_rate)

    def irr(self) -> float:
        return irr(self.cash_flows())

    def payback(self) -> float:
        return payback_period(self.cash_flows())
