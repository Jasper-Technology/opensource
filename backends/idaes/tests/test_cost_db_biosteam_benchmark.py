"""
C7: cross-tool benchmark vs BioSTEAM (a third, independent open TEA tool).

BioSTEAM uses its own cost correlations, so the check is a *spread* check, not an
exact match: our DB cost should land within the inter-tool band (~Class 5) of
BioSTEAM's simulated purchase cost for the same unit. Validates we're not wildly
off from a third established tool.

Skips when biosteam isn't installed (it's a benchmark-only dep, intentionally NOT
in requirements.txt / CI). Requires DATABASE_URL.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import Session


def _biosteam_available() -> bool:
    try:
        import biosteam  # noqa: F401
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not _biosteam_available(),
    reason="needs DATABASE_URL + biosteam (benchmark-only dep)",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_BACKEND_DIR)


def _load_seed_module():
    import importlib.util

    path = os.path.join(_REPO, "cost-db", "load.py")
    spec = importlib.util.spec_from_file_location("cost_db_load", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def session():
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
    s = Session(bind=db.get_engine())
    try:
        yield s
    finally:
        s.close()


def _our_pump_cost_at_ce(session, power_kw, target_ce):
    """Our Turton pump purchased cost at `power_kw`, escalated to CEPCI=target_ce."""
    from app.tea import costing, repository as repo

    corr = repo.get_correlation(session, "Pump", "Centrifugal", source="turton")
    inp = costing.CostInputs(
        functional_form=corr.functional_form, coeff=corr.coeff,
        base_index_value=float(corr.base_index_value), Fm=1.0,
        size=power_kw, index_now=target_ce, contingency=0.0,
        bare_module=corr.bare_module, pressure_model=corr.pressure_model,
        size_min=float(corr.size_min) if corr.size_min is not None else None,
        size_max=float(corr.size_max) if corr.size_max is not None else None,
    )
    return costing.compute_cost(inp).purchased


def test_pump_within_intertool_band(session):
    import warnings

    import biosteam as bst

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bst.settings.set_thermo(["Water"])
        feed = bst.Stream("feed", Water=100000, units="kg/hr", P=101325)
        pump = bst.units.Pump("P_bench", ins=feed, P=20e5)
        pump.simulate()
        bs_cost = pump.purchase_cost
        power_kw = pump.power_utility.rate

    ours = _our_pump_cost_at_ce(session, power_kw, bst.CE)
    ratio = ours / bs_cost
    # Third-source agreement within the Class-5 band (different correlations).
    assert 0.4 < ratio < 2.5, (
        f"pump: ours ${ours:,.0f} vs BioSTEAM ${bs_cost:,.0f} (CE {bst.CE}) ratio {ratio:.2f}"
    )
