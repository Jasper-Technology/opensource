"""
Reaction Package Factory

Builds IDAES GenericReactionParameterBlocks from frontend reaction data.
"""
from typing import Any, Optional


def build_reaction_package(
    property_package,
    reactions: list[dict[str, Any]],
) -> Optional[Any]:
    """Build an IDAES reaction parameter block from frontend reaction specs.

    Args:
        property_package: The IDAES property parameter block for the flowsheet.
        reactions: List of reaction dicts from the frontend, each containing:
            - id: str
            - stoichiometry: dict[str, float]  (component formula -> coefficient)
            - rate_constant: float (optional, for rate-based reactions)
            - equilibrium_constant: float (optional, for equilibrium reactions)
            - type: 'rate' | 'equilibrium'

    Returns:
        GenericReactionParameterBlock or None if reactions list is empty.
    """
    if not reactions:
        return None

    from idaes.models.properties.modular_properties.base.generic_reaction import (
        GenericReactionParameterBlock,
    )

    # Determine which phases are defined in the property package
    available_phases: list[str] = []
    if hasattr(property_package, "phase_list"):
        available_phases = [str(p) for p in property_package.phase_list]
    if not available_phases:
        available_phases = ["Liq", "Vap"]  # default assumption

    rate_reactions = {}
    equilibrium_reactions = {}

    for rxn in reactions:
        rxn_id = rxn.get("id", f"rxn_{len(rate_reactions) + len(equilibrium_reactions)}")
        stoich = rxn.get("stoichiometry", {})
        rxn_type = rxn.get("type", "rate")

        # Build stoichiometry dict in IDAES format, only for phases
        # that actually exist in the property package
        stoich_dict = {}
        for comp, coeff in stoich.items():
            for phase in available_phases:
                stoich_dict[(phase, comp)] = coeff

        if rxn_type == "equilibrium":
            equilibrium_reactions[rxn_id] = {
                "stoichiometry": stoich_dict,
                "equilibrium_constant": rxn.get("equilibrium_constant", 1.0),
            }
        else:
            # Build rate reaction config — supports constant k or Arrhenius
            rxn_config: dict[str, Any] = {
                "stoichiometry": stoich_dict,
            }
            arrhenius = rxn.get("arrhenius")
            if isinstance(arrhenius, dict) and "A" in arrhenius and "Ea" in arrhenius:
                # Arrhenius form: k(T) = A * exp(-Ea / (R * T))
                rxn_config["rate_form"] = "arrhenius"
                rxn_config["rate_constant"] = {
                    "A": arrhenius["A"],
                    "Ea": arrhenius["Ea"],
                }
                if "T_ref" in arrhenius and arrhenius["T_ref"]:
                    rxn_config["rate_constant"]["T_ref"] = arrhenius["T_ref"]
                # Concentration orders (optional): {comp: exponent}
                conc_orders = rxn.get("concentration_orders")
                if isinstance(conc_orders, dict) and conc_orders:
                    rxn_config["concentration_orders"] = conc_orders
            else:
                rxn_config["rate_constant"] = rxn.get("rate_constant", 1.0)

            rate_reactions[rxn_id] = rxn_config

    config: dict[str, Any] = {
        "property_package": property_package,
        "base_units": {
            "time": "s",
            "length": "m",
            "mass": "kg",
            "amount": "mol",
            "temperature": "K",
        },
    }

    if rate_reactions:
        config["rate_reactions"] = rate_reactions
    if equilibrium_reactions:
        config["equilibrium_reactions"] = equilibrium_reactions

    return GenericReactionParameterBlock(**config)
