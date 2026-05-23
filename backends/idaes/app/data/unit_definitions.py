"""
Unit Definitions — Single Source of Truth
==========================================

This file is the canonical definition of every unit type Jasper supports.
Both the model builder (backend) and the /api/units endpoint (frontend) read
from here, so frontend and backend can never drift apart.

To add a new unit:
  1. Add an entry to UNIT_DEFINITIONS below.
  2. Add a creator function to unit_models.py and register it in unit_creators.
  That's it — no other mapping tables to update.

Port name convention
--------------------
  ``name`` is the ID used in the frontend ReactFlow Handle and stored in
  StreamEdge.from.portName / StreamEdge.to.portName.
  ``idaes_attr`` is the attribute name on the IDAES unit object.
"""
from __future__ import annotations
from typing import TypedDict, Literal, Optional


class PortDef(TypedDict, total=False):
    name: str                           # frontend port name (Handle id)
    idaes_attr: str                     # IDAES unit attribute name
    direction: Literal["in", "out"]
    phase: Optional[str]                # V, L, VL, or None


class ParamDef(TypedDict, total=False):
    type: str                           # quantity | number | int | enum | boolean | composition | string
    default: object
    unit: Optional[str]                 # SI unit for quantity params
    optional: bool
    description: str


class UnitDef(TypedDict, total=False):
    description: str
    ports: list[PortDef]
    params: dict[str, ParamDef]
    supported: bool                     # True if IDAES can actually simulate this
    note: Optional[str]                 # shown to users when supported=False


UNIT_DEFINITIONS: dict[str, UnitDef] = {
    "Feed": {
        "description": "Feed stream source — specifies temperature, pressure, flow, and composition.",
        "ports": [
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "T":           {"type": "quantity", "default": {"value": 25, "unit": "C"}, "description": "Temperature"},
            "P":           {"type": "quantity", "default": {"value": 1,  "unit": "bar"}, "description": "Pressure"},
            "flow":        {"type": "quantity", "default": {"value": 100, "unit": "kmol/h"}, "description": "Molar flow rate"},
            "composition": {"type": "composition", "description": "Component mole fractions (must sum to 1)"},
        },
        "supported": True,
    },
    "Sink": {
        "description": "Product sink — collects an outlet stream.",
        "ports": [
            {"name": "in", "idaes_attr": "inlet", "direction": "in"},
        ],
        "params": {},
        "supported": True,
    },
    "Mixer": {
        "description": "Mixes two or more inlet streams into one outlet.",
        "ports": [
            {"name": "in1", "idaes_attr": "inlet_1", "direction": "in"},
            {"name": "in2", "idaes_attr": "inlet_2", "direction": "in"},
            {"name": "out", "idaes_attr": "outlet",   "direction": "out"},
        ],
        "params": {
            "numInlets": {"type": "int", "default": 2, "description": "Number of inlet streams"},
        },
        "supported": True,
    },
    "Splitter": {
        "description": "Splits one inlet stream into two or more outlets with a fixed split fraction.",
        "ports": [
            {"name": "in",   "idaes_attr": "inlet",    "direction": "in"},
            {"name": "out1", "idaes_attr": "outlet_1", "direction": "out"},
            {"name": "out2", "idaes_attr": "outlet_2", "direction": "out"},
        ],
        "params": {
            "splitRatio":  {"type": "number", "default": 0.5, "description": "Fraction of feed to outlet_1"},
            "numOutlets":  {"type": "int",    "default": 2,   "description": "Number of outlet streams"},
        },
        "supported": True,
    },
    "Flash": {
        "description": "Adiabatic flash drum — splits a feed into vapor and liquid phases.",
        "ports": [
            {"name": "in",     "idaes_attr": "inlet",      "direction": "in"},
            {"name": "vapor",  "idaes_attr": "vap_outlet", "direction": "out", "phase": "V"},
            {"name": "liquid", "idaes_attr": "liq_outlet", "direction": "out", "phase": "L"},
        ],
        "params": {
            "T": {"type": "quantity", "default": {"value": 50, "unit": "C"}, "optional": True,
                  "description": "Outlet temperature (omit for adiabatic flash)"},
            "P": {"type": "quantity", "default": {"value": 1, "unit": "bar"}, "optional": True,
                  "description": "Outlet pressure (omit for isobaric flash)"},
        },
        "supported": True,
    },
    "Heater": {
        "description": "Heats a stream to a target outlet temperature.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "outletT": {"type": "quantity", "default": {"value": 100, "unit": "C"},
                        "description": "Target outlet temperature"},
        },
        "supported": True,
    },
    "Cooler": {
        "description": "Cools a stream to a target outlet temperature.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "outletT": {"type": "quantity", "default": {"value": 25, "unit": "C"},
                        "description": "Target outlet temperature"},
        },
        "supported": True,
    },
    "Pump": {
        "description": "Raises liquid stream pressure by a specified pressure rise.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "dP": {"type": "quantity", "default": {"value": 5, "unit": "bar"},
                   "description": "Pressure rise across the pump"},
        },
        "supported": True,
    },
    "Compressor": {
        "description": "Raises gas stream pressure isentropically.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "outletP":    {"type": "quantity", "default": {"value": 10, "unit": "bar"},
                           "description": "Target outlet pressure"},
            "assumption": {"type": "enum", "default": "isentropic",
                           "description": "Thermodynamic assumption (isentropic | isothermal | adiabatic)"},
        },
        "supported": True,
    },
    "Valve": {
        "description": "Throttles a stream to reduce pressure.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "dP": {"type": "quantity", "default": {"value": -2, "unit": "bar"},
                   "description": "Pressure drop across the valve (negative = drop)"},
        },
        "supported": True,
    },
    "HeatExchanger": {
        "description": "Shell-and-tube heat exchanger with hot and cold sides.",
        "ports": [
            {"name": "hot-in",   "idaes_attr": "hot_side_inlet",  "direction": "in"},
            {"name": "hot-out",  "idaes_attr": "hot_side_outlet", "direction": "out"},
            {"name": "cold-in",  "idaes_attr": "cold_side_inlet", "direction": "in"},
            {"name": "cold-out", "idaes_attr": "cold_side_outlet","direction": "out"},
        ],
        "params": {
            "flowPattern": {"type": "enum", "default": "countercurrent",
                            "description": "countercurrent | cocurrent | crossflow"},
        },
        "supported": True,
    },
    "RCSTR": {
        "description": "Continuous stirred tank reactor (CSTR).",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "volume":          {"type": "quantity", "default": {"value": 1, "unit": "m3"}},
            "hasHeatTransfer": {"type": "boolean",  "default": True},
        },
        "supported": True,
    },
    "RPfr": {
        "description": "Plug flow reactor (PFR).",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {
            "length":          {"type": "quantity", "default": {"value": 1, "unit": "m"}},
            "hasHeatTransfer": {"type": "boolean",  "default": True},
        },
        "supported": True,
    },
    "REquil": {
        "description": "Equilibrium reactor — minimises Gibbs energy of reaction.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {},
        "supported": True,
    },
    "RGibbs": {
        "description": "Gibbs free energy reactor — finds equilibrium by minimising Gibbs energy.",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",  "direction": "in"},
            {"name": "out", "idaes_attr": "outlet", "direction": "out"},
        ],
        "params": {},
        "supported": True,
    },
    "DistillationColumn": {
        "description": "Multi-tray distillation column with condenser and reboiler.",
        "ports": [
            {"name": "feed",       "idaes_attr": "feed",             "direction": "in"},
            {"name": "overhead",   "idaes_attr": "condenser_distillate", "direction": "out", "phase": "V"},
            {"name": "bottoms",    "idaes_attr": "reboiler_bottoms", "direction": "out", "phase": "L"},
        ],
        "params": {
            "numTrays":      {"type": "int",    "default": 10},
            "feedTray":      {"type": "int",    "default": 5},
            "refluxRatio":   {"type": "number", "default": 2.0},
            "condenserType": {"type": "enum",   "default": "total"},
        },
        "supported": True,
    },
    "Absorber": {
        "description": "Gas-liquid absorber column.",
        "ports": [
            {"name": "gas-in",    "idaes_attr": "gas_inlet",     "direction": "in"},
            {"name": "liquid-in", "idaes_attr": "liquid_inlet",  "direction": "in"},
            {"name": "gas-out",   "idaes_attr": "gas_outlet",    "direction": "out"},
            {"name": "liquid-out","idaes_attr": "liquid_outlet", "direction": "out"},
        ],
        "params": {
            "numTrays": {"type": "int", "default": 10},
        },
        "supported": True,
    },
    "Stripper": {
        "description": "Stripping column — removes dissolved gas from liquid.",
        "ports": [
            {"name": "liquid-in", "idaes_attr": "liquid_inlet",  "direction": "in"},
            {"name": "gas-out",   "idaes_attr": "gas_outlet",    "direction": "out"},
            {"name": "liquid-out","idaes_attr": "liquid_outlet", "direction": "out"},
        ],
        "params": {
            "numTrays": {"type": "int", "default": 10},
        },
        "supported": True,
    },
    # ── Legacy / not yet supported ────────────────────────────────────────────
    "Separator": {
        "description": "Generic separator (use Flash or Splitter instead).",
        "ports": [
            {"name": "in",  "idaes_attr": "inlet",    "direction": "in"},
            {"name": "out1","idaes_attr": "outlet_1", "direction": "out"},
            {"name": "out2","idaes_attr": "outlet_2", "direction": "out"},
        ],
        "params": {},
        "supported": False,
        "note": "Use Flash for VLE separation or Splitter for stream splitting.",
    },
    "RBatch": {
        "description": "Batch reactor (not yet supported in steady-state IDAES).",
        "ports": [],
        "params": {},
        "supported": False,
        "note": "Batch reactors require dynamic simulation. Use RCSTR or RPfr for steady-state.",
    },
    "RStoic": {
        "description": "Stoichiometric reactor (not yet implemented).",
        "ports": [],
        "params": {},
        "supported": False,
        "note": "Coming soon. Use REquil or RGibbs as alternatives.",
    },
    "RYield": {
        "description": "Yield-specified reactor (not yet implemented).",
        "ports": [],
        "params": {},
        "supported": False,
        "note": "Coming soon.",
    },
}

# ── Property method definitions ───────────────────────────────────────────────

class PropertyMethodDef(TypedDict, total=False):
    description: str
    supported: bool
    fallback: Optional[str]     # what actually runs when this is selected
    note: Optional[str]         # shown to users when supported=False


PROPERTY_METHODS: dict[str, PropertyMethodDef] = {
    "Ideal": {
        "description": "Ideal gas / Raoult's Law. Fast, suitable for near-ideal systems.",
        "supported": True,
    },
    "SRK": {
        "description": "Soave-Redlich-Kwong cubic EOS. Good for hydrocarbons and gases.",
        "supported": True,
    },
    "PR": {
        "description": "Peng-Robinson cubic EOS. Industry standard for oil & gas systems.",
        "supported": True,
    },
    "NRTL": {
        "description": "Non-Random Two-Liquid activity coefficient model for non-ideal liquid mixtures.",
        "supported": False,
        "fallback": "Ideal",
        "note": (
            "NRTL requires binary interaction parameters (τ, α) that are not yet in "
            "the Jasper component database. The simulation will use the Ideal model instead. "
            "Contact the Jasper team to add NRTL parameters for your system."
        ),
    },
    "UNIQUAC": {
        "description": "UNIQUAC activity coefficient model.",
        "supported": False,
        "fallback": "Ideal",
        "note": "UNIQUAC requires fitted interaction parameters not yet in the database. Falls back to Ideal.",
    },
    "eNRTL": {
        "description": "Electrolyte NRTL — for systems with ionic species.",
        "supported": False,
        "fallback": "Ideal",
        "note": "eNRTL requires ion speciation data not yet available. Falls back to Ideal.",
    },
}


