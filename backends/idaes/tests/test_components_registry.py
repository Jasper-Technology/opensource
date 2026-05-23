"""Tests for the curated component registry."""
from __future__ import annotations
import pytest

from app.components_registry import DEFAULT_COMPONENTS, get_default_registry


def test_registry_has_expected_chemicals() -> None:
    reg = get_default_registry()
    for name in ["Methanol", "Ethanol", "Benzene", "CO", "CO2", "H2", "H2O", "NH3"]:
        assert name in reg, f"{name} missing from seed"


def test_cas_lookup() -> None:
    reg = get_default_registry()
    # Methanol CAS 67-56-1
    c = reg.lookup("67-56-1")
    assert c is not None
    assert c.name == "Methanol"
    assert c.mw == pytest.approx(32.042, abs=0.01)


def test_case_insensitive_name_lookup() -> None:
    reg = get_default_registry()
    assert reg.lookup("methanol") == reg.lookup("Methanol") == reg.lookup("METHANOL")


def test_smiles_lookup() -> None:
    reg = get_default_registry()
    c = reg.lookup("CO")  # first matches by name ("CO" = carbon monoxide)
    assert c is not None
    assert c.name == "CO"


def test_unknown_returns_none() -> None:
    assert get_default_registry().lookup("Banana") is None
    assert get_default_registry().lookup("") is None


def test_seed_coverage_sanity() -> None:
    # Should have enough to cover common R1 use cases
    assert len(DEFAULT_COMPONENTS) >= 40
    assert len(get_default_registry()) == len(DEFAULT_COMPONENTS)


def test_mws_reasonable() -> None:
    # Sanity check the MW column against known values
    reg = get_default_registry()
    assert reg.lookup("H2O").mw == pytest.approx(18.015, abs=0.01)
    assert reg.lookup("Benzene").mw == pytest.approx(78.114, abs=0.01)
    assert reg.lookup("CO2").mw == pytest.approx(44.010, abs=0.01)


def test_every_component_has_mw_and_cas() -> None:
    for c in DEFAULT_COMPONENTS:
        assert c.cas, f"{c.name} missing CAS"
        assert c.mw > 0, f"{c.name} has invalid MW {c.mw}"
        # NBP and density are optional but if present should be positive
        if c.nbp is not None:
            assert c.nbp > 0, f"{c.name} has invalid NBP {c.nbp}"
        if c.density is not None:
            assert c.density > 0, f"{c.name} has invalid density {c.density}"
