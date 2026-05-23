"""
Quantity — value + unit + dimension triple.

Used as a schema field type on ``StreamResult`` / ``UnitResult`` /
``EconomicConfig``. Construction validates dimension; conversion helpers
round-trip through the canonical SI magnitude.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Self

from .dimensions import Dimension
from .converters import convert, to_si, from_si


@dataclass(frozen=True)
class Quantity:
    """
    A dimensional value.

    - ``value`` is stored in the ``unit`` provided at construction.
    - ``dimension`` is validated against the unit.
    - ``si_value`` returns the magnitude in canonical SI.
    - ``as_unit(u)`` returns a new Quantity in ``u`` (same dimension).
    """

    value: float
    unit: str
    dimension: Dimension = field(default=Dimension.DIMENSIONLESS)

    def __post_init__(self) -> None:
        # Validate: the unit must be compatible with the declared dimension.
        # Cheapest check: round-trip to SI — if that throws, dimension is wrong.
        if self.dimension is Dimension.DIMENSIONLESS:
            return
        try:
            _ = to_si(self.value, self.unit, self.dimension)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"Unit {self.unit!r} does not match dimension {self.dimension.value!r}: {exc}"
            ) from exc

    @property
    def si_value(self) -> float:
        if self.dimension is Dimension.DIMENSIONLESS:
            return self.value
        return to_si(self.value, self.unit, self.dimension)

    def as_unit(self, unit: str) -> Self:
        if self.dimension is Dimension.DIMENSIONLESS:
            return type(self)(value=self.value, unit=unit, dimension=self.dimension)
        new_value = convert(self.value, self.unit, unit)
        return type(self)(value=new_value, unit=unit, dimension=self.dimension)

    @classmethod
    def from_si(cls, si_value: float, display_unit: str, dimension: Dimension) -> Self:
        v = from_si(si_value, display_unit, dimension)
        return cls(value=v, unit=display_unit, dimension=dimension)
