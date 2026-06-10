"""
C6: override scope precedence — scenario → project → global → default.

The most specific applicable override wins; price lookups report which scope.

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
CAS = "108-88-3"  # toluene
KEY = {"cas": CAS, "region": "US-GC"}


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


def _ovr(session, scope, ref, price):
    from app.tea import repository as repo

    repo.record_override(session, "chemical_prices", KEY, "price",
                         {"price": price}, scope=scope, scope_ref=ref)
    session.flush()


def test_default_when_no_override(session):
    from app.tea import repository as repo

    p = repo.get_chemical_price(session, CAS, "US-GC", scenario_ref="s1",
                                project_ref="p1")
    assert p["layer"] == "default"


def test_global_applies(session):
    from app.tea import repository as repo

    _ovr(session, "global", None, 0.70)
    p = repo.get_chemical_price(session, CAS, "US-GC", scenario_ref="s1",
                                project_ref="p1")
    assert p["layer"] == "override" and p["override_scope"] == "global"
    assert p["price"] == pytest.approx(0.70)


def test_project_beats_global(session):
    from app.tea import repository as repo

    _ovr(session, "global", None, 0.70)
    _ovr(session, "project", "p1", 0.65)
    p = repo.get_chemical_price(session, CAS, "US-GC", scenario_ref="s1",
                                project_ref="p1")
    assert p["override_scope"] == "project" and p["price"] == pytest.approx(0.65)
    # A different project falls back to global.
    other = repo.get_chemical_price(session, CAS, "US-GC", project_ref="p2")
    assert other["override_scope"] == "global"


def test_scenario_beats_project_beats_global(session):
    from app.tea import repository as repo

    _ovr(session, "global", None, 0.70)
    _ovr(session, "project", "p1", 0.65)
    _ovr(session, "scenario", "s1", 0.55)
    p = repo.get_chemical_price(session, CAS, "US-GC", scenario_ref="s1",
                                project_ref="p1")
    assert p["override_scope"] == "scenario" and p["price"] == pytest.approx(0.55)
    # Same project, different scenario -> project wins.
    p2 = repo.get_chemical_price(session, CAS, "US-GC", scenario_ref="s2",
                                 project_ref="p1")
    assert p2["override_scope"] == "project" and p2["price"] == pytest.approx(0.65)
