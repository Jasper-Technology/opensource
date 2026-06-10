"""
C7: cross-tool benchmark vs IDAES's OWN solved costing output.

Builds + SOLVES an IDAES SSLW costing block (its real Pyomo machinery) and
asserts our DB's seeded SSLW coefficients reproduce IDAES's solver-computed
base_cost_per_unit. Stronger than the formula-recompute checks: it matches the
upstream library's actual output end-to-end.

Skips when idaes-pse or the ipopt solver isn't available (e.g. cost-only CI).
Requires DATABASE_URL.
"""
from __future__ import annotations

import math
import os

import pytest
from sqlalchemy.orm import Session

# Put the IDAES-bundled solvers on PATH before importing pyomo solver factory.
os.environ["PATH"] = (
    os.path.expanduser("~/.idaes/bin") + os.pathsep + os.environ.get("PATH", "")
)


def _idaes_available() -> bool:
    try:
        import idaes  # noqa: F401
        from pyomo.environ import SolverFactory
        return bool(SolverFactory("ipopt").available())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not _idaes_available(),
    reason="needs DATABASE_URL + idaes-pse + ipopt",
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


def _our_sslw_base(session, equipment_type, subtype, size_in_native_unit):
    """Our DB's SSLW purchased cost at the correlation's base index (escal=1) = base."""
    from app.tea import costing, repository as repo

    corr = repo.get_correlation(session, equipment_type, subtype, source="idaes-sslw")
    inp = costing.CostInputs(
        functional_form=corr.functional_form, coeff=corr.coeff,
        base_index_value=float(corr.base_index_value), Fm=1.0,
        size=size_in_native_unit, index_now=float(corr.base_index_value),
        contingency=0.0,
    )
    return costing.compute_cost(inp).purchased


def _idaes_compressor_base():
    from pyomo.common.config import ConfigValue
    from pyomo.environ import (ConcreteModel, Param, SolverFactory, value,
                               units as pyunits)
    import idaes  # noqa: F401
    from idaes.core import FlowsheetBlock, UnitModelBlock, UnitModelCostingBlock
    from idaes.models.costing.SSLW import (SSLWCosting, SSLWCostingData,
                                           CompressorType, CompressorDriveType,
                                           CompressorMaterial)
    from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption

    m = ConcreteModel()
    m.fs = FlowsheetBlock()
    m.fs.costing = SSLWCosting()
    m.fs.unit = UnitModelBlock()
    m.fs.unit.config.declare("compressor", ConfigValue(default=True))
    m.fs.unit.config.declare(
        "thermodynamic_assumption", ConfigValue(default=ThermodynamicAssumption.isentropic)
    )
    work_w = 101410.4
    m.fs.unit.work_mechanical = Param([0], initialize=work_w, units=pyunits.J / pyunits.s)
    m.fs.unit.costing = UnitModelCostingBlock(
        flowsheet_costing_block=m.fs.costing,
        costing_method=SSLWCostingData.cost_compressor,
        costing_method_arguments={
            "compressor_type": CompressorType.Centrifugal,
            "drive_type": CompressorDriveType.ElectricMotor,
            "material_type": CompressorMaterial.StainlessSteel,
        },
    )
    SolverFactory("ipopt").solve(m)
    base = value(m.fs.unit.costing.base_cost_per_unit)  # CE500
    hp = work_w / 745.6998
    return base, hp


def _idaes_hx_base():
    from pyomo.environ import (Block, ConcreteModel, Param, SolverFactory, value,
                               units as pyunits)
    import idaes  # noqa: F401
    from idaes.core import FlowsheetBlock, UnitModelBlock, UnitModelCostingBlock
    from idaes.models.costing.SSLW import (SSLWCosting, SSLWCostingData, HXType,
                                           HXMaterial, HXTubeLength)

    m = ConcreteModel()
    m.fs = FlowsheetBlock()
    m.fs.costing = SSLWCosting()
    m.fs.unit = UnitModelBlock()
    area_m2 = 1000.0
    m.fs.unit.area = Param(initialize=area_m2, units=pyunits.m**2)
    m.fs.unit.hot_side = Block()
    m.fs.unit.hot_side.properties_in = Block(m.fs.time)
    m.fs.unit.hot_side.properties_in[0].pressure = Param(initialize=2, units=pyunits.atm)
    m.fs.unit.costing = UnitModelCostingBlock(
        flowsheet_costing_block=m.fs.costing,
        costing_method=SSLWCostingData.cost_heat_exchanger,
        costing_method_arguments={
            "hx_type": HXType.floating_head,
            "material_type": HXMaterial.CarbonSteelCarbonSteel,
            "tube_length": HXTubeLength.TwelveFoot,
        },
    )
    SolverFactory("ipopt").solve(m)
    base = value(m.fs.unit.costing.base_cost_per_unit)  # CE500
    area_ft2 = area_m2 * 10.76391
    return base, area_ft2


def test_our_compressor_reproduces_idaes_solved_base(session):
    idaes_base, hp = _idaes_compressor_base()
    our_base = _our_sslw_base(session, "Compressor", "Centrifugal", hp)
    assert our_base == pytest.approx(idaes_base, rel=1e-3), (
        f"our ${our_base:,.0f} vs IDAES-solved ${idaes_base:,.0f}"
    )


def test_our_hx_reproduces_idaes_solved_base(session):
    idaes_base, area_ft2 = _idaes_hx_base()
    our_base = _our_sslw_base(session, "HeatExchanger", "FloatingHead", area_ft2)
    assert our_base == pytest.approx(idaes_base, rel=1e-3), (
        f"our ${our_base:,.0f} vs IDAES-solved ${idaes_base:,.0f}"
    )
