"""
C3 benchmark expansion — capacity scaling (economy of scale).

Scaling the HDA plant's equipment sizes by a capacity factor must make total
CAPEX grow *sub-linearly* (cost ~ size^~0.6-0.7), i.e. 2x capacity costs well
under 2x — a real validation that the correlations' size exponents behave across
the whole assembly, not just per unit.

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


def _scaled_equipment(factor: float):
    """HDA equipment with size drivers scaled by capacity factor."""
    from tests.test_cost_db_economics import HDA

    out = []
    for u in HDA["equipment"]:
        v = dict(u)
        if v.get("column"):
            v["shell_volume"] = v["shell_volume"] * factor
            v["diameter_m"] = v["diameter_m"] * (factor ** 0.5)  # area ~ throughput
        else:
            v["size"] = v["size"] * factor
        out.append(v)
    return out


def _capex(session, factor: float) -> float:
    from app.tea import repository as repo

    return repo.estimate_project(session, _scaled_equipment(factor))["capex_total_module"]


def test_capex_increases_with_capacity(session):
    half, base, double = _capex(session, 0.5), _capex(session, 1.0), _capex(session, 2.0)
    assert half < base < double


def test_capex_scales_sublinearly(session):
    base, double = _capex(session, 1.0), _capex(session, 2.0)
    ratio = double / base
    # cost ~ size^0.6-0.7 -> 2x capacity ~ 1.5-1.6x cost. Allow a band for the mix.
    assert 1.3 < ratio < 1.9, f"2x-capacity CAPEX ratio {ratio:.2f} not sub-linear"


def test_effective_scaling_exponent_sane(session):
    import math

    base, double = _capex(session, 1.0), _capex(session, 2.0)
    # exponent n where ratio = 2^n
    n = math.log(double / base) / math.log(2)
    assert 0.4 < n < 0.95, f"effective scaling exponent {n:.2f} out of range"
