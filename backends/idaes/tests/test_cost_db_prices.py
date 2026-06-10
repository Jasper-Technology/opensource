"""
B5 (prices) + B6 (override resolver).

  - chemical/utility prices are sourced (not 'estimated'),
  - two-factor utilities recompute when the fuel price changes,
  - the override resolver returns the effective value + which layer it came from,
  - user override beats public default; append-only newest-wins,
  - the override event log is queryable.

Requires DATABASE_URL.
"""
from __future__ import annotations

import importlib.util
import os

import pytest
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
        s.rollback()
        s.close()


def test_chemical_price_is_sourced(session):
    from app.tea import repository as repo

    p = repo.get_chemical_price(session, "108-88-3", "US-GC")  # toluene
    assert p["layer"] == "default"
    assert p["source"] == "literature-prices"  # not 'estimated-placeholder'
    assert p["price"] > 0 and p["unit"] == "USD/kg"


def test_utility_two_factor_responds_to_fuel(session):
    from app.tea import repository as repo

    low = repo.get_utility_cost(session, "steam_lp", "US-GC", fuel_price=4.0)
    high = repo.get_utility_cost(session, "steam_lp", "US-GC", fuel_price=8.0)
    assert low["layer"] == "two_factor" and low["fuel"] == "natural_gas"
    # price = capital(1.5) + 1.25*fuel  -> 6.5 at 4.0, 11.5 at 8.0
    assert low["price"] == pytest.approx(1.5 + 1.25 * 4.0)
    assert high["price"] == pytest.approx(1.5 + 1.25 * 8.0)
    assert high["price"] > low["price"]


def test_steam_uses_natural_gas_price_by_default(session):
    from app.tea import repository as repo

    natgas = repo.get_utility_cost(session, "natural_gas", "US-GC")["price"]
    steam = repo.get_utility_cost(session, "steam_lp", "US-GC")
    assert steam["fuel_price"] == pytest.approx(natgas)
    assert steam["price"] == pytest.approx(1.5 + 1.25 * natgas)


def test_override_beats_default(session):
    from app.tea import repository as repo

    default = repo.get_chemical_price(session, "108-88-3", "US-GC")
    assert default["layer"] == "default"

    repo.record_override(
        session, "chemical_prices", {"cas": "108-88-3", "region": "US-GC"}, "price",
        {"price": 0.55, "unit": "USD/kg"}, scope="scenario", scope_ref="proj-9",
        reason="negotiated contract", actor="user@example.com",
    )
    session.flush()

    overridden = repo.get_chemical_price(session, "108-88-3", "US-GC", scenario_ref="proj-9")
    assert overridden["layer"] == "override"
    assert overridden["price"] == pytest.approx(0.55)
    # Another scenario still sees the default.
    other = repo.get_chemical_price(session, "108-88-3", "US-GC", scenario_ref="proj-X")
    assert other["layer"] == "default"


def test_override_is_append_only_newest_wins(session):
    from app.tea import repository as repo

    key = {"cas": "71-43-2", "region": "US-GC"}
    repo.record_override(session, "chemical_prices", key, "price",
                         {"price": 1.20}, scope_ref="proj-7", reason="v1")
    repo.record_override(session, "chemical_prices", key, "price",
                         {"price": 1.35}, scope_ref="proj-7", reason="v2")
    session.flush()
    ov = repo.resolve_override(session, "chemical_prices", key, "price",
                               scope_ref="proj-7")
    assert ov.new_value["price"] == 1.35  # newest event wins


def test_override_event_log_queryable(session):
    from sqlalchemy import select

    from app.tea import models, repository as repo

    repo.record_override(session, "chemical_prices",
                         {"cas": "1333-74-0", "region": "US-GC"}, "price",
                         {"price": 1.8}, scope_ref="proj-log",
                         reason="bulk H2 deal", context={"volume_tpa": 5000})
    session.flush()
    rows = session.scalars(
        select(models.Override).where(models.Override.scope_ref == "proj-log")
    ).all()
    assert len(rows) == 1
    ev = rows[0]
    # Clean enough to serve as preference data later.
    assert ev.reason == "bulk H2 deal"
    assert ev.context == {"volume_tpa": 5000}
    assert ev.new_value == {"price": 1.8}
