"""
B3: Jasper Cost Index validation.

  - continuous monthly series back to 2001 (no gaps),
  - escalation within a few % of publicly reported CEPCI ratios (CEPCI used as a
    test-only external sanity constant — never stored in the DB),
  - index is public-sourced (not 'estimated'),
  - the index_name override hook works (a user CEPCI series overrides 'jasper').

Requires DATABASE_URL.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — cost DB unavailable",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_BACKEND_DIR)

# Publicly reported CEPCI annual averages — used ONLY as an external sanity
# check here; never stored in the DB (licensing).
CEPCI_2001 = 397.0
CEPCI_2024 = 800.0  # ~2023-2024 annual average


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


def _jasper_periods(session):
    from app.tea import models

    return sorted(session.scalars(
        select(models.CostIndex.period).where(
            models.CostIndex.index_name == "jasper"
        )
    ).all())


def test_continuous_monthly_back_to_2001(session):
    periods = _jasper_periods(session)
    assert periods[0] == dt.date(2001, 1, 1), f"starts at {periods[0]}, not 2001-01"
    assert periods[-1].year >= 2024
    # No month gaps from start to end.
    expected = []
    y, m = 2001, 1
    while dt.date(y, m, 1) <= periods[-1]:
        expected.append(dt.date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    assert periods == expected, "monthly series has gaps"


def test_escalation_matches_cepci_ratio(session):
    from app.tea import repository as repo

    j2001 = repo.get_index_value_at_year(session, "jasper", 2001)
    j2024 = repo.get_index_value_at_year(session, "jasper", 2024)
    jasper_ratio = j2024 / j2001
    cepci_ratio = CEPCI_2024 / CEPCI_2001
    # Within a few percent of the publicly reported CEPCI escalation.
    assert abs(jasper_ratio / cepci_ratio - 1) < 0.05, (
        f"Jasper {jasper_ratio:.3f} vs CEPCI {cepci_ratio:.3f}"
    )


def test_index_is_public_sourced(session):
    from app.tea import models

    row = session.scalars(
        select(models.CostIndex).where(models.CostIndex.index_name == "jasper")
    ).first()
    assert row.source.slug == "bls-ppi-ces"
    assert row.source.source_type == "public_dataset"  # not 'estimated'


def test_index_override_hook(session):
    """A user CEPCI series overrides the Jasper index for escalation."""
    from app.tea import models, repository as repo

    src = models.Source(
        slug="cepci-user", title="User-licensed CEPCI", source_type="user_override",
        license="user-provided",
    )
    session.add(src)
    session.flush()
    for period, value in [(dt.date(2001, 1, 1), CEPCI_2001),
                          (dt.date(2024, 1, 1), CEPCI_2024)]:
        session.add(models.CostIndex(
            source_id=src.id, basis_date=period, index_name="cepci-user",
            period=period, value=value,
        ))
    session.commit()

    jasper = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                                 "CarbonSteel", 100.0)["purchased_cost"]
    cepci = repo.cost_equipment(session, "HeatExchanger", "FloatingHead",
                                "CarbonSteel", 100.0,
                                index_name="cepci-user")["purchased_cost"]
    # Different index → different escalation → different cost (hook is wired).
    assert cepci != pytest.approx(jasper, rel=1e-3)
    # CEPCI ratio (2.015) < Jasper ratio (~2.3 by 2026) → lower escalated cost.
    assert cepci < jasper
