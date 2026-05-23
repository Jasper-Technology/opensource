"""
GET /api/units — Unit capability advertisement
================================================

Returns the complete list of unit types and property methods this backend
supports, derived from app/data/unit_definitions.py (the single source of truth).

The frontend uses this to:
  • Know which unit types it can send to the backend
  • Know what port names to use in StreamEdge.from.portName / .to.portName
  • Show which property methods actually work (not fall back silently)
  • Warn users before they run a simulation that will fail

This endpoint makes the system LLM-friendly: Claude (or any agent) can call
GET /api/units to understand the full capability of the backend without
reading the Python source code.
"""
from fastapi import APIRouter
from app.data.unit_definitions import UNIT_DEFINITIONS, PROPERTY_METHODS

router = APIRouter()


@router.get("/units")
def get_units():
    """
    Return all supported unit types and property methods.

    Response shape:
    {
      "units": {
        "Flash": {
          "description": "...",
          "ports": [{"name": "in", "direction": "in"}, ...],
          "params": {"T": {"type": "quantity", ...}},
          "supported": true
        },
        ...
      },
      "property_methods": {
        "Ideal":  {"description": "...", "supported": true},
        "NRTL":   {"description": "...", "supported": false, "fallback": "Ideal", "note": "..."},
        ...
      }
    }
    """
    # Strip internal-only keys (idaes_attr) before returning to frontend
    units_out = {}
    for unit_type, defn in UNIT_DEFINITIONS.items():
        ports_out = [
            {k: v for k, v in port.items() if k != "idaes_attr"}
            for port in defn.get("ports", [])
        ]
        units_out[unit_type] = {
            "description": defn.get("description", ""),
            "ports": ports_out,
            "params": defn.get("params", {}),
            "supported": defn.get("supported", True),
            **({"note": defn["note"]} if "note" in defn else {}),
        }

    return {
        "units": units_out,
        "property_methods": PROPERTY_METHODS,
    }
