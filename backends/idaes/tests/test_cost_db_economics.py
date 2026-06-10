"""
B7 capstone: end-to-end HDA economics benchmark.

Ties everything together — equipment correlations x Jasper index x location x
contingency (CAPEX) and annual flows x effective prices (OPEX/revenue) — for a
~70 kt/yr benzene HDA plant, asserts the picture is sane + in a cited band, and
locks it in CI with a corrupt-coefficient guard.

References (external sanity only): Yalcin et al. 2025 (HDA TCI $17-32M; ISBL is
~35-65% of TCI); HDA stoichiometry C7H8 + H2 -> C6H6 + CH4.

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

# ~70 kt/yr benzene HDA plant.
BENZENE_KG = 7.0e7
HDA = {
    "equipment": [
        {"type": "Compressor", "size": 1500.0, "pressure": 25.0},
        {"type": "HeatExchanger", "size": 600.0, "material": "StainlessSteel", "pressure": 25.0},
        {"type": "HeatExchanger", "size": 200.0, "pressure": 5.0},
        {"type": "Heater", "size": 4.0e7, "pressure": 25.0},
        {"type": "RStoic", "size": 25.0, "material": "StainlessSteel", "pressure": 25.0},
        {"type": "DistillationColumn", "column": True, "shell_volume": 30.0,
         "diameter_m": 1.8, "n_stages": 25, "pressure": 3.0},
        {"type": "DistillationColumn", "column": True, "shell_volume": 18.0,
         "diameter_m": 1.4, "n_stages": 20, "pressure": 2.0},
        {"type": "Flash", "size": 8.0, "pressure": 25.0},
        {"type": "Pump", "size": 30.0, "pressure": 30.0},
    ],
    "feeds": [
        {"cas": "108-88-3", "annual_kg": 1.18 * BENZENE_KG},   # toluene
        {"cas": "1333-74-0", "annual_kg": 0.026 * BENZENE_KG},  # hydrogen
    ],
    "products": [{"cas": "71-43-2", "annual_kg": BENZENE_KG}],  # benzene
    "utilities": [
        {"utility_type": "electricity", "annual": 2.0e7},  # kWh/yr
        {"utility_type": "steam_lp", "annual": 5.0e5},     # GJ/yr
    ],
}
ISBL_BAND = (6_000_000.0, 21_000_000.0)


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


def _estimate(session):
    from app.tea import repository as repo

    return repo.estimate_project(
        session, HDA["equipment"], HDA["feeds"], HDA["products"], HDA["utilities"],
    )


def test_hda_capex_in_cited_band(session):
    est = _estimate(session)
    lo, hi = ISBL_BAND
    assert lo < est["capex_total_module"] < hi, (
        f"CAPEX ${est['capex_total_module']:,.0f} outside ${lo:,.0f}-${hi:,.0f}"
    )
    assert est["accuracy_class"].startswith("AACE Class 4-5")


def test_hda_opex_magnitudes_sane(session):
    est = _estimate(session)
    # 70 kt/yr plant: revenue & feed cost are tens of $M/yr; utilities a few $M.
    assert 3.0e7 < est["annual_revenue"] < 2.0e8
    assert 3.0e7 < est["annual_feed_cost"] < 2.0e8
    assert 0 < est["annual_utility_cost"] < 5.0e7
    # Gross margin is computed (HDA is genuinely marginal — sign not asserted).
    assert "gross_annual_margin" in est
    assert est["uses_representative_prices"] is True  # chemicals are literature-sourced


def test_hda_end_to_end_via_route(seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/api/tea/estimate", json={**HDA})
    assert r.status_code == 200, r.text
    body = r.json()
    assert ISBL_BAND[0] < body["capex_total_module"] < ISBL_BAND[1]
    assert body["annual_revenue"] > 0
    assert len(body["breakdown"]["capex"]) == len(HDA["equipment"])


# --------------------------------------------------------------------------- #
# Breakdown enrichment: id echo, per-item detail, gap tolerance (product wiring)
# --------------------------------------------------------------------------- #
def test_estimate_echoes_ids_and_detail(session):
    from app.tea import repository as repo

    est = repo.estimate_project(
        session,
        equipment=[
            {"id": "n1", "type": "Pump", "size": 30.0, "pressure": 30.0},
            {"id": "n2", "type": "DistillationColumn", "column": True,
             "shell_volume": 30.0, "diameter_m": 1.8, "n_stages": 25},
        ],
        feeds=[{"id": "f1:toluene", "cas": "108-88-3", "annual_kg": 1.0e6}],
        utilities=[{"id": "u1", "utility_type": "electricity", "annual": 1.0e6}],
    )
    capex = {item["id"]: item for item in est["breakdown"]["capex"]}
    assert set(capex) == {"n1", "n2"}
    pump = capex["n1"]
    assert pump["size"] == 30.0
    assert pump["accuracy_class"].startswith("AACE Class 4-5")
    assert "provenance" in pump and "in_range" in pump
    column = capex["n2"]
    assert column["n_stages"] == 25 and column["internals_cost"] > 0
    feed = est["breakdown"]["feeds"][0]
    assert feed["id"] == "f1:toluene" and feed["annual_kg"] == 1.0e6
    assert feed["source"] and feed["unit"]
    util = est["breakdown"]["utilities"][0]
    assert util["id"] == "u1" and util["annual"] == 1.0e6 and util["source"]
    assert est["gaps"] == [] and est["n_gaps"] == 0 and est["n_costed"] == 4


def test_estimate_gap_tolerant(session):
    from app.tea import repository as repo

    est = repo.estimate_project(
        session,
        equipment=[
            {"id": "good", "type": "Pump", "size": 30.0},
            {"id": "bad", "type": "CustomUnit", "size": 5.0},  # no base_type
        ],
        feeds=[
            {"id": "priced", "cas": "108-88-3", "annual_kg": 1.0e6},
            {"id": "unpriced", "cas": "0000-00-0", "annual_kg": 1.0e6},
        ],
        utilities=[{"id": "unknown", "utility_type": "pixie_dust", "annual": 1.0}],
    )
    capex = {item["id"]: item for item in est["breakdown"]["capex"]}
    assert capex["bad"]["gap"] is True and "base_type" in capex["bad"]["reason"]
    assert "total_module_cost" not in capex["bad"]
    # Totals include only the costed/priced items.
    assert est["capex_total_module"] == capex["good"]["total_module_cost"]
    priced = next(f for f in est["breakdown"]["feeds"] if f["id"] == "priced")
    assert est["annual_feed_cost"] == pytest.approx(priced["annual_cost"], abs=0.01)
    assert est["annual_utility_cost"] == 0.0
    gap_kinds = sorted(g["kind"] for g in est["gaps"])
    assert gap_kinds == ["equipment", "feed", "utility"]
    assert est["n_gaps"] == 3 and est["n_costed"] == 2


def test_estimate_custom_unit_via_base_type(session):
    from app.tea import repository as repo

    direct = repo.estimate_project(
        session, [{"id": "p", "type": "Pump", "size": 15.0}])
    via_custom = repo.estimate_project(
        session,
        [{"id": "c", "type": "CustomUnit", "base_type": "Pump", "size": 15.0}],
    )
    item = via_custom["breakdown"]["capex"][0]
    assert item["resolved_via"] == "Pump"
    assert via_custom["capex_total_module"] == direct["capex_total_module"]


def test_heater_primary_correlation_is_btu_hr(session):
    """Guard for the frontend's kW -> BTU/hr conversion (sim/tea mapping layer).

    The seeded primary FiredHeater correlation is BTU/hr-based; if this ever
    repoints to an SI correlation, the frontend constant must be removed.
    """
    from app.tea import repository as repo

    um = repo.get_unit_map(session, "Heater")
    corr = repo.get_correlation(session, um.equipment_type, um.default_subtype)
    assert corr.size_unit == "BTU/hr"


def test_corrupt_coefficient_breaks_benchmark(session):
    from app.tea import repository as repo

    baseline = _estimate(session)["capex_total_module"]
    assert ISBL_BAND[0] < baseline < ISBL_BAND[1]

    # Corrupt the heat-exchanger correlation (appears twice in HDA -> big swing).
    corr = repo.get_correlation(session, "HeatExchanger", "FloatingHead")
    k = list(corr.coeff["K"])
    corr.coeff = {"K": [k[0] + 1.5, k[1], k[2]]}  # ~30x that unit
    session.flush()
    session.expire_all()
    corrupted = _estimate(session)["capex_total_module"]
    session.rollback()

    assert corrupted != pytest.approx(baseline, rel=0.05)
    assert not (ISBL_BAND[0] < corrupted < ISBL_BAND[1]), "corruption not caught"
