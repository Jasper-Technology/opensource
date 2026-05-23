"""Tests for property package creation.

These tests require IDAES to be installed and import real IDAES classes.
Mark them as slow / integration tests so they can be skipped in CI
if IDAES is not available.
"""
import pytest

try:
    import idaes  # noqa: F401
    HAS_IDAES = True
except ImportError:
    HAS_IDAES = False

pytestmark = pytest.mark.skipif(not HAS_IDAES, reason="IDAES not installed")


def test_create_ideal_package():
    from app.idaes_wrapper.property_packages import create_property_package

    pkg = create_property_package("Ideal", ["H2O", "CO2"])
    assert pkg is not None


def test_create_srk_package():
    from app.idaes_wrapper.property_packages import create_property_package

    pkg = create_property_package("SRK", ["CH4", "C2H6"])
    assert pkg is not None


def test_unknown_component_raises():
    from app.idaes_wrapper.property_packages import create_property_package

    with pytest.raises(ValueError, match="Unknown component"):
        create_property_package("Ideal", ["H2O", "FakeMolecule"])
