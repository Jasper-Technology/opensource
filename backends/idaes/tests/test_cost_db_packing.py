"""
C5: packed-column internals (alternative to trays).

  - a packed column = shell + packing > shell alone,
  - structured packing > random; ceramic > metal,
  - packing scales with bed volume (height, diameter^2),
  - route supports internals=packing.

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


def _packed(session, **kw):
    from app.tea import repository as repo

    base = dict(jasper_unit_type="DistillationColumn", shell_volume=30.0,
                diameter_m=1.5, internals="packing", packed_height_m=12.0)
    base.update(kw)
    return repo.cost_column(session, **base)


def test_packing_adds_cost(session):
    from app.tea import repository as repo

    shell = repo.cost_unit(session, "DistillationColumn", size=30.0)
    col = _packed(session)
    assert col["internals"] == "packing"
    assert col["internals_cost"] > 0
    assert col["total_module_cost"] > shell["total_module_cost"]
    assert col["provenance"]["internals"] == "turton"


def test_structured_costs_more_than_random(session):
    rand = _packed(session, packing_type="Random")["internals_cost"]
    struct = _packed(session, packing_type="Structured")["internals_cost"]
    assert struct > rand  # 4500 vs 1500 USD/m3


def test_ceramic_costs_more_than_metal(session):
    metal = _packed(session, packing_material="Metal")["internals_cost"]
    ceramic = _packed(session, packing_material="Ceramic")["internals_cost"]
    assert ceramic > metal  # material factor 1.3 vs 1.0


def test_packing_scales_with_bed_volume(session):
    short = _packed(session, packed_height_m=6.0)["internals_cost"]
    tall = _packed(session, packed_height_m=12.0)["internals_cost"]
    assert tall == pytest.approx(2 * short, rel=1e-6)  # linear in height


def test_packed_column_route(seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/api/tea/cost-column", json={
        "jasper_unit_type": "DistillationColumn", "shell_volume": 30.0,
        "diameter_m": 1.5, "internals": "packing", "packed_height_m": 12.0,
        "packing_type": "Structured",
    })
    assert r.status_code == 200, r.text
    assert r.json()["internals"] == "packing"
    assert r.json()["internals_cost"] > 0
