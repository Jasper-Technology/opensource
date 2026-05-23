"""Regression coverage for the expanded catalog (centrifuge, filter, dryer,
evaporator, fan)."""
from __future__ import annotations
import pytest

from app.tea import bare_module_cost, get_catalog, purchased_cost


@pytest.fixture(autouse=True)
def reload_catalog() -> None:
    # The catalog uses lru_cache — force a fresh load so the new JSON entries
    # are picked up even if an earlier test populated the cache.
    get_catalog.cache_clear()


class TestExpandedCatalog:
    @pytest.mark.parametrize(
        "equipment,subtype,material,size",
        [
            ("Centrifuge", "Belt", "CarbonSteel", 10.0),
            ("Centrifuge", "Apron", "StainlessSteel", 5.0),
            ("Filter", "Drum", "CarbonSteel", 50.0),
            ("Filter", "PlateFrame", "StainlessSteel", 20.0),
            ("Dryer", "Rotary", "CarbonSteel", 30.0),
            ("Dryer", "Tray", "StainlessSteel", 10.0),
            ("Evaporator", "ForcedCirculation", "CarbonSteel", 100.0),
            ("Evaporator", "LongTube", "NiAlloy", 500.0),
            ("Fan", "CentrifugalRadial", "CarbonSteel", 10.0),
            ("Fan", "AxialVane", "StainlessSteel", 50.0),
            ("Electrolyzer", "PEM", "Standard", 1000.0),
            ("Electrolyzer", "Alkaline", "HighSpec", 5000.0),
            ("Membrane", "RO", "Polymer", 500.0),
            ("Membrane", "UF", "Ceramic", 100.0),
            ("PSA", "Skid", "CarbonSteel", 2.0),
            ("Crystallizer", "Batch", "StainlessSteel", 10.0),
            ("Crystallizer", "Continuous", "NiAlloy", 50.0),
            ("SprayDryer", "CoCurrent", "StainlessSteel", 1.0),
        ],
    )
    def test_every_new_combination_produces_positive_cost(
        self,
        equipment: str,
        subtype: str,
        material: str,
        size: float,
    ) -> None:
        r = bare_module_cost(equipment, subtype, material, size, pressure=0, cepci=800)
        assert r.bare_module > 0
        assert r.purchased > 0

    def test_material_factor_increases_cost(self) -> None:
        cs = bare_module_cost("Centrifuge", "Belt", "CarbonSteel", 10, 0, 800)
        ss = bare_module_cost("Centrifuge", "Belt", "StainlessSteel", 10, 0, 800)
        assert ss.bare_module > cs.bare_module

    def test_fan_uses_volumetric_flow_unit(self) -> None:
        cat = get_catalog()
        st = cat.klass("Fan").subtype("CentrifugalRadial")
        assert st.size_unit == "m3/s"

    def test_evaporator_two_factor_model(self) -> None:
        # Evaporator is the only new class that uses (B1, B2) rather than F_bare.
        # Validate the bare-module multiplier.
        cat = get_catalog()
        st = cat.klass("Evaporator").subtype("ForcedCirculation")
        assert st.F_bare is None
        assert st.B1 == 1.89
        assert st.B2 == 1.35

    def test_all_new_classes_listed(self) -> None:
        cat = get_catalog()
        for name in (
            "Centrifuge", "Filter", "Dryer", "Evaporator", "Fan",
            "Electrolyzer", "Membrane", "PSA", "Crystallizer", "SprayDryer",
        ):
            assert name in cat.equipment

    def test_purchased_cost_scales_with_size(self) -> None:
        small = purchased_cost("Filter", "Drum", 10, 800)
        big = purchased_cost("Filter", "Drum", 100, 800)
        assert big > small
