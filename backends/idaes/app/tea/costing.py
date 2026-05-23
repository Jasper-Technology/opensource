"""
Turton module-costing equations — pure functions, no I/O.

Hot-loop safe: no pint/Quantity instantiation, no catalog reads. Callers
fetch the Subtype from the catalog once and pass coefficients in.

Math reference (Turton, *Analysis, Synthesis and Design of Chemical
Processes*, 4th ed.):

    log10(Cp0) = K1 + K2 · log10(A) + K3 · log10(A)^2
    Cp = Cp0 · (CEPCI_now / CEPCI_ref)
    Fp = 10 ^ (C1 + C2 · log10(P) + C3 · log10(P)^2)
    C_BM = Cp · (B1 + B2 · Fm · Fp)                              (two-factor)
    C_BM = Cp · F_bare · Fm · Fp                                 (reactors/heaters)
    C_TM = C_BM · (1 + contingency)
"""
from __future__ import annotations
import math
import warnings
from dataclasses import dataclass
from typing import Optional

from .catalog import PressureRange, Subtype, EquipmentClass, get_catalog


class CostingError(ValueError):
    """Raised when a costing inputs violate contract (e.g. negative size)."""


class SizeOutOfRangeWarning(UserWarning):
    """Emitted when a size is outside the correlation's validity range."""


@dataclass(frozen=True)
class CostResult:
    """Output of a costing computation."""

    purchased: float       # Cp (USD, CEPCI-scaled)
    bare_module: float     # C_BM (USD)
    total_module: float    # C_TM (USD)
    Fp: float              # Pressure factor (dimensionless)
    Fm: float              # Material factor (dimensionless)
    cepci: float
    in_range: bool         # False if size was clipped to validity range
    range_note: str        # Human-readable validity status


def _check_size(size: float, subtype: Subtype) -> tuple[bool, str]:
    if size < subtype.size_min:
        return False, f"Size {size} {subtype.size_unit} below min {subtype.size_min}"
    if size > subtype.size_max:
        return False, f"Size {size} {subtype.size_unit} above max {subtype.size_max}"
    return True, "OK"


def _log10_cp0(size: float, subtype: Subtype) -> float:
    """Base purchased cost in USD at the catalog's reference CEPCI."""
    if size <= 0:
        raise CostingError(f"Size must be positive; got {size}")
    k1, k2, k3 = subtype.K
    log_s = math.log10(size)
    return 10 ** (k1 + k2 * log_s + k3 * (log_s ** 2))


def pressure_factor(pressure: float, subtype: Subtype) -> float:
    """
    Piecewise pressure factor. At or below the lowest range's upper bound,
    Fp = 1. Above the highest range, extrapolates with the top range's
    coefficients (matches Gilvan's behavior).
    """
    if pressure == 0.0:
        return 1.0

    ranges = subtype.pressure_ranges
    if not ranges:
        return 1.0

    def _eval(r: PressureRange) -> float:
        c1, c2, c3 = r.C
        if c1 == 0.0 and c2 == 0.0 and c3 == 0.0:
            return 1.0
        log_p = math.log10(pressure)
        return 10 ** (c1 + c2 * log_p + c3 * (log_p ** 2))

    for r in ranges:
        if r.contains(pressure):
            return _eval(r)

    # Out of every declared range → use nearest.
    sorted_ranges = sorted(
        ranges,
        key=lambda r: (r.upper if r.upper is not None else math.inf),
    )
    if pressure > (sorted_ranges[-1].upper or math.inf):
        return _eval(sorted_ranges[-1])
    return _eval(sorted_ranges[0])


def _resolve(
    equipment: str,
    subtype_name: str,
    material: str,
) -> tuple[EquipmentClass, Subtype, float]:
    klass = get_catalog().klass(equipment)
    subtype = klass.subtype(subtype_name)
    Fm = klass.material_factor(material, subtype_name)
    return klass, subtype, Fm


def purchased_cost(
    equipment: str,
    subtype: str,
    size: float,
    cepci: float,
    cepci_reference: Optional[float] = None,
) -> float:
    """Purchased cost ``Cp`` in USD, scaled to current CEPCI."""
    _, st, _ = _resolve(equipment, subtype, next(iter(get_catalog().klass(equipment).material_factors)))
    ok, msg = _check_size(size, st)
    if not ok:
        warnings.warn(msg, SizeOutOfRangeWarning, stacklevel=2)
    cp0 = _log10_cp0(size, st)
    ref = cepci_reference if cepci_reference is not None else get_catalog().cepci_reference
    return cp0 * (cepci / ref)


def _bm_factor(st: Subtype, Fm: float, Fp: float) -> float:
    """F_BM — the bare-module factor. Two-factor for most, single for reactors/heaters."""
    if st.F_bare is not None:
        # Reactors/heaters: C_BM = Cp · F_bare (material-independent in Turton)
        # Keep Fm/Fp folded in for consistency with other classes — reactors
        # default Fm=1, Fp=1 in catalog so this reduces to F_bare.
        return st.F_bare * Fm * Fp
    return st.B1 + st.B2 * Fm * Fp


def bare_module_cost(
    equipment: str,
    subtype: str,
    material: str,
    size: float,
    pressure: float = 0.0,
    cepci: float = 800.0,
    cepci_reference: Optional[float] = None,
) -> CostResult:
    """
    Bare-module cost ``C_BM`` in USD. Includes direct + indirect costs.
    ``pressure`` must be in the subtype's ``pressure_unit`` (usually barg).
    """
    klass, st, Fm = _resolve(equipment, subtype, material)
    ok, msg = _check_size(size, st)
    if not ok:
        warnings.warn(msg, SizeOutOfRangeWarning, stacklevel=2)

    cp0 = _log10_cp0(size, st)
    ref = cepci_reference if cepci_reference is not None else get_catalog().cepci_reference
    cp = cp0 * (cepci / ref)
    Fp = pressure_factor(pressure, st)
    F_bm = _bm_factor(st, Fm, Fp)
    c_bm = cp * F_bm
    c_tm = c_bm  # downstream layer applies contingency separately

    return CostResult(
        purchased=cp,
        bare_module=c_bm,
        total_module=c_tm,
        Fp=Fp,
        Fm=Fm,
        cepci=cepci,
        in_range=ok,
        range_note=msg,
    )


def total_module_cost(
    equipment: str,
    subtype: str,
    material: str,
    size: float,
    pressure: float = 0.0,
    cepci: float = 800.0,
    contingency: float = 0.18,
    cepci_reference: Optional[float] = None,
) -> CostResult:
    """
    Total-module cost ``C_TM`` in USD.

        C_TM = C_BM · (1 + contingency)

    Default contingency 18% (Turton recommendation: 15–18% for grassroots).
    """
    if contingency < 0:
        raise CostingError(f"contingency must be non-negative; got {contingency}")

    result = bare_module_cost(
        equipment=equipment,
        subtype=subtype,
        material=material,
        size=size,
        pressure=pressure,
        cepci=cepci,
        cepci_reference=cepci_reference,
    )
    return CostResult(
        purchased=result.purchased,
        bare_module=result.bare_module,
        total_module=result.bare_module * (1 + contingency),
        Fp=result.Fp,
        Fm=result.Fm,
        cepci=result.cepci,
        in_range=result.in_range,
        range_note=result.range_note,
    )
