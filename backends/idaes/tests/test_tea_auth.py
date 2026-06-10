"""
TEA route auth: POST /tea/override is API-key-gated (it writes, append-only);
read routes stay open (public, licensed-clean data).

Requires DATABASE_URL (skip-gated like the other cost-db tests).
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


@pytest.fixture(scope="module", autouse=True)
def seeded():
    """Migrate + seed (idempotent) so these tests don't depend on file order."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")

    path = os.path.join(_REPO, "cost-db", "load.py")
    spec = importlib.util.spec_from_file_location("cost_db_load", path)
    loadmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loadmod)
    from app.tea import db

    seed = loadmod._merge_seed_files()
    with Session(bind=db.get_engine()) as s:
        loadmod.load(s, seed)
    yield

OVERRIDE_BODY = {
    "target_table": "chemical_prices",
    "target_key": {"cas": "108-88-3", "region": "US-GC"},
    "field": "price",
    "new_value": {"price": 0.80, "unit": "USD/kg"},
    "scope": "scenario",
    "scope_ref": "test-auth-scenario",
    "reason": "auth test",
}


def test_override_requires_api_key(client):
    r = client.post("/api/tea/override", json=OVERRIDE_BODY)
    assert r.status_code == 403


def test_override_accepts_valid_key(client, auth_headers):
    r = client.post("/api/tea/override", json=OVERRIDE_BODY, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recorded"] is True and body["layer"] == "override"


def test_read_routes_stay_open(client):
    assert client.get("/api/tea/health").status_code == 200
    assert client.get("/api/tea/coverage").status_code == 200
    assert client.get(
        "/api/tea/price/chemical", params={"cas": "108-88-3"}
    ).status_code == 200
