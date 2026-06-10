"""
TEA cost endpoints. Backed by the cost DB (repository.py); only mounted when
DATABASE_URL is configured (see main.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.tea import db, models, repository

router = APIRouter()


class CostEquipmentRequest(BaseModel):
    equipment_type: str = Field(..., examples=["HeatExchanger"])
    subtype: str = Field(..., examples=["FloatingHead"])
    material: str = Field(..., examples=["CarbonSteel"])
    size: float = Field(..., gt=0, description="In the correlation's size_unit")
    pressure: float = 0.0
    source: str | None = None
    index_name: str = "jasper"
    region: str = "US-GC"
    aace_class: int = 5


@router.get("/tea/health")
def tea_health(session: Session = Depends(db.get_session)) -> dict:
    n = session.scalar(select(func.count()).select_from(models.EquipmentCorrelation))
    return {"status": "ok", "correlations": int(n or 0)}


@router.get("/tea/cost-blended")
def cost_blended(
    equipment_type: str, size: float, si_unit: str, subtype: str | None = None,
    material: str = "CarbonSteel", session: Session = Depends(db.get_session),
) -> dict:
    """Blended purchased cost across all sources for a unit: value + range."""
    try:
        return repository.blended_purchased_cost(
            session, equipment_type, size, si_unit, subtype, material,
        )
    except repository.CostDataMissing as exc:
        raise _missing(exc)
    except repository.costing.CostingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "costing_error", "message": str(exc)}
        )


class CostUnitRequest(BaseModel):
    jasper_unit_type: str = Field(..., examples=["DistillationColumn"])
    size: float = Field(..., gt=0, description="In the unit's sizing_basis unit")
    material: str | None = None
    pressure: float = 0.0
    base_type: str | None = Field(None, description="Required for CustomUnit")
    region: str = "US-GC"
    aace_class: int = 5


def _missing(exc: "repository.CostDataMissing") -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": "cost_data_missing",
            "message": str(exc),
            "note": "Uncovered equipment is gap-logged, never estimated.",
        },
    )


@router.post("/tea/cost-equipment")
def cost_equipment(
    req: CostEquipmentRequest, session: Session = Depends(db.get_session)
) -> dict:
    try:
        return repository.cost_equipment(
            session, req.equipment_type, req.subtype, req.material,
            req.size, req.pressure, req.source, req.index_name,
            req.region, req.aace_class,
        )
    except repository.CostDataMissing as exc:
        raise _missing(exc)
    except repository.costing.CostingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "costing_error", "message": str(exc)}
        )


@router.post("/tea/cost-unit")
def cost_unit(
    req: CostUnitRequest, session: Session = Depends(db.get_session)
) -> dict:
    """Cost a Jasper flowsheet unit by its schema.ts UnitType."""
    try:
        return repository.cost_unit(
            session, req.jasper_unit_type, req.size, req.material,
            req.pressure, req.base_type, req.region, req.aace_class,
        )
    except repository.CostDataMissing as exc:
        raise _missing(exc)
    except repository.costing.CostingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "costing_error", "message": str(exc)}
        )


class CostColumnRequest(BaseModel):
    jasper_unit_type: str = Field(..., examples=["DistillationColumn"])
    shell_volume: float = Field(..., gt=0, description="m^3")
    diameter_m: float = Field(..., gt=0)
    n_stages: int = 1  # trays only
    tray_type: str = "Sieve"
    tray_material: str = "CarbonSteel"
    material: str | None = None
    pressure: float = 0.0
    region: str = "US-GC"
    aace_class: int = 5
    internals: str = "trays"
    packed_height_m: float | None = None
    packing_type: str = "Random"
    packing_material: str = "Metal"


@router.post("/tea/cost-column")
def cost_column(
    req: CostColumnRequest, session: Session = Depends(db.get_session)
) -> dict:
    """Cost a column = shell + internals (trays or packing)."""
    try:
        return repository.cost_column(
            session, req.jasper_unit_type, req.shell_volume, req.diameter_m,
            req.n_stages, req.tray_type, req.tray_material, req.material,
            req.pressure, req.region, req.aace_class,
            internals=req.internals, packed_height_m=req.packed_height_m,
            packing_type=req.packing_type, packing_material=req.packing_material,
        )
    except repository.CostDataMissing as exc:
        raise _missing(exc)
    except repository.costing.CostingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "costing_error", "message": str(exc)}
        )


@router.get("/tea/coverage")
def coverage(session: Session = Depends(db.get_session)) -> dict:
    """Coverage of Jasper's unit catalog: each type's correlation + sourced status."""
    rows = repository.coverage_report(session)
    cost_bearing = [r for r in rows if r["cost_bearing"]]
    return {
        "total_unit_types": len(rows),
        "cost_bearing": len(cost_bearing),
        "covered": sum(1 for r in cost_bearing if r["covered"]),
        "uncovered": [r["jasper_unit_type"] for r in cost_bearing if not r["covered"]],
        "units": rows,
    }


class EstimateRequest(BaseModel):
    # Optional `id` on any item is echoed into its breakdown row (node mapping).
    equipment: list[dict] = Field(..., description="[{id?,type,size,base_type?,...} | {id?,type,column:true,shell_volume,diameter_m,n_stages}]")
    feeds: list[dict] = Field(default_factory=list, description="[{id?, cas, annual_kg}]")
    products: list[dict] = Field(default_factory=list, description="[{id?, cas, annual_kg}]")
    utilities: list[dict] = Field(default_factory=list, description="[{id?, utility_type, annual}]")
    region: str = "US-GC"
    aace_class: int = 5
    scenario: str | None = None


@router.post("/tea/estimate")
def estimate(
    req: EstimateRequest, session: Session = Depends(db.get_session)
) -> dict:
    """End-to-end project estimate: CAPEX (equipment) + OPEX (flows x prices)."""
    try:
        return repository.estimate_project(
            session, req.equipment, req.feeds, req.products, req.utilities,
            region=req.region, aace_class=req.aace_class, scenario_ref=req.scenario,
        )
    except repository.CostDataMissing as exc:
        raise _missing(exc)
    except repository.costing.CostingError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "costing_error", "message": str(exc)}
        )


@router.get("/tea/sources")
def sources(session: Session = Depends(db.get_session)) -> dict:
    """Source registry: every source, its license, and where it's used."""
    reg = repository.source_registry(session)
    return {"count": len(reg), "sources": reg}


# --- prices + overrides (B5/B6) ------------------------------------------- #
@router.get("/tea/price/chemical")
def chemical_price(
    cas: str, region: str | None = None, scenario: str | None = None,
    project: str | None = None, session: Session = Depends(db.get_session),
) -> dict:
    try:
        return repository.get_chemical_price(session, cas, region, scenario, project)
    except repository.CostDataMissing as exc:
        raise _missing(exc)


@router.get("/tea/price/utility")
def utility_price(
    utility_type: str, region: str | None = None, fuel_price: float | None = None,
    scenario: str | None = None, project: str | None = None,
    session: Session = Depends(db.get_session),
) -> dict:
    try:
        return repository.get_utility_cost(session, utility_type, region,
                                           fuel_price, scenario, project)
    except repository.CostDataMissing as exc:
        raise _missing(exc)


class OverrideRequest(BaseModel):
    target_table: str = Field(..., examples=["chemical_prices"])
    target_key: dict = Field(..., examples=[{"cas": "108-88-3", "region": "US-GC"}])
    field: str = "price"
    new_value: dict = Field(..., examples=[{"price": 0.80, "unit": "USD/kg"}])
    scope: str = "scenario"
    scope_ref: str | None = None
    reason: str | None = None
    context: dict | None = None
    actor: str | None = None


@router.post("/tea/override")
def record_override(
    req: OverrideRequest, session: Session = Depends(db.get_session),
    _key: str = Depends(require_api_key),
) -> dict:
    """Append an override event (append-only, API-key-gated). Returns its id + layer."""
    ov = repository.record_override(
        session, req.target_table, req.target_key, req.field, req.new_value,
        scope=req.scope, scope_ref=req.scope_ref, reason=req.reason,
        context=req.context, actor=req.actor,
    )
    session.commit()
    return {"id": ov.id, "layer": "override", "recorded": True}


@router.get("/tea/overrides")
def list_overrides(
    target_table: str | None = None, scope_ref: str | None = None,
    session: Session = Depends(db.get_session),
) -> dict:
    """Queryable override event log (preference-data-clean)."""
    from sqlalchemy import select

    from app.tea import models

    stmt = select(models.Override).order_by(models.Override.created_at.desc())
    if target_table:
        stmt = stmt.where(models.Override.target_table == target_table)
    if scope_ref:
        stmt = stmt.where(models.Override.scope_ref == scope_ref)
    rows = session.scalars(stmt).all()
    return {
        "count": len(rows),
        "events": [
            {"id": o.id, "target_table": o.target_table, "target_key": o.target_key,
             "field": o.field, "new_value": o.new_value, "scope": o.scope,
             "scope_ref": o.scope_ref, "reason": o.reason}
            for o in rows
        ],
    }
