"""
Unit Model Factory

Creates IDAES unit models based on Jasper node types.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def create_unit_model(
    flowsheet,
    unit_type: str,
    unit_id: str,
    unit_name: str,
    property_package,
    params: dict,
    reaction_package: Optional[Any] = None,
) -> Optional[Any]:
    """
    Create an IDAES unit model based on Jasper unit type.

    Args:
        flowsheet: The IDAES FlowsheetBlock
        unit_type: Jasper unit type (Feed, Mixer, Flash, etc.)
        unit_id: Unique identifier
        unit_name: Display name
        property_package: IDAES property package
        params: Unit parameters from Jasper

    Returns:
        IDAES unit model instance
    """
    # Map Jasper types to IDAES unit models
    unit_creators = {
        'Feed': _create_feed,
        'Sink': _create_product,
        'Product': _create_product,
        'Mixer': _create_mixer,
        'Splitter': _create_separator,
        'Flash': _create_flash,
        'Heater': _create_heater,
        'Cooler': _create_heater,  # Same as heater, just negative duty
        'Pump': _create_pump,
        'Compressor': _create_compressor,
        'Valve': _create_valve,
        'HeatExchanger': _create_heat_exchanger,
        'RCSTR': _create_cstr,
        'RPfr': _create_pfr,
        'REquil': _create_equilibrium_reactor,
        'RGibbs': _create_gibbs_reactor,
        'DistillationColumn': _create_tray_column,
        'Absorber': _create_tray_column,
        'Stripper': _create_tray_column,
    }

    creator = unit_creators.get(unit_type)
    if creator is None:
        logger.warning("Unknown unit type '%s', skipping", unit_type)
        return None

    # Reactor factories accept reaction_package; others do not.
    if unit_type in ('RCSTR', 'RPfr', 'REquil', 'RGibbs'):
        return creator(flowsheet, unit_id, property_package, params, reaction_package)
    return creator(flowsheet, unit_id, property_package, params)


def _create_feed(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Feed unit (source)."""
    from idaes.models.unit_models import Feed

    return Feed(
        property_package=property_package
    )


def _create_product(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Product unit (sink)."""
    from idaes.models.unit_models import Product

    return Product(
        property_package=property_package
    )


def _create_mixer(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Mixer unit."""
    from idaes.models.unit_models import Mixer, MomentumMixingType

    num_inlets = params.get('numInlets', 2)

    return Mixer(
        property_package=property_package,
        num_inlets=num_inlets,
        momentum_mixing_type=MomentumMixingType.minimize
    )


def _create_separator(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Separator (splitter) unit."""
    from idaes.models.unit_models import Separator

    num_outlets = params.get('numOutlets', 2)
    outlet_list = [f"outlet_{i+1}" for i in range(num_outlets)]

    return Separator(
        property_package=property_package,
        outlet_list=outlet_list,
        split_basis=params.get('splitBasis', 'mole')
    )


def _create_flash(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Flash drum unit."""
    from idaes.models.unit_models import Flash

    return Flash(
        property_package=property_package,
        has_heat_transfer=True,
        has_pressure_change=True
    )


def _create_heater(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Heater unit."""
    from idaes.models.unit_models import Heater

    return Heater(
        property_package=property_package,
        has_pressure_change=params.get('hasPressureDrop', False)
    )


def _create_pump(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Pump unit."""
    from idaes.models.unit_models import Pump

    return Pump(
        property_package=property_package
    )


def _create_compressor(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Compressor unit."""
    from idaes.models.unit_models.pressure_changer import (
        Compressor,
        ThermodynamicAssumption
    )

    assumption = params.get('assumption', 'isentropic')
    thermo_assumption = {
        'isentropic': ThermodynamicAssumption.isentropic,
        'isothermal': ThermodynamicAssumption.isothermal,
        'adiabatic': ThermodynamicAssumption.adiabatic,
    }.get(assumption, ThermodynamicAssumption.isentropic)

    return Compressor(
        property_package=property_package,
        thermodynamic_assumption=thermo_assumption
    )


def _create_valve(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Valve unit."""
    from idaes.models.unit_models import Valve

    return Valve(
        property_package=property_package
    )


def _create_heat_exchanger(flowsheet, unit_id: str, property_package, params: dict):
    """Create a Heat Exchanger unit."""
    from idaes.models.unit_models import HeatExchanger1D
    from idaes.models.unit_models.heat_exchanger import HeatExchangerFlowPattern

    flow_pattern = params.get('flowPattern', 'countercurrent')
    pattern = {
        'countercurrent': HeatExchangerFlowPattern.countercurrent,
        'cocurrent': HeatExchangerFlowPattern.cocurrent,
        'crossflow': HeatExchangerFlowPattern.crossflow,
    }.get(flow_pattern, HeatExchangerFlowPattern.countercurrent)

    return HeatExchanger1D(
        hot_side={"property_package": property_package},
        cold_side={"property_package": property_package},
        flow_pattern=pattern
    )


def _create_cstr(flowsheet, unit_id: str, property_package, params: dict,
                 reaction_package: Optional[Any] = None):
    """Create a CSTR reactor unit."""
    from idaes.models.unit_models import CSTR

    config: dict[str, Any] = {
        "property_package": property_package,
        "has_heat_transfer": params.get('hasHeatTransfer', True),
        "has_pressure_change": params.get('hasPressureChange', False),
    }
    if reaction_package is not None:
        config["reaction_package"] = reaction_package
    return CSTR(**config)


def _create_pfr(flowsheet, unit_id: str, property_package, params: dict,
                reaction_package: Optional[Any] = None):
    """Create a PFR reactor unit."""
    from idaes.models.unit_models import PFR

    config: dict[str, Any] = {
        "property_package": property_package,
        "has_heat_transfer": params.get('hasHeatTransfer', True),
        "has_pressure_change": params.get('hasPressureChange', True),
    }
    if reaction_package is not None:
        config["reaction_package"] = reaction_package
    return PFR(**config)


def _create_equilibrium_reactor(flowsheet, unit_id: str, property_package, params: dict,
                                reaction_package: Optional[Any] = None):
    """Create an Equilibrium Reactor unit."""
    from idaes.models.unit_models import EquilibriumReactor

    config: dict[str, Any] = {
        "property_package": property_package,
        "has_heat_transfer": True,
        "has_pressure_change": False,
    }
    if reaction_package is not None:
        config["reaction_package"] = reaction_package
    return EquilibriumReactor(**config)


def _create_gibbs_reactor(flowsheet, unit_id: str, property_package, params: dict,
                          reaction_package: Optional[Any] = None):
    """Create a Gibbs Reactor unit.

    Note: GibbsReactor minimizes Gibbs free energy and does NOT take a
    reaction_package (reactions are determined by thermodynamic equilibrium).
    The parameter is accepted for signature uniformity.
    """
    from idaes.models.unit_models import GibbsReactor
    _ = reaction_package  # intentionally unused

    return GibbsReactor(
        property_package=property_package,
        has_heat_transfer=True,
        has_pressure_change=False
    )


def _create_tray_column(flowsheet, unit_id: str, property_package, params: dict):
    """Create a TrayColumn (distillation/absorber/stripper)."""
    from idaes.models.unit_models.distillation import TrayColumn
    from idaes.models.unit_models.distillation.condenser import (
        CondenserType,
        TemperatureSpec,
    )

    num_trays = params.get('numTrays', params.get('stages', 10))
    feed_tray = params.get('feedTray', max(1, num_trays // 2))

    condenser_type_str = params.get('condenserType', 'total')
    condenser_type = (
        CondenserType.totalCondenser
        if condenser_type_str == 'total'
        else CondenserType.partialCondenser
    )

    return TrayColumn(
        number_of_trays=num_trays,
        feed_tray_location=feed_tray,
        condenser_type=condenser_type,
        condenser_temperature_spec=TemperatureSpec.atBubblePoint,
        property_package=property_package,
        has_heat_transfer=True,
        has_pressure_change=True,
    )
