"""
Unit converter — thin wrapper around ``pint``.

Design rules
------------
1. All *stored* values are canonical SI (see ``dimensions.py``). Convert at
   ingest (parsers) and egress (display) only.
2. ``pint`` is only touched at the boundary. Hot loops (Monte Carlo, TEA
   tree-walk) use plain floats plus a dimension sidecar; never instantiate
   a ``pint.Quantity`` per sample.
3. Every public function raises ``DimensionMismatchError`` or
   ``UnknownUnitError`` — never silently returns an incorrect value.
4. The user-facing unit vocabulary is locked (see ``UNIT_CATALOG``); this
   module accepts aliases but rejects anything outside the catalog to keep
   the TS mirror in sync.

The TS mirror at ``site/src/core/units.ts`` must cover the same unit
strings. Parity is enforced by ``tests/test_units_parity.py``.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable

import pint

from .dimensions import Dimension

# ── Single shared registry ────────────────────────────────────────────────────
# Reused across calls so parsed units are cached; thread-safe for reads.
_UREG = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)

# Pint's default registry does not include pound_mole. Add it.
# 1 lbmol = 453.59237 mol (same as 1 lb in g).
_UREG.define("pound_mole = 453.59237 * mole = lbmol")

# UI-friendly aliases → pint-canonical tokens.
# ``C`` in pint = Coulomb; Jasper users always mean Celsius. Resolve early.
_UI_ALIAS: dict[str, str] = {
    "C": "degC",
    "degC": "degC",
    "celsius": "degC",
    "°C": "degC",
    "F": "degF",
    "degF": "degF",
    "fahrenheit": "degF",
    "°F": "degF",
    "R": "degR",
    "degR": "degR",
    "rankine": "degR",
    # Pressure aliases
    "bara": "bar",
    "psia": "psi",
    # Gauge pressures: gauge = absolute - 1 atm. Handled in convert() below.
    # Energy rate common shorthands
    "GJ/h": "gigajoule/hour",
    "MJ/h": "megajoule/hour",
    "kJ/h": "kilojoule/hour",
    # Pin to IT Btu (1055.05585262 J) to match TS table; pint's default "Btu"
    # is 1055.056 (rounded).
    "Btu": "Btu_it",
    "BTU": "Btu_it",
    "MJ": "megajoule",
    "GJ": "gigajoule",
    "BTU/h": "Btu_it/hour",
    "Btu/h": "Btu_it/hour",
    "Btu/lbmol": "Btu_it/pound_mole",
    # Flow shorthands
    "kmol/h": "kilomole/hour",
    "mol/h": "mole/hour",
    "kg/h": "kilogram/hour",
    "ton": "metric_ton",          # align with TS (1 ton = 1000 kg, not 907.18)
    "ton/d": "metric_ton/day",
    "lb/h": "pound/hour",
    "bbl": "oil_barrel",          # pint default "bbl" is UK barrel; Jasper means oil
    "lbmol": "pound_mole",
    "m3/h": "meter**3/hour",
    "m3/s": "meter**3/second",
    "L/min": "liter/minute",
    "gal/min": "gallon/minute",
    # Density
    "kg/m3": "kilogram/meter**3",
    "g/cm3": "gram/centimeter**3",
    "lb/ft3": "pound/foot**3",
    # Molar enthalpy / entropy
    "J/mol": "joule/mole",
    "kJ/mol": "kilojoule/mole",
    "J/kmol": "joule/kilomole",
    "kJ/kmol": "kilojoule/kilomole",
    "J/(mol*K)": "joule/(mole*kelvin)",
    "J/mol/K": "joule/(mole*kelvin)",
    "kJ/(mol*K)": "kilojoule/(mole*kelvin)",
    # Length/volume common
    "m2": "meter**2",
    "m3": "meter**3",
    "ft2": "foot**2",
    "ft3": "foot**3",
    # Time
    "hr": "hour",
    "yr": "year",
}

# Pre-multiplier aliases: value is scaled by N and the remaining unit string
# is sent to pint. Avoids pint's "no scaling factor" rule while still giving
# users a short UI vocabulary (``MMBtu`` = 1e6 Btu).
_SCALED_UNITS: dict[str, tuple[float, str]] = {
    "MMBtu": (1e6, "Btu_it"),
    "MMBtu/h": (1e6, "Btu_it/hour"),
}

# Gauge-pressure units that need +1 atm when converted to absolute.
_GAUGE_UNITS: frozenset[str] = frozenset({"barg", "psig", "kPag", "MPag"})
_GAUGE_BASE: dict[str, str] = {
    "barg": "bar",
    "psig": "psi",
    "kPag": "kPa",
    "MPag": "MPa",
}
_ATM_PA = 101325.0


class UnknownUnitError(ValueError):
    """Raised when a unit string cannot be parsed."""

    def __init__(self, unit: str) -> None:
        self.unit = unit
        super().__init__(
            f"Unknown unit {unit!r}. Add it to app/units/converters.py "
            "and site/src/core/units.ts to keep Python and TS in sync."
        )


class DimensionMismatchError(ValueError):
    """Raised when conversion is attempted between incompatible dimensions."""

    def __init__(self, src: str, dst: str) -> None:
        self.src = src
        self.dst = dst
        super().__init__(f"Cannot convert {src!r} to {dst!r}: incompatible dimensions.")


@dataclass(frozen=True)
class ParsedQuantity:
    value: float
    unit: str  # original unit string as provided


_QUANTITY_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(.+?)\s*$")


def parse_quantity(text: str) -> ParsedQuantity:
    """Parse "250 C" / "1e5 Pa" / "100 kmol/h" into (value, unit)."""
    if not isinstance(text, str) or not text.strip():
        raise UnknownUnitError(str(text))
    m = _QUANTITY_RE.match(text)
    if not m:
        raise UnknownUnitError(text)
    return ParsedQuantity(float(m.group(1)), m.group(2))


def _resolve_unit(unit: str) -> tuple[float, str, bool]:
    """Return (scale_factor, pint-canonical unit, is_gauge)."""
    if unit in _SCALED_UNITS:
        scale, base = _SCALED_UNITS[unit]
        # The base may itself need alias resolution.
        return scale, _UI_ALIAS.get(base, base), False
    if unit in _GAUGE_UNITS:
        return 1.0, _UI_ALIAS.get(_GAUGE_BASE[unit], _GAUGE_BASE[unit]), True
    return 1.0, _UI_ALIAS.get(unit, unit), False


def _pint_quantity(value: float, unit: str):
    if not isinstance(unit, str) or not unit.strip():
        raise UnknownUnitError(unit)
    scale, pint_unit, is_gauge = _resolve_unit(unit)
    try:
        q = _UREG.Quantity(value * scale, pint_unit)
    except (pint.errors.UndefinedUnitError, AttributeError, ValueError) as exc:
        raise UnknownUnitError(unit) from exc
    if is_gauge:
        q = q + _UREG.Quantity(_ATM_PA, "Pa").to(q.units)
    return q


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """
    Convert ``value`` from ``from_unit`` to ``to_unit``.

    Raises ``DimensionMismatchError`` on cross-dimension attempts and
    ``UnknownUnitError`` on unparseable unit strings.
    """
    q = _pint_quantity(value, from_unit)
    target_scale, target_unit, target_gauge = _resolve_unit(to_unit)

    try:
        target = q.to(target_unit)
    except pint.errors.DimensionalityError as exc:
        raise DimensionMismatchError(from_unit, to_unit) from exc
    except pint.errors.UndefinedUnitError as exc:
        raise UnknownUnitError(to_unit) from exc

    magnitude = float(target.magnitude)
    if target_gauge:
        magnitude -= float(_UREG.Quantity(_ATM_PA, "Pa").to(target_unit).magnitude)
    if target_scale != 1.0:
        magnitude /= target_scale
    return magnitude


def to_si(value: float, from_unit: str, dimension: Dimension | None = None) -> float:
    """Convert to the canonical SI unit for ``dimension``. If ``dimension``
    is None, infer from the source unit's pint dimensionality."""
    if dimension is None:
        # Infer by pint dimensionality.
        q = _pint_quantity(value, from_unit)
        dimension = _infer_dimension(q)
    return convert(value, from_unit, dimension.canonical_si or "")


def from_si(value: float, to_unit: str, dimension: Dimension | None = None) -> float:
    """Inverse of ``to_si``."""
    if dimension is None:
        q = _pint_quantity(value, to_unit)
        dimension = _infer_dimension(q)
    src_unit = dimension.canonical_si or ""
    return convert(value, src_unit, to_unit)


def _dim(pint_unit: str):
    """Return pint's parsed dimensionality object for a pint-canonical unit."""
    return _UREG.Quantity(1.0, pint_unit).dimensionality


# Map canonical-SI dimensionality objects to our Dimension enum. Using pint's
# parsed Dimensionality object avoids fragile string ordering across versions.
# Keys must be pint-canonical unit strings (not Jasper UI aliases).
_DIMENSIONALITY_LOOKUP: list[tuple[object, Dimension]] = [
    (_dim("K"), Dimension.TEMPERATURE),
    (_dim("Pa"), Dimension.PRESSURE),
    (_dim("mol/s"), Dimension.MOLAR_FLOW),
    (_dim("kg/s"), Dimension.MASS_FLOW),
    (_dim("meter**3/s"), Dimension.VOLUMETRIC_FLOW),
    (_dim("J"), Dimension.ENERGY),
    (_dim("W"), Dimension.POWER),
    (_dim("J/mol"), Dimension.MOLAR_ENTHALPY),
    (_dim("J/(mol*K)"), Dimension.MOLAR_ENTROPY),
    (_dim("kg/meter**3"), Dimension.DENSITY),
    (_dim("m"), Dimension.LENGTH),
    (_dim("meter**2"), Dimension.AREA),
    (_dim("meter**3"), Dimension.VOLUME),
    (_dim("s"), Dimension.TIME),
    (_dim("kg"), Dimension.MASS),
]


def _infer_dimension(q) -> Dimension:
    target = q.dimensionality
    if not target:
        return Dimension.DIMENSIONLESS
    for ref_dim, dim_enum in _DIMENSIONALITY_LOOKUP:
        if target == ref_dim:
            return dim_enum
    raise UnknownUnitError(str(q.units))


def known_units() -> Iterable[str]:
    """Return the UI-alias catalog keys — every unit Jasper officially supports."""
    return _UI_ALIAS.keys()
