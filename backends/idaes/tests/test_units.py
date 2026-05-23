"""Unit converter behaviour tests."""
from __future__ import annotations
import math
import pytest

from app.units import (
    Dimension,
    Quantity,
    convert,
    to_si,
    from_si,
    parse_quantity,
    DimensionMismatchError,
    UnknownUnitError,
)


# ── Temperature (offset scale — historic pint gotcha) ────────────────────────

class TestTemperature:
    def test_celsius_to_kelvin(self) -> None:
        assert convert(100, "C", "K") == pytest.approx(373.15)

    def test_celsius_alias(self) -> None:
        assert convert(0, "degC", "K") == pytest.approx(273.15)
        assert convert(0, "°C", "K") == pytest.approx(273.15)

    def test_fahrenheit_to_kelvin(self) -> None:
        assert convert(32, "F", "K") == pytest.approx(273.15)

    def test_rankine_to_kelvin(self) -> None:
        assert convert(491.67, "R", "K") == pytest.approx(273.15, abs=1e-3)

    def test_kelvin_roundtrip(self) -> None:
        assert convert(convert(100, "C", "K"), "K", "C") == pytest.approx(100)


# ── Pressure (absolute vs gauge) ─────────────────────────────────────────────

class TestPressure:
    def test_bar_to_pa(self) -> None:
        assert convert(1, "bar", "Pa") == pytest.approx(1e5)

    def test_barg_to_bar_adds_one_atm(self) -> None:
        # 5 barg = 5 + 1.01325 bar absolute
        got = convert(5, "barg", "bar")
        assert got == pytest.approx(6.01325, rel=1e-5)

    def test_psig_to_psi(self) -> None:
        assert convert(100, "psig", "psi") == pytest.approx(114.696, rel=1e-4)

    def test_atm_to_bar(self) -> None:
        assert convert(1, "atm", "bar") == pytest.approx(1.01325)

    def test_pa_to_barg_subtracts_atm(self) -> None:
        got = convert(2e5, "Pa", "barg")
        # 2 bar absolute = 0.98675 barg
        assert got == pytest.approx(0.98675, rel=1e-4)


# ── Flow ─────────────────────────────────────────────────────────────────────

class TestFlow:
    def test_kmol_per_hour(self) -> None:
        assert convert(100, "kmol/h", "mol/s") == pytest.approx(27.7778, rel=1e-4)

    def test_kg_per_hour(self) -> None:
        assert convert(3600, "kg/h", "kg/s") == pytest.approx(1.0)

    def test_lb_per_hour(self) -> None:
        # 1 lb ≈ 0.45359237 kg
        got = convert(1000, "lb/h", "kg/s")
        assert got == pytest.approx(1000 * 0.45359237 / 3600, rel=1e-5)

    def test_ton_per_day(self) -> None:
        # 24 ton/d = 24000 kg / 86400 s
        assert convert(24, "ton/d", "kg/s") == pytest.approx(24000 / 86400, rel=1e-5)


# ── Energy / power ───────────────────────────────────────────────────────────

class TestEnergy:
    def test_kw_to_w(self) -> None:
        assert convert(1, "kW", "W") == pytest.approx(1000)

    def test_gj_per_hour_to_watts(self) -> None:
        # 1 GJ/h = 1e9 J / 3600 s ≈ 277777.78 W
        got = convert(1, "GJ/h", "W")
        assert got == pytest.approx(1e9 / 3600, rel=1e-5)

    def test_btu_per_hour(self) -> None:
        # 1 Btu ≈ 1055.06 J
        got = convert(1, "BTU/h", "W")
        assert got == pytest.approx(1055.06 / 3600, rel=1e-3)


# ── Dimension mismatch ───────────────────────────────────────────────────────

class TestMismatch:
    def test_bar_to_kelvin_raises(self) -> None:
        with pytest.raises(DimensionMismatchError):
            convert(1, "bar", "K")

    def test_unknown_unit_raises(self) -> None:
        with pytest.raises(UnknownUnitError):
            convert(1, "banana", "K")

    def test_empty_unit_raises(self) -> None:
        with pytest.raises(UnknownUnitError):
            convert(1, "", "K")


# ── to_si / from_si ──────────────────────────────────────────────────────────

class TestSiRoundtrip:
    def test_to_si_temperature(self) -> None:
        assert to_si(100, "C", Dimension.TEMPERATURE) == pytest.approx(373.15)

    def test_to_si_pressure(self) -> None:
        assert to_si(10, "bar", Dimension.PRESSURE) == pytest.approx(1e6)

    def test_from_si_temperature(self) -> None:
        assert from_si(373.15, "C", Dimension.TEMPERATURE) == pytest.approx(100)

    def test_to_si_infer_dimension(self) -> None:
        # Without explicit dimension, infer from unit
        assert to_si(100, "C") == pytest.approx(373.15)
        assert to_si(1, "bar") == pytest.approx(1e5)


# ── parse_quantity ───────────────────────────────────────────────────────────

class TestParseQuantity:
    def test_simple(self) -> None:
        pq = parse_quantity("250 K")
        assert pq.value == 250
        assert pq.unit == "K"

    def test_scientific(self) -> None:
        pq = parse_quantity("1.5e5 Pa")
        assert pq.value == 1.5e5
        assert pq.unit == "Pa"

    def test_compound_unit(self) -> None:
        pq = parse_quantity("100 kmol/h")
        assert pq.unit == "kmol/h"

    def test_invalid(self) -> None:
        with pytest.raises(UnknownUnitError):
            parse_quantity("bogus")


# ── Quantity dataclass ───────────────────────────────────────────────────────

class TestQuantity:
    def test_construct_and_si(self) -> None:
        q = Quantity(value=100, unit="C", dimension=Dimension.TEMPERATURE)
        assert q.si_value == pytest.approx(373.15)

    def test_as_unit_converts(self) -> None:
        q = Quantity(value=100, unit="C", dimension=Dimension.TEMPERATURE)
        qf = q.as_unit("F")
        assert qf.value == pytest.approx(212, rel=1e-4)
        assert qf.unit == "F"

    def test_from_si_builds_in_display(self) -> None:
        q = Quantity.from_si(373.15, "C", Dimension.TEMPERATURE)
        assert q.value == pytest.approx(100)
        assert q.unit == "C"

    def test_wrong_dimension_raises(self) -> None:
        with pytest.raises(ValueError):
            Quantity(value=100, unit="C", dimension=Dimension.PRESSURE)


# ── Roundtrip sanity across every declared unit ──────────────────────────────

ROUNDTRIP_UNITS: list[tuple[str, float]] = [
    ("K", 300.0), ("C", 100.0), ("F", 212.0), ("R", 540.0),
    ("Pa", 1e5), ("kPa", 100.0), ("MPa", 1.0), ("bar", 1.5),
    ("atm", 2.0), ("psi", 14.7), ("barg", 5.0), ("psig", 100.0),
    ("mol/s", 27.7), ("kmol/h", 100.0), ("kg/s", 1.0), ("kg/h", 3600.0),
    ("lb/h", 1000.0), ("ton/d", 24.0),
    ("W", 1000.0), ("kW", 1.0), ("GJ/h", 1.0), ("BTU/h", 3412.0),
    ("m3", 1.0), ("ft3", 35.3), ("m2", 1.0),
    ("hr", 1.0), ("yr", 1.0),
]


@pytest.mark.parametrize("unit,value", ROUNDTRIP_UNITS)
def test_si_roundtrip(unit: str, value: float) -> None:
    """Every supported unit must roundtrip to SI and back within 1e-9."""
    si = to_si(value, unit)
    back = from_si(si, unit)
    assert math.isclose(value, back, rel_tol=1e-9, abs_tol=1e-9), \
        f"{unit}: {value} → {si} → {back}"
