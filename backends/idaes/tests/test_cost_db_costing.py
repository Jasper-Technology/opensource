"""
A3 tests: DB-backed costing path.

Validates that costs compute correctly from seeded data for both functional
forms, carry their provenance + accuracy class, reconcile the SSLW basis (G7),
and that uncovered equipment 404s (gap) rather than fabricating a number.

Requires DATABASE_URL. The module ensures the schema + loads the HDA seed.
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


def _escal(session, base_year):
    """Jasper-index escalation factor base_year -> latest (matches the costing layer)."""
    from app.tea import repository as repo

    latest = float(repo.get_current_index(session, "jasper").value)
    base = repo.get_index_value_at_year(session, "jasper", base_year)
    return latest / base


def test_turton_heat_exchanger(session):
    import math

    from app.tea import repository as repo

    r = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                            "CarbonSteel", size=100.0, pressure=5.0)
    # Cp0 = 10^(4.8306 - 0.8509*log10(100) + 0.3187*log10(100)^2) @ CEPCI base year 2001,
    # escalated by the Jasper index (2001 -> latest). Fp=1 at 5 barg, Fm=1 (CS).
    log_s = math.log10(100.0)
    cp0 = 10 ** (4.8306 - 0.8509 * log_s + 0.3187 * log_s ** 2)
    exp_cp = cp0 * _escal(session, 2001)
    assert r["purchased_cost"] == pytest.approx(exp_cp, rel=1e-3)
    assert r["bare_module_cost"] == pytest.approx(exp_cp * (1.63 + 1.66), rel=1e-3)
    assert r["total_module_cost"] == pytest.approx(exp_cp * 3.29 * 1.18, rel=1e-3)
    assert r["functional_form"] == "turton_log10"
    assert r["provenance"]["correlation"] == "turton"
    assert r["provenance"]["cost_index"] == "bls-ppi-ces"
    assert r["accuracy_class"].startswith("AACE Class 4-5")


def test_sslw_fired_heater_reconciled(session):
    from app.tea import repository as repo

    import math

    r = repo.cost_equipment(session, "FiredHeater", "Fuel",
                            "CarbonSteel", size=1e7, pressure=0.0)
    assert r["functional_form"] == "sslw_ln"
    # base=exp(0.32325+0.766*ln(1e7)) @ CEPCI base year 2006, escalated by Jasper
    # index (2006 -> latest); then x Fp(0.986) x F_install(2.19).
    base = math.exp(0.32325 + 0.766 * math.log(1e7))
    exp_cp = base * _escal(session, 2006)
    assert r["purchased_cost"] == pytest.approx(exp_cp, rel=1e-3)
    assert r["bare_module_cost"] == pytest.approx(exp_cp * 0.986 * 2.19, rel=1e-3)
    assert "F_install=2.19" in r["basis_note"]
    assert r["provenance"]["correlation"] == "idaes-sslw"


def test_material_factor_scales_cost(session):
    from app.tea import repository as repo

    cs = repo.cost_equipment(session, "Vessel", "Vertical", "CarbonSteel", size=10.0)
    ss = repo.cost_equipment(session, "Vessel", "Vertical", "StainlessSteel", size=10.0)
    # Same size, pricier material -> higher bare-module cost.
    assert ss["bare_module_cost"] > cs["bare_module_cost"]
    assert ss["Fm"] == pytest.approx(3.12)


def test_uncovered_equipment_raises_not_invents(session):
    from app.tea import repository as repo

    with pytest.raises(repo.CostDataMissing):
        repo.cost_equipment(session, "Bioreactor", "Fermenter",
                            "StainlessSteel", size=10.0)


def test_capex_not_flagged_estimated(session):
    from app.tea import repository as repo

    # CAPEX inputs (correlation, material, Jasper index, contingency) are all
    # sourced now that the BLS index replaced the placeholder — flag is False.
    r = repo.cost_equipment(session, "Pump", "Centrifugal", "CastIron", size=50.0)
    assert r["uses_estimated_inputs"] is False
    assert r["provenance"]["cost_index"] == "bls-ppi-ces"


def test_route_end_to_end(session, seeded):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.tea import repository as repo

    client = TestClient(app)

    ok = client.post("/api/tea/cost-equipment", json={
        "equipment_type": "HeatExchanger", "subtype": "FloatingHead",
        "material": "CarbonSteel", "size": 100.0, "pressure": 5.0,
    })
    assert ok.status_code == 200, ok.text
    # Route result matches the repository computation (DRY — no hardcoded magic).
    expected = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                                   "CarbonSteel", 100.0, 5.0)["total_module_cost"]
    assert ok.json()["total_module_cost"] == pytest.approx(expected, rel=1e-6)

    missing = client.post("/api/tea/cost-equipment", json={
        "equipment_type": "Bioreactor", "subtype": "Fermenter",
        "material": "StainlessSteel", "size": 10.0,
    })
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "cost_data_missing"
