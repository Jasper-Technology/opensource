"""
Cost math — pure functions, no I/O. Callers fetch coefficients from the DB
(see repository.py) and pass them in.

Two functional forms are supported (the seed families differ):

  turton_log10:  Cp0 = 10^(K1 + K2·log10 S + K3·log10²S)        [USD @ base index]
                 Fp  = 10^(C1 + C2·log10 P + C3·log10²P)         [piecewise; 1 at low P]
                 C_BM = Cp·(B1 + B2·Fm·Fp)                        [two-factor]
                 C_BM = Cp·F_bare·Fm·Fp                           [reactors/heaters]

  sslw_ln:       base = exp(a1 + a2·ln S + a3·ln²S)              [USD @ base index]
                 Fp   = c0 + c1·(P/ref) + c2·(P/ref)²            [quadratic ratio, psig]
                 purchased = Fm·Fp·base                           [SSLW "capital"]
                 C_BM = purchased · F_install                     [G7: put on bare-module basis]

For both:  Cp   = Cp_base · (index_now / base_index_value)        [escalation]
           C_TM = C_BM · (1 + contingency)

Accuracy class is AACE Class 4-5 (±30-40%) and is surfaced on every result.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Optional

ACCURACY_CLASS = "AACE Class 4-5 (+/-30-40%)"


class CostingError(ValueError):
    """Inputs violate contract (e.g. non-positive size)."""


class SizeOutOfRangeWarning(UserWarning):
    """Size outside the correlation's validity range."""


@dataclass(frozen=True)
class CostInputs:
    functional_form: str
    coeff: dict[str, Any]
    base_index_value: float
    Fm: float
    size: float
    index_now: float
    contingency: float
    pressure: float = 0.0
    bare_module: Optional[dict[str, Any]] = None
    pressure_model: Optional[dict[str, Any]] = None
    size_min: Optional[float] = None
    size_max: Optional[float] = None
    # G7: default purchased->bare-module factor for sslw rows lacking F_install.
    sslw_install_factor_default: float = 2.19


@dataclass(frozen=True)
class CostResult:
    purchased: float        # Cp, escalated
    bare_module: float      # C_BM
    total_module: float     # C_TM
    Fp: float
    Fm: float
    functional_form: str
    accuracy_class: str
    basis_note: str
    in_range: bool
    range_note: str


def _check_size(inp: CostInputs) -> tuple[bool, str]:
    if inp.size <= 0:
        raise CostingError(f"size must be positive; got {inp.size}")
    if inp.size_min is not None and inp.size < inp.size_min:
        return False, f"size {inp.size} below min {inp.size_min}"
    if inp.size_max is not None and inp.size > inp.size_max:
        return False, f"size {inp.size} above max {inp.size_max}"
    return True, "OK"


def _turton_pressure_factor(pressure: float, model: Optional[dict[str, Any]]) -> float:
    if pressure == 0.0 or not model:
        return 1.0
    ranges = model.get("ranges") or []

    def _eval(c: list[float]) -> float:
        c1, c2, c3 = c
        if c1 == 0.0 and c2 == 0.0 and c3 == 0.0:
            return 1.0
        log_p = math.log10(pressure)
        return 10 ** (c1 + c2 * log_p + c3 * log_p ** 2)

    for r in ranges:
        lo, hi = r["bounds"]
        lo = -math.inf if lo is None else lo
        hi = math.inf if hi is None else hi
        if lo < pressure <= hi:
            return _eval(r["C"])
    # Outside every band → nearest by upper bound.
    ordered = sorted(ranges, key=lambda r: (r["bounds"][1] if r["bounds"][1] is not None else math.inf))
    return _eval(ordered[-1]["C"]) if pressure > 0 else _eval(ordered[0]["C"])


def _sslw_pressure_factor(pressure: float, model: Optional[dict[str, Any]]) -> float:
    if not model or model.get("form") != "sslw_quadratic_ratio":
        return 1.0
    ref = model["ref"]
    c0, c1, c2 = model["coeff"]
    r = pressure / ref
    return c0 + c1 * r + c2 * r ** 2


def cost_trays(
    diameter_ft: float,
    n_trays: int,
    tray_type: str,
    tray_material: str,
    coeff: dict[str, Any],
    index_now: float,
    base_index_value: float,
) -> float:
    """
    SSLW distillation-tray cost (installed, USD at index_now). coeff carries the
    SSLW constants:
      base_per_tray = tray_base[0] * exp(tray_base[1] * D_ft)
      N_factor      = max(1, number_factor[0] / number_factor[1]^N)
      Ftm           = material_factors[mat][0] + material_factors[mat][1] * D_ft
      trays         = N * N_factor * type_factor * Ftm * base_per_tray
      installed     = trays * (index_now/base) * install_factor
    """
    if n_trays <= 0 or diameter_ft <= 0:
        raise CostingError("trays need positive diameter and count")
    tb0, tb1 = coeff["tray_base"]
    nf0, nf1 = coeff["number_factor"]
    type_factor = coeff["type_factors"][tray_type]
    a1, a2 = coeff["material_factors"][tray_material]
    install = coeff.get("install_factor", 1.4)

    base_per_tray = tb0 * math.exp(tb1 * diameter_ft)
    n_factor = max(1.0, nf0 / (nf1 ** n_trays))
    ftm = a1 + a2 * diameter_ft
    trays = n_trays * n_factor * type_factor * ftm * base_per_tray
    return trays * (index_now / base_index_value) * install


_M3_TO_IN3 = 61023.74
_M3S_TO_GPM = 15850.32
_M_TO_FT = 3.280840


def sslw_vessel_base(volume_m3: float, coeff: dict[str, Any]) -> float:
    """
    SSLW vessel base cost (USD @ CE500) from VOLUME, via geometry → weight:
      volume → D,L (assumed aspect ratio L/D) → weight (shell) → exp(poly).
    Reconciles SSLW's weight basis with Turton's volume basis for blending.
    coeff: {alpha:[a1,a2,a3], aspect_ratio, thickness_in, density}
    """
    if volume_m3 <= 0:
        raise CostingError("vessel volume must be positive")
    r = coeff.get("aspect_ratio", 4.0)
    t = coeff.get("thickness_in", 1.25)
    density = coeff.get("density", 0.284)  # carbon steel lb/in^3
    a1, a2, a3 = coeff["alpha"]
    v_in3 = volume_m3 * _M3_TO_IN3
    d_in = (4.0 * v_in3 / (math.pi * r)) ** (1.0 / 3.0)
    l_in = r * d_in
    weight = math.pi * (d_in + t) * (l_in + 0.8 * d_in) * t * density
    lw = math.log(weight)
    return math.exp(a1 + a2 * lw + a3 * lw ** 2)


def sslw_pump_base(power_kw: float, coeff: dict[str, Any]) -> float:
    """
    SSLW pump base cost (USD @ CE394, pump less motor) from POWER, via an assumed
    head: power → Q (P = ρgQH/η) → size factor S = Q[gpm]·√(H[ft]) → exp(poly).
    The head assumption makes this an approximate cross-basis comparison.
    coeff: {alpha:[a1,a2,a3], head_m, efficiency}
    """
    if power_kw <= 0:
        raise CostingError("pump power must be positive")
    head_m = coeff.get("head_m", 50.0)
    eta = coeff.get("efficiency", 0.7)
    a1, a2, a3 = coeff["alpha"]
    q_m3s = power_kw * 1000.0 * eta / (1000.0 * 9.81 * head_m)
    s = (q_m3s * _M3S_TO_GPM) * (head_m * _M_TO_FT) ** 0.5
    ls = math.log(s)
    return math.exp(a1 + a2 * ls + a3 * ls ** 2)


def cost_packing(
    diameter_m: float,
    packed_height_m: float,
    packing_type: str,
    packing_material: str,
    coeff: dict[str, Any],
    index_now: float,
    base_index_value: float,
) -> float:
    """
    Packed-column internals cost (installed, USD @ index_now) — an alternative to
    trays. Packing volume x unit cost x material factor, plus a liquid-distributor
    allowance, escalated and installed.
      coeff: {unit_cost:{Random,Structured}, material_factors:{...},
              distributor_frac, install_factor}
    """
    if diameter_m <= 0 or packed_height_m <= 0:
        raise CostingError("packing needs positive diameter and height")
    volume = math.pi / 4.0 * diameter_m ** 2 * packed_height_m
    unit = coeff["unit_cost"][packing_type]              # USD/m^3 at base index
    mat = coeff.get("material_factors", {}).get(packing_material, 1.0)
    distributor = coeff.get("distributor_frac", 0.15)
    install = coeff.get("install_factor", 1.4)
    packing = volume * unit * mat
    return packing * (1.0 + distributor) * (index_now / base_index_value) * install


def compute_cost(inp: CostInputs) -> CostResult:
    in_range, range_note = _check_size(inp)
    if not in_range:
        warnings.warn(range_note, SizeOutOfRangeWarning, stacklevel=2)

    escal = inp.index_now / inp.base_index_value

    if inp.functional_form == "turton_log10":
        k1, k2, k3 = inp.coeff["K"]
        log_s = math.log10(inp.size)
        cp0 = 10 ** (k1 + k2 * log_s + k3 * log_s ** 2)
        cp = cp0 * escal
        fp = _turton_pressure_factor(inp.pressure, inp.pressure_model)
        bm = inp.bare_module or {}
        if "F_bare" in bm and bm["F_bare"] is not None:
            c_bm = cp * bm["F_bare"] * inp.Fm * fp
            basis = "Turton single-factor (F_bare)"
        else:
            c_bm = cp * (bm["B1"] + bm["B2"] * inp.Fm * fp)
            basis = "Turton two-factor bare-module"

    elif inp.functional_form == "sslw_ln":
        a1, a2, a3 = inp.coeff["alpha"]
        # input_scale folds in fixed multipliers (e.g. SSLW HX oversize 1.1).
        ln_s = math.log(inp.size * inp.coeff.get("input_scale", 1.0))
        base = math.exp(a1 + a2 * ln_s + a3 * ln_s ** 2)
        cp = base * escal
        fp = _sslw_pressure_factor(inp.pressure, inp.pressure_model)
        purchased_w_factors = inp.Fm * fp * cp
        bm = inp.bare_module or {}
        f_install = bm.get("F_install", inp.sslw_install_factor_default)
        c_bm = purchased_w_factors * f_install
        basis = (
            f"SSLW purchased x F_install={f_install} -> bare-module basis (G7)"
        )

    elif inp.functional_form in ("sslw_vessel", "sslw_pump"):
        if inp.functional_form == "sslw_vessel":
            base = sslw_vessel_base(inp.size, inp.coeff)
            label = "SSLW vessel (volume->geometry->weight)"
        else:
            base = sslw_pump_base(inp.size, inp.coeff)
            label = "SSLW pump (power->size-factor, assumed head)"
        cp = base * escal
        fp = 1.0
        bm = inp.bare_module or {}
        f_install = bm.get("F_install", inp.sslw_install_factor_default)
        c_bm = inp.Fm * cp * f_install
        basis = f"{label} x F_install={f_install} -> bare-module (G7)"

    else:
        raise CostingError(f"unknown functional_form: {inp.functional_form}")

    c_tm = c_bm * (1 + inp.contingency)
    return CostResult(
        purchased=cp,
        bare_module=c_bm,
        total_module=c_tm,
        Fp=fp,
        Fm=inp.Fm,
        functional_form=inp.functional_form,
        accuracy_class=ACCURACY_CLASS,
        basis_note=basis,
        in_range=in_range,
        range_note=range_note,
    )
