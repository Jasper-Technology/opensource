"""Tests for Monte Carlo sensitivity."""
from __future__ import annotations
import pytest

from app.tea.sensitivity import MonteCarloResult, run_monte_carlo


def _base() -> dict:
    return {
        "economics": {"npv_usd": 10_000_000, "irr": 0.15, "payback_years": 5, "tac_usd": 0, "lcop": -1},
        "totals": {
            "capex_bare_module_usd": 8_000_000,
            "capex_total_module_usd": 12_000_000,
            "opex_annual_usd": 6_000_000,
            "opex_utilities_usd": 1_000_000,
            "opex_labor_usd": 1_800_000,
            "opex_maintenance_usd": 200_000,
            "opex_feedstock_usd": 3_000_000,
            "revenue_annual_usd": 10_000_000,
        },
        "blocks": [],
        "status": "ok",
        "warnings": [],
    }


def _scn() -> dict:
    return {
        "cepci": 800,
        "discount_rate": 0.10,
        "project_life_years": 20,
        "default_material": "CarbonSteel",
    }


class TestRunMonteCarlo:
    def test_returns_requested_sample_count(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=500, seed=42)
        assert r.samples == 500
        assert len(r.npv_samples) == 500

    def test_samples_sorted_ascending(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=200, seed=42)
        for i in range(1, len(r.npv_samples)):
            assert r.npv_samples[i] >= r.npv_samples[i - 1]

    def test_percentile_ordering(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=1000, seed=42)
        assert r.p10 <= r.p50 <= r.p90

    def test_reproducible_with_seed(self) -> None:
        r1 = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=100, seed=7)
        r2 = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=100, seed=7)
        assert r1.npv_samples == r2.npv_samples

    def test_different_seeds_differ(self) -> None:
        r1 = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=100, seed=1)
        r2 = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=100, seed=2)
        assert r1.npv_samples != r2.npv_samples

    def test_probability_positive_in_range(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=1000, seed=42)
        assert 0.0 <= r.probability_positive <= 1.0

    def test_positive_project_probability(self) -> None:
        # Base has revenue=10M, OPEX=6M, CAPEX=12M, life=20, r=10% → NPV ~22M
        # With symmetric ±20% triangular noise the vast majority should stay positive
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=2000, seed=42)
        assert r.probability_positive > 0.90

    def test_mean_approximates_base_case(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=5000, seed=42)
        # Base NPV ≈ -12M + (10M-6M) * annuity_factor(10%, 20yr)
        # annuity factor = (1 - 1.1^-20)/0.1 = 8.5136
        # NPV ≈ -12M + 4M * 8.5136 = 22.05M
        expected_mean = 22_054_000  # ≈
        assert abs(r.mean - expected_mean) / expected_mean < 0.02

    def test_too_few_samples_raises(self) -> None:
        with pytest.raises(ValueError):
            run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=5)

    def test_too_many_samples_raises(self) -> None:
        with pytest.raises(ValueError):
            run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=200_000)


class TestHistogram:
    def test_bin_counts_sum_to_total(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=500, seed=42)
        hist = r.histogram(bins=10)
        assert sum(b["count"] for b in hist) == 500

    def test_bins_are_contiguous(self) -> None:
        r = run_monte_carlo(base_result=_base(), base_scenario=_scn(), samples=500, seed=42)
        hist = r.histogram(bins=10)
        for i in range(1, len(hist)):
            assert hist[i]["low"] == pytest.approx(hist[i - 1]["high"], rel=1e-6)

    def test_single_point_histogram(self) -> None:
        # Edge case: zero variance
        import random
        result = MonteCarloResult(
            samples=10,
            npv_samples=tuple([5_000_000.0] * 10),
            p10=5_000_000, p50=5_000_000, p90=5_000_000,
            mean=5_000_000, std=0.0, probability_positive=1.0,
        )
        hist = result.histogram(bins=10)
        assert len(hist) == 1
        assert hist[0]["count"] == 10
