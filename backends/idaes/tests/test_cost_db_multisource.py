"""
C1: multi-source correlations + blended estimate.

  - overlap classes (HX, compressor) have >1 source; blend returns value + range,
  - single-source units return a point estimate,
  - the geomean estimate sits within [low, high],
  - the primary correlation is deterministic (first-seeded = Turton) so existing
    single-source costing is unchanged,
  - the per-unit spread reflects real inter-source disagreement.

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
        s.close()


def test_hx_has_two_sources_blended(session):
    from app.tea import repository as repo

    r = repo.blended_purchased_cost(session, "HeatExchanger", 100.0, "m2",
                                    subtype="FloatingHead")
    assert r["n_sources"] == 2
    sources = {p["source"] for p in r["per_source"]}
    assert sources == {"turton", "idaes-sslw"}
    assert r["low"] <= r["estimate"] <= r["high"]


def test_compressor_spread_is_informative(session):
    from app.tea import repository as repo

    r = repo.blended_purchased_cost(session, "Compressor", 1000.0, "kW",
                                    subtype="Centrifugal")
    assert r["n_sources"] == 2
    # Real inter-source disagreement (~2x) -> a wide, informative range.
    assert r["spread_pct"] > 30.0


def test_vessel_and_pump_now_multisource(session):
    from app.tea import repository as repo

    # C4: vessel (volume->geometry->weight) and pump (power->size-factor) now
    # have an SSLW second source.
    ves = repo.blended_purchased_cost(session, "Vessel", 20.0, "m3", subtype="Vertical")
    pump = repo.blended_purchased_cost(session, "Pump", 50.0, "kW", subtype="Centrifugal")
    assert ves["n_sources"] == 2 and pump["n_sources"] == 2
    assert {p["source"] for p in ves["per_source"]} == {"turton", "idaes-sslw"}
    # Vessel costing is method-sensitive — the range is wide and honest.
    assert ves["spread_pct"] > 50.0


def test_single_source_is_point_estimate(session):
    from app.tea import repository as repo

    # Reactor has only the Turton source -> a point estimate.
    r = repo.blended_purchased_cost(session, "Reactor", 10.0, "m3",
                                    subtype="JacketedAgitated")
    assert r["n_sources"] == 1
    assert r["low"] == r["high"] == r["estimate"]
    assert r["spread_pct"] == 0.0


def test_estimate_is_geomean(session):
    import math

    from app.tea import repository as repo

    r = repo.blended_purchased_cost(session, "Compressor", 1000.0, "kW",
                                    subtype="Centrifugal")
    vals = [p["purchased"] for p in r["per_source"]]
    geomean = math.exp(sum(math.log(v) for v in vals) / len(vals))
    assert r["estimate"] == pytest.approx(geomean, rel=1e-3)


def test_primary_correlation_deterministic(session):
    from app.tea import repository as repo

    # Single-source cost_equipment still resolves to Turton (first-seeded) — so
    # adding SSLW didn't change existing costing.
    corr = repo.get_correlation(session, "HeatExchanger", "FloatingHead")
    assert corr.source.slug == "turton"


def test_blended_route(seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/api/tea/cost-blended", params={
        "equipment_type": "HeatExchanger", "size": 100.0, "si_unit": "m2",
        "subtype": "FloatingHead",
    })
    assert r.status_code == 200, r.text
    assert r.json()["n_sources"] == 2
