"""Tests for NPV / IRR / Payback / TAC / LCOP."""
from __future__ import annotations
import math
import pytest

from app.tea import (
    EconomicsError,
    LCOPInputs,
    SimpleProject,
    annualized_capex,
    irr,
    lcop,
    npv,
    payback_period,
    tac,
)


class TestNPV:
    def test_zero_rate_sums(self) -> None:
        # At r=0, NPV is just the sum of cash flows.
        assert npv([-100, 30, 30, 30, 30], 0) == pytest.approx(20)

    def test_discounts_future(self) -> None:
        # At r=10%, later cash flows are worth less.
        result = npv([-100, 110], 0.1)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_textbook_example(self) -> None:
        # -1000 capex, 300/yr for 5 yr at 10% = NPV ~ 137.24
        got = npv([-1000, 300, 300, 300, 300, 300], 0.10)
        assert got == pytest.approx(137.24, abs=0.01)

    def test_empty_raises(self) -> None:
        with pytest.raises(EconomicsError):
            npv([], 0.1)

    def test_invalid_rate_raises(self) -> None:
        with pytest.raises(EconomicsError):
            npv([1, 2], -1.5)


class TestIRR:
    def test_breakeven_investment(self) -> None:
        # -100 then 110 → IRR = 10%
        assert irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)

    def test_five_year_payback(self) -> None:
        # Standard textbook example
        got = irr([-1000, 300, 300, 300, 300, 300])
        assert 0.15 < got < 0.16

    def test_npv_at_irr_is_zero(self) -> None:
        flows = [-500, 150, 200, 250]
        r = irr(flows)
        assert npv(flows, r) == pytest.approx(0.0, abs=1e-6)

    def test_never_pays_back_returns_nan(self) -> None:
        # Monotonic negative — no real IRR
        got = irr([-100, -50, -50])
        assert math.isnan(got)

    def test_too_few_flows_raises(self) -> None:
        with pytest.raises(EconomicsError):
            irr([100])


class TestPayback:
    def test_exact_year(self) -> None:
        # -100, 50, 50, ... payback at year 2 exactly
        assert payback_period([-100, 50, 50, 50]) == pytest.approx(2.0)

    def test_fractional_year(self) -> None:
        # -100, 40, 80 → after year 1: -60; fraction = 60/80 = 0.75 → 1.75
        assert payback_period([-100, 40, 80]) == pytest.approx(1.75)

    def test_never_pays_back(self) -> None:
        assert payback_period([-100, 10, 10, 10]) == math.inf


class TestAnnualizedCapex:
    def test_zero_rate_straightline(self) -> None:
        # 1000 CAPEX over 10 years at r=0 → 100/yr
        assert annualized_capex(1000, 10, 0) == pytest.approx(100)

    def test_textbook_crf(self) -> None:
        # 1000 at 10% over 20yr, CRF = 0.10/(1-1.10^-20) = 0.1175
        # → annualized = 117.46
        assert annualized_capex(1000, 20, 0.10) == pytest.approx(117.46, abs=0.01)

    def test_invalid_life_raises(self) -> None:
        with pytest.raises(EconomicsError):
            annualized_capex(1000, 0, 0.1)


class TestTAC:
    def test_capex_plus_opex(self) -> None:
        # 1000 CAPEX over 10 yr at r=0 (100/yr annualized) + 50 OPEX = 150
        assert tac(1000, 50, 10, 0) == pytest.approx(150)


class TestLCOP:
    def test_per_unit_cost(self) -> None:
        # CAPEX 1M at r=0 over 10 yr = 100k/yr annualized + 200k OPEX = 300k/yr
        # at 1M kg/yr production → 0.30 $/kg
        inputs = LCOPInputs(
            capex=1_000_000,
            annual_opex=200_000,
            annual_production=1_000_000,
            lifetime_years=10,
            discount_rate=0,
        )
        assert lcop(inputs) == pytest.approx(0.30)

    def test_negative_production_raises(self) -> None:
        inputs = LCOPInputs(
            capex=1_000_000,
            annual_opex=200_000,
            annual_production=0,
            lifetime_years=10,
        )
        with pytest.raises(EconomicsError):
            lcop(inputs)


class TestSimpleProject:
    def test_npv_irr_payback_agree(self) -> None:
        p = SimpleProject(capex=1000, annual_net_cash_flow=300, lifetime_years=5)
        flows = p.cash_flows()
        assert flows[0] == -1000
        assert flows[-1] == 300
        assert len(flows) == 6
        assert p.npv(0.10) == pytest.approx(137.24, abs=0.01)
        assert p.payback() == pytest.approx(1000 / 300, rel=1e-3)
        assert p.irr() > 0.14 and p.irr() < 0.16
