"""
B2 deepening: column internals (trays) + inter-source conflict report.

Column internals: a tray column = shell + trays, combined at bare-module.
Conflict report: Turton (DB) vs SSLW (recomputed here) purchased cost for
overlapping classes — the spread calibrates the AACE Class 4-5 accuracy claim.
Pinned so a coefficient drift changes the documented relationship visibly.

Requires DATABASE_URL.
"""
from __future__ import annotations

import importlib.util
import math
import os

import pytest
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — cost DB unavailable",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_BACKEND_DIR)

_KW2HP = 1 / 0.7457
_M2_2_FT2 = 10.7639
_IDX = 800.0  # placeholder current index (matches the seed)


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


# --- column internals ----------------------------------------------------- #
def test_column_adds_tray_cost(session):
    from app.tea import repository as repo

    shell = repo.cost_unit(session, "DistillationColumn", size=30.0, pressure=3.0)
    column = repo.cost_column(
        session, "DistillationColumn", shell_volume=30.0, diameter_m=1.5,
        n_stages=20, pressure=3.0,
    )
    assert column["trays_cost"] > 0
    assert column["total_module_cost"] > shell["total_module_cost"]
    assert column["provenance"]["shell"] == "turton"
    assert column["provenance"]["internals"] == "idaes-sslw"


def test_more_trays_cost_more(session):
    from app.tea import repository as repo

    def col(n):
        return repo.cost_column(
            session, "DistillationColumn", shell_volume=30.0, diameter_m=1.5,
            n_stages=n,
        )["total_module_cost"]

    assert col(40) > col(20) > col(10)


def test_tray_type_factor(session):
    from app.tea import repository as repo

    sieve = repo.cost_column(session, "DistillationColumn", 30.0, 1.5, 20,
                             tray_type="Sieve")["trays_cost"]
    bubble = repo.cost_column(session, "DistillationColumn", 30.0, 1.5, 20,
                              tray_type="BubbleCap")["trays_cost"]
    assert bubble > sieve  # BubbleCap factor 1.87 vs Sieve 1.0


# --- inter-source conflict report ----------------------------------------- #
def _sslw_hx_purchased(area_m2: float, escal: float) -> float:
    a = [11.3852, 0.9186, 0.09790]  # SSLW UTube, oversize 1.1, CE500 base
    area_ft2 = area_m2 * _M2_2_FT2 * 1.1
    ln = math.log(area_ft2)
    return math.exp(a[0] - a[1] * ln + a[2] * ln * ln) * escal


def _sslw_compressor_purchased(kw: float, escal: float) -> float:
    hp = kw * _KW2HP  # SSLW centrifugal, CE500 base
    return math.exp(7.58 + 0.8 * math.log(hp)) * escal


def _sslw_escal(session) -> float:
    """Jasper escalation 2006 (SSLW seed base year) -> latest — same as the DB uses."""
    from app.tea import repository as repo

    latest = float(repo.get_current_index(session, "jasper").value)
    return latest / repo.get_index_value_at_year(session, "jasper", 2006)


def test_intersource_spread_heat_exchanger(session):
    from app.tea import repository as repo

    # Both escalated to the same "now" via the Jasper index: Turton via its 2001
    # base (in the DB), SSLW via its 2006 base — a fair "today's cost" comparison.
    turton = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                                 "CarbonSteel", 100.0)["purchased_cost"]
    sslw = _sslw_hx_purchased(100.0, _sslw_escal(session))
    ratio = turton / sslw
    assert 1.4 < ratio < 2.2, f"HX inter-source ratio drifted: {ratio:.2f}"


def test_intersource_spread_compressor(session):
    from app.tea import repository as repo

    turton = repo.cost_equipment(session, "Compressor", "Centrifugal",
                                 "CarbonSteel", 1000.0)["purchased_cost"]
    sslw = _sslw_compressor_purchased(1000.0, _sslw_escal(session))
    ratio = turton / sslw
    assert 0.40 < ratio < 0.70, f"compressor inter-source ratio drifted: {ratio:.2f}"


def test_spread_justifies_accuracy_class(session):
    """The inter-source spread is order-of the accuracy class — Class 4-5 honest."""
    from app.tea import repository as repo

    escal = _sslw_escal(session)
    hx_t = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                               "CarbonSteel", 100.0)["purchased_cost"]
    comp_t = repo.cost_equipment(session, "Compressor", "Centrifugal",
                                 "CarbonSteel", 1000.0)["purchased_cost"]
    spreads = [
        abs(hx_t / _sslw_hx_purchased(100.0, escal) - 1),
        abs(comp_t / _sslw_compressor_purchased(1000.0, escal) - 1),
    ]
    # Both spreads exceed 30% — single-source estimates can't honestly claim
    # better than Class 4-5.
    assert all(sp > 0.30 for sp in spreads)
