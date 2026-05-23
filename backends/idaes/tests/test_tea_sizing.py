"""Tests for algebraic sizing."""
from __future__ import annotations
import math
import pytest

from app.tea import (
    BlockInput,
    Stream,
    bare_module_cost,
    cost_ready,
    heat_exchanger_area,
    lmtd,
    size,
)


# ── Low-level primitives ───────────────────────────────────────────────────


class TestLMTD:
    def test_nominal_countercurrent(self) -> None:
        # Th_in=400K, Th_out=350K; Tc_in=300K, Tc_out=350K
        # dT1 = Th_in - Tc_out = 50; dT2 = Th_out - Tc_in = 50 → arithmetic = 50
        assert lmtd(400, 350, 300, 350) == pytest.approx(50.0)

    def test_asymmetric(self) -> None:
        # dT1 = 100, dT2 = 10; lmtd = (100-10)/ln(100/10) ≈ 39.09
        got = lmtd(500, 320, 310, 400)
        # dT1 = 500-400 = 100; dT2 = 320-310 = 10
        assert got == pytest.approx(39.087, abs=0.01)

    def test_floors_at_minimum(self) -> None:
        # Equal temperatures would give 0 → floor at 5 K
        assert lmtd(300, 300, 300, 300) == 5.0

    def test_pinch_returns_floor(self) -> None:
        # dT1 negative (temperature cross) → floor
        assert lmtd(300, 250, 280, 320) == 5.0


class TestHXArea:
    def test_basic(self) -> None:
        # Q = 1 MW, LMTD = 50 K, U = 500 → A = 1e6/(500*50) = 40 m²
        assert heat_exchanger_area(1e6, 50, 500) == pytest.approx(40.0)

    def test_zero_lmtd_raises(self) -> None:
        with pytest.raises(ValueError):
            heat_exchanger_area(1e6, 0, 500)

    def test_negative_duty_absolute(self) -> None:
        # Cooler has negative duty; area must still be positive.
        assert heat_exchanger_area(-1e6, 50) > 0


# ── Block sizers ───────────────────────────────────────────────────────────


def _stream(T=300.0, P=1e5, flow_mol=10.0, mw=50.0, rho=800.0) -> Stream:
    return Stream(T=T, P=P, flow_mol=flow_mol, molecular_weight=mw, density=rho)


class TestHeaterCooler:
    def test_heater_produces_area(self) -> None:
        block = BlockInput(
            block_type="Heater",
            duty=1e6,  # 1 MW
            inlet=_stream(T=300),
            outlet=_stream(T=400),
        )
        r = size(block)
        assert r is not None
        assert r.equipment_class == "HeatExchanger"
        assert r.size_unit == "m2"
        assert r.size > 0

    def test_cooler_positive_area(self) -> None:
        block = BlockInput(
            block_type="Cooler",
            duty=-500_000,
            inlet=_stream(T=400),
            outlet=_stream(T=320),
        )
        r = size(block)
        assert r is not None
        assert r.size > 0


class TestPump:
    def test_from_work(self) -> None:
        block = BlockInput(
            block_type="Pump", work=50_000, inlet=_stream(P=1e5), outlet=_stream(P=5e5)
        )
        r = size(block)
        assert r is not None
        assert r.equipment_class == "Pump"
        assert r.subtype == "Centrifugal"
        assert r.size == pytest.approx(50.0)  # 50 kW
        assert r.pressure_barg > 0

    def test_missing_work_raises(self) -> None:
        with pytest.raises(ValueError):
            size(BlockInput(block_type="Pump"))


class TestCompressor:
    def test_from_work(self) -> None:
        block = BlockInput(block_type="Compressor", work=2_000_000, inlet=_stream(P=5e5), outlet=_stream(P=5e6))
        r = size(block)
        assert r is not None
        assert r.equipment_class == "Compressor"
        assert r.size == pytest.approx(2000.0)


class TestFlash:
    def test_volume_from_flow(self) -> None:
        block = BlockInput(block_type="Flash", inlet=_stream(flow_mol=10, mw=50, rho=800))
        r = size(block)
        assert r is not None
        assert r.equipment_class == "Vessel"
        assert r.size > 0

    def test_missing_inlet_raises(self) -> None:
        with pytest.raises(ValueError):
            size(BlockInput(block_type="Flash"))


class TestReactor:
    def test_cstr_uses_default_residence(self) -> None:
        block = BlockInput(block_type="RCSTR", inlet=_stream(flow_mol=10))
        r = size(block)
        assert r is not None
        assert r.equipment_class == "Reactor"
        assert r.size > 0


class TestAreaBasedUnits:
    def _stream(self) -> Stream:
        return Stream(T=300.0, P=2e5, flow_mol=10.0, molecular_weight=50.0, density=800.0)

    @pytest.mark.parametrize("block_type", ["Centrifuge", "Filter", "Dryer", "Evaporator"])
    def test_size_from_mass_flow(self, block_type: str) -> None:
        b = BlockInput(block_type=block_type, inlet=self._stream())
        r = size(b)
        assert r is not None
        assert r.equipment_class == block_type
        assert r.size_unit == "m2"
        assert r.size > 0

    def test_missing_inlet_raises(self) -> None:
        with pytest.raises(ValueError):
            size(BlockInput(block_type="Centrifuge"))


class TestElectrolyzer:
    def test_power_from_work(self) -> None:
        b = BlockInput(
            block_type="Electrolyzer", work=1_000_000,  # 1 MW
            outlet=Stream(T=300, P=30e5, flow_mol=10),
        )
        r = size(b)
        assert r is not None
        assert r.equipment_class == "Electrolyzer"
        assert r.size == pytest.approx(1000)
        assert r.pressure_barg > 0

    def test_missing_work_raises(self) -> None:
        with pytest.raises(ValueError):
            size(BlockInput(block_type="Electrolyzer"))


class TestMembrane:
    def test_area_from_flow(self) -> None:
        b = BlockInput(
            block_type="Membrane",
            inlet=Stream(T=300, P=5e5, flow_mol=100, molecular_weight=18, density=1000),
        )
        r = size(b)
        assert r is not None
        assert r.equipment_class == "Membrane"
        assert r.size > 0


class TestPSA:
    def test_from_volumetric_flow(self) -> None:
        b = BlockInput(
            block_type="PSA",
            inlet=Stream(T=300, P=20e5, flow_mol=100, molecular_weight=29, density=24),
        )
        r = size(b)
        assert r is not None
        assert r.size_unit == "m3/s"


class TestCrystallizer:
    def test_volume_from_residence(self) -> None:
        b = BlockInput(
            block_type="Crystallizer",
            inlet=Stream(T=300, P=1e5, flow_mol=10, molecular_weight=100, density=1500),
        )
        r = size(b)
        assert r is not None
        assert r.size_unit == "m3"


class TestSprayDryer:
    def test_sizes_from_mass_flow(self) -> None:
        b = BlockInput(
            block_type="SprayDryer",
            inlet=Stream(T=300, P=1e5, flow_mol=10, molecular_weight=50, density=800),
        )
        r = size(b)
        assert r is not None
        assert r.size_unit == "kg/s"


class TestFan:
    def test_from_volumetric_flow(self) -> None:
        b = BlockInput(
            block_type="Fan",
            inlet=Stream(T=300.0, P=1e5, flow_mol=100, molecular_weight=29, density=1.2),
        )
        r = size(b)
        assert r is not None
        assert r.equipment_class == "Fan"
        assert r.size_unit == "m3/s"
        assert r.size > 0


class TestComponentRegistryEnrichment:
    """When a stream carries composition but lacks MW / density, the registry
    fills them in — if the known components cover ≥50% of the composition."""

    def test_registry_mw_wins_over_default_fallback(self) -> None:
        # Pure water: registry has MW = 18.015 g/mol vs default 50
        s = Stream(T=300, P=1e5, flow_mol=10, composition={"H2O": 1.0})
        assert s.mass_flow() == pytest.approx(10 * 0.018015, rel=1e-3)

    def test_registry_density_wins_over_default_fallback(self) -> None:
        # Pure water: registry has ρ ≈ 998 kg/m³ vs default 800
        s = Stream(T=300, P=1e5, flow_mol=10, composition={"H2O": 1.0})
        vol = s.volumetric_flow()
        mass = s.mass_flow()
        # rho = mass / vol, should equal registry water density
        assert mass / vol == pytest.approx(998.0, abs=1.0)

    def test_explicit_mw_overrides_registry(self) -> None:
        s = Stream(
            T=300, P=1e5, flow_mol=10,
            molecular_weight=20.0,
            composition={"H2O": 1.0},  # registry MW would be 18 if used
        )
        # Explicit MW should win
        assert s.mass_flow() == pytest.approx(10 * 0.020, rel=1e-6)

    def test_composition_coverage_threshold_falls_back(self) -> None:
        # Only 30% of stream is a known component → registry skipped
        s = Stream(
            T=300, P=1e5, flow_mol=10,
            composition={"Unobtanium": 0.7, "H2O": 0.3},
        )
        # Falls back to DEFAULTS.fallback_mw = 50
        assert s.mass_flow() == pytest.approx(10 * 0.050, rel=1e-6)

    def test_mixture_uses_weighted_mw(self) -> None:
        # 50/50 H2 (MW=2.016) and CO (MW=28.010) → weighted ≈ 15.013
        s = Stream(T=300, P=1e5, flow_mol=10, composition={"H2": 0.5, "CO": 0.5})
        expected_mw = (2.016 + 28.010) / 2  # = 15.013
        assert s.mass_flow() * 1000 / 10 == pytest.approx(expected_mw, rel=1e-3)


class TestNoCostBlocks:
    @pytest.mark.parametrize("t", ["Feed", "Sink", "Mixer", "Splitter", "Valve", "Product"])
    def test_returns_none(self, t: str) -> None:
        assert size(BlockInput(block_type=t)) is None


# ── Integration: size → cost roundtrip ─────────────────────────────────────


class TestCostIntegration:
    def test_pump_sized_and_costed(self) -> None:
        block = BlockInput(block_type="Pump", work=100_000, inlet=_stream(P=1e5), outlet=_stream(P=10e5))
        klass, subtype, sz, pressure = cost_ready(block)
        assert klass == "Pump"
        assert subtype == "Centrifugal"
        r = bare_module_cost(klass, subtype, "CarbonSteel", sz, pressure, cepci=800)
        assert r.bare_module > 0

    def test_heater_sized_and_costed(self) -> None:
        block = BlockInput(
            block_type="Heater",
            duty=2e6,
            inlet=_stream(T=300, P=2e5),
            outlet=_stream(T=400, P=2e5),
        )
        klass, subtype, sz, pressure = cost_ready(block)
        r = bare_module_cost(klass, subtype, "CarbonSteel", sz, pressure, cepci=800)
        assert r.bare_module > 0
