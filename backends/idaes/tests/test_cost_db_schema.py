"""
A1 acceptance tests for the cost-DB schema + provenance foundation.

Validates the brief's "done when":
  - migrations apply cleanly on a fresh Postgres,
  - a round-trip preserves units + provenance,
  - inserting an unsourced (or bad-unit) value fails,
  - the overrides table is append-only.

Requires DATABASE_URL pointing at a Postgres (local Docker in dev). The module
re-runs migrations to a clean schema, so it is self-contained.
"""
from __future__ import annotations

import datetime as dt
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.tea import models

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — cost DB unavailable",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def engine():
    """Apply migrations to a clean schema, yield an engine."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))

    # Hard-reset to a guaranteed-clean schema (no seed data, no migration-down
    # cruft) so this test's fixed-slug source inserts can't collide, and so
    # "migrations apply cleanly on a fresh DB" is genuinely exercised.
    from sqlalchemy import text

    eng = create_engine(os.environ["DATABASE_URL"], future=True)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    s = Session(bind=engine, expire_on_commit=False)
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _make_source(session: Session, slug: str) -> models.Source:
    src = models.Source(
        slug=slug,
        title="IDAES SSLW costing",
        source_type="open_source_code",
        license="IDAES-BSD-3",
        reference_citation="Seider, Seader, Lewin, Widagdo, 3rd ed.",
    )
    session.add(src)
    session.flush()
    return src


def test_units_allowlist_seeded(session: Session):
    symbols = set(session.scalars(select(models.Unit.symbol)).all())
    # A representative spread across dimensions must be present.
    assert {"m2", "kW", "barg", "USD", "USD/kg", "fraction"} <= symbols


def test_roundtrip_preserves_units_and_provenance(session: Session):
    src = _make_source(session, "idaes-sslw")
    corr = models.EquipmentCorrelation(
        source_id=src.id,
        basis_date=dt.date(2018, 1, 1),
        equipment_type="HeatExchanger",
        subtype="UTube",
        functional_form="sslw_ln",
        size_quantity="area",
        size_unit="ft2",
        size_min=10,
        size_max=1000,
        coeff={"alpha": [11.3852, 0.9186, 0.09790], "sign": -1},
        currency="USD",
        base_index_name="CE",
        base_index_value=500,
        base_index_year=2018,
        bare_module={"B1": 1.63, "B2": 1.66},
    )
    session.add(corr)
    session.commit()

    fetched = session.scalars(
        select(models.EquipmentCorrelation).where(
            models.EquipmentCorrelation.equipment_type == "HeatExchanger"
        )
    ).one()
    assert fetched.size_unit == "ft2"
    assert fetched.currency == "USD"
    assert fetched.functional_form == "sslw_ln"
    assert fetched.coeff["alpha"][0] == pytest.approx(11.3852)
    assert fetched.basis_date == dt.date(2018, 1, 1)
    # Provenance is reachable from the fact.
    assert fetched.source.license == "IDAES-BSD-3"


def test_unsourced_value_fails(session: Session):
    """No source_id → cannot insert (provenance enforced at DB layer)."""
    corr = models.EquipmentCorrelation(
        basis_date=dt.date(2018, 1, 1),
        equipment_type="Pump",
        subtype="Centrifugal",
        functional_form="turton_log10",
        size_quantity="power",
        size_unit="kW",
        coeff={"K": [3.3892, 0.0536, 0.1538]},
        currency="USD",
        base_index_name="CEPCI",
        base_index_value=397,
        base_index_year=2001,
    )
    session.add(corr)
    with pytest.raises(IntegrityError):
        session.flush()


def test_bad_unit_rejected(session: Session):
    """A unit symbol outside the allowlist is rejected by the FK."""
    src = _make_source(session, "idaes-sslw-badunit")
    corr = models.EquipmentCorrelation(
        source_id=src.id,
        basis_date=dt.date(2018, 1, 1),
        equipment_type="Compressor",
        subtype="Centrifugal",
        functional_form="sslw_ln",
        size_quantity="power",
        size_unit="furlongs",  # not in the allowlist
        coeff={"alpha": [7.58, 0.8, 0.0]},
        currency="USD",
        base_index_name="CE",
        base_index_value=500,
        base_index_year=2018,
    )
    session.add(corr)
    with pytest.raises(IntegrityError):
        session.flush()


def test_bad_functional_form_rejected(session: Session):
    src = _make_source(session, "idaes-sslw-badform")
    corr = models.EquipmentCorrelation(
        source_id=src.id,
        basis_date=dt.date(2018, 1, 1),
        equipment_type="Vessel",
        subtype="Vertical",
        functional_form="made_up_form",  # CHECK violation
        size_quantity="volume",
        size_unit="m3",
        coeff={"K": [3.4974, 0.4485, 0.1074]},
        currency="USD",
        base_index_name="CEPCI",
        base_index_value=397,
        base_index_year=2001,
    )
    session.add(corr)
    with pytest.raises(IntegrityError):
        session.flush()


def test_overrides_are_append_only(session: Session):
    ov = models.Override(
        scope="scenario",
        scope_ref="proj-123",
        target_table="chemical_prices",
        target_key={"chemical": "toluene", "region": "US-GC"},
        field="price",
        new_value={"price": 0.95, "unit": "USD/kg"},
        reason="user supplied contract price",
        actor="user@example.com",
    )
    session.add(ov)
    session.commit()
    ov_id = ov.id

    # UPDATE must be blocked by the trigger.
    with pytest.raises(DBAPIError):
        session.execute(
            models.Override.__table__.update()
            .where(models.Override.id == ov_id)
            .values(reason="tampered")
        )
        session.flush()
    session.rollback()

    # DELETE must be blocked by the trigger.
    with pytest.raises(DBAPIError):
        session.execute(
            models.Override.__table__.delete().where(models.Override.id == ov_id)
        )
        session.flush()
    session.rollback()
