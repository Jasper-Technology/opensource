"""
Tests for Turton module-costing math.

Golden values computed from the same formulas (no independent source), so
these are regression tests, not "textbook validation" tests. A future
sweep against published Turton Ch.8 worked examples lives under the
pending ``tests/golden/`` tranche.
"""
from __future__ import annotations
import math
import pytest

from app.tea import (
    CostingError,
    SizeOutOfRangeWarning,
    bare_module_cost,
    get_catalog,
    load_catalog,
    pressure_factor,
    purchased_cost,
    total_module_cost,
)
from app.tea.catalog import Catalog, PressureRange


# ── Catalog ──────────────────────────────────────────────────────────────────

class TestCatalog:
    def test_loads(self) -> None:
        cat = get_catalog()
        assert isinstance(cat, Catalog)
        assert cat.cepci_reference > 0
        assert "Pump" in cat.equipment

    def test_expected_classes_present(self) -> None:
        cat = get_catalog()
        for name in ("Pump", "Compressor", "HeatExchanger", "Vessel", "Tank", "Reactor", "Heater"):
            assert name in cat.equipment

    def test_pump_has_centrifugal_subtype(self) -> None:
        st = get_catalog().klass("Pump").subtype("Centrifugal")
        assert st.K == (3.3892, 0.0536, 0.1538)
        assert st.size_unit == "kW"

    def test_pump_materials(self) -> None:
        klass = get_catalog().klass("Pump")
        assert klass.material_factor("CarbonSteel", "Centrifugal") == 1.54
        assert klass.material_factor("StainlessSteel", "Centrifugal") == 2.31

    def test_unknown_class_raises(self) -> None:
        with pytest.raises(KeyError):
            get_catalog().klass("Banana")

    def test_unknown_material_raises(self) -> None:
        with pytest.raises(KeyError):
            get_catalog().klass("Pump").material_factor("Kryptonite", "Centrifugal")


# ── Purchased cost ──────────────────────────────────────────────────────────

class TestPurchasedCost:
    def test_pump_basic(self) -> None:
        # 100 kW centrifugal pump, carbon steel, at CEPCI 800
        # log10(Cp0) = 3.3892 + 0.0536*log10(100) + 0.1538*log10(100)^2
        #            = 3.3892 + 0.1072 + 0.6152 = 4.1116 → Cp0 ≈ 12928.3
        # Cp = Cp0 * (800/397) ≈ 26053
        cp = purchased_cost("Pump", "Centrifugal", size=100, cepci=800)
        assert 25_000 < cp < 27_000

    def test_purchased_scales_linearly_with_cepci(self) -> None:
        cp_400 = purchased_cost("Pump", "Centrifugal", size=100, cepci=400)
        cp_800 = purchased_cost("Pump", "Centrifugal", size=100, cepci=800)
        assert cp_800 / cp_400 == pytest.approx(2.0, rel=1e-9)

    def test_compressor_cost(self) -> None:
        # Centrifugal compressor, 1000 kW
        cp = purchased_cost("Compressor", "Centrifugal", size=1000, cepci=800)
        assert cp > 0

    def test_negative_size_raises(self) -> None:
        with pytest.raises(CostingError):
            purchased_cost("Pump", "Centrifugal", size=-1, cepci=800)

    def test_size_below_min_warns(self) -> None:
        with pytest.warns(SizeOutOfRangeWarning):
            # Pump min is 1 kW
            purchased_cost("Pump", "Centrifugal", size=0.5, cepci=800)

    def test_size_above_max_warns(self) -> None:
        with pytest.warns(SizeOutOfRangeWarning):
            # Pump centrifugal max is 300 kW
            purchased_cost("Pump", "Centrifugal", size=500, cepci=800)


# ── Pressure factor ─────────────────────────────────────────────────────────

class TestPressureFactor:
    def test_atmospheric_is_one(self) -> None:
        st = get_catalog().klass("Pump").subtype("Centrifugal")
        assert pressure_factor(0.0, st) == 1.0

    def test_low_pressure_range_returns_one(self) -> None:
        # Centrifugal pump: 0-10 barg range has all zeros → Fp = 1
        st = get_catalog().klass("Pump").subtype("Centrifugal")
        assert pressure_factor(5.0, st) == pytest.approx(1.0)

    def test_high_pressure_increases_factor(self) -> None:
        st = get_catalog().klass("Pump").subtype("Centrifugal")
        fp_50 = pressure_factor(50.0, st)
        fp_5 = pressure_factor(5.0, st)
        assert fp_50 > fp_5

    def test_flat_plate_hx_always_one(self) -> None:
        # FlatPlate HX has no nontrivial pressure range up to 19 barg
        st = get_catalog().klass("HeatExchanger").subtype("FlatPlate")
        assert pressure_factor(10.0, st) == pytest.approx(1.0)
        assert pressure_factor(0.0, st) == pytest.approx(1.0)


# ── Bare-module cost ────────────────────────────────────────────────────────

class TestBareModuleCost:
    def test_cs_pump_atmospheric(self) -> None:
        # 100 kW centrifugal CS pump at 0 barg, CEPCI 800
        # Fm = 1.54, Fp = 1.0
        # F_BM = B1 + B2 * Fm * Fp = 1.89 + 1.35 * 1.54 * 1.0 = 3.969
        # C_BM = Cp * 3.969
        r = bare_module_cost(
            "Pump", "Centrifugal", "CarbonSteel", size=100, pressure=0, cepci=800
        )
        assert r.Fm == 1.54
        assert r.Fp == 1.0
        assert r.bare_module / r.purchased == pytest.approx(3.969, rel=1e-6)
        assert r.in_range is True

    def test_ss_pump_higher_cost(self) -> None:
        cs = bare_module_cost("Pump", "Centrifugal", "CarbonSteel", 100, 0, 800)
        ss = bare_module_cost("Pump", "Centrifugal", "StainlessSteel", 100, 0, 800)
        assert ss.bare_module > cs.bare_module

    def test_high_pressure_raises_cost(self) -> None:
        r_low = bare_module_cost("Pump", "Centrifugal", "CarbonSteel", 100, 0, 800)
        r_high = bare_module_cost("Pump", "Centrifugal", "CarbonSteel", 100, 50, 800)
        assert r_high.bare_module > r_low.bare_module
        assert r_high.Fp > 1.0

    def test_out_of_range_still_returns_value(self) -> None:
        # Should warn but still compute (analysts may extrapolate knowingly)
        with pytest.warns(SizeOutOfRangeWarning):
            r = bare_module_cost("Pump", "Centrifugal", "CarbonSteel", 500, 0, 800)
        assert r.in_range is False
        assert r.bare_module > 0


# ── Total-module cost ───────────────────────────────────────────────────────

class TestTotalModuleCost:
    def test_default_contingency_is_18pct(self) -> None:
        r = total_module_cost("Pump", "Centrifugal", "CarbonSteel", 100, 0, 800)
        # C_TM / C_BM should be 1.18
        assert r.total_module / r.bare_module == pytest.approx(1.18, rel=1e-9)

    def test_custom_contingency(self) -> None:
        r = total_module_cost(
            "Pump", "Centrifugal", "CarbonSteel", 100, 0, 800, contingency=0.25
        )
        assert r.total_module / r.bare_module == pytest.approx(1.25, rel=1e-9)

    def test_negative_contingency_raises(self) -> None:
        with pytest.raises(CostingError):
            total_module_cost(
                "Pump", "Centrifugal", "CarbonSteel", 100, 0, 800, contingency=-0.1
            )


# ── HeatExchanger integration ──────────────────────────────────────────────

class TestHeatExchanger:
    def test_fixed_tube_cs(self) -> None:
        r = bare_module_cost(
            "HeatExchanger", "FixedTube", "CarbonSteel", size=100, pressure=0, cepci=800
        )
        assert r.bare_module > 0
        assert r.Fm == 1.0  # CS base is 1.0
        assert r.Fp == 1.0  # 0 barg → below lowest range upper bound

    def test_floating_head_ss_hp(self) -> None:
        r = bare_module_cost(
            "HeatExchanger", "FloatingHead", "StainlessSteel",
            size=500, pressure=50, cepci=800,
        )
        assert r.Fm == 2.74
        assert r.Fp > 1.0


# ── Vessel ─────────────────────────────────────────────────────────────────

class TestVessel:
    def test_vertical_cs(self) -> None:
        r = bare_module_cost("Vessel", "Vertical", "CarbonSteel", size=10, pressure=0, cepci=800)
        assert r.bare_module > 0


# ── Reactor (F_bare path) ──────────────────────────────────────────────────

class TestReactor:
    def test_jacketed_agitated(self) -> None:
        r = bare_module_cost(
            "Reactor", "JacketedAgitated", "CarbonSteel", size=5, pressure=0, cepci=800
        )
        # F_bare path: C_BM = Cp · F_bare · Fm · Fp = Cp · 4.0 · 1.0 · 1.0
        assert r.bare_module / r.purchased == pytest.approx(4.0, rel=1e-9)
