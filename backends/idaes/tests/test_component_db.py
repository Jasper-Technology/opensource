"""Tests for the component database."""
from app.data.component_db import (
    get_component,
    get_component_by_formula,
    get_component_by_id,
    get_idaes_parameter_data,
    get_all_categories,
    COMPONENTS,
)
import pytest


def test_lookup_by_formula():
    comp = get_component_by_formula("H2O")
    assert comp is not None
    assert comp.name == "Water"
    assert comp.mw == pytest.approx(18.015)


def test_lookup_by_id():
    comp = get_component_by_id("methane")
    assert comp is not None
    assert comp.formula == "CH4"


def test_fuzzy_lookup():
    assert get_component("H2O") is not None
    assert get_component("water") is not None
    assert get_component("Water") is not None


def test_unknown_component_returns_none():
    assert get_component("UnknowniumX") is None


def test_idaes_parameter_data_valid():
    data = get_idaes_parameter_data("CO2")
    assert "mw" in data
    assert "pressure_crit" in data
    assert "temperature_crit" in data
    assert "omega" in data
    assert data["mw"] == pytest.approx(44.01)


def test_idaes_parameter_data_raises_on_unknown():
    with pytest.raises(ValueError, match="Unknown component"):
        get_idaes_parameter_data("FakeCompound99")


def test_all_components_have_positive_mw():
    for comp in COMPONENTS:
        assert comp.mw > 0, f"{comp.formula} has non-positive MW"


def test_categories():
    cats = get_all_categories()
    assert "alkane" in cats
    assert "inorganic" in cats


def test_at_least_30_components():
    assert len(COMPONENTS) >= 30
