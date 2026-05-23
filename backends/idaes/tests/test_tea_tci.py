"""Tests for ISBL/OSBL split + Lang-factor TCI roll-up."""
from __future__ import annotations
import pytest

from app.tea.tci import (
    BlockCategory,
    LangFactorBreakdown,
    TciConfig,
    classify,
    compute_tci,
)


class TestClassification:
    @pytest.mark.parametrize(
        "block_type,expected",
        [
            ("Pump", BlockCategory.ISBL),
            ("Compressor", BlockCategory.ISBL),
            ("Reactor", BlockCategory.ISBL),
            ("DistillationColumn", BlockCategory.ISBL),
            ("Tank", BlockCategory.OSBL),
            ("Feed", BlockCategory.UNKNOWN),
            ("Sink", BlockCategory.UNKNOWN),
            ("UnknownType", BlockCategory.ISBL),  # conservative default
        ],
    )
    def test_default_classification(self, block_type: str, expected: BlockCategory) -> None:
        assert classify(block_type) == expected


class TestComputeTci:
    def _sample_blocks(self) -> list[dict]:
        return [
            {"id": "P1", "type": "Pump", "total_module_usd": 500_000},
            {"id": "R1", "type": "RCSTR", "total_module_usd": 3_000_000},
            {"id": "T1", "type": "Tank", "total_module_usd": 1_500_000},
            {"id": "Feed", "type": "Feed"},  # no cost
        ]

    def test_isbl_osbl_separation(self) -> None:
        tci = compute_tci(blocks=self._sample_blocks(), annual_revenue=10_000_000)
        # P1 + R1 = 3.5M ISBL; T1 = 1.5M OSBL (ratio shortcut not used
        # because we have an explicit OSBL block)
        assert tci.isbl_equipment == 3_500_000
        assert tci.osbl_equipment == 1_500_000

    def test_osbl_ratio_fallback_when_no_explicit_osbl(self) -> None:
        blocks_no_osbl = [
            {"id": "P1", "type": "Pump", "total_module_usd": 1_000_000},
            {"id": "R1", "type": "RCSTR", "total_module_usd": 4_000_000},
        ]
        tci = compute_tci(
            blocks=blocks_no_osbl, annual_revenue=5_000_000,
            config=TciConfig(osbl_ratio=0.3),
        )
        assert tci.isbl_equipment == 5_000_000
        assert tci.osbl_equipment == pytest.approx(1_500_000)  # 30% of 5M

    def test_working_capital_scales_with_revenue(self) -> None:
        tci_lo = compute_tci(
            blocks=self._sample_blocks(),
            annual_revenue=1_000_000,
            config=TciConfig(working_capital_fraction=0.20),
        )
        tci_hi = compute_tci(
            blocks=self._sample_blocks(),
            annual_revenue=10_000_000,
            config=TciConfig(working_capital_fraction=0.20),
        )
        assert tci_hi.working_capital == 10 * tci_lo.working_capital
        assert tci_lo.working_capital == pytest.approx(200_000)

    def test_startup_is_fraction_of_fixed_capital(self) -> None:
        tci = compute_tci(
            blocks=self._sample_blocks(), annual_revenue=5_000_000,
            config=TciConfig(startup_fraction=0.10),
        )
        assert tci.startup_costs == pytest.approx(tci.fixed_capital * 0.10)

    def test_land_and_permits_passed_through(self) -> None:
        tci = compute_tci(
            blocks=self._sample_blocks(),
            annual_revenue=5_000_000,
            config=TciConfig(land_cost_usd=2_000_000, permitting_cost_usd=500_000),
        )
        assert tci.land_plus_permits == 2_500_000

    def test_tci_is_sum_of_buckets(self) -> None:
        tci = compute_tci(blocks=self._sample_blocks(), annual_revenue=5_000_000)
        assert tci.total_capital_investment == pytest.approx(
            tci.fixed_capital + tci.working_capital + tci.startup_costs + tci.land_plus_permits,
            rel=1e-9,
        )

    def test_override_category_wins_over_default(self) -> None:
        # Force a Pump to be OSBL
        blocks = [
            {"id": "P1", "type": "Pump", "total_module_usd": 1_000_000},
            {"id": "R1", "type": "RCSTR", "total_module_usd": 2_000_000},
        ]
        tci = compute_tci(
            blocks=blocks,
            annual_revenue=5_000_000,
            category_overrides={"P1": BlockCategory.OSBL},
        )
        assert tci.osbl_equipment == 1_000_000
        assert tci.isbl_equipment == 2_000_000

    def test_solids_plant_has_lower_piping(self) -> None:
        cfg_fluid = TciConfig(plant_type="fluid")
        cfg_solids = TciConfig(plant_type="solids")
        assert cfg_fluid.lang().piping > cfg_solids.lang().piping


class TestLangFactors:
    def test_direct_multiplier_equals_1_plus_components(self) -> None:
        lang = LangFactorBreakdown()
        mult = lang.total_direct_multiplier
        components = (
            lang.piping + lang.instrumentation + lang.electrical
            + lang.insulation + lang.paint + lang.civil
            + lang.service_facilities + lang.buildings
        )
        assert mult == pytest.approx(1.0 + components)

    def test_fluid_processing_total_multiplier_in_expected_range(self) -> None:
        # Turton grass-roots Lang factor ≈ 4.74 for fluids — our product of
        # direct × indirect multipliers should be in that neighbourhood.
        lang = LangFactorBreakdown()
        total = lang.total_direct_multiplier * lang.indirects_multiplier
        assert 3.0 <= total <= 5.5
