"""
TEA coefficient catalog — single source of truth for every correlation.

Loads ``railway/tea-catalog.json`` at import-time (reference), validates
shape, exposes typed accessors. Frontend will eventually fetch the same
file via ``GET /api/tea/catalog`` so Python and TS never drift.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal, Optional

# Default catalog path — ``railway/tea-catalog.json`` (two levels up from this file).
_DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "tea-catalog.json"
)

SizeQuantity = Literal["power", "area", "volume", "length", "mass_flow"]


@dataclass(frozen=True)
class PressureRange:
    """One segment of a piecewise pressure-factor correlation."""

    lower: Optional[float]  # None means "no lower bound"
    upper: Optional[float]
    C: tuple[float, float, float]

    def contains(self, pressure: float) -> bool:
        if self.lower is not None and pressure < self.lower:
            return False
        if self.upper is not None and pressure > self.upper:
            return False
        return True


@dataclass(frozen=True)
class Subtype:
    """One equipment subtype (e.g. Pump/Centrifugal)."""

    name: str
    K: tuple[float, float, float]
    size_unit: str
    size_min: float
    size_max: float
    B1: float
    B2: float
    pressure_unit: str
    pressure_ranges: tuple[PressureRange, ...]
    F_bare: Optional[float] = None  # For reactors/heaters that use a single bare-module factor


@dataclass(frozen=True)
class EquipmentClass:
    """One equipment class (Pump, HeatExchanger, etc.)."""

    name: str
    size_quantity: SizeQuantity
    subtypes: dict[str, Subtype]
    # material_factors[material_name][subtype_name] -> Fm
    material_factors: dict[str, dict[str, float]]

    def subtype(self, name: str) -> Subtype:
        if name not in self.subtypes:
            raise KeyError(
                f"Unknown subtype {name!r} for equipment {self.name!r}. "
                f"Available: {sorted(self.subtypes)}"
            )
        return self.subtypes[name]

    def material_factor(self, material: str, subtype: str) -> float:
        if material not in self.material_factors:
            raise KeyError(
                f"Unknown material {material!r} for equipment {self.name!r}. "
                f"Available: {sorted(self.material_factors)}"
            )
        by_subtype = self.material_factors[material]
        if subtype not in by_subtype:
            raise KeyError(
                f"Material {material!r} is not tabulated for subtype "
                f"{subtype!r} of equipment {self.name!r}."
            )
        return by_subtype[subtype]


@dataclass(frozen=True)
class Catalog:
    """Top-level container loaded from ``tea-catalog.json``."""

    cepci_reference: float
    equipment: dict[str, EquipmentClass]

    def klass(self, name: str) -> EquipmentClass:
        if name not in self.equipment:
            raise KeyError(
                f"Unknown equipment class {name!r}. "
                f"Available: {sorted(self.equipment)}"
            )
        return self.equipment[name]

    def equipment_names(self) -> Iterable[str]:
        return self.equipment.keys()


# ── Parsing ──────────────────────────────────────────────────────────────────


def _parse_pressure_ranges(raw: list[dict]) -> tuple[PressureRange, ...]:
    out: list[PressureRange] = []
    for r in raw:
        bounds = r["bounds"]
        lower = bounds[0] if bounds[0] is not None else None
        upper = bounds[1] if bounds[1] is not None else None
        c0, c1, c2 = r["C"]
        out.append(PressureRange(lower=lower, upper=upper, C=(c0, c1, c2)))
    return tuple(out)


def _parse_subtype(name: str, raw: dict) -> Subtype:
    k1, k2, k3 = raw["K"]
    return Subtype(
        name=name,
        K=(k1, k2, k3),
        size_unit=raw["size_unit"],
        size_min=float(raw["size_min"]),
        size_max=float(raw["size_max"]),
        B1=float(raw["B1"]),
        B2=float(raw["B2"]),
        pressure_unit=raw["pressure_unit"],
        pressure_ranges=_parse_pressure_ranges(raw["pressure_ranges"]),
        F_bare=float(raw["F_bare"]) if "F_bare" in raw else None,
    )


def _parse_equipment(name: str, raw: dict) -> EquipmentClass:
    subtypes = {s_name: _parse_subtype(s_name, s_raw) for s_name, s_raw in raw["subtypes"].items()}
    return EquipmentClass(
        name=name,
        size_quantity=raw["size_quantity"],
        subtypes=subtypes,
        material_factors=raw["materials"],
    )


def load_catalog(path: Path | str | None = None) -> Catalog:
    """Parse ``tea-catalog.json`` and return a Catalog. Re-reads on every call."""
    path = Path(path) if path else _DEFAULT_CATALOG_PATH
    data = json.loads(path.read_text())
    equipment = {
        name: _parse_equipment(name, raw) for name, raw in data["equipment"].items()
    }
    return Catalog(
        cepci_reference=float(data["cepci_reference"]),
        equipment=equipment,
    )


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Process-lifetime cached catalog. Safe to call in hot paths."""
    return load_catalog()
