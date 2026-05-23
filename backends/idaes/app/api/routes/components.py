"""Component database endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.data.component_db import COMPONENTS, get_component_by_id, get_all_categories

router = APIRouter()


class ComponentInfo(BaseModel):
    """Component information."""
    id: str
    name: str
    formula: str
    cas_number: Optional[str] = None
    molecular_weight: float
    critical_temperature: float  # K
    critical_pressure: float  # Pa
    acentric_factor: float
    normal_boiling_point: float  # K
    category: str


def _to_info(c) -> ComponentInfo:
    return ComponentInfo(
        id=c.id,
        name=c.name,
        formula=c.formula,
        cas_number=c.cas_number,
        molecular_weight=c.mw,
        critical_temperature=c.temperature_crit,
        critical_pressure=c.pressure_crit,
        acentric_factor=c.omega,
        normal_boiling_point=c.normal_bp,
        category=c.category,
    )


# Pre-build list once at import time
_ALL_COMPONENTS: list[ComponentInfo] = [_to_info(c) for c in COMPONENTS]
_ALL_CATEGORIES: list[str] = get_all_categories()


@router.get("/components")
async def get_components(
    search: Optional[str] = Query(None, description="Search term"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, le=500),
    _key: str = Depends(require_api_key),
):
    """Get available components from the database."""
    results = _ALL_COMPONENTS

    if search:
        search_lower = search.lower()
        results = [
            c for c in results
            if search_lower in c.name.lower()
            or search_lower in c.formula.lower()
            or (c.cas_number and search_lower in c.cas_number)
        ]

    if category:
        results = [c for c in results if c.category == category]

    return {
        "components": results[:limit],
        "total": len(results),
        "categories": _ALL_CATEGORIES,
    }


@router.get("/components/{component_id}")
async def get_component(component_id: str, _key: str = Depends(require_api_key)):
    """Get detailed information for a specific component."""
    comp = get_component_by_id(component_id)
    if comp is None:
        return {"error": "Component not found", "component_id": component_id}
    return _to_info(comp)
