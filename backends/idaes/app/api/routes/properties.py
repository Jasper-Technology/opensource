"""Property calculation endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


class PropertyRequest(BaseModel):
    """Request for property calculations."""
    components: list[str]
    temperature: float  # K
    pressure: float  # Pa
    composition: dict[str, float]  # mole fractions
    property_method: str = "Ideal"


class PropertyResponse(BaseModel):
    """Response with calculated properties."""
    phase: str
    vapor_fraction: float
    density: float  # kg/m3
    enthalpy: float  # J/mol
    entropy: float  # J/mol/K
    heat_capacity: float  # J/mol/K
    molecular_weight: float  # g/mol
    fugacity_coefficients: dict[str, float]
    activity_coefficients: dict[str, float]


@router.get("/properties/methods")
async def get_property_methods(_key: str = Depends(require_api_key)):
    """Get available property calculation methods."""
    return {
        "methods": [
            {
                "id": "Ideal",
                "name": "Ideal Gas / Raoult's Law",
                "description": "Simple ideal gas and ideal liquid assumptions",
                "best_for": ["Non-polar mixtures", "Low pressure systems"]
            },
            {
                "id": "SRK",
                "name": "Soave-Redlich-Kwong",
                "description": "Cubic equation of state for hydrocarbon systems",
                "best_for": ["Hydrocarbons", "Gas processing", "Refinery applications"]
            },
            {
                "id": "PR",
                "name": "Peng-Robinson",
                "description": "Cubic equation of state, improved liquid density",
                "best_for": ["Hydrocarbons", "Natural gas", "Petrochemicals"]
            },
            {
                "id": "NRTL",
                "name": "Non-Random Two-Liquid",
                "description": "Activity coefficient model for non-ideal liquids",
                "best_for": ["Polar mixtures", "Azeotropic systems", "Liquid-liquid equilibrium"]
            },
            {
                "id": "UNIQUAC",
                "name": "Universal Quasi-Chemical",
                "description": "Activity coefficient model based on molecular structure",
                "best_for": ["Polymer solutions", "Size-asymmetric systems"]
            },
            {
                "id": "eNRTL",
                "name": "Electrolyte NRTL",
                "description": "NRTL extended for electrolyte solutions",
                "best_for": ["Electrolyte solutions", "Acid-base systems", "Aqueous systems"]
            }
        ]
    }


@router.post("/properties/calculate", response_model=PropertyResponse)
async def calculate_properties(request: PropertyRequest, _key: str = Depends(require_api_key)):
    """
    Calculate thermodynamic properties for a stream.

    Uses IDAES property packages for accurate calculations.
    """
    try:
        from idaes.models.properties.modular_properties.base.generic_property import (
            GenericParameterBlock
        )
        from pyomo.environ import ConcreteModel, value

        # Build minimal property model
        m = ConcreteModel()

        # Configure property package based on method
        config = _get_property_config(
            request.property_method,
            request.components
        )

        m.props = GenericParameterBlock(**config)

        # Create state block
        m.state = m.props.build_state_block([0], defined_state=True)

        # Fix state
        m.state[0].temperature.fix(request.temperature)
        m.state[0].pressure.fix(request.pressure)
        for comp, frac in request.composition.items():
            m.state[0].mole_frac_comp[comp].fix(frac)

        # Initialize and calculate
        m.state.initialize()

        # Extract properties
        return PropertyResponse(
            phase=_determine_phase(m.state[0]),
            vapor_fraction=value(m.state[0].vapor_frac) if hasattr(m.state[0], 'vapor_frac') else 0.0,
            density=value(m.state[0].dens_mol_phase['Liq']) * value(m.state[0].mw) / 1000
                if hasattr(m.state[0], 'dens_mol_phase') else 1000.0,
            enthalpy=value(m.state[0].enth_mol) if hasattr(m.state[0], 'enth_mol') else 0.0,
            entropy=value(m.state[0].entr_mol) if hasattr(m.state[0], 'entr_mol') else 0.0,
            heat_capacity=value(m.state[0].cp_mol) if hasattr(m.state[0], 'cp_mol') else 0.0,
            molecular_weight=value(m.state[0].mw) if hasattr(m.state[0], 'mw') else 0.0,
            fugacity_coefficients={
                comp: value(m.state[0].fug_coeff_phase_comp['Vap', comp])
                for comp in request.components
            } if hasattr(m.state[0], 'fug_coeff_phase_comp') else {},
            activity_coefficients={
                comp: value(m.state[0].act_coeff_phase_comp['Liq', comp])
                for comp in request.components
            } if hasattr(m.state[0], 'act_coeff_phase_comp') else {}
        )

    except Exception as e:
        logger.error("Property calculation failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Property calculation failed. Please check your inputs."},
        )


def _get_property_config(method: str, components: list[str]) -> dict:
    """Get IDAES property package configuration for the given method.

    Delegates to the same property_packages module used by the simulation
    pipeline so that configs are consistent.
    """
    from app.idaes_wrapper.property_packages import (
        _build_ideal_config,
        _build_cubic_config,
        _build_activity_config,
        _build_electrolyte_config,
    )

    builders = {
        "Ideal": lambda: _build_ideal_config(components),
        "SRK": lambda: _build_cubic_config(components, "SRK"),
        "PR": lambda: _build_cubic_config(components, "PR"),
        "NRTL": lambda: _build_activity_config(components, "NRTL"),
        "UNIQUAC": lambda: _build_activity_config(components, "UNIQUAC"),
        "eNRTL": lambda: _build_electrolyte_config(components),
    }

    builder = builders.get(method, lambda: _build_ideal_config(components))
    return builder()


def _determine_phase(state) -> str:
    """Determine phase from state block."""
    try:
        vf = state.vapor_frac.value
        if vf is None:
            return "unknown"
        if vf > 0.999:
            return "vapor"
        elif vf < 0.001:
            return "liquid"
        else:
            return "two-phase"
    except Exception:
        return "unknown"
