"""
Python ↔ TypeScript unit-converter parity test.

Generates a fixture of (value, from_unit, to_unit, expected_si) triples from
the Python converter. CI runs an equivalent Node script that evaluates the
TS converter against the same fixture and asserts agreement within 1e-9
relative tolerance.

This file produces the fixture; run
``python3 -m pytest tests/test_units_parity.py --fixture=gen``
or simply import ``PARITY_FIXTURE`` from another tool to regenerate.

The fixture lives at ``idaes-backend/tests/fixtures/units_parity.json``.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import pytest

from app.units import convert, to_si, UnknownUnitError

# Representative value × unit × target triples covering every dimension.
# Each triple: (value, from_unit, to_unit). Expected values are computed
# from the Python converter and written to the fixture file.
PARITY_TRIPLES: list[tuple[float, str, str]] = [
    # temperature
    (100, "C", "K"),
    (0, "C", "K"),
    (-40, "C", "F"),   # the famous equal-value crossover
    (32, "F", "K"),
    (212, "F", "C"),
    (491.67, "R", "K"),
    # pressure
    (1, "bar", "Pa"),
    (1, "atm", "Pa"),
    (14.7, "psi", "Pa"),
    (5, "barg", "bar"),
    (100, "psig", "psi"),
    (1e5, "Pa", "bar"),
    (1.01325, "bar", "atm"),
    # molar flow
    (100, "kmol/h", "mol/s"),
    (1, "mol/s", "kmol/h"),
    # mass flow
    (3600, "kg/h", "kg/s"),
    (1000, "lb/h", "kg/s"),
    (24, "ton/d", "kg/s"),
    # power
    (1, "kW", "W"),
    (1, "GJ/h", "W"),
    (3412, "BTU/h", "W"),
    (1, "MMBtu/h", "W"),
    # energy
    (1, "MWh", "J"),
    (1000, "Btu", "J"),
    # length / area / volume
    (1, "ft", "m"),
    (1, "in", "m") if False else (1, "inch", "m"),  # TS uses "inch"
    (1, "ft2", "m2"),
    (1, "ft3", "m3"),
    (1, "gal", "L"),
    (1, "bbl", "L"),
    # volumetric flow
    (60, "L/min", "m3/s"),
    (1, "gal/min", "m3/s"),
    # time
    (1, "yr", "s"),
    (1, "day", "hr"),
    # mass / density
    (1, "lb", "kg"),
    (1, "ton", "kg"),
    (1, "g/cm3", "kg/m3"),
    # molar enthalpy
    (1, "kJ/mol", "J/mol"),
    (1, "Btu/lbmol", "J/mol"),
]

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "units_parity.json"


@pytest.mark.parametrize("value,from_unit,to_unit", PARITY_TRIPLES)
def test_python_converter_produces_finite_result(
    value: float, from_unit: str, to_unit: str
) -> None:
    result = convert(value, from_unit, to_unit)
    assert math.isfinite(result), f"{value} {from_unit} → {to_unit} = {result}"


def test_write_parity_fixture() -> None:
    """Regenerate the fixture file. Not a pass/fail test — always passes."""
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cases = []
    for value, from_unit, to_unit in PARITY_TRIPLES:
        try:
            expected = convert(value, from_unit, to_unit)
        except UnknownUnitError:
            continue
        cases.append(
            {
                "value": value,
                "from": from_unit,
                "to": to_unit,
                "expected": expected,
            }
        )
    FIXTURE_PATH.write_text(json.dumps(cases, indent=2) + "\n")
    assert FIXTURE_PATH.exists()
    assert len(cases) >= 30
