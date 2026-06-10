"""
A4 benchmark (Stage-A gate). "Both" anchoring:

  1. PER-UNIT EXACT MATCH vs upstream source (hard regression): our DB-computed
     purchased cost must equal the source formula recomputed independently
     (Turton from tea-catalog.json; SSLW from the SSLW.py constants). Catches
     any transcription/math drift in the seed or costing layer.

  2. ASSEMBLY in a CITED public band: a representative HDA (toluene->benzene)
     ISBL equipment list totals to a plausible figure vs published HDA economics
     (Yalcin et al. 2025, Int. J. Energy Research: HDA TCI ~$17-32M; ISBL is
     ~35-65% of TCI). Sizes are documented representative values, NOT the exact
     published case — faithful reproduction (IDAES HDA example, BioSTEAM, Turton)
     is B7.

  3. CORRUPT-COEFFICIENT guard: perturbing one seeded coefficient pushes the
     assembly out of band — proving the benchmark actually guards.

Requires DATABASE_URL. References:
  - Yalcin et al. (2025), Int. J. Energy Research, HDA TEA (TCI $17.2-31.9M).
  - IDAES HDA Flowsheet Costing example (open-source, B7 anchor).
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import warnings

import pytest
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — cost DB unavailable",
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_BACKEND_DIR)
_CATALOG = os.path.join(_REPO, "tea-catalog.json")

# Representative HDA ISBL equipment (equip, subtype, material, size, pressure).
# Sizes are documented representative values for a mid-capacity unit.
HDA_EQUIPMENT = [
    ("Compressor", "Centrifugal", "CarbonSteel", 1500.0, 25.0),
    ("HeatExchanger", "FloatingHead", "StainlessSteel", 600.0, 25.0),
    ("HeatExchanger", "FloatingHead", "CarbonSteel", 200.0, 5.0),
    ("HeatExchanger", "FloatingHead", "CarbonSteel", 150.0, 5.0),
    ("FiredHeater", "Fuel", "CarbonSteel", 4.0e7, 25.0),
    ("Vessel", "Vertical", "StainlessSteel", 25.0, 25.0),
    ("Vessel", "Vertical", "CarbonSteel", 18.0, 3.0),
    ("Vessel", "Vertical", "CarbonSteel", 12.0, 2.0),
    ("Vessel", "Horizontal", "CarbonSteel", 8.0, 25.0),
    ("Vessel", "Horizontal", "CarbonSteel", 6.0, 3.0),
    ("Pump", "Centrifugal", "CarbonSteel", 30.0, 30.0),
    ("Pump", "Centrifugal", "CarbonSteel", 15.0, 30.0),
]

# Public HDA TCI ~$17-32M; ISBL module sum ~35-65% of TCI → ~$6-21M band.
ISBL_BAND = (6_000_000.0, 21_000_000.0)


def _load_seed_module():
    path = os.path.join(_REPO, "cost-db", "load.py")
    spec = importlib.util.spec_from_file_location("cost_db_load", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _reload_seed():
    from app.tea import db

    loadmod = _load_seed_module()
    seed = loadmod._merge_seed_files()
    with Session(bind=db.get_engine()) as s:
        loadmod.load(s, seed)


@pytest.fixture(scope="module")
def seeded():
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    _reload_seed()
    yield


@pytest.fixture
def session(seeded):
    from app.tea import db

    s = Session(bind=db.get_engine())
    try:
        yield s
    finally:
        s.close()


def _assembly_total(session) -> float:
    from app.tea import repository as repo

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sum(
            repo.cost_equipment(session, et, st, mat, size, p)["total_module_cost"]
            for (et, st, mat, size, p) in HDA_EQUIPMENT
        )


# --- 1. exact per-unit match vs upstream ---------------------------------- #
def _escal(session, base_year):
    from app.tea import repository as repo

    latest = float(repo.get_current_index(session, "jasper").value)
    return latest / repo.get_index_value_at_year(session, "jasper", base_year)


def test_turton_units_match_catalog(session):
    from app.tea import repository as repo

    catalog = json.load(open(_CATALOG))
    escal = _escal(session, 2001)  # Turton seed base year
    cases = [
        ("HeatExchanger", "FloatingHead", 100.0),
        ("HeatExchanger", "FloatingHead", 500.0),
        ("Compressor", "Centrifugal", 1000.0),
        ("Compressor", "Centrifugal", 2000.0),
        ("Vessel", "Vertical", 20.0),
        ("Vessel", "Horizontal", 15.0),
        ("Pump", "Centrifugal", 50.0),
        ("Pump", "Centrifugal", 150.0),
        ("Reactor", "JacketedAgitated", 10.0),
    ]
    for et, st, size in cases:
        k1, k2, k3 = catalog["equipment"][et]["subtypes"][st]["K"]
        log_s = math.log10(size)
        expected = 10 ** (k1 + k2 * log_s + k3 * log_s ** 2) * escal
        got = repo.cost_equipment(session, et, st, "CarbonSteel", size)["purchased_cost"]
        assert got == pytest.approx(expected, rel=1e-4), f"{et}/{st} drift"


def test_sslw_fired_heater_matches_source(session):
    from app.tea import repository as repo

    # SSLW.py cost_fired_heater (Fuel): base = exp(0.32325 + 0.766*ln(Q)), seed base year 2006.
    q = 1.0e7
    expected = math.exp(0.32325 + 0.766 * math.log(q)) * _escal(session, 2006)
    got = repo.cost_equipment(session, "FiredHeater", "Fuel", "CarbonSteel", q, 0.0)
    assert got["purchased_cost"] == pytest.approx(expected, rel=1e-4)


# --- 2. assembly in the cited public band --------------------------------- #
def test_hda_assembly_in_public_band(session):
    total = _assembly_total(session)
    lo, hi = ISBL_BAND
    assert lo < total < hi, (
        f"HDA ISBL total ${total:,.0f} outside cited band "
        f"${lo:,.0f}-${hi:,.0f} (Yalcin 2025 TCI $17-32M, ISBL ~35-65%)"
    )


# --- 3. corrupt-coefficient guard (runs last; restores seed) -------------- #
def test_corrupt_coefficient_breaks_benchmark(session):
    from app.tea import repository as repo

    baseline = _assembly_total(session)
    assert ISBL_BAND[0] < baseline < ISBL_BAND[1]

    # Corrupt the fired-heater coefficient (alpha1 += 3 → ~e^3≈20x that unit).
    corr = repo.get_correlation(session, "FiredHeater", "Fuel")
    a = list(corr.coeff["alpha"])
    corr.coeff = {"alpha": [a[0] + 3.0, a[1], a[2]]}
    session.commit()
    session.expire_all()

    corrupted = _assembly_total(session)
    # Release this session's locks before TRUNCATE in _reload_seed (else the
    # truncate blocks on our open read transaction).
    session.rollback()
    _reload_seed()  # restore clean state for any later tests

    assert corrupted != pytest.approx(baseline, rel=0.05), "corruption had no effect"
    lo, hi = ISBL_BAND
    assert not (lo < corrupted < hi), "corrupted total still in band — benchmark would not catch it"
