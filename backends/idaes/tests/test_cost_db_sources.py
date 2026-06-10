"""
B1: source registry — completeness, licensing discipline, provenance integrity.

  - every source has a license + a valid source_type,
  - every source is actually used (no orphan registry entries),
  - every provenanced category has at least one sourced row (no empty coverage),
  - no licensed/commercial feed is stored as a value source (CEPCI/Richardson/ICIS).

Requires DATABASE_URL.
"""
from __future__ import annotations

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

_VALID_TYPES = {
    "open_source_code", "public_api", "public_dataset",
    "textbook_via_oss", "user_override", "estimated",
}
_EXPECTED_CATEGORIES = {
    "equipment_correlations", "material_factors", "chemicals", "chemical_prices",
    "utilities", "location_drivers", "economic_factors", "cost_index",
    "unit_cost_map",
}


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


def test_every_source_has_license_and_valid_type(session):
    from app.tea import repository as repo

    for src in repo.source_registry(session):
        assert src["license"], f"{src['slug']} missing license"
        assert src["source_type"] in _VALID_TYPES, src["slug"]


def test_no_orphan_sources(session):
    from app.tea import repository as repo

    orphans = [s["slug"] for s in repo.source_registry(session) if not s["used_in"]]
    assert not orphans, f"unused sources in registry: {orphans}"


def test_every_category_has_sourced_rows(session):
    from app.tea import repository as repo

    covered = set()
    for s in repo.source_registry(session):
        covered |= set(s["used_in"].keys())
    missing = _EXPECTED_CATEGORIES - covered
    assert not missing, f"categories with no sourced rows: {missing}"


def test_no_licensed_feed_stored_as_source(session):
    from app.tea import models

    slugs = " ".join(session.scalars(select(models.Source.slug)).all()).lower()
    titles = " ".join(session.scalars(select(models.Source.title)).all()).lower()
    blob = slugs + " " + titles
    # Licensing discipline: these must never be a stored value source.
    for forbidden in ("richardson", "icis", "ihs"):
        assert forbidden not in blob, f"licensed feed '{forbidden}' as a source"
    # CEPCI may appear in citations (sanity-check basis) but not as a value source
    # type — index values come from BLS, not a CEPCI series.
    cepci_sources = session.scalars(
        select(models.Source).where(models.Source.slug.ilike("%cepci%"))
    ).all()
    assert not cepci_sources, "a CEPCI series must not be a stored source"


def test_registry_is_complete(session):
    from app.tea import repository as repo

    reg = repo.source_registry(session)
    # At least the 11 Stage-A/B sources, each with a citation or url.
    assert len(reg) >= 11
    for s in reg:
        assert s["reference_citation"] or s["url"] or s["source_type"] in (
            "estimated", "user_override"
        ), f"{s['slug']} has no citation/url"
