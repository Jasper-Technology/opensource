"""
B4: materials / factors / location.

  - location factor is COMPOSED from inspectable drivers (not a country constant),
  - a non-base region's factor responds to driver changes,
  - costs scale with region,
  - contingency varies by AACE class,
  - documented economic defaults are present + sourced.

Requires DATABASE_URL.
"""
from __future__ import annotations

import importlib.util
import os

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — cost DB unavailable",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_BACKEND_DIR)


def _load_seed_module():
    path = os.path.join(_REPO, "cost-db", "load.py")
    spec = importlib.util.spec_from_file_location("cost_db_load", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def seeded():
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    loadmod = _load_seed_module()
    from app.tea import db

    seed = loadmod._merge_seed_files()
    with Session(bind=db.get_engine()) as s:
        loadmod.load(s, seed)
    yield


@pytest.fixture
def session(seeded):
    from app.tea import db

    s = Session(bind=db.get_engine())
    try:
        yield s
    finally:
        s.close()


def test_base_region_factor_is_one(session):
    from app.tea import repository as repo

    assert repo.location_factor(session, "US-GC") == 1.0


def test_alternate_region_composed_from_drivers(session):
    from app.tea import repository as repo

    d = repo.get_location_drivers(session, "US-MW")
    # factor = 0.6*material_index*fx*freight_duty + 0.4*labor_rate/productivity
    expected = (0.6 * d["material_index"] * d["fx"] * d["freight_duty"]
                + 0.4 * d["labor_rate"] / d["productivity"])
    assert repo.location_factor(session, "US-MW") == pytest.approx(expected)
    assert repo.location_factor(session, "US-MW") > 1.0  # MW pricier than GC


def test_factor_responds_to_driver_change(session):
    from app.tea import models, repository as repo

    before = repo.location_factor(session, "US-MW")
    row = session.scalars(
        select(models.LocationDriver).where(
            models.LocationDriver.region == "US-MW",
            models.LocationDriver.driver_type == "labor_rate",
        )
    ).one()
    row.value = float(row.value) + 0.20  # bump labor rate
    session.flush()
    after = repo.location_factor(session, "US-MW")
    session.rollback()
    assert after > before  # higher labor rate -> higher location factor


def test_cost_scales_with_region(session):
    from app.tea import repository as repo

    gc = repo.cost_equipment(session, "Vessel", "Vertical", "CarbonSteel", 20.0)
    mw = repo.cost_equipment(session, "Vessel", "Vertical", "CarbonSteel", 20.0,
                             region="US-MW")
    assert mw["total_module_cost"] > gc["total_module_cost"]
    assert mw["location_factor"] > 1.0 and gc["location_factor"] == 1.0
    # purchased (FOB equipment) is location-independent; install/bare-module isn't.
    assert mw["purchased_cost"] == pytest.approx(gc["purchased_cost"])


def test_contingency_varies_by_aace_class(session):
    from app.tea import repository as repo

    c5 = repo.cost_equipment(session, "Pump", "Centrifugal", "CastIron", 50.0,
                             aace_class=5)
    c4 = repo.cost_equipment(session, "Pump", "Centrifugal", "CastIron", 50.0,
                             aace_class=4)
    # Class 4 (0.15) < Class 5 (0.18) contingency -> lower total.
    assert c4["total_module_cost"] < c5["total_module_cost"]
    assert c4["bare_module_cost"] == pytest.approx(c5["bare_module_cost"])


def test_eu_region_composed_with_fx_and_freight(session):
    from app.tea import repository as repo

    d = repo.get_location_drivers(session, "EU")
    assert d["fx"] != 1.0 and d["freight_duty"] != 1.0  # actually exercised
    expected = (0.6 * d["material_index"] * d["fx"] * d["freight_duty"]
                + 0.4 * d["labor_rate"] / d["productivity"])
    assert repo.location_factor(session, "EU") == pytest.approx(expected)
    assert repo.location_factor(session, "EU") > 1.0


def test_eu_drivers_are_sourced(session):
    from sqlalchemy import select

    from app.tea import models

    rows = session.scalars(
        select(models.LocationDriver).where(models.LocationDriver.region == "EU")
    ).all()
    assert rows and all(r.source.slug == "eurostat-ecb" for r in rows)


def test_fx_term_moves_eu_factor(session):
    from sqlalchemy import select

    from app.tea import models, repository as repo

    before = repo.location_factor(session, "EU")
    fx = session.scalars(
        select(models.LocationDriver).where(
            models.LocationDriver.region == "EU",
            models.LocationDriver.driver_type == "fx",
        )
    ).one()
    fx.value = float(fx.value) + 0.10  # stronger EUR
    session.flush()
    after = repo.location_factor(session, "EU")
    session.rollback()
    assert after > before  # FX term is live (it was inert when all regions had fx=1)


def test_economic_defaults_present(session):
    from app.tea import models

    types = set(session.scalars(
        select(models.EconomicFactor.factor_type)
    ).all())
    assert {"contingency", "tax_rate", "discount_rate"} <= types
