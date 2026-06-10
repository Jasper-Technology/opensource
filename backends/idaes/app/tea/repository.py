"""
Cost-DB queries + the costing service.

Fetches sourced coefficients from the DB, computes a cost via costing.py, and
returns the number together with its provenance chain (which source produced
each input) and the accuracy class. Honest by construction: if a correlation or
material factor is missing, it raises CostDataMissing rather than inventing a
number — callers surface that as a gap / partial result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import costing, models

DEFAULT_INDEX = "jasper"


class CostDataMissing(LookupError):
    """A required sourced input is not in the DB. Never fabricate — gap-log it."""


@dataclass(frozen=True)
class Provenance:
    correlation: str
    material_factor: str
    cost_index: str
    contingency: str


def get_correlation(
    session: Session, equipment_type: str, subtype: str, source: Optional[str] = None
) -> models.EquipmentCorrelation:
    stmt = select(models.EquipmentCorrelation).where(
        models.EquipmentCorrelation.equipment_type == equipment_type,
        models.EquipmentCorrelation.subtype == subtype,
    )
    if source:
        stmt = stmt.join(models.Source).where(models.Source.slug == source)
    # Deterministic primary when multiple sources exist: first-seeded (lowest id).
    row = session.scalars(
        stmt.order_by(models.EquipmentCorrelation.id.asc())
    ).first()
    if row is None:
        raise CostDataMissing(
            f"no correlation for {equipment_type}/{subtype}"
            + (f" from {source}" if source else "")
        )
    return row


def get_all_correlations(
    session: Session, equipment_type: str, subtype: Optional[str] = None
) -> list[models.EquipmentCorrelation]:
    """All correlations for a type (across sources) — for multi-source blending."""
    stmt = select(models.EquipmentCorrelation).where(
        models.EquipmentCorrelation.equipment_type == equipment_type
    )
    if subtype is not None:
        stmt = stmt.where(models.EquipmentCorrelation.subtype == subtype)
    return list(session.scalars(
        stmt.order_by(models.EquipmentCorrelation.id.asc())
    ).all())


def get_material_factor(
    session: Session, equipment_type: str, subtype: str, material: str
) -> models.MaterialFactor:
    row = session.scalars(
        select(models.MaterialFactor).where(
            models.MaterialFactor.equipment_type == equipment_type,
            models.MaterialFactor.subtype == subtype,
            models.MaterialFactor.material == material,
        ).order_by(models.MaterialFactor.id.asc())
    ).first()
    if row is None:
        raise CostDataMissing(
            f"no material factor for {equipment_type}/{subtype}/{material}"
        )
    return row


def _scalar_factor(mf: models.MaterialFactor, size: float) -> float:
    model = mf.factor_model
    if model.get("kind") == "scalar":
        return float(model["value"])
    if model.get("kind") == "ab":  # SSLW HX-style Fm = A + (S/100)^B
        return float(model["A"]) + (size / 100.0) ** float(model["B"])
    raise costing.CostingError(f"unknown material factor_model: {model}")


def get_current_index(
    session: Session, index_name: str = DEFAULT_INDEX
) -> models.CostIndex:
    row = session.scalars(
        select(models.CostIndex)
        .where(models.CostIndex.index_name == index_name)
        .order_by(models.CostIndex.period.desc())
    ).first()
    if row is None:
        raise CostDataMissing(f"no cost index '{index_name}'")
    return row


def get_index_value_at_year(
    session: Session, index_name: str, year: int
) -> float:
    """Index value at the start of ``year`` (earliest month present)."""
    import datetime as _dt

    row = session.scalars(
        select(models.CostIndex)
        .where(
            models.CostIndex.index_name == index_name,
            models.CostIndex.period >= _dt.date(year, 1, 1),
            models.CostIndex.period <= _dt.date(year, 12, 31),
        )
        .order_by(models.CostIndex.period.asc())
    ).first()
    if row is None:
        raise CostDataMissing(f"index '{index_name}' has no value for {year}")
    return float(row.value)


def get_contingency(session: Session, aace_class: int = 5) -> models.EconomicFactor:
    # Prefer the row for the requested AACE class; fall back to any contingency.
    stmt = select(models.EconomicFactor).where(
        models.EconomicFactor.factor_type == "contingency"
    )
    row = session.scalars(
        stmt.where(models.EconomicFactor.aace_class == aace_class)
    ).first() or session.scalars(stmt).first()
    if row is None:
        raise CostDataMissing("no contingency economic factor")
    return row


BASE_REGION = "US-GC"


def get_location_drivers(session: Session, region: str) -> dict[str, float]:
    rows = session.scalars(
        select(models.LocationDriver).where(
            models.LocationDriver.region == region
        )
    ).all()
    if not rows:
        raise CostDataMissing(f"no location drivers for region '{region}'")
    return {r.driver_type: float(r.value) for r in rows}


def location_factor(
    session: Session, region: str, material_split: float = 0.6
) -> float:
    """
    Composed location factor (NOT a hardcoded country constant). Splits cost into
    a material/equipment portion and a labor portion, each scaled by inspectable
    drivers:

        material term = material_split * material_index * fx * freight_duty
        labor term    = (1-material_split) * labor_rate / productivity
        factor        = material term + labor term

    Base region (US-GC) has all drivers = 1.0 -> factor = 1.0. Changing any driver
    changes the factor, so locations respond to driver edits.
    """
    if region == BASE_REGION:
        return 1.0
    d = get_location_drivers(session, region)
    material = material_split * d["material_index"] * d["fx"] * d["freight_duty"]
    labor = (1 - material_split) * d["labor_rate"] / d["productivity"]
    return material + labor


# Size-unit conversions for cross-source blending (SI input -> each correlation's
# native unit). Only the quantities with multiple unit systems need entries.
_SIZE_CONVERT = {
    ("m2", "ft2"): 10.76391, ("ft2", "m2"): 1 / 10.76391,
    ("kW", "hp"): 1.341022, ("hp", "kW"): 1 / 1.341022,
}


def _convert_size(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit:
        return value
    factor = _SIZE_CONVERT.get((from_unit, to_unit))
    if factor is None:
        raise costing.CostingError(f"no size conversion {from_unit} -> {to_unit}")
    return value * factor


def get_unit_map(session: Session, jasper_unit_type: str) -> models.UnitCostMap:
    row = session.scalars(
        select(models.UnitCostMap).where(
            models.UnitCostMap.jasper_unit_type == jasper_unit_type
        )
    ).first()
    if row is None:
        raise CostDataMissing(
            f"no cost mapping for Jasper unit type '{jasper_unit_type}'"
        )
    return row


def cost_unit(
    session: Session,
    jasper_unit_type: str,
    size: float,
    material: Optional[str] = None,
    pressure: float = 0.0,
    base_type: Optional[str] = None,
    region: str = BASE_REGION,
    aace_class: int = 5,
) -> dict[str, Any]:
    """Cost a Jasper flowsheet unit by its schema.ts type, via unit_cost_map."""
    um = get_unit_map(session, jasper_unit_type)

    if not um.cost_bearing:
        return {
            "jasper_unit_type": jasper_unit_type,
            "cost_bearing": False,
            "total_module_cost": 0.0,
            "note": um.notes or "non-physical / connector — no equipment cost",
        }

    if um.equipment_type is None:  # CustomUnit → resolve via its baseType
        if not base_type:
            raise CostDataMissing(
                f"{jasper_unit_type} needs base_type to resolve its correlation"
            )
        result = cost_unit(session, base_type, size, material, pressure,
                           region=region, aace_class=aace_class)
        result["jasper_unit_type"] = jasper_unit_type
        result["resolved_via"] = base_type
        return result

    result = cost_equipment(
        session, um.equipment_type, um.default_subtype,
        material or um.default_material, size, pressure,
        region=region, aace_class=aace_class,
    )
    result["jasper_unit_type"] = jasper_unit_type
    result["cost_bearing"] = True
    return result


_PROVENANCED_TABLES = {
    "equipment_correlations": "EquipmentCorrelation",
    "material_factors": "MaterialFactor",
    "chemicals": "Chemical",
    "chemical_prices": "ChemicalPrice",
    "utilities": "Utility",
    "location_drivers": "LocationDriver",
    "economic_factors": "EconomicFactor",
    "cost_index": "CostIndex",
    "unit_cost_map": "UnitCostMap",
}


def source_registry(session: Session) -> list[dict[str, Any]]:
    """The B1 source registry: every source + license + where it's used."""
    from sqlalchemy import func

    out: list[dict[str, Any]] = []
    for src in session.scalars(
        select(models.Source).order_by(models.Source.slug)
    ).all():
        used: dict[str, int] = {}
        for tname, cls in _PROVENANCED_TABLES.items():
            model = getattr(models, cls)
            n = session.scalar(
                select(func.count()).select_from(model).where(
                    model.source_id == src.id
                )
            )
            if n:
                used[tname] = int(n)
        out.append({
            "slug": src.slug,
            "title": src.title,
            "source_type": src.source_type,
            "license": src.license,
            "url": src.url,
            "reference_citation": src.reference_citation,
            "accessed_on": src.accessed_on.isoformat() if src.accessed_on else None,
            "used_in": used,
        })
    return out


def coverage_report(session: Session) -> list[dict[str, Any]]:
    """Every mapped Jasper unit type and whether its correlation is sourced."""
    out: list[dict[str, Any]] = []
    for um in session.scalars(
        select(models.UnitCostMap).order_by(models.UnitCostMap.jasper_unit_type)
    ).all():
        covered = True
        if um.cost_bearing and um.equipment_type is not None:
            try:
                get_correlation(session, um.equipment_type, um.default_subtype)
                get_material_factor(
                    session, um.equipment_type, um.default_subtype, um.default_material
                )
            except CostDataMissing:
                covered = False
        out.append({
            "jasper_unit_type": um.jasper_unit_type,
            "cost_bearing": um.cost_bearing,
            "equipment_type": um.equipment_type,
            "subtype": um.default_subtype,
            "covered": covered if um.cost_bearing else None,
        })
    return out


COLUMN_TYPES = {
    "DistillationColumn", "ShortcutDistillation", "ReactiveDistillation",
    "Absorber", "Stripper",
}


def cost_column(
    session: Session,
    jasper_unit_type: str,
    shell_volume: float,
    diameter_m: float,
    n_stages: int = 1,
    tray_type: str = "Sieve",
    tray_material: str = "CarbonSteel",
    material: Optional[str] = None,
    pressure: float = 0.0,
    region: str = BASE_REGION,
    aace_class: int = 5,
    internals: str = "trays",
    packed_height_m: Optional[float] = None,
    packing_type: str = "Random",
    packing_material: str = "Metal",
) -> dict[str, Any]:
    """
    Column cost = shell (Vessel) + internals, combined at bare-module.
    internals='trays' (n_stages trays) or 'packing' (packed bed). Trays and
    packing are both location-scaled; shell is scaled inside cost_equipment.
    """
    um = get_unit_map(session, jasper_unit_type)
    if um.equipment_type is None:
        raise CostDataMissing(f"{jasper_unit_type} is not a shell-based column")

    shell = cost_equipment(
        session, um.equipment_type, um.default_subtype,
        material or um.default_material, shell_volume, pressure,
        region=region, aace_class=aace_class,
    )
    idx = get_current_index(session)
    cont = get_contingency(session, aace_class)
    loc = location_factor(session, region)

    result = {
        "jasper_unit_type": jasper_unit_type, "cost_bearing": True,
        "shell_volume": shell_volume, "diameter_m": diameter_m,
        "internals": internals, "currency": shell["currency"],
        "shell_bare_module_cost": shell["bare_module_cost"],
        "accuracy_class": shell["accuracy_class"],
        "uses_estimated_inputs": shell["uses_estimated_inputs"],
    }

    if internals == "packing":
        pk = get_correlation(session, "ColumnPacking", "Standard")
        pk_base = get_index_value_at_year(session, idx.index_name, pk.base_index_year)
        if packed_height_m is None:  # default: full column height
            packed_height_m = shell_volume / (3.141592653589793 / 4 * diameter_m ** 2)
        internals_cost = costing.cost_packing(
            diameter_m, packed_height_m, packing_type, packing_material,
            pk.coeff, float(idx.value), pk_base,
        ) * loc
        result.update({
            "packed_height_m": round(packed_height_m, 3),
            "packing_type": packing_type, "packing_material": packing_material,
            "internals_cost": round(internals_cost, 2),
            "internals_source": pk.source.slug,
        })
    else:  # trays
        trays_corr = get_correlation(session, "ColumnTrays", "Standard")
        tr_base = get_index_value_at_year(session, idx.index_name, trays_corr.base_index_year)
        internals_cost = costing.cost_trays(
            diameter_m * 3.280839895, n_stages, tray_type, tray_material,
            trays_corr.coeff, float(idx.value), tr_base,
        ) * loc
        result.update({
            "n_stages": n_stages, "tray_type": tray_type, "tray_material": tray_material,
            "trays_cost": round(internals_cost, 2),
            "internals_cost": round(internals_cost, 2),
            "internals_source": trays_corr.source.slug,
        })

    column_bm = shell["bare_module_cost"] + internals_cost
    result["bare_module_cost"] = round(column_bm, 2)
    result["total_module_cost"] = round(column_bm * (1 + float(cont.value)), 2)
    result["provenance"] = {
        "shell": shell["provenance"]["correlation"],
        "internals": result["internals_source"],
        "cost_index": idx.source.slug,
        "contingency": cont.source.slug,
    }
    return result


# --------------------------------------------------------------------------- #
# Overrides (B6) — append-only event log + resolver
# --------------------------------------------------------------------------- #
def record_override(
    session: Session,
    target_table: str,
    target_key: dict[str, Any],
    field: str,
    new_value: dict[str, Any],
    *,
    scope: str = "scenario",
    scope_ref: Optional[str] = None,
    old_value: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    actor: Optional[str] = None,
    basis_date=None,
) -> models.Override:
    """Append an override event (the table is append-only; never updated)."""
    ov = models.Override(
        scope=scope, scope_ref=scope_ref, target_table=target_table,
        target_key=target_key, field=field, old_value=old_value,
        new_value=new_value, reason=reason, context=context, actor=actor,
        basis_date=basis_date,
    )
    session.add(ov)
    session.flush()
    return ov


def resolve_override(
    session: Session,
    target_table: str,
    target_key: dict[str, Any],
    field: str,
    *,
    scope: str = "scenario",
    scope_ref: Optional[str] = None,
) -> Optional[models.Override]:
    """Latest matching override event, or None. Append-only → newest wins."""
    stmt = select(models.Override).where(
        models.Override.target_table == target_table,
        models.Override.field == field,
        models.Override.scope == scope,
        models.Override.target_key.contains(target_key),
    )
    if scope_ref is not None:
        stmt = stmt.where(models.Override.scope_ref == scope_ref)
    return session.scalars(
        stmt.order_by(models.Override.created_at.desc(), models.Override.id.desc())
    ).first()


def resolve_effective_override(
    session: Session,
    target_table: str,
    target_key: dict[str, Any],
    field: str,
    *,
    scenario_ref: Optional[str] = None,
    project_ref: Optional[str] = None,
) -> tuple[Optional[models.Override], Optional[str]]:
    """
    Walk override precedence: scenario (most specific) → project → global.
    Returns (override, scope) for the first match, or (None, None).
    """
    chain = [
        ("scenario", scenario_ref),
        ("project", project_ref),
        ("global", None),
    ]
    for scope, ref in chain:
        if scope != "global" and ref is None:
            continue
        ov = resolve_override(session, target_table, target_key, field,
                              scope=scope, scope_ref=ref)
        if ov is not None:
            return ov, scope
    return None, None


# --------------------------------------------------------------------------- #
# Prices (B5) — override-aware; two-factor utilities respond to fuel price
# --------------------------------------------------------------------------- #
def get_chemical_price(
    session: Session, cas: str, region: Optional[str] = None,
    scenario_ref: Optional[str] = None, project_ref: Optional[str] = None,
) -> dict[str, Any]:
    """Effective chemical price: override (scenario→project→global) beats default."""
    key = {"cas": cas, "region": region}
    ov, scope = resolve_effective_override(
        session, "chemical_prices", key, "price",
        scenario_ref=scenario_ref, project_ref=project_ref,
    )
    if ov is not None:
        v = ov.new_value
        return {"price": float(v["price"]), "unit": v.get("unit"),
                "layer": "override", "override_scope": scope,
                "source": "user-override"}

    chem = session.scalars(
        select(models.Chemical).where(models.Chemical.cas_number == cas)
    ).first()
    if chem is None:
        raise CostDataMissing(f"no chemical with CAS {cas}")
    stmt = select(models.ChemicalPrice).where(
        models.ChemicalPrice.chemical_id == chem.id
    )
    if region is not None:
        stmt = stmt.where(models.ChemicalPrice.region == region)
    price = session.scalars(
        stmt.order_by(models.ChemicalPrice.as_of_date.desc())
    ).first()
    if price is None:
        raise CostDataMissing(f"no price for CAS {cas} (region={region})")
    return {"price": float(price.price), "unit": price.price_unit,
            "layer": "default", "source": price.source.slug}


def get_utility_cost(
    session: Session, utility_type: str, region: Optional[str] = None,
    fuel_price: Optional[float] = None, scenario_ref: Optional[str] = None,
    project_ref: Optional[str] = None,
) -> dict[str, Any]:
    """
    Effective utility price. Two-factor utilities (capital + fuel-coupled energy)
    recompute when the fuel price changes:  price = capital + energy_coeff * fuel.
    Override (scenario→project→global) beats default.
    """
    key = {"utility_type": utility_type, "region": region}
    ov, scope = resolve_effective_override(
        session, "utilities", key, "price",
        scenario_ref=scenario_ref, project_ref=project_ref,
    )
    if ov is not None:
        return {"price": float(ov.new_value["price"]), "unit": ov.new_value.get("unit"),
                "layer": "override", "override_scope": scope,
                "source": "user-override"}

    stmt = select(models.Utility).where(models.Utility.utility_type == utility_type)
    if region is not None:
        stmt = stmt.where(models.Utility.region == region)
    util = session.scalars(stmt).first()
    if util is None:
        raise CostDataMissing(f"no utility '{utility_type}' (region={region})")

    if util.two_factor:
        tf = util.two_factor
        if fuel_price is None:
            fuel = get_utility_cost(session, tf["fuel"], region,
                                    scenario_ref=scenario_ref,
                                    project_ref=project_ref)
            fuel_price = fuel["price"]
        price = float(tf["capital"]) + float(tf["energy_coeff"]) * fuel_price
        return {"price": round(price, 4), "unit": util.price_unit,
                "layer": "two_factor", "source": util.source.slug,
                "fuel": tf["fuel"], "fuel_price": fuel_price}
    return {"price": float(util.price), "unit": util.price_unit,
            "layer": "default", "source": util.source.slug}


def cost_equipment(
    session: Session,
    equipment_type: str,
    subtype: str,
    material: str,
    size: float,
    pressure: float = 0.0,
    source: Optional[str] = None,
    index_name: str = DEFAULT_INDEX,
    region: str = BASE_REGION,
    aace_class: int = 5,
) -> dict[str, Any]:
    """
    Cost one unit from sourced data. Returns cost + provenance + accuracy.

    Escalation uses the ratio of ``index_name`` (default the Jasper Cost Index)
    between the correlation's base year and the latest available period — never
    a stored CEPCI magnitude. ``index_name`` is the override hook: a user with a
    CEPCI license can load a 'cepci-licensed' series and pass it here.
    """
    corr = get_correlation(session, equipment_type, subtype, source)
    mf = get_material_factor(session, equipment_type, subtype, material)
    idx = get_current_index(session, index_name)
    base_index = get_index_value_at_year(session, index_name, corr.base_index_year)
    cont = get_contingency(session, aace_class)
    loc = location_factor(session, region)

    inp = costing.CostInputs(
        functional_form=corr.functional_form,
        coeff=corr.coeff,
        base_index_value=base_index,
        Fm=_scalar_factor(mf, size),
        size=size,
        pressure=pressure,
        index_now=float(idx.value),
        contingency=float(cont.value),
        bare_module=corr.bare_module,
        pressure_model=corr.pressure_model,
        size_min=float(corr.size_min) if corr.size_min is not None else None,
        size_max=float(corr.size_max) if corr.size_max is not None else None,
    )
    result = costing.compute_cost(inp)
    prov = Provenance(
        correlation=corr.source.slug,
        material_factor=mf.source.slug,
        cost_index=idx.source.slug,
        contingency=cont.source.slug,
    )
    return {
        "equipment_type": equipment_type,
        "subtype": subtype,
        "material": material,
        "size": size,
        "size_unit": corr.size_unit,
        "pressure": pressure,
        "currency": corr.currency,
        "region": region,
        "location_factor": round(loc, 4),
        "aace_class": aace_class,
        "purchased_cost": round(result.purchased, 2),
        "bare_module_cost": round(result.bare_module * loc, 2),
        "total_module_cost": round(result.total_module * loc, 2),
        "Fp": round(result.Fp, 4),
        "Fm": round(result.Fm, 4),
        "functional_form": result.functional_form,
        "basis_note": result.basis_note,
        "accuracy_class": result.accuracy_class,
        "in_range": result.in_range,
        "range_note": result.range_note,
        "provenance": {
            "correlation": prov.correlation,
            "material_factor": prov.material_factor,
            "cost_index": prov.cost_index,
            "contingency": prov.contingency,
        },
        # Honest surfacing: anything 'estimated' taints the defensibility.
        "uses_estimated_inputs": idx.source.source_type == "estimated",
    }


# --------------------------------------------------------------------------- #
# Project estimate (B7) — ties CAPEX (equipment) to OPEX (prices/utilities)
# --------------------------------------------------------------------------- #
def estimate_project(
    session: Session,
    equipment: list[dict[str, Any]],
    feeds: Optional[list[dict[str, Any]]] = None,
    products: Optional[list[dict[str, Any]]] = None,
    utilities: Optional[list[dict[str, Any]]] = None,
    *,
    region: str = BASE_REGION,
    aace_class: int = 5,
    scenario_ref: Optional[str] = None,
    project_ref: Optional[str] = None,
) -> dict[str, Any]:
    """
    End-to-end estimate. CAPEX = sum of equipment total-module costs (correlations
    x Jasper index x location x contingency). OPEX/revenue = annual chemical/
    utility flows x effective (override-aware) prices.

    equipment: [{id?, type, size, material?, pressure?, base_type?} |
                {id?, type, column:True, shell_volume, diameter_m, n_stages, ...}]
    feeds/products: [{id?, cas, annual_kg}]
    utilities: [{id?, utility_type, annual}]

    Optional `id` on any item is echoed into its breakdown row so callers can
    map results back (e.g. to flowsheet node ids). Items whose data is missing
    become {gap: True, reason} rows + entries in the top-level `gaps` list and
    are excluded from all totals — one bad item never sinks the estimate.
    """
    feeds = feeds or []
    products = products or []
    utilities = utilities or []

    # Gap-tolerant: a single uncovered unit or unpriced chemical must not sink
    # the whole estimate — it becomes a gap row, excluded from every total.
    gaps: list[dict[str, Any]] = []

    capex_total = 0.0
    capex_breakdown = []
    # Keys an item carries through from cost_unit/cost_column when present
    # (plain and column results differ; columns add internals fields).
    _ITEM_KEYS = (
        "cost_bearing", "purchased_cost", "bare_module_cost", "material",
        "accuracy_class", "in_range", "provenance", "uses_estimated_inputs",
        "resolved_via", "n_stages", "internals", "internals_cost",
        "internals_source", "note",
    )
    for u in equipment:
        try:
            if u.get("column"):
                r = cost_column(
                    session, u["type"], u["shell_volume"], u["diameter_m"],
                    u["n_stages"], tray_type=u.get("tray_type", "Sieve"),
                    tray_material=u.get("tray_material", "CarbonSteel"),
                    material=u.get("material"), pressure=u.get("pressure", 0.0),
                    region=region, aace_class=aace_class,
                )
            else:
                if "size" not in u:
                    raise CostDataMissing(f"{u.get('type')} item has no size")
                r = cost_unit(
                    session, u["type"], u["size"], material=u.get("material"),
                    pressure=u.get("pressure", 0.0),
                    base_type=u.get("base_type"), region=region,
                    aace_class=aace_class,
                )
        except CostDataMissing as exc:
            capex_breakdown.append({"id": u.get("id"), "type": u.get("type"),
                                    "gap": True, "reason": str(exc)})
            gaps.append({"id": u.get("id"), "kind": "equipment",
                         "ref": u.get("type"), "reason": str(exc)})
            continue
        capex_total += r["total_module_cost"]
        item: dict[str, Any] = {
            "id": u.get("id"), "type": u["type"],
            "total_module_cost": r["total_module_cost"],
        }
        if "size" in u:
            item["size"] = u["size"]
        for k in _ITEM_KEYS:
            if k in r:
                item[k] = r[k]
        capex_breakdown.append(item)

    def _chem_total(items, kind):
        total, detail = 0.0, []
        for it in items:
            try:
                p = get_chemical_price(session, it["cas"], region, scenario_ref,
                                       project_ref)
            except CostDataMissing as exc:
                detail.append({"id": it.get("id"), "cas": it.get("cas"),
                               "gap": True, "reason": str(exc)})
                gaps.append({"id": it.get("id"), "kind": kind,
                             "ref": it.get("cas"), "reason": str(exc)})
                continue
            cost = p["price"] * it["annual_kg"]
            total += cost
            detail.append({"id": it.get("id"), "cas": it["cas"],
                           "annual_kg": it["annual_kg"],
                           "annual_cost": round(cost, 2),
                           "price": p["price"], "unit": p.get("unit"),
                           "source": p.get("source"), "layer": p["layer"]})
        return total, detail

    feed_cost, feed_detail = _chem_total(feeds, "feed")
    revenue, revenue_detail = _chem_total(products, "product")

    util_cost, util_detail = 0.0, []
    for ut in utilities:
        try:
            p = get_utility_cost(session, ut["utility_type"], region,
                                 scenario_ref=scenario_ref,
                                 project_ref=project_ref)
        except CostDataMissing as exc:
            util_detail.append({"id": ut.get("id"),
                                "utility_type": ut.get("utility_type"),
                                "gap": True, "reason": str(exc)})
            gaps.append({"id": ut.get("id"), "kind": "utility",
                         "ref": ut.get("utility_type"), "reason": str(exc)})
            continue
        cost = p["price"] * ut["annual"]
        util_cost += cost
        util_detail.append({"id": ut.get("id"),
                            "utility_type": ut["utility_type"],
                            "annual": ut["annual"],
                            "annual_cost": round(cost, 2), "price": p["price"],
                            "unit": p.get("unit"), "source": p.get("source"),
                            "layer": p["layer"]})

    gross_margin = revenue - feed_cost - util_cost
    # Honest: chemical prices are representative (literature), not feed-sourced.
    representative_prices = any(
        d.get("layer") == "default" for d in (feed_detail + revenue_detail)
    )
    n_items = len(equipment) + len(feeds) + len(products) + len(utilities)
    return {
        "region": region,
        "aace_class": aace_class,
        "currency": "USD",
        "capex_total_module": round(capex_total, 2),
        "annual_feed_cost": round(feed_cost, 2),
        "annual_revenue": round(revenue, 2),
        "annual_utility_cost": round(util_cost, 2),
        "gross_annual_margin": round(gross_margin, 2),
        "accuracy_class": costing.ACCURACY_CLASS,
        "uses_representative_prices": representative_prices,
        "gaps": gaps,
        "n_costed": n_items - len(gaps),
        "n_gaps": len(gaps),
        "breakdown": {
            "capex": capex_breakdown,
            "feeds": feed_detail,
            "products": revenue_detail,
            "utilities": util_detail,
        },
    }


# --------------------------------------------------------------------------- #
# Multi-source blended estimate (C1) — value + inter-source range
# --------------------------------------------------------------------------- #
def blended_purchased_cost(
    session: Session,
    equipment_type: str,
    size_si: float,
    si_unit: str,
    subtype: Optional[str] = None,
    material: str = "CarbonSteel",
    index_name: str = DEFAULT_INDEX,
) -> dict[str, Any]:
    """
    Blend purchased cost across ALL sources for a unit. Each source's correlation
    is evaluated at the same physical size (converted to its native unit) and
    escalated to now; the result reports the geometric-mean estimate plus the
    inter-source low/high range (the conflict report, as a feature).

    Purchased cost is the comparison point — that's where sources genuinely
    disagree; downstream bare-module/location/contingency factors apply on top.
    """
    import math

    corrs = get_all_correlations(session, equipment_type, subtype)
    if not corrs:
        raise CostDataMissing(f"no correlations for {equipment_type}")

    per_source = []
    for c in corrs:
        size = _convert_size(size_si, si_unit, c.size_unit)
        try:
            r = cost_equipment(session, equipment_type, c.subtype, material, size,
                               source=c.source.slug, index_name=index_name)
        except CostDataMissing:
            continue  # material not defined for this source's subtype — skip
        per_source.append({
            "source": c.source.slug, "subtype": c.subtype,
            "size": round(size, 4), "size_unit": c.size_unit,
            "purchased": r["purchased_cost"],
        })
    if not per_source:
        raise CostDataMissing(
            f"no costable correlation for {equipment_type} (material {material})"
        )

    vals = [p["purchased"] for p in per_source]
    estimate = math.exp(sum(math.log(v) for v in vals) / len(vals))  # geomean
    low, high = min(vals), max(vals)
    return {
        "equipment_type": equipment_type,
        "subtype": subtype,
        "size_si": size_si,
        "si_unit": si_unit,
        "currency": "USD",
        "n_sources": len(per_source),
        "estimate": round(estimate, 2),
        "low": round(low, 2),
        "high": round(high, 2),
        "spread_pct": round(100.0 * (high - low) / estimate, 1) if estimate else 0.0,
        "accuracy_class": costing.ACCURACY_CLASS,
        "per_source": per_source,
    }
