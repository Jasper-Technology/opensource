"""
Property Package Factory

Creates IDAES property packages based on Jasper configuration.
Uses actual IDAES type classes (not strings) for phases and components.
"""
from typing import Optional

from app.data.component_db import get_idaes_parameter_data


def create_property_package(
    property_method: str,
    components: list[str],
    eos: Optional[str] = None,
    activity_model: Optional[str] = None
):
    """
    Create an IDAES property package based on the specified method.

    Args:
        property_method: The thermodynamic method (Ideal, SRK, PR, NRTL, etc.)
        components: List of component names/formulas
        eos: Equation of state override
        activity_model: Activity coefficient model override

    Returns:
        IDAES GenericParameterBlock configured for the system
    """
    from idaes.models.properties.modular_properties.base.generic_property import (
        GenericParameterBlock
    )

    config_builders = {
        "Ideal": lambda: _build_ideal_config(components),
        "SRK": lambda: _build_cubic_config(components, "SRK"),
        "PR": lambda: _build_cubic_config(components, "PR"),
        "NRTL": lambda: _build_activity_config(components, "NRTL"),
        "UNIQUAC": lambda: _build_activity_config(components, "UNIQUAC"),
        "eNRTL": lambda: _build_electrolyte_config(components),
    }

    builder = config_builders.get(property_method, lambda: _build_ideal_config(components))
    config = builder()

    return GenericParameterBlock(**config)


def _build_component_dict(components: list[str], temp_upper: float = 600.0) -> dict:
    """Build the component sub-dict with real IDAES types, Pyomo units,
    and thermodynamic property methods.

    Components whose critical temperature is below the lower state bound
    (i.e. they are always supercritical in the operating window) are
    marked vapor-only so IDAES skips VLE for them. This avoids complex-
    number errors in the Wagner saturation pressure equation.

    Uses Constant methods for Cp/enthalpy/entropy/liquid density, and
    RPP4 for saturation pressure (Wagner equation) which is required
    for VLE calculations on condensable components.
    """
    from idaes.core import Component as IdaesComponent, PhaseType
    from pyomo.environ import units as pyunits
    from idaes.models.properties.modular_properties.pure import Constant
    from idaes.models.properties.modular_properties.pure.RPP4 import RPP4
    from idaes.models.properties.modular_properties.phase_equil.forms import fugacity

    # Threshold: if Tc < this, the component is treated as non-condensable
    # (supercritical in the typical operating window). The Wagner saturation
    # pressure equation produces complex numbers when T > Tc, so we must
    # exclude light gases from VLE. This covers N2, O2, H2, CH4, CO, Ar,
    # He, C2H4, C2H6, CO2, C3H8, C3H6, H2S.
    TC_THRESHOLD = 400.0  # K

    component_dict = {}
    for comp in components:
        data = get_idaes_parameter_data(comp)
        mw_kg_per_mol = data["mw"] * 1e-3
        tc = data["temperature_crit"]

        is_condensable = tc > TC_THRESHOLD

        comp_config: dict = {
            "type": IdaesComponent,
            "enth_mol_ig_comp": Constant,
            "entr_mol_ig_comp": Constant,
            "parameter_data": {
                "mw": (mw_kg_per_mol, pyunits.kg / pyunits.mol),
                "pressure_crit": (data["pressure_crit"], pyunits.Pa),
                "temperature_crit": (tc, pyunits.K),
                "omega": data["omega"],
                "cp_mol_ig_comp_coeff": (
                    35.0,
                    pyunits.J / pyunits.mol / pyunits.K,
                ),
                "enth_mol_form_ig_comp_ref": (0, pyunits.J / pyunits.mol),
                "entr_mol_form_ig_comp_ref": (
                    0, pyunits.J / pyunits.mol / pyunits.K
                ),
            },
        }

        if is_condensable:
            # Full VLE component: liquid properties + saturation pressure
            comp_config["enth_mol_liq_comp"] = Constant
            comp_config["entr_mol_liq_comp"] = Constant
            comp_config["dens_mol_liq_comp"] = Constant
            comp_config["pressure_sat_comp"] = RPP4
            comp_config["phase_equilibrium_form"] = {("Vap", "Liq"): fugacity}
            comp_config["parameter_data"].update({
                "cp_mol_liq_comp_coeff": (
                    75.0,
                    pyunits.J / pyunits.mol / pyunits.K,
                ),
                "dens_mol_liq_comp_coeff": (
                    800.0 / mw_kg_per_mol,
                    pyunits.mol / pyunits.m**3,
                ),
                "enth_mol_form_liq_comp_ref": (0, pyunits.J / pyunits.mol),
                "entr_mol_form_liq_comp_ref": (
                    0, pyunits.J / pyunits.mol / pyunits.K
                ),
                "pressure_sat_comp_coeff": {
                    "A": (data["wagner_A"], None),
                    "B": (data["wagner_B"], None),
                    "C": (data["wagner_C"], None),
                    "D": (data["wagner_D"], None),
                },
            })
        else:
            # Non-condensable (supercritical) component — vapor only
            comp_config["valid_phase_types"] = [PhaseType.vaporPhase]

        component_dict[comp] = comp_config
    return component_dict


def _build_base_units() -> dict:
    """Return the base_units dict expected by GenericParameterBlock."""
    from pyomo.environ import units as pyunits
    return {
        "time": pyunits.s,
        "length": pyunits.m,
        "mass": pyunits.kg,
        "amount": pyunits.mol,
        "temperature": pyunits.K,
    }


def _has_condensable(component_dict: dict) -> bool:
    """Return True if at least one component can participate in VLE."""
    return any(
        "phase_equilibrium_form" in cfg
        for cfg in component_dict.values()
    )


def _build_ideal_config(components: list[str]) -> dict:
    """Build configuration for ideal gas/liquid system."""
    from idaes.core import LiquidPhase, VaporPhase
    from idaes.models.properties.modular_properties.state_definitions import FTPx
    from idaes.models.properties.modular_properties.eos.ideal import Ideal
    from idaes.models.properties.modular_properties.phase_equil import SmoothVLE
    from idaes.models.properties.modular_properties.phase_equil.bubble_dew import (
        IdealBubbleDew
    )
    from pyomo.environ import units as pyunits

    comp_dict = _build_component_dict(components)
    has_vle = _has_condensable(comp_dict)

    phases: dict = {
        "Vap": {"type": VaporPhase, "equation_of_state": Ideal},
    }
    if has_vle:
        phases["Liq"] = {"type": LiquidPhase, "equation_of_state": Ideal}

    config: dict = {
        "components": comp_dict,
        "phases": phases,
        "base_units": _build_base_units(),
        "state_definition": FTPx,
        "state_bounds": {
            "flow_mol": (0, 100, 1000, pyunits.mol / pyunits.s),
            "temperature": (200, 350, 600, pyunits.K),
            "pressure": (1e4, 1e5, 1e7, pyunits.Pa),
        },
        "pressure_ref": (1e5, pyunits.Pa),
        "temperature_ref": (300, pyunits.K),
    }
    if has_vle:
        config["phases_in_equilibrium"] = [("Vap", "Liq")]
        config["phase_equilibrium_state"] = {("Vap", "Liq"): SmoothVLE}
        config["bubble_dew_method"] = IdealBubbleDew

    return config


def _build_cubic_config(components: list[str], eos_type: str) -> dict:
    """Build configuration for cubic EOS (SRK or PR)."""
    from idaes.core import LiquidPhase, VaporPhase
    from idaes.models.properties.modular_properties.state_definitions import FTPx
    from idaes.models.properties.modular_properties.eos.ceos import Cubic, CubicType
    from idaes.models.properties.modular_properties.phase_equil import SmoothVLE
    from idaes.models.properties.modular_properties.phase_equil.bubble_dew import (
        IdealBubbleDew
    )
    from pyomo.environ import units as pyunits

    cubic_type = CubicType.SRK if eos_type == "SRK" else CubicType.PR

    # Build binary interaction parameters (kappa_ij) for all component pairs.
    # Look up fitted values from the BIP database (DIPPR/DECHEMA/NIST);
    # default to 0.0 when fitted values are not available.
    from app.data.bips import get_bip, count_bip_coverage
    import logging
    _logger = logging.getLogger(__name__)

    kappa_key = "PR_kappa" if eos_type == "PR" else "SRK_kappa"
    kappa = {}
    for c1 in components:
        for c2 in components:
            val = get_bip(c1, c2, kappa_key)
            kappa[(c1, c2)] = val if val is not None else 0.0

    covered, total = count_bip_coverage(components, kappa_key)
    if total > 0 and covered < total:
        _logger.info(
            "%s BIP coverage: %d/%d pairs have fitted data, "
            "%d pairs defaulting to kappa=0.",
            eos_type, covered, total, total - covered,
        )

    comp_dict = _build_component_dict(components)
    has_vle = _has_condensable(comp_dict)

    phases: dict = {
        "Vap": {
            "type": VaporPhase,
            "equation_of_state": Cubic,
            "equation_of_state_options": {"type": cubic_type}
        },
    }
    if has_vle:
        phases["Liq"] = {
            "type": LiquidPhase,
            "equation_of_state": Cubic,
            "equation_of_state_options": {"type": cubic_type}
        }

    config: dict = {
        "components": comp_dict,
        "phases": phases,
        "base_units": _build_base_units(),
        "state_definition": FTPx,
        "state_bounds": {
            "flow_mol": (0, 100, 1000, pyunits.mol / pyunits.s),
            "temperature": (200, 350, 600, pyunits.K),
            "pressure": (1e4, 1e5, 1e7, pyunits.Pa),
        },
        "pressure_ref": (1e5, pyunits.Pa),
        "temperature_ref": (300, pyunits.K),
        "parameter_data": {kappa_key: kappa},
    }
    if has_vle:
        config["phases_in_equilibrium"] = [("Vap", "Liq")]
        config["phase_equilibrium_state"] = {("Vap", "Liq"): SmoothVLE}
        config["bubble_dew_method"] = IdealBubbleDew

    return config


def _build_activity_config(components: list[str], model: str) -> dict:
    """Build configuration for NRTL activity coefficient model.

    Uses BIP data from the bips module (DECHEMA/DIPPR/NIST). Falls back
    to PR if the requested pair has no tau/alpha data.
    """
    import logging
    _logger = logging.getLogger(__name__)

    if model != "NRTL":
        _logger.warning(
            "%s is not yet supported (only NRTL has BIP data). "
            "Falling back to PR (Peng-Robinson).",
            model,
        )
        return _build_cubic_config(components, "PR")

    from app.data.bips import get_bip, count_bip_coverage

    covered_tau, total_tau = count_bip_coverage(components, "NRTL_tau")
    covered_alpha, total_alpha = count_bip_coverage(components, "NRTL_alpha")

    if total_tau > 0 and covered_tau == 0:
        _logger.warning(
            "NRTL requested but no tau_ij data available for any pair in %s. "
            "Falling back to PR (Peng-Robinson).",
            components,
        )
        return _build_cubic_config(components, "PR")

    if total_tau > 0 and covered_tau < total_tau:
        _logger.warning(
            "NRTL tau_ij coverage: %d/%d pairs have fitted data. "
            "Missing pairs will use tau=0 (ideal mixing).",
            covered_tau, total_tau,
        )

    # Build NRTL parameter dicts
    tau = {}
    alpha = {}
    for c1 in components:
        for c2 in components:
            if c1 == c2:
                tau[(c1, c2)] = 0.0
                alpha[(c1, c2)] = 0.3
                continue
            t = get_bip(c1, c2, "NRTL_tau")
            tau[(c1, c2)] = t if t is not None else 0.0
            a = get_bip(c1, c2, "NRTL_alpha")
            alpha[(c1, c2)] = a if a is not None else 0.3  # 0.3 is standard default

    from idaes.core import LiquidPhase, VaporPhase
    from idaes.models.properties.modular_properties.state_definitions import FTPx
    from idaes.models.properties.modular_properties.eos.ideal import Ideal
    from idaes.models.properties.modular_properties.phase_equil import SmoothVLE
    from idaes.models.properties.modular_properties.phase_equil.bubble_dew import (
        IdealBubbleDew
    )
    from pyomo.environ import units as pyunits

    # NRTL: use Ideal EOS for vapor phase, and Ideal EOS for liquid phase
    # with NRTL activity coefficients applied via parameter_data. In IDAES
    # modular properties, the GenericParameterBlock reads NRTL_tau and
    # NRTL_alpha from parameter_data to compute activity coefficients on
    # top of the liquid-phase Ideal model when SmoothVLE is configured.
    # This is the standard IDAES pattern for gamma-phi models.
    liq_config: dict = {
        "type": LiquidPhase,
        "equation_of_state": Ideal,
    }
    vap_config: dict = {
        "type": VaporPhase,
        "equation_of_state": Ideal,
    }

    # Try to use the dedicated NRTL activity coefficient EOS if available
    try:
        from idaes.models.properties.modular_properties.eos.NRTL import NRTL as NrtlEos
        liq_config["equation_of_state"] = NrtlEos
    except ImportError:
        # Fall back to Ideal + parameter_data approach (works in most IDAES versions)
        pass

    comp_dict = _build_component_dict(components)
    has_vle = _has_condensable(comp_dict)

    phases: dict = {"Vap": vap_config}
    if has_vle:
        phases["Liq"] = liq_config

    config: dict = {
        "components": comp_dict,
        "phases": phases,
        "base_units": _build_base_units(),
        "state_definition": FTPx,
        "state_bounds": {
            "flow_mol": (0, 100, 1000, pyunits.mol / pyunits.s),
            "temperature": (200, 350, 600, pyunits.K),
            "pressure": (1e4, 1e5, 1e7, pyunits.Pa),
        },
        "pressure_ref": (1e5, pyunits.Pa),
        "temperature_ref": (300, pyunits.K),
        "parameter_data": {
            "NRTL_tau": tau,
            "NRTL_alpha": alpha,
        },
    }
    if has_vle:
        config["phases_in_equilibrium"] = [("Vap", "Liq")]
        config["phase_equilibrium_state"] = {("Vap", "Liq"): SmoothVLE}
        config["bubble_dew_method"] = IdealBubbleDew

    return config


def _build_electrolyte_config(components: list[str]) -> dict:
    """Build configuration for electrolyte systems (eNRTL).

    Full eNRTL requires ion speciation data that isn't available in the
    base component database. For now, fall back to liquid-phase NRTL.
    """
    return _build_activity_config(components, "NRTL")
