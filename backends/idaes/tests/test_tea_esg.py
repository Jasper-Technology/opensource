"""Tests for ESG scope 1/2/3 + carbon intensity."""
from __future__ import annotations
import pytest

from app.tea.esg import (
    EsgConfig,
    FeedstockInput,
    FuelConsumption,
    compute_esg,
    FUEL_EF_KGCO2_PER_KG,
    GRID_EF_KGCO2_PER_KWH,
)


class TestWaterFootprint:
    def test_withdrawal_and_consumption_per_kg(self) -> None:
        r = compute_esg(
            EsgConfig(
                annual_production_kg=1_000_000,
                water_withdrawal_m3_per_year=2_000_000,
                water_consumption_m3_per_year=50_000,
            )
        )
        assert r.water_withdrawal_m3_per_kg == pytest.approx(2.0)
        assert r.water_consumption_m3_per_kg == pytest.approx(0.05)

    def test_zero_production_yields_zero(self) -> None:
        r = compute_esg(
            EsgConfig(
                annual_production_kg=0,
                water_consumption_m3_per_year=10_000,
            )
        )
        assert r.water_consumption_m3_per_kg == 0.0


class TestScope1:
    def test_natural_gas_combustion(self) -> None:
        # 1 million kg/yr of NG at EF=2.75 = 2.75M kg = 2,750 tons
        r = compute_esg(EsgConfig(fuels=(FuelConsumption("natural_gas", 1_000_000),)))
        assert r.scope_1_tco2_per_year == pytest.approx(2_750)

    def test_biomass_is_biogenic_zero(self) -> None:
        r = compute_esg(EsgConfig(fuels=(FuelConsumption("biomass", 1_000_000),)))
        assert r.scope_1_tco2_per_year == 0

    def test_unknown_fuel_contributes_zero(self) -> None:
        r = compute_esg(EsgConfig(fuels=(FuelConsumption("unobtanium", 1_000_000),)))
        assert r.scope_1_tco2_per_year == 0

    def test_multiple_fuels_aggregate(self) -> None:
        r = compute_esg(
            EsgConfig(
                fuels=(
                    FuelConsumption("natural_gas", 100_000),
                    FuelConsumption("fuel_oil", 50_000),
                )
            )
        )
        assert r.scope_1_tco2_per_year == pytest.approx(100 * 2.75 + 50 * 3.15)


class TestScope2:
    def test_default_region_applies(self) -> None:
        r = compute_esg(EsgConfig(grid_region="US-MW", electricity_kwh_per_year=1_000_000))
        # 1M kWh × 0.45 = 450,000 kg = 450 tons
        assert r.scope_2_tco2_per_year == pytest.approx(450)

    def test_override_wins_over_region(self) -> None:
        r = compute_esg(
            EsgConfig(
                grid_region="US-MW",
                grid_ef_override=0.10,
                electricity_kwh_per_year=1_000_000,
            )
        )
        assert r.scope_2_tco2_per_year == pytest.approx(100)

    def test_unknown_region_uses_custom_fallback(self) -> None:
        r = compute_esg(EsgConfig(grid_region="Mars-01", electricity_kwh_per_year=1000))
        # Falls back to CUSTOM (0.45)
        assert r.scope_2_tco2_per_year == pytest.approx(0.45)


class TestScope3:
    def test_single_feedstock_uses_table(self) -> None:
        r = compute_esg(
            EsgConfig(feedstocks=(FeedstockInput("natural_gas", 1_000_000),))
        )
        # 1M kg × 0.30 = 300,000 kg = 300 tons
        assert r.scope_3_tco2_per_year == pytest.approx(300)

    def test_ci_override_wins(self) -> None:
        r = compute_esg(
            EsgConfig(
                feedstocks=(
                    FeedstockInput("natural_gas", 1_000_000, ci_kgco2_per_kg=0.10),
                )
            )
        )
        assert r.scope_3_tco2_per_year == pytest.approx(100)


class TestCarbonIntensity:
    def test_ci_per_product_kg(self) -> None:
        # 1000 tons CO2/yr scope 1 only; 1M kg/yr product
        r = compute_esg(
            EsgConfig(
                fuels=(FuelConsumption("natural_gas", 363_636),),  # ~1000 t CO2
                annual_production_kg=1_000_000,
            )
        )
        # 1000 tons / 1M kg = 1 kg CO2/kg product
        assert r.ci_kgco2_per_kg_product == pytest.approx(1.0, rel=1e-3)

    def test_zero_production_gives_zero_ci(self) -> None:
        r = compute_esg(
            EsgConfig(
                fuels=(FuelConsumption("natural_gas", 1000),),
                annual_production_kg=0,
            )
        )
        assert r.ci_kgco2_per_kg_product == 0.0


class TestTotals:
    def test_total_is_sum_of_scopes(self) -> None:
        r = compute_esg(
            EsgConfig(
                fuels=(FuelConsumption("natural_gas", 100_000),),
                grid_region="US-GC",
                electricity_kwh_per_year=500_000,
                feedstocks=(FeedstockInput("natural_gas", 200_000),),
            )
        )
        assert r.total_tco2_per_year == pytest.approx(
            r.scope_1_tco2_per_year + r.scope_2_tco2_per_year + r.scope_3_tco2_per_year,
            rel=1e-9,
        )


class TestTablesWellFormed:
    def test_all_grid_efs_positive(self) -> None:
        for region, ef in GRID_EF_KGCO2_PER_KWH.items():
            assert ef >= 0, f"{region} has invalid EF {ef}"

    def test_fuel_efs_in_expected_range(self) -> None:
        for fuel, ef in FUEL_EF_KGCO2_PER_KG.items():
            assert 0 <= ef <= 5, f"{fuel} EF out of range: {ef}"
