"""Tests for reliability (availability + batch/continuous mode)."""
from __future__ import annotations
import pytest

from app.tea.reliability import (
    OperationMode,
    ReliabilityConfig,
    apply_reliability_to_totals,
)


class TestContinuousMode:
    def test_100_percent_availability_no_turnaround_passes_through(self) -> None:
        cfg = ReliabilityConfig(availability=1.0, turnaround_interval_years=0, turnaround_days=0)
        assert cfg.effective_hours_per_year(8000) == pytest.approx(8000)
        assert cfg.revenue_multiplier(8000) == pytest.approx(1.0)

    def test_availability_scales_linearly(self) -> None:
        cfg = ReliabilityConfig(availability=0.85, turnaround_interval_years=0)
        assert cfg.effective_hours_per_year(8000) == pytest.approx(6800)

    def test_turnaround_averaged_annually(self) -> None:
        cfg = ReliabilityConfig(
            availability=1.0,
            turnaround_interval_years=4,
            turnaround_days=14,
        )
        # 14 days / 4 years = 3.5 days/yr = 3.5/365 = 0.96% downtime
        effective = cfg.effective_hours_per_year(8000)
        assert effective == pytest.approx(8000 * (1 - 14 / 4 / 365), rel=1e-3)

    def test_combined_availability_and_turnaround(self) -> None:
        cfg = ReliabilityConfig(
            availability=0.95,
            turnaround_interval_years=4,
            turnaround_days=14,
        )
        effective = cfg.effective_hours_per_year(8000)
        # 0.95 × (1 - 14/4/365) ≈ 0.941 × 8000 ≈ 7528
        assert 7400 < effective < 7600


class TestBatchMode:
    def test_batch_scales_by_productive_fraction(self) -> None:
        cfg = ReliabilityConfig(
            operation_mode=OperationMode.BATCH,
            availability=1.0,
            turnaround_interval_years=0,
            batch_cycle_hours=24,
            batch_changeover_hours=4,
        )
        # 20/24 = 83.3% productive, availability 100% → 6667 h/yr effective
        effective = cfg.effective_hours_per_year(8000)
        assert effective == pytest.approx(8000 * 20 / 24, rel=1e-3)

    def test_batch_combined_with_availability(self) -> None:
        cfg = ReliabilityConfig(
            operation_mode=OperationMode.BATCH,
            availability=0.90,
            turnaround_interval_years=0,
            batch_cycle_hours=12,
            batch_changeover_hours=2,
        )
        # 0.90 × 10/12 = 0.75
        assert cfg.revenue_multiplier(8000) == pytest.approx(0.75, rel=1e-3)

    def test_zero_changeover_equals_continuous(self) -> None:
        cfg = ReliabilityConfig(
            operation_mode=OperationMode.BATCH,
            availability=1.0,
            turnaround_interval_years=0,
            batch_cycle_hours=24,
            batch_changeover_hours=0,
        )
        assert cfg.revenue_multiplier(8000) == pytest.approx(1.0)


class TestApplyReliabilityToTotals:
    def _totals(self) -> dict:
        return {
            "revenue_annual_usd": 10_000_000,
            "opex_annual_usd": 4_000_000,
            "opex_utilities_usd": 1_500_000,
            "opex_labor_usd": 1_800_000,
            "opex_maintenance_usd": 200_000,
            "opex_feedstock_usd": 500_000,
            "capex_bare_module_usd": 0, "capex_total_module_usd": 0,
        }

    def test_labor_and_maintenance_do_not_scale(self) -> None:
        cfg = ReliabilityConfig(availability=0.80, turnaround_interval_years=0)
        scaled = apply_reliability_to_totals(self._totals(), nominal_hours=8000, config=cfg)
        assert scaled["opex_labor_usd"] == 1_800_000
        assert scaled["opex_maintenance_usd"] == 200_000

    def test_revenue_and_utilities_scale(self) -> None:
        cfg = ReliabilityConfig(availability=0.80, turnaround_interval_years=0)
        scaled = apply_reliability_to_totals(self._totals(), nominal_hours=8000, config=cfg)
        assert scaled["revenue_annual_usd"] == pytest.approx(8_000_000)
        assert scaled["opex_utilities_usd"] == pytest.approx(1_200_000)
        assert scaled["opex_feedstock_usd"] == pytest.approx(400_000)

    def test_total_opex_recomputed(self) -> None:
        cfg = ReliabilityConfig(availability=0.80, turnaround_interval_years=0)
        scaled = apply_reliability_to_totals(self._totals(), nominal_hours=8000, config=cfg)
        expected = 1_200_000 + 400_000 + 1_800_000 + 200_000
        assert scaled["opex_annual_usd"] == pytest.approx(expected)

    def test_continuous_100pct_noop(self) -> None:
        cfg = ReliabilityConfig(
            availability=1.0, turnaround_interval_years=0,
            operation_mode=OperationMode.CONTINUOUS,
        )
        scaled = apply_reliability_to_totals(self._totals(), nominal_hours=8000, config=cfg)
        assert scaled == self._totals()
