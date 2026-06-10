"""
B2 coverage tests: every Jasper unit type maps to a correlation or is an
explicit non-cost connector — no silent gaps. The expected unit list is pinned
here, so adding a UnitType in schema.ts without mapping it fails this test.

Requires DATABASE_URL. Module ensures schema + loads the seed.
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

# Pinned mirror of site/src/core/schema.ts UnitTypeSchema (keep in sync).
JASPER_UNIT_TYPES = {
    "Feed", "Mixer", "Splitter", "Flash", "Pump", "Compressor", "Expander",
    "Valve", "Heater", "Cooler", "HeatExchanger", "PipeSegment", "Absorber",
    "Stripper", "DistillationColumn", "ShortcutDistillation",
    "ReactiveDistillation", "Reactor", "RCSTR", "RPfr", "RBatch", "RStoic",
    "RYield", "REquil", "RGibbs", "Separator", "ThreePhaseSeparator", "Sink",
    "TextBox", "CustomUnit",
}


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


def test_every_jasper_unit_type_is_mapped(session):
    from app.tea import repository as repo

    mapped = {r["jasper_unit_type"] for r in repo.coverage_report(session)}
    missing = JASPER_UNIT_TYPES - mapped
    assert not missing, f"unmapped Jasper unit types (add to unit_cost_map): {missing}"


def test_no_silent_coverage_gaps(session):
    from app.tea import repository as repo

    report = repo.coverage_report(session)
    # Every cost-bearing mapping (except CustomUnit, which resolves at runtime)
    # must point at a sourced correlation + material factor.
    uncovered = [
        r["jasper_unit_type"]
        for r in report
        if r["cost_bearing"] and r["equipment_type"] is not None and not r["covered"]
    ]
    assert not uncovered, f"cost-bearing units with no sourced correlation: {uncovered}"


def test_cost_distillation_column(session):
    from app.tea import repository as repo

    r = repo.cost_unit(session, "DistillationColumn", size=30.0, pressure=3.0)
    assert r["cost_bearing"] is True
    assert r["equipment_type"] == "Vessel" and r["subtype"] == "Vertical"
    assert r["total_module_cost"] > 0


def test_cost_expander_uses_turbine(session):
    from app.tea import repository as repo

    r = repo.cost_unit(session, "Expander", size=500.0)
    assert r["equipment_type"] == "Turbine"
    assert r["functional_form"] == "sslw_ln"
    assert r["total_module_cost"] > 0


def test_non_cost_unit_returns_zero(session):
    from app.tea import repository as repo

    for ut in ("Valve", "Splitter", "Feed", "PipeSegment"):
        r = repo.cost_unit(session, ut, size=1.0)
        assert r["cost_bearing"] is False
        assert r["total_module_cost"] == 0.0


def test_custom_unit_resolves_via_base_type(session):
    from app.tea import repository as repo

    with pytest.raises(repo.CostDataMissing):
        repo.cost_unit(session, "CustomUnit", size=10.0)  # no base_type
    r = repo.cost_unit(session, "CustomUnit", size=10.0, base_type="Pump")
    assert r["resolved_via"] == "Pump"
    assert r["total_module_cost"] > 0
