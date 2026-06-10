#!/usr/bin/env python3
"""
Load git-versioned cost-DB seed files into Postgres.

Repo is the source of truth for defaults; this script (re)builds the serving
layer. Idempotent: truncates the seedable tables and re-inserts, so running it
twice yields the same DB. The migration-seeded ``units`` allowlist and the
append-only ``overrides`` log are never touched.

Usage:
    export DATABASE_URL=postgresql+psycopg://costdb:costdb@localhost:5432/costdb
    python cost-db/load.py            # loads cost-db/seed/*.json
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys

# Make app.tea importable (idaes-backend is a sibling of cost-db/).
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "idaes-backend"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.tea import db, models  # noqa: E402

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")

# Truncated (in any order — CASCADE handles FKs) on every load. NOT units /
# overrides / alembic_version.
_SEED_TABLES = [
    "chemical_prices", "utilities", "material_factors", "equipment_correlations",
    "economic_factors", "cost_index", "location_drivers", "unit_cost_map",
    "chemicals", "sources",
]


def _date(value: str | None) -> dt.date | None:
    return dt.date.fromisoformat(value) if value else None


def _merge_seed_files() -> dict[str, list[dict]]:
    """Concatenate every section across all seed JSON files."""
    merged: dict[str, list[dict]] = {}
    files = sorted(glob.glob(os.path.join(SEED_DIR, "*.json")))
    if not files:
        raise SystemExit(f"No seed files in {SEED_DIR}")
    for path in files:
        with open(path) as fh:
            data = json.load(fh)
        for key, rows in data.items():
            if key.startswith("_"):
                continue
            merged.setdefault(key, []).extend(rows)
    return merged


def load(session: Session, seed: dict[str, list[dict]]) -> dict[str, int]:
    session.execute(
        text(f"TRUNCATE {', '.join(_SEED_TABLES)} RESTART IDENTITY CASCADE")
    )

    src_id: dict[str, int] = {}
    for row in seed.get("sources", []):
        obj = models.Source(
            slug=row["slug"], title=row["title"], source_type=row["source_type"],
            license=row["license"], license_url=row.get("license_url"),
            url=row.get("url"), reference_citation=row.get("reference_citation"),
            accessed_on=_date(row.get("accessed_on")), notes=row.get("notes"),
        )
        session.add(obj)
        session.flush()
        src_id[row["slug"]] = obj.id

    cas_id: dict[str, int] = {}
    for row in seed.get("chemicals", []):
        obj = models.Chemical(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            cas_number=row.get("cas_number"), name=row["name"],
            formula=row.get("formula"), component_db_id=row.get("component_db_id"),
            notes=row.get("notes"),
        )
        session.add(obj)
        session.flush()
        if row.get("cas_number"):
            cas_id[row["cas_number"]] = obj.id

    for row in seed.get("equipment_correlations", []):
        session.add(models.EquipmentCorrelation(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            equipment_type=row["equipment_type"], subtype=row["subtype"],
            functional_form=row["functional_form"], size_quantity=row["size_quantity"],
            size_unit=row["size_unit"], size_min=row.get("size_min"),
            size_max=row.get("size_max"), coeff=row["coeff"], currency=row["currency"],
            base_index_name=row["base_index_name"], base_index_value=row["base_index_value"],
            base_index_year=row["base_index_year"], bare_module=row.get("bare_module"),
            pressure_model=row.get("pressure_model"), notes=row.get("notes"),
        ))

    for row in seed.get("material_factors", []):
        session.add(models.MaterialFactor(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            equipment_type=row["equipment_type"], subtype=row["subtype"],
            material=row["material"], factor_model=row["factor_model"],
            notes=row.get("notes"),
        ))

    for row in seed.get("economic_factors", []):
        session.add(models.EconomicFactor(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            factor_type=row["factor_type"], aace_class=row.get("aace_class"),
            value=row["value"], unit=row["unit"], region=row.get("region"),
            notes=row.get("notes"),
        ))

    for row in seed.get("cost_index", []):
        session.add(models.CostIndex(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            index_name=row["index_name"], period=_date(row["period"]),
            value=row["value"], component_weights=row.get("component_weights"),
            notes=row.get("notes"),
        ))

    for row in seed.get("chemical_prices", []):
        session.add(models.ChemicalPrice(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            chemical_id=cas_id[row["chemical_cas"]], price=row["price"],
            currency=row["currency"], price_unit=row["price_unit"],
            region=row.get("region"), price_type=row.get("price_type"),
            as_of_date=_date(row.get("as_of_date")), notes=row.get("notes"),
        ))

    for row in seed.get("utilities", []):
        fuel_cas = row.get("fuel_chemical_cas")
        session.add(models.Utility(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            utility_type=row["utility_type"], price=row["price"],
            currency=row["currency"], price_unit=row["price_unit"],
            region=row.get("region"), two_factor=row.get("two_factor"),
            fuel_chemical_id=cas_id.get(fuel_cas) if fuel_cas else None,
            notes=row.get("notes"),
        ))

    for row in seed.get("location_drivers", []):
        session.add(models.LocationDriver(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            region=row["region"], driver_type=row["driver_type"],
            value=row["value"], unit=row["unit"], notes=row.get("notes"),
        ))

    for row in seed.get("unit_cost_map", []):
        session.add(models.UnitCostMap(
            source_id=src_id[row["source"]], basis_date=_date(row["basis_date"]),
            jasper_unit_type=row["jasper_unit_type"],
            cost_bearing=row.get("cost_bearing", True),
            equipment_type=row.get("equipment_type"),
            default_subtype=row.get("default_subtype"),
            default_material=row.get("default_material"),
            sizing_basis=row.get("sizing_basis"), notes=row.get("notes"),
        ))

    session.commit()
    return {k: len(seed.get(k, [])) for k in (
        "sources", "chemicals", "equipment_correlations", "material_factors",
        "economic_factors", "cost_index", "chemical_prices", "utilities",
        "location_drivers", "unit_cost_map",
    )}


def main() -> None:
    if not db.is_configured():
        raise SystemExit("DATABASE_URL not set — cannot load cost DB.")
    seed = _merge_seed_files()
    with Session(bind=db.get_engine()) as session:
        counts = load(session, seed)
    print("Loaded cost-DB seed:")
    for table, n in counts.items():
        if n:
            print(f"  {table:24s} {n}")


if __name__ == "__main__":
    main()
