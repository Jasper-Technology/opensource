"""Tests for MACRS depreciation + tax model + credits."""
from __future__ import annotations
import pytest

from app.tea.taxes import (
    MacrsClass,
    ProductionTaxCredit,
    TaxConfig,
    cash_flow_with_taxes,
    irr_of,
    macrs_schedule,
    npv_of,
    payback_years_after_tax,
    ptc_schedule,
)


class TestMacrsSchedule:
    def test_seven_year_rates_sum_to_capex(self) -> None:
        schedule = macrs_schedule(1_000_000, MacrsClass.SEVEN_YEAR, 20)
        # First 8 entries cover the depreciable life
        assert sum(schedule[:8]) == pytest.approx(1_000_000, rel=1e-6)
        # Remaining years are zero
        assert all(x == 0 for x in schedule[8:])

    def test_five_year_rates_sum_to_capex(self) -> None:
        schedule = macrs_schedule(500_000, MacrsClass.FIVE_YEAR, 10)
        assert sum(schedule[:6]) == pytest.approx(500_000, rel=1e-6)

    def test_straight_line_rates(self) -> None:
        schedule = macrs_schedule(1_000_000, MacrsClass.STRAIGHT_LINE_20, 20)
        for s in schedule:
            assert s == pytest.approx(50_000)

    def test_shorter_project_life_truncates(self) -> None:
        schedule = macrs_schedule(1_000_000, MacrsClass.SEVEN_YEAR, 3)
        assert len(schedule) == 3


class TestPtcSchedule:
    def test_single_credit_applied_for_configured_years(self) -> None:
        credits = (ProductionTaxCredit(usd_per_unit=3.0, units_per_year=1_000_000, start_year=1, years=10),)
        schedule = ptc_schedule(credits, 20)
        assert all(v == 3_000_000 for v in schedule[:10])
        assert all(v == 0 for v in schedule[10:])

    def test_multiple_credits_aggregate(self) -> None:
        credits = (
            ProductionTaxCredit(usd_per_unit=3.0, units_per_year=1_000_000, start_year=1, years=10, name="45V"),
            ProductionTaxCredit(usd_per_unit=85.0, units_per_year=50_000, start_year=1, years=12, name="45Q"),
        )
        schedule = ptc_schedule(credits, 20)
        # Year 1 has both credits
        assert schedule[0] == 3_000_000 + 85 * 50_000
        # Year 11 has only 45Q
        assert schedule[10] == 85 * 50_000
        # Year 13 has neither
        assert schedule[12] == 0

    def test_late_start_credit(self) -> None:
        credits = (ProductionTaxCredit(usd_per_unit=1.0, units_per_year=1_000_000, start_year=3, years=5),)
        schedule = ptc_schedule(credits, 10)
        assert schedule[0] == 0
        assert schedule[1] == 0
        assert schedule[2] == 1_000_000  # year 3 (index 2)
        assert schedule[6] == 1_000_000
        assert schedule[7] == 0


class TestCashFlowWithTaxes:
    def test_year_zero_is_minus_capex(self) -> None:
        flows = cash_flow_with_taxes(
            capex=10_000_000,
            annual_revenue=3_000_000,
            annual_opex=1_500_000,
            project_life_years=20,
            tax_config=TaxConfig(),
        )
        assert flows[0].year == 0
        assert flows[0].net_cf == pytest.approx(-10_000_000)

    def test_itc_reduces_year_zero_capex(self) -> None:
        flows = cash_flow_with_taxes(
            capex=10_000_000,
            annual_revenue=3_000_000,
            annual_opex=1_500_000,
            project_life_years=20,
            tax_config=TaxConfig(itc_fraction=0.30),
        )
        assert flows[0].net_cf == pytest.approx(-7_000_000)

    def test_depreciation_shields_tax_early_years(self) -> None:
        # With high revenue, early years should show tax > 0 but lower than
        # (revenue - opex) × τ because depreciation shields income
        flows = cash_flow_with_taxes(
            capex=10_000_000,
            annual_revenue=5_000_000,
            annual_opex=2_000_000,
            project_life_years=20,
            tax_config=TaxConfig(
                corporate_tax_rate=0.21, state_tax_rate=0.0,
                revenue_escalation=0, opex_escalation=0,
            ),
        )
        year_1 = flows[1]
        # EBIT = 5M - 2M - 1.429M (7yr MACRS first year) = 1.571M
        # Tax = 1.571M × 0.21 = 0.33M (vs 0.63M without depreciation)
        assert year_1.tax < 3_000_000 * 0.21  # would be the un-shielded number
        assert year_1.tax == pytest.approx(1.571e6 * 0.21, rel=1e-2)

    def test_45v_ptc_on_hydrogen_project(self) -> None:
        credits = (
            ProductionTaxCredit(usd_per_unit=3.0, units_per_year=1_000_000, start_year=1, years=10),
        )
        flows = cash_flow_with_taxes(
            capex=50_000_000,
            annual_revenue=10_000_000,
            annual_opex=5_000_000,
            project_life_years=20,
            tax_config=TaxConfig(production_credits=credits),
        )
        # Year 1 net_cf should be well above the pre-credit operating profit
        assert flows[1].ptc == 3_000_000
        # Year 11 drops back to zero
        assert flows[11].ptc == 0

    def test_escalation_increases_revenue_year_over_year(self) -> None:
        flows = cash_flow_with_taxes(
            capex=1_000_000,
            annual_revenue=1_000_000,
            annual_opex=500_000,
            project_life_years=5,
            tax_config=TaxConfig(revenue_escalation=0.03, opex_escalation=0),
        )
        # 1M × 1.03^1 ≈ 1.03M
        assert flows[2].revenue == pytest.approx(1_030_000)
        # 1M × 1.03^4 ≈ 1.126M
        assert flows[5].revenue == pytest.approx(1_000_000 * 1.03 ** 4)

    def test_carbon_cost_applied(self) -> None:
        tc = TaxConfig(
            carbon_price_usd_per_ton=50.0,
            carbon_emissions_ton_per_year=10_000,
            revenue_escalation=0, opex_escalation=0,
        )
        flows = cash_flow_with_taxes(
            capex=1_000_000, annual_revenue=5_000_000, annual_opex=1_000_000,
            project_life_years=5, tax_config=tc,
        )
        assert flows[1].carbon_cost == 500_000


class TestNpvIrrPayback:
    def test_npv_positive_project(self) -> None:
        flows = cash_flow_with_taxes(
            capex=1_000_000, annual_revenue=500_000, annual_opex=100_000,
            project_life_years=20,
            tax_config=TaxConfig(revenue_escalation=0, opex_escalation=0),
        )
        assert npv_of(flows, 0.10) > 0

    def test_irr_recovers_base_rate_on_zero_npv_series(self) -> None:
        # Engineered so NPV@10% ≈ 0 — IRR should come back near 10%
        # NPV = -1M + 5 × cf / 1.1^t = 0 → cf = 263,797.48
        flows = cash_flow_with_taxes(
            capex=1_000_000, annual_revenue=263_797.48, annual_opex=0,
            project_life_years=5,
            # Disable taxes/escalation so the math is clean
            tax_config=TaxConfig(
                corporate_tax_rate=0, state_tax_rate=0,
                revenue_escalation=0, opex_escalation=0,
                macrs_class=MacrsClass.STRAIGHT_LINE_20,
            ),
        )
        rate = irr_of(flows)
        assert rate == pytest.approx(0.10, abs=0.01)

    def test_payback_for_simple_project(self) -> None:
        flows = cash_flow_with_taxes(
            capex=1_000_000, annual_revenue=500_000, annual_opex=100_000,
            project_life_years=10,
            tax_config=TaxConfig(
                corporate_tax_rate=0, state_tax_rate=0,
                revenue_escalation=0, opex_escalation=0,
                macrs_class=MacrsClass.STRAIGHT_LINE_20,
            ),
        )
        # Net CF without depreciation shielding: ~400k/yr → payback = 2.5yr
        pb = payback_years_after_tax(flows)
        assert 2.0 < pb < 3.0


class TestCombinedTaxRate:
    def test_state_is_deductible(self) -> None:
        tc = TaxConfig(corporate_tax_rate=0.21, state_tax_rate=0.05)
        # 0.21 + 0.05 × (1 - 0.21) = 0.21 + 0.0395 = 0.2495
        assert tc.combined_tax_rate == pytest.approx(0.2495)

    def test_zero_state_equals_federal(self) -> None:
        tc = TaxConfig(corporate_tax_rate=0.21, state_tax_rate=0)
        assert tc.combined_tax_rate == 0.21
