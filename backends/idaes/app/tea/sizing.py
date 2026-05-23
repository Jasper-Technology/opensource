"""
Algebraic equipment sizing from imported stream data.

No solver, no property calls. Input is the stream table + block duties
Jasper already receives from an import parser. Output is
``(equipment_class, subtype, size, pressure)`` tuples that feed directly
into ``costing.total_module_cost``.

Design rules:
- Inputs assumed in canonical SI (K, Pa, W, mol/s, kg/s, m3/s). Convert at
  ingest; this module never parses unit strings.
- Every public function is pure. Heat-transfer coefficients, residence
  times, and other rules-of-thumb live in ``DEFAULTS`` so they can be
  overridden per project without touching the math.
- Size bounds are NOT clipped here — correlations enforce their own
  validity range and emit ``SizeOutOfRangeWarning`` downstream.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

from .catalog import get_catalog


# ── Rule-of-thumb defaults ──────────────────────────────────────────────────


@dataclass(frozen=True)
class SizingDefaults:
    """Heat-transfer coefficients and residence times (tunable per project)."""

    # Overall U for shell-tube HX — Turton Table 11.11 (liquid/liquid range)
    U_default: float = 500.0  # W/(m² K)
    # Minimum LMTD to avoid pinch singularities
    LMTD_floor: float = 5.0  # K
    # Minimum approach temperature for utility-side HX
    approach_min: float = 10.0  # K
    # Reactor residence times by subtype (seconds)
    residence_time_cstr: float = 3600.0  # 1 hr
    residence_time_pfr: float = 1800.0   # 30 min
    # Flash residence time (5 min liquid) — Turton rule of thumb
    flash_residence: float = 300.0
    flash_liquid_holdup: float = 0.5
    # Rough MW + density for volumetric-flow estimation when imported
    # streams don't carry density directly.
    fallback_mw: float = 50.0      # kg/kmol
    fallback_density: float = 800.0  # kg/m3
    # Minimum equipment sizes — below these, correlations go nonsensical.
    hx_area_min: float = 1.0        # m²
    pump_power_min: float = 0.1     # kW
    compressor_power_min: float = 1.0  # kW
    vessel_volume_min: float = 0.1  # m³


DEFAULTS = SizingDefaults()


# ── Stream / block input shapes ─────────────────────────────────────────────


@dataclass(frozen=True)
class Stream:
    """Minimum stream data needed for sizing. All SI."""

    T: float              # K
    P: float              # Pa (absolute)
    flow_mol: float       # mol/s
    flow_mass: Optional[float] = None  # kg/s; if absent, derived from flow_mol*MW
    density: Optional[float] = None    # kg/m³; fallback to DEFAULTS.fallback_density
    molecular_weight: Optional[float] = None  # g/mol
    vapor_fraction: Optional[float] = None
    composition: dict[str, float] = field(default_factory=dict)  # component → mole fraction

    def mass_flow(self) -> float:
        if self.flow_mass is not None:
            return self.flow_mass
        mw_g = self.molecular_weight or self._mw_from_composition() or DEFAULTS.fallback_mw
        # mol/s * g/mol / 1000 = kg/s
        return self.flow_mol * mw_g / 1000.0

    def volumetric_flow(self) -> float:
        rho = self.density or self._density_from_composition() or DEFAULTS.fallback_density
        return self.mass_flow() / rho  # m³/s

    # ── Registry-backed property estimators ──────────────────────────────────
    # When stream composition is populated, look up MW and liquid density
    # from the curated component registry and compute a mole-fraction-
    # weighted mean. Falls back to None when no components match the
    # registry — caller then uses DEFAULTS.

    def _mw_from_composition(self) -> Optional[float]:
        if not self.composition:
            return None
        from app.components_registry import get_default_registry

        reg = get_default_registry()
        total_frac = 0.0
        mw_sum = 0.0
        for name, frac in self.composition.items():
            c = reg.lookup(name)
            if c is None:
                continue
            mw_sum += c.mw * frac
            total_frac += frac
        if total_frac < 0.5:
            # Less than 50% of the composition was recognised — don't trust it
            return None
        return mw_sum / total_frac

    def _density_from_composition(self) -> Optional[float]:
        if not self.composition:
            return None
        from app.components_registry import get_default_registry

        reg = get_default_registry()
        total_frac = 0.0
        rho_sum = 0.0
        for name, frac in self.composition.items():
            c = reg.lookup(name)
            if c is None or c.density is None:
                continue
            rho_sum += c.density * frac
            total_frac += frac
        if total_frac < 0.5:
            return None
        return rho_sum / total_frac


@dataclass(frozen=True)
class BlockInput:
    """A unit operation with enough context to size its equipment."""

    block_type: str                   # Jasper unit type string (Heater, Pump, etc.)
    duty: Optional[float] = None      # W (positive = heating, negative = cooling)
    work: Optional[float] = None      # W (pump/compressor shaft power)
    pressure_drop: Optional[float] = None  # Pa
    inlet: Optional[Stream] = None
    outlet: Optional[Stream] = None


@dataclass(frozen=True)
class SizingResult:
    equipment_class: str
    subtype: str
    size: float
    size_unit: str
    pressure_barg: float
    note: str


# ── Sizing primitives ──────────────────────────────────────────────────────


def lmtd(Th_in: float, Th_out: float, Tc_in: float, Tc_out: float, floor: float = DEFAULTS.LMTD_floor) -> float:
    """
    Log-mean temperature difference for a countercurrent exchanger.

    Uses arithmetic mean when the two endpoints are within 0.1 K. Floors at
    ``floor`` to prevent pinch singularities.
    """
    dT1 = Th_in - Tc_out
    dT2 = Th_out - Tc_in
    if abs(dT1 - dT2) < 0.1:
        mean = (dT1 + dT2) / 2
    elif dT1 <= 0 or dT2 <= 0:
        mean = floor
    else:
        mean = (dT1 - dT2) / math.log(dT1 / dT2)
    return max(mean, floor)


def heat_exchanger_area(duty_w: float, lmtd_k: float, u: float = DEFAULTS.U_default) -> float:
    """``A = Q / (U · ΔT_lm)`` in m²."""
    if lmtd_k <= 0:
        raise ValueError(f"lmtd must be positive; got {lmtd_k}")
    return abs(duty_w) / (u * lmtd_k)


def utility_endpoints(block_type: str, inlet_T: float, outlet_T: float) -> tuple[float, float, float, float]:
    """
    Infer utility-side temperatures when an HX is sized against a utility.

    Heater (positive duty): steam side at ~180°C condensing.
    Cooler (negative duty): cooling water 25→35°C.
    HeatExchanger with two process streams: caller should use their own
    Th/Tc — this helper is only for heater/cooler shortcut.
    """
    if block_type in ("Heater",):
        Th_in = Th_out = 453.15  # 180°C
        Tc_in = inlet_T
        Tc_out = outlet_T
    else:  # Cooler
        Th_in = inlet_T
        Th_out = outlet_T
        Tc_in = 298.15  # 25°C
        Tc_out = 308.15  # 35°C
    return Th_in, Th_out, Tc_in, Tc_out


# ── Block dispatchers ──────────────────────────────────────────────────────


def _infer_sensible_duty(inlet: Stream, outlet: Stream) -> Optional[float]:
    """Rough sensible-heat duty: Q = ṁ · Cp · ΔT.

    Cp defaults: 4180 J/(kg·K) for liquids, 1000 for vapour, 2200 otherwise.
    Returns None when we don't have enough temperature info.
    """
    if inlet.T <= 0 or outlet.T <= 0:
        return None
    dT = outlet.T - inlet.T
    if abs(dT) < 0.1:
        return None
    vf = inlet.vapor_fraction if inlet.vapor_fraction is not None else 0.0
    if vf >= 0.9:
        cp = 1000.0
    elif vf <= 0.1:
        cp = 4180.0
    else:
        cp = 2200.0
    try:
        m_dot = inlet.mass_flow()
    except Exception:  # noqa: BLE001
        return None
    if m_dot <= 0:
        return None
    return m_dot * cp * dT


def size_heater_cooler(block: BlockInput) -> SizingResult:
    """Heater/Cooler → shell-tube HX area from duty + utility approach."""
    if block.inlet is None or block.outlet is None:
        raise ValueError(f"{block.block_type} requires inlet + outlet streams")
    duty = block.duty
    inferred_note = ""
    if duty is None:
        duty = _infer_sensible_duty(block.inlet, block.outlet)
        if duty is None:
            raise ValueError(
                f"{block.block_type} requires duty, or inlet+outlet streams with temperatures"
            )
        inferred_note = " | duty inferred from ṁ·Cp·ΔT"
    Th_in, Th_out, Tc_in, Tc_out = utility_endpoints(
        block.block_type, block.inlet.T, block.outlet.T
    )
    dt = lmtd(Th_in, Th_out, Tc_in, Tc_out)
    area = max(heat_exchanger_area(duty, dt), DEFAULTS.hx_area_min)
    return SizingResult(
        equipment_class="HeatExchanger",
        subtype="FloatingHead",  # default shell-tube — users override in inspector
        size=area,
        size_unit="m2",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"LMTD {dt:.1f} K{inferred_note}",
    )


def size_heat_exchanger(block: BlockInput) -> SizingResult:
    """Two-process-stream HX.

    Preferred inputs: explicit ``duty`` plus hot-in/hot-out temperatures on
    ``inlet`` (hot side) and cold-in/cold-out on ``outlet`` (cold side).

    Fallbacks, in order:
    1. Both sides known → duty from cold-side sensible ΔT; LMTD countercurrent.
    2. Only one side known → fall back to the utility-approach heater model
       so we still get a reasonable area.
    """
    if block.inlet is None or block.outlet is None:
        raise ValueError(
            "HeatExchanger requires both hot (inlet) and cold (outlet) streams, "
            "or an explicit duty with one side"
        )

    duty = block.duty
    note_extra = ""
    if duty is None:
        duty = _infer_sensible_duty(block.inlet, block.outlet)
        if duty is None:
            # Last-ditch: treat as utility HX.
            return size_heater_cooler(block)
        note_extra = " | duty inferred from ṁ·Cp·ΔT"

    # If both sides look process-temperatures (non-default), use a real LMTD.
    dt = lmtd(block.inlet.T, block.outlet.T, block.outlet.T - 10, block.inlet.T - 10)
    area = max(heat_exchanger_area(abs(duty), dt), DEFAULTS.hx_area_min)
    return SizingResult(
        equipment_class="HeatExchanger",
        subtype="FloatingHead",
        size=area,
        size_unit="m2",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"LMTD {dt:.1f} K{note_extra}",
    )


def _infer_pump_work(block: BlockInput) -> Optional[float]:
    """Hydraulic work estimate when ``work`` wasn't provided.

    W = V̇ · ΔP / η_pump, using a typical pump efficiency of 0.7.
    Requires an inlet stream (for V̇) plus either a pressure_drop or an
    outlet pressure to compute ΔP.
    """
    if block.inlet is None:
        return None
    if block.pressure_drop is not None:
        dp = abs(block.pressure_drop)
    elif block.outlet is not None and block.outlet.P and block.inlet.P:
        dp = abs(block.outlet.P - block.inlet.P)
    else:
        return None
    if dp <= 0:
        return None
    v_dot = block.inlet.volumetric_flow()
    eta = 0.7
    return (v_dot * dp) / eta  # W


def _infer_compressor_work(block: BlockInput) -> Optional[float]:
    """Polytropic work for an ideal-gas compressor.

    W ≈ n · (k/(k-1)) · R · T_in · [(P2/P1)^((k-1)/k) - 1] / η
    with k=1.4 (diatomic default) and η=0.75.
    """
    if block.inlet is None or block.inlet.T <= 0 or block.inlet.P <= 0:
        return None
    if block.outlet is not None and block.outlet.P:
        p_out = block.outlet.P
    elif block.pressure_drop is not None:
        p_out = block.inlet.P + abs(block.pressure_drop)
    else:
        return None
    if p_out <= block.inlet.P:
        return None
    k = 1.4
    R = 8.314
    eta = 0.75
    ratio = p_out / block.inlet.P
    return (
        block.inlet.flow_mol
        * (k / (k - 1))
        * R
        * block.inlet.T
        * (ratio ** ((k - 1) / k) - 1.0)
        / eta
    )


def size_pump(block: BlockInput) -> SizingResult:
    work = block.work if block.work is not None else _infer_pump_work(block)
    if work is None:
        raise ValueError(
            "Pump requires either work or (inlet stream + pressure_drop / outlet pressure)"
        )
    power_kw = max(abs(work) / 1000.0, DEFAULTS.pump_power_min)
    discharge = block.outlet.P if block.outlet else (block.inlet.P if block.inlet else 1e5)
    note = "" if block.work is not None else "work inferred from ΔP × V̇ / η"
    return SizingResult(
        equipment_class="Pump",
        subtype="Centrifugal",
        size=power_kw,
        size_unit="kW",
        pressure_barg=_to_barg(discharge),
        note=note,
    )


def size_compressor(block: BlockInput) -> SizingResult:
    work = block.work if block.work is not None else _infer_compressor_work(block)
    if work is None:
        raise ValueError(
            "Compressor requires either work or (inlet stream + outlet pressure / pressure_drop)"
        )
    power_kw = max(abs(work) / 1000.0, DEFAULTS.compressor_power_min)
    discharge = block.outlet.P if block.outlet else (block.inlet.P if block.inlet else 1e5)
    note = "" if block.work is not None else "work inferred from polytropic compression"
    return SizingResult(
        equipment_class="Compressor",
        subtype="Centrifugal",
        size=power_kw,
        size_unit="kW",
        pressure_barg=_to_barg(discharge),
        note=note,
    )


def size_flash(block: BlockInput) -> SizingResult:
    if block.inlet is None:
        raise ValueError("Flash requires inlet stream")
    liquid_v = block.inlet.volumetric_flow() * DEFAULTS.flash_residence  # m³
    volume = max(liquid_v / DEFAULTS.flash_liquid_holdup, DEFAULTS.vessel_volume_min)
    return SizingResult(
        equipment_class="Vessel",
        subtype="Vertical",
        size=volume,
        size_unit="m3",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"{DEFAULTS.flash_residence/60:.0f}-min residence",
    )


def size_reactor(block: BlockInput, residence_time_s: Optional[float] = None) -> SizingResult:
    if block.inlet is None:
        raise ValueError("Reactor requires inlet stream")
    tau = residence_time_s if residence_time_s is not None else DEFAULTS.residence_time_cstr
    volume = max(block.inlet.volumetric_flow() * tau, 1.0)
    return SizingResult(
        equipment_class="Reactor",
        subtype="JacketedAgitated",
        size=volume,
        size_unit="m3",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"{tau/60:.0f}-min residence",
    )


def size_column(block: BlockInput) -> SizingResult:
    """Distillation column — volume-based rough sizing (Turton Ch.15 Sec 2)."""
    if block.inlet is None:
        raise ValueError("DistillationColumn requires inlet stream")
    # Rough estimate: 2 m diameter × 10 m tray stack = 31 m³
    volume = max(math.pi * 1.0 ** 2 * 10.0, DEFAULTS.vessel_volume_min)
    return SizingResult(
        equipment_class="Vessel",
        subtype="Vertical",
        size=volume,
        size_unit="m3",
        pressure_barg=_to_barg(block.inlet.P),
        note="rough volume; R2 will size from vapor velocity + stages",
    )


def size_tank(block: BlockInput) -> SizingResult:
    if block.inlet is None:
        raise ValueError("Tank requires inlet stream")
    # 1-day inventory at inlet volumetric flow
    volume = max(block.inlet.volumetric_flow() * 86400, 90.0)
    return SizingResult(
        equipment_class="Tank",
        subtype="APIFixedRoof",
        size=volume,
        size_unit="m3",
        pressure_barg=_to_barg(block.inlet.P),
        note="1-day inventory",
    )


# ── Main dispatch ──────────────────────────────────────────────────────────


def size(block: BlockInput) -> Optional[SizingResult]:
    """
    Size a single block. Returns ``None`` for no-cost unit ops (Feed, Sink,
    Mixer, Splitter, Valve). Raises ``ValueError`` when required data is
    missing.
    """
    t = block.block_type
    if t in ("Feed", "Sink", "Mixer", "Splitter", "Valve", "Product", "TextBox"):
        return None
    if t in ("Heater", "Cooler"):
        return size_heater_cooler(block)
    if t == "HeatExchanger":
        return size_heat_exchanger(block)
    if t == "Pump":
        return size_pump(block)
    if t == "Compressor":
        return size_compressor(block)
    if t == "Flash":
        return size_flash(block)
    if t in ("Reactor", "RCSTR", "RPfr", "REquil", "RGibbs", "RStoic"):
        return size_reactor(block)
    if t in ("DistillationColumn", "Absorber", "Stripper"):
        return size_column(block)
    if t == "Tank":
        return size_tank(block)
    if t in ("Centrifuge", "Filter", "Dryer", "Evaporator"):
        return _size_area_based(block, t)
    if t == "Fan":
        return _size_fan(block)
    if t == "Electrolyzer":
        return _size_electrolyzer(block)
    if t == "Membrane":
        return _size_membrane(block)
    if t == "PSA":
        return _size_psa(block)
    if t == "Crystallizer":
        return _size_crystallizer(block)
    if t == "SprayDryer":
        return _size_spray_dryer(block)
    # Unknown — return None so caller skips costing.
    return None


def cost_ready(block: BlockInput) -> tuple[str, str, float, float]:
    """
    Convenience shim — size the block and expand the tuple a costing
    function wants: (equipment_class, subtype, size, pressure_barg).
    Validates the subtype exists in the catalog.
    """
    result = size(block)
    if result is None:
        raise ValueError(f"Block type {block.block_type!r} is not sizeable")
    # Sanity check against catalog
    klass = get_catalog().klass(result.equipment_class)
    klass.subtype(result.subtype)
    return result.equipment_class, result.subtype, result.size, result.pressure_barg


# ── Helpers ────────────────────────────────────────────────────────────────


def _to_barg(pressure_pa: float) -> float:
    """Convert absolute Pa → barg. Clamps at 0 since our catalog rejects negative."""
    return max(0.0, pressure_pa / 1e5 - 1.01325)


# ── Area-based units (Centrifuge / Filter / Dryer / Evaporator) ─────────────

_AREA_DEFAULT_SUBTYPE: dict[str, str] = {
    "Centrifuge": "Belt",
    "Filter": "Drum",
    "Dryer": "Rotary",
    "Evaporator": "ForcedCirculation",
}

# Rule-of-thumb specific capacity for area-based separation equipment.
# Values from Turton Ch.22 ranges; conservative defaults suitable for R1.
_AREA_PER_KGPS: dict[str, float] = {
    "Centrifuge": 0.5,   # m² per kg/s feed
    "Filter": 2.0,       # m² per kg/s feed (typical cake filter)
    "Dryer": 3.0,        # m² per kg/s wet feed
    "Evaporator": 10.0,  # m² per kg/s evaporation rate (liquid-dominant)
}


def _size_area_based(block: BlockInput, block_type: str) -> SizingResult:
    """
    Shared sizing for separation/drying units that the catalog stores by
    area (m²). All four (Centrifuge, Filter, Dryer, Evaporator) size from
    inlet mass flow × a specific-capacity rule of thumb.
    """
    if block.inlet is None:
        raise ValueError(f"{block_type} requires inlet stream")
    mass_flow = block.inlet.mass_flow()  # kg/s
    capacity = _AREA_PER_KGPS[block_type]
    area = max(mass_flow * capacity, DEFAULTS.hx_area_min)
    return SizingResult(
        equipment_class=block_type,
        subtype=_AREA_DEFAULT_SUBTYPE[block_type],
        size=area,
        size_unit="m2",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"{capacity:.1f} m²/(kg/s) rule of thumb",
    )


def _size_fan(block: BlockInput) -> SizingResult:
    """Fan sizing — volumetric flow in m³/s at inlet conditions."""
    if block.inlet is None:
        raise ValueError("Fan requires inlet stream")
    vol_flow = max(block.inlet.volumetric_flow(), 0.1)  # m³/s
    return SizingResult(
        equipment_class="Fan",
        subtype="CentrifugalRadial",
        size=vol_flow,
        size_unit="m3/s",
        pressure_barg=_to_barg(block.inlet.P),
        note="inlet volumetric flow",
    )


def _size_electrolyzer(block: BlockInput) -> SizingResult:
    """Electrolyzer — sized by stack power (kW)."""
    if block.work is None:
        raise ValueError("Electrolyzer requires work (stack power in W)")
    power_kw = max(abs(block.work) / 1000.0, 10.0)
    pressure_barg = _to_barg(block.outlet.P if block.outlet else 1e5)
    return SizingResult(
        equipment_class="Electrolyzer",
        subtype="PEM",
        size=power_kw,
        size_unit="kW",
        pressure_barg=pressure_barg,
        note="rated stack power",
    )


def _size_membrane(block: BlockInput) -> SizingResult:
    """Membrane — area from flow × specific flux rule of thumb."""
    if block.inlet is None:
        raise ValueError("Membrane requires inlet stream")
    # Default RO flux ~25 L/(m²·h) at typical water conditions
    vol_per_s = block.inlet.volumetric_flow()
    vol_lph = vol_per_s * 1000 * 3600
    area = max(vol_lph / 25.0, 5.0)
    return SizingResult(
        equipment_class="Membrane",
        subtype="RO",
        size=area,
        size_unit="m2",
        pressure_barg=_to_barg(block.inlet.P),
        note="25 L/(m²·h) flux rule of thumb",
    )


def _size_psa(block: BlockInput) -> SizingResult:
    """PSA — sized by inlet volumetric flow at pressure."""
    if block.inlet is None:
        raise ValueError("PSA requires inlet stream")
    flow = max(block.inlet.volumetric_flow(), 0.05)
    return SizingResult(
        equipment_class="PSA",
        subtype="Skid",
        size=flow,
        size_unit="m3/s",
        pressure_barg=_to_barg(block.inlet.P),
        note="feed volumetric flow",
    )


def _size_crystallizer(block: BlockInput) -> SizingResult:
    """Crystallizer — sized by residence volume (F × τ)."""
    if block.inlet is None:
        raise ValueError("Crystallizer requires inlet stream")
    # 2-hour residence typical for continuous crystallizers
    tau = 7200.0
    volume = max(block.inlet.volumetric_flow() * tau, 1.5)
    return SizingResult(
        equipment_class="Crystallizer",
        subtype="Continuous",
        size=volume,
        size_unit="m3",
        pressure_barg=_to_barg(block.inlet.P),
        note=f"{tau / 3600:.1f}-h residence",
    )


def _size_spray_dryer(block: BlockInput) -> SizingResult:
    """Spray dryer — sized by evaporation mass flow (kg/s water)."""
    if block.inlet is None:
        raise ValueError("SprayDryer requires inlet stream")
    mass_flow = max(block.inlet.mass_flow(), 0.05)
    return SizingResult(
        equipment_class="SprayDryer",
        subtype="CoCurrent",
        size=mass_flow,
        size_unit="kg/s",
        pressure_barg=_to_barg(block.inlet.P),
        note="inlet mass flow (conservative)",
    )
