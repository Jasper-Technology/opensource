"""TEA endpoints — standalone and import-chained."""
from __future__ import annotations
import logging
import warnings
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tea import (
    BlockInput,
    Stream,
    CostingError,
    SimpleProject,
    SizeOutOfRangeWarning,
    bare_module_cost,
    get_catalog,
    lcop,
    LCOPInputs,
    size as size_block,
    tac as total_annual_cost,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / response models ─────────────────────────────────────────────────


class StreamIn(BaseModel):
    """Stream data (SI units)."""

    T: float = Field(description="Temperature in K")
    P: float = Field(description="Pressure in Pa (absolute)")
    flow_mol: float = Field(description="Molar flow in mol/s")
    flow_mass: Optional[float] = Field(default=None, description="kg/s — derived if absent")
    density: Optional[float] = Field(default=None, description="kg/m³")
    molecular_weight: Optional[float] = Field(default=None, description="g/mol")
    vapor_fraction: Optional[float] = Field(default=None)
    composition: dict[str, float] = Field(
        default_factory=dict,
        description="component name → mole fraction (used for MW/density lookup)",
    )


class BlockIn(BaseModel):
    """Unit operation with sizing context."""

    id: str
    type: str
    name: Optional[str] = None
    duty: Optional[float] = Field(default=None, description="W (positive = heating)")
    work: Optional[float] = Field(default=None, description="W (shaft power)")
    pressure_drop: Optional[float] = Field(default=None, description="Pa")
    inlet: Optional[StreamIn] = None
    outlet: Optional[StreamIn] = None
    # User overrides (optional; inference fills in defaults)
    material: Optional[str] = Field(default=None, description="e.g. CarbonSteel")
    subtype_override: Optional[str] = Field(default=None)


class ScenarioConfig(BaseModel):
    """Scenario-level inputs."""

    cepci: float = Field(default=800.0, description="Current CEPCI")
    contingency: float = Field(default=0.18, ge=0, le=1)
    operating_hours: float = Field(default=8000.0, ge=0)
    default_material: str = Field(default="CarbonSteel")
    discount_rate: float = Field(default=0.10, ge=-0.5, le=1.0)
    project_life_years: int = Field(default=20, ge=1, le=100)
    annual_revenue: float = Field(default=0.0, description="USD/yr")
    annual_feedstock_cost: float = Field(default=0.0, description="USD/yr")
    utility_prices: dict[str, float] = Field(
        default_factory=lambda: {"steam_usd_per_gj": 14.0, "electricity_usd_per_kwh": 0.07}
    )
    annual_production: Optional[float] = Field(
        default=None, description="Units/yr for LCOP (product-agnostic)"
    )


class TEARequest(BaseModel):
    scenario: ScenarioConfig
    blocks: list[BlockIn]
    # Optional top-level stream list. When present, streams are wired to
    # blocks by matching from_block / to_block → block.id so the frontend
    # doesn't have to embed inlet/outlet on every block.
    streams: Optional[list["ImportedStreamRef"]] = None


class BlockCostResult(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    equipment_class: Optional[str]
    subtype: Optional[str]
    material: Optional[str]
    size: Optional[float]
    size_unit: Optional[str]
    pressure_barg: Optional[float]
    purchased_usd: Optional[float]
    bare_module_usd: Optional[float]
    total_module_usd: Optional[float]
    Fm: Optional[float]
    Fp: Optional[float]
    in_range: bool
    note: str
    error: Optional[str] = None


class TEAResult(BaseModel):
    status: Literal["ok", "partial"]
    blocks: list[BlockCostResult]
    totals: dict[str, float]
    economics: dict[str, float]
    warnings: list[str]


# ── Handler ──────────────────────────────────────────────────────────────────


@router.get("/tea/catalog")
def catalog() -> dict:
    """Return the TEA coefficient catalog for the frontend (ETag-cacheable)."""
    cat = get_catalog()
    return {
        "cepci_reference": cat.cepci_reference,
        "equipment": {
            name: {
                "size_quantity": k.size_quantity,
                "subtypes": sorted(k.subtypes.keys()),
                "materials": sorted(k.material_factors.keys()),
            }
            for name, k in cat.equipment.items()
        },
    }


@router.post("/tea/run", response_model=TEAResult)
def run_tea(req: TEARequest) -> TEAResult:
    """
    Run Turton costing + simple-project economics on an imported project.

    For each block: size it algebraically, look up material/pressure factors,
    compute purchased/bare-module/total-module. Aggregate into totals, then
    fold in user-supplied revenue/OPEX to compute NPV/IRR/Payback/LCOP.
    """
    block_results: list[BlockCostResult] = []
    all_warnings: list[str] = []
    total_cbm = 0.0
    total_ctm = 0.0
    had_failure = False

    # Wire top-level streams onto blocks if the caller sent them separately.
    # Blocks that already carry inlet/outlet keep those values.
    block_streams: dict[str, list[ImportedStreamRef]] = {}
    block_outlets: dict[str, list[ImportedStreamRef]] = {}
    if req.streams:
        for s in req.streams:
            if s.to_block:
                block_streams.setdefault(s.to_block, []).append(s)
            if s.from_block:
                block_outlets.setdefault(s.from_block, []).append(s)

    for b in req.blocks:
        if req.streams and (b.inlet is None or b.outlet is None):
            inlet_ref, outlet_ref = _pick_inlet_outlet(
                b.type,
                block_streams.get(b.id, []),
                block_outlets.get(b.id, []),
            )
            b = b.model_copy(update={
                "inlet": b.inlet or (_to_stream_in(inlet_ref) if inlet_ref else None),
                "outlet": b.outlet or (_to_stream_in(outlet_ref) if outlet_ref else None),
            })
        result = _cost_one_block(b, req.scenario)
        block_results.append(result)
        if result.error:
            had_failure = True
            continue
        if result.bare_module_usd is not None:
            total_cbm += result.bare_module_usd
        if result.total_module_usd is not None:
            total_ctm += result.total_module_usd

    # Annual cash flow for SimpleProject: revenue - feedstock - utilities - labor - maintenance
    utility_annual = _estimate_utility_cost(req)
    maintenance_annual = 0.03 * total_ctm  # 3% of installed capex, Turton rule
    labor_annual = _labor_cost(block_results, req)
    annual_opex = (
        req.scenario.annual_feedstock_cost
        + utility_annual
        + maintenance_annual
        + labor_annual
    )
    annual_net_cf = req.scenario.annual_revenue - annual_opex

    project = SimpleProject(
        capex=total_ctm,
        annual_net_cash_flow=annual_net_cf,
        lifetime_years=req.scenario.project_life_years,
    )

    npv = project.npv(req.scenario.discount_rate)
    irr = project.irr() if total_ctm > 0 else float("nan")
    payback = project.payback() if total_ctm > 0 else float("inf")
    tac_value = total_annual_cost(
        total_ctm, annual_opex, req.scenario.project_life_years, req.scenario.discount_rate
    ) if total_ctm > 0 else 0.0

    lcop_value: Optional[float] = None
    if req.scenario.annual_production and req.scenario.annual_production > 0 and total_ctm > 0:
        lcop_value = lcop(
            LCOPInputs(
                capex=total_ctm,
                annual_opex=annual_opex,
                annual_production=req.scenario.annual_production,
                lifetime_years=req.scenario.project_life_years,
                discount_rate=req.scenario.discount_rate,
            )
        )

    return TEAResult(
        status="partial" if had_failure else "ok",
        blocks=block_results,
        totals={
            "capex_bare_module_usd": total_cbm,
            "capex_total_module_usd": total_ctm,
            "opex_annual_usd": annual_opex,
            "opex_utilities_usd": utility_annual,
            "opex_labor_usd": labor_annual,
            "opex_maintenance_usd": maintenance_annual,
            "opex_feedstock_usd": req.scenario.annual_feedstock_cost,
            "revenue_annual_usd": req.scenario.annual_revenue,
        },
        economics={
            "npv_usd": npv,
            "irr": irr if irr == irr else 0.0,  # NaN → 0 for JSON
            "payback_years": payback if payback != float("inf") else -1.0,
            "tac_usd": tac_value,
            "lcop": lcop_value if lcop_value is not None else -1.0,
        },
        warnings=all_warnings,
    )


# ── Internals ────────────────────────────────────────────────────────────────


def _cost_one_block(b: BlockIn, scn: ScenarioConfig) -> BlockCostResult:
    try:
        block = BlockInput(
            block_type=b.type,
            duty=b.duty,
            work=b.work,
            pressure_drop=b.pressure_drop,
            inlet=Stream(**b.inlet.model_dump()) if b.inlet else None,
            outlet=Stream(**b.outlet.model_dump()) if b.outlet else None,
        )
    except Exception as exc:  # noqa: BLE001
        return _empty_block_result(b, error=f"invalid input: {exc}")

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SizeOutOfRangeWarning)
            sizing = size_block(block)
            if sizing is None:
                return _empty_block_result(b, note="no-cost block")

            subtype = b.subtype_override or sizing.subtype
            material = b.material or scn.default_material

            cost = bare_module_cost(
                equipment=sizing.equipment_class,
                subtype=subtype,
                material=material,
                size=sizing.size,
                pressure=sizing.pressure_barg,
                cepci=scn.cepci,
            )

            total_module_usd = cost.bare_module * (1 + scn.contingency)

            return BlockCostResult(
                id=b.id,
                type=b.type,
                name=b.name,
                equipment_class=sizing.equipment_class,
                subtype=subtype,
                material=material,
                size=sizing.size,
                size_unit=sizing.size_unit,
                pressure_barg=sizing.pressure_barg,
                purchased_usd=cost.purchased,
                bare_module_usd=cost.bare_module,
                total_module_usd=total_module_usd,
                Fm=cost.Fm,
                Fp=cost.Fp,
                in_range=cost.in_range and not caught,
                note=sizing.note + (f" | size-range: {cost.range_note}" if not cost.in_range else ""),
            )
    except CostingError as exc:
        return _empty_block_result(b, error=str(exc))
    except KeyError as exc:
        return _empty_block_result(b, error=f"catalog miss: {exc}")
    except ValueError as exc:
        return _empty_block_result(b, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected TEA failure on block %s", b.id)
        return _empty_block_result(b, error=f"internal error: {exc}")


def _empty_block_result(
    b: BlockIn, note: str = "", error: Optional[str] = None
) -> BlockCostResult:
    return BlockCostResult(
        id=b.id,
        type=b.type,
        name=b.name,
        equipment_class=None,
        subtype=None,
        material=None,
        size=None,
        size_unit=None,
        pressure_barg=None,
        purchased_usd=None,
        bare_module_usd=None,
        total_module_usd=None,
        Fm=None,
        Fp=None,
        in_range=True,
        note=note,
        error=error,
    )


def _estimate_utility_cost(req: TEARequest) -> float:
    """Rough OPEX from duties and powers. Blocks with positive duty ≈ steam;
    blocks with negative duty ≈ cooling water; blocks with work ≈ electricity."""
    hours = req.scenario.operating_hours
    steam_usd_per_gj = req.scenario.utility_prices.get("steam_usd_per_gj", 14.0)
    elec_usd_per_kwh = req.scenario.utility_prices.get("electricity_usd_per_kwh", 0.07)
    cooling_usd_per_gj = req.scenario.utility_prices.get("cooling_usd_per_gj", 2.0)

    total = 0.0
    for b in req.blocks:
        if b.duty and b.duty > 0:
            # Steam cost: duty (W) * hours (h) = Wh ; → GJ = Wh*3600/1e9
            gj = b.duty * hours * 3600 / 1e9
            total += gj * steam_usd_per_gj
        elif b.duty and b.duty < 0:
            gj = abs(b.duty) * hours * 3600 / 1e9
            total += gj * cooling_usd_per_gj
        if b.work:
            kwh = abs(b.work) / 1000 * hours
            total += kwh * elec_usd_per_kwh
    return total


def _labor_cost(block_results: list[BlockCostResult], req: TEARequest) -> float:
    """Turton 6-operator rule: ~4.8 operators per shift × 2 shifts × $75k/operator/yr.
    Scales with number of costed equipment units for small plants."""
    n_equipment = sum(1 for r in block_results if r.bare_module_usd)
    # Scale from 2 operators (small plant) to ~10 operators (50+ units)
    operators = min(10, max(2, 2 + n_equipment // 5))
    shifts = 4.8  # covers 24/7 operation with vacation/sick
    return operators * shifts * 75_000


# ── Import-chained endpoint ──────────────────────────────────────────────────


class ImportedStreamRef(BaseModel):
    """A stream as produced by the Excel/DWSIM parsers (SI units)."""

    id: str
    from_block: Optional[str] = None
    from_port: Optional[str] = None
    to_block: Optional[str] = None
    to_port: Optional[str] = None
    T: Optional[float] = None
    P: Optional[float] = None
    flow_mol: Optional[float] = None
    flow_mass: Optional[float] = None
    composition: dict[str, float] = Field(default_factory=dict)


class ImportedBlockRef(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    duty: Optional[float] = None
    work: Optional[float] = None
    pressure_drop: Optional[float] = None
    material: Optional[str] = None
    subtype_override: Optional[str] = None


class TEARunFromImportRequest(BaseModel):
    scenario: ScenarioConfig
    blocks: list[ImportedBlockRef]
    streams: list[ImportedStreamRef]


# Resolve TEARequest.streams forward reference now that ImportedStreamRef exists
TEARequest.model_rebuild()


@router.post("/tea/run-from-import", response_model=TEAResult)
def run_from_import(req: TEARunFromImportRequest) -> TEAResult:
    """
    Run TEA directly on the output of an import parser. The caller sends
    ``ImportedProject.blocks`` + ``.streams`` as-is and this endpoint
    wires inlet/outlet streams by matching ``from_block`` / ``to_block``.
    """
    # Index streams by their endpoints for fast inlet/outlet lookup
    incoming_by_block: dict[str, list[ImportedStreamRef]] = {}
    outgoing_by_block: dict[str, list[ImportedStreamRef]] = {}
    for s in req.streams:
        if s.to_block:
            incoming_by_block.setdefault(s.to_block, []).append(s)
        if s.from_block:
            outgoing_by_block.setdefault(s.from_block, []).append(s)

    tea_blocks: list[BlockIn] = []
    for b in req.blocks:
        inlet, outlet = _pick_inlet_outlet(
            b.type,
            incoming_by_block.get(b.id, []),
            outgoing_by_block.get(b.id, []),
        )
        tea_blocks.append(
            BlockIn(
                id=b.id,
                type=b.type,
                name=b.name,
                duty=b.duty,
                work=b.work,
                pressure_drop=b.pressure_drop,
                inlet=_to_stream_in(inlet) if inlet else None,
                outlet=_to_stream_in(outlet) if outlet else None,
                material=b.material,
                subtype_override=b.subtype_override,
            )
        )

    forwarded = TEARequest(scenario=req.scenario, blocks=tea_blocks)
    return run_tea(forwarded)


class FuelConsumptionIn(BaseModel):
    fuel: str
    mass_kg_per_year: float


class FeedstockInputIn(BaseModel):
    name: str
    mass_kg_per_year: float
    ci_kgco2_per_kg: Optional[float] = None


class EsgRequest(BaseModel):
    fuels: list[FuelConsumptionIn] = Field(default_factory=list)
    grid_region: str = "US-GC"
    grid_ef_override: Optional[float] = None
    electricity_kwh_per_year: float = 0.0
    feedstocks: list[FeedstockInputIn] = Field(default_factory=list)
    annual_production_kg: float = 0.0
    water_withdrawal_m3_per_year: float = 0.0
    water_consumption_m3_per_year: float = 0.0


class EsgResponse(BaseModel):
    scope_1_tco2_per_year: float
    scope_2_tco2_per_year: float
    scope_3_tco2_per_year: float
    total_tco2_per_year: float
    ci_kgco2_per_kg_product: float
    water_withdrawal_m3_per_kg: float = 0.0
    water_consumption_m3_per_kg: float = 0.0
    unknown_feedstocks: list[str] = Field(default_factory=list)
    unknown_fuels: list[str] = Field(default_factory=list)


@router.post("/tea/esg", response_model=EsgResponse)
def run_esg(req: EsgRequest) -> EsgResponse:
    """Compute scope 1/2/3 tons CO2e/yr + product carbon intensity."""
    from app.tea.esg import (
        EsgConfig,
        FeedstockInput,
        FuelConsumption,
        compute_esg,
    )

    config = EsgConfig(
        fuels=tuple(FuelConsumption(**f.model_dump()) for f in req.fuels),
        grid_region=req.grid_region,
        grid_ef_override=req.grid_ef_override,
        electricity_kwh_per_year=req.electricity_kwh_per_year,
        feedstocks=tuple(FeedstockInput(**f.model_dump()) for f in req.feedstocks),
        annual_production_kg=req.annual_production_kg,
        water_withdrawal_m3_per_year=req.water_withdrawal_m3_per_year,
        water_consumption_m3_per_year=req.water_consumption_m3_per_year,
    )
    result = compute_esg(config)
    return EsgResponse(**result.to_dict())


class ReliabilityRequest(BaseModel):
    totals: dict[str, float]
    nominal_hours: float = 8000.0
    operation_mode: Literal["continuous", "batch"] = "continuous"
    availability: float = Field(default=0.95, ge=0.0, le=1.0)
    turnaround_interval_years: int = 4
    turnaround_days: int = 14
    batch_cycle_hours: float = 24.0
    batch_changeover_hours: float = 2.0


class ReliabilityResponse(BaseModel):
    effective_hours_per_year: float
    revenue_multiplier: float
    scaled_totals: dict[str, float]


@router.post("/tea/reliability", response_model=ReliabilityResponse)
def run_reliability(req: ReliabilityRequest) -> ReliabilityResponse:
    """Scale revenue + utility OPEX by plant availability and operating mode."""
    from app.tea.reliability import (
        OperationMode,
        ReliabilityConfig,
        apply_reliability_to_totals,
    )

    config = ReliabilityConfig(
        operation_mode=OperationMode(req.operation_mode),
        availability=req.availability,
        turnaround_interval_years=req.turnaround_interval_years,
        turnaround_days=req.turnaround_days,
        batch_cycle_hours=req.batch_cycle_hours,
        batch_changeover_hours=req.batch_changeover_hours,
    )
    scaled = apply_reliability_to_totals(
        req.totals, nominal_hours=req.nominal_hours, config=config,
    )
    return ReliabilityResponse(
        effective_hours_per_year=config.effective_hours_per_year(req.nominal_hours),
        revenue_multiplier=config.revenue_multiplier(req.nominal_hours),
        scaled_totals=scaled,
    )


class TciConfigIn(BaseModel):
    plant_type: Literal["fluid", "solids"] = "fluid"
    osbl_ratio: float = Field(default=0.30, ge=0.0, le=2.0)
    startup_fraction: float = Field(default=0.10, ge=0.0, le=1.0)
    working_capital_fraction: float = Field(default=0.15, ge=0.0, le=1.0)
    land_cost_usd: float = 0.0
    permitting_cost_usd: float = 0.0
    category_overrides: dict[str, Literal["isbl", "osbl", "unknown"]] = Field(default_factory=dict)


class TciRequest(BaseModel):
    result: TEAResult
    annual_revenue: float
    config: TciConfigIn = Field(default_factory=TciConfigIn)


class TciResponse(BaseModel):
    isbl_equipment: float
    osbl_equipment: float
    direct_costs: float
    indirect_costs: float
    fixed_capital: float
    working_capital: float
    startup_costs: float
    land_plus_permits: float
    total_capital_investment: float


@router.post("/tea/tci", response_model=TciResponse)
def run_tci(req: TciRequest) -> TciResponse:
    """Compute total capital investment with ISBL+OSBL split and Lang factors."""
    from app.tea.tci import BlockCategory, TciConfig, compute_tci

    cfg = TciConfig(
        plant_type=req.config.plant_type,
        osbl_ratio=req.config.osbl_ratio,
        startup_fraction=req.config.startup_fraction,
        working_capital_fraction=req.config.working_capital_fraction,
        land_cost_usd=req.config.land_cost_usd,
        permitting_cost_usd=req.config.permitting_cost_usd,
    )
    overrides = {
        k: BlockCategory(v) for k, v in req.config.category_overrides.items()
    }
    blocks_payload = [
        b.model_dump() if hasattr(b, "model_dump") else dict(b)
        for b in req.result.blocks
    ]
    tci = compute_tci(
        blocks=blocks_payload,
        annual_revenue=req.annual_revenue,
        config=cfg,
        category_overrides=overrides,
    )
    return TciResponse(**tci.to_dict())


class PtcConfig(BaseModel):
    usd_per_unit: float
    units_per_year: float
    start_year: int = 1
    years: int = 10
    name: str = "PTC"


class TaxScenario(BaseModel):
    """R2 tax/credit config layered on the simple project cash flow."""
    corporate_tax_rate: float = 0.21
    state_tax_rate: float = 0.05
    macrs_class: Literal["5-year", "7-year", "10-year", "15-year", "straight-line-20"] = "7-year"
    itc_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    production_credits: list[PtcConfig] = Field(default_factory=list)
    carbon_price_usd_per_ton: float = 0.0
    carbon_emissions_ton_per_year: float = 0.0
    revenue_escalation: float = Field(default=0.02, ge=-0.2, le=0.2)
    opex_escalation: float = Field(default=0.025, ge=-0.2, le=0.2)


class AfterTaxCashFlowRow(BaseModel):
    year: int
    revenue: float
    opex: float
    depreciation: float
    ebit: float
    tax: float
    ptc: float
    carbon_cost: float
    net_cf: float


class AfterTaxEconomics(BaseModel):
    npv_usd: float
    irr: float
    payback_years: float
    rows: list[AfterTaxCashFlowRow]


class AfterTaxRequest(BaseModel):
    """Take an existing TEAResult + tax scenario and produce the full
    after-tax cash flow."""
    scenario: ScenarioConfig
    result: TEAResult
    tax: TaxScenario


@router.post("/tea/after-tax", response_model=AfterTaxEconomics)
def run_after_tax(req: AfterTaxRequest) -> AfterTaxEconomics:
    from app.tea.taxes import (
        MacrsClass,
        ProductionTaxCredit,
        TaxConfig,
        cash_flow_with_taxes,
        irr_of,
        npv_of,
        payback_years_after_tax,
    )

    tc = TaxConfig(
        corporate_tax_rate=req.tax.corporate_tax_rate,
        state_tax_rate=req.tax.state_tax_rate,
        macrs_class=MacrsClass(req.tax.macrs_class),
        itc_fraction=req.tax.itc_fraction,
        production_credits=tuple(
            ProductionTaxCredit(
                usd_per_unit=c.usd_per_unit,
                units_per_year=c.units_per_year,
                start_year=c.start_year,
                years=c.years,
                name=c.name,
            )
            for c in req.tax.production_credits
        ),
        carbon_price_usd_per_ton=req.tax.carbon_price_usd_per_ton,
        carbon_emissions_ton_per_year=req.tax.carbon_emissions_ton_per_year,
        revenue_escalation=req.tax.revenue_escalation,
        opex_escalation=req.tax.opex_escalation,
    )

    totals = req.result.totals
    flows = cash_flow_with_taxes(
        capex=float(totals["capex_total_module_usd"]),
        annual_revenue=float(totals["revenue_annual_usd"]),
        annual_opex=float(totals["opex_annual_usd"]),
        project_life_years=req.scenario.project_life_years,
        tax_config=tc,
    )

    discount = req.scenario.discount_rate
    npv = npv_of(flows, discount)
    irr = irr_of(flows)
    pb = payback_years_after_tax(flows)

    return AfterTaxEconomics(
        npv_usd=npv,
        irr=irr if irr == irr else 0.0,
        payback_years=pb if pb != float("inf") else -1.0,
        rows=[AfterTaxCashFlowRow(**f.summary()) for f in flows],
    )


class ExportRequest(BaseModel):
    """POST /api/tea/export/xlsx — package a TEAResult as a multi-sheet workbook."""
    scenario: ScenarioConfig
    result: TEAResult
    project_name: str = "Jasper TEA Report"


@router.post("/tea/export/xlsx")
def export_xlsx(req: ExportRequest):
    """Produce a multi-sheet XLSX report from a TEA run and return it inline."""
    from fastapi.responses import Response

    from app.tea.report import build_report

    data = build_report(
        tea_result=req.result.model_dump(),
        scenario=req.scenario.model_dump(),
        project_name=req.project_name,
    )
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in req.project_name)[:60] or "jasper-tea"
    headers = {"Content-Disposition": f'attachment; filename="{safe_name}.xlsx"'}
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


class SensitivityRequest(BaseModel):
    scenario: ScenarioConfig
    blocks: list[ImportedBlockRef]
    streams: list[ImportedStreamRef]
    perturbation: float = Field(default=0.20, ge=0.01, le=1.0)


class SensitivityDriverOut(BaseModel):
    label: str
    category: str
    low_npv: float
    high_npv: float
    low_label: str
    high_label: str
    base_npv: float
    swing: float


class SensitivityResponse(BaseModel):
    base_npv: float
    drivers: list[SensitivityDriverOut]


class HeatmapAxisIn(BaseModel):
    variable: Literal["revenue", "opex", "capex", "discount"]
    min_fraction: float
    max_fraction: float
    steps: int = Field(default=11, ge=3, le=51)


class HeatmapRequest(BaseModel):
    scenario: ScenarioConfig
    blocks: list[ImportedBlockRef]
    streams: list[ImportedStreamRef]
    x: HeatmapAxisIn
    y: HeatmapAxisIn


class HeatmapResponse(BaseModel):
    x_variable: str
    y_variable: str
    x_labels: list[float]
    y_labels: list[float]
    npv_grid: list[list[float]]
    base_npv: float
    min_npv: float
    max_npv: float


@router.post("/tea/heatmap", response_model=HeatmapResponse)
def run_heatmap_endpoint(req: HeatmapRequest) -> HeatmapResponse:
    """2D NPV heatmap — pick any two of revenue/opex/capex/discount."""
    from app.tea.sensitivity import HeatmapAxis, run_heatmap

    base_req = TEARunFromImportRequest(
        scenario=req.scenario, blocks=req.blocks, streams=req.streams
    )
    base_result = run_from_import(base_req).model_dump()

    result = run_heatmap(
        base_result=base_result,
        base_scenario=req.scenario.model_dump(),
        x_axis=HeatmapAxis(
            variable=req.x.variable,
            min_fraction=req.x.min_fraction,
            max_fraction=req.x.max_fraction,
            steps=req.x.steps,
        ),
        y_axis=HeatmapAxis(
            variable=req.y.variable,
            min_fraction=req.y.min_fraction,
            max_fraction=req.y.max_fraction,
            steps=req.y.steps,
        ),
    )

    return HeatmapResponse(
        x_variable=result.x_variable,
        y_variable=result.y_variable,
        x_labels=list(result.x_labels),
        y_labels=list(result.y_labels),
        npv_grid=[list(row) for row in result.npv_grid],
        base_npv=result.base_npv,
        min_npv=result.min_npv,
        max_npv=result.max_npv,
    )


class MonteCarloRequest(BaseModel):
    scenario: ScenarioConfig
    blocks: list[ImportedBlockRef]
    streams: list[ImportedStreamRef]
    samples: int = Field(default=1000, ge=10, le=100_000)
    price_spread: float = Field(default=0.20, ge=0.01, le=1.0)
    capex_spread: float = Field(default=0.15, ge=0.01, le=1.0)
    rate_spread_pp: float = Field(default=0.02, ge=0.0, le=0.5)
    seed: Optional[int] = None


class MonteCarloHistBin(BaseModel):
    low: float
    high: float
    count: int


class MonteCarloResponse(BaseModel):
    samples: int
    p10: float
    p50: float
    p90: float
    mean: float
    std: float
    probability_positive: float
    histogram: list[MonteCarloHistBin]


@router.post("/tea/monte-carlo", response_model=MonteCarloResponse)
def run_monte_carlo_endpoint(req: MonteCarloRequest) -> MonteCarloResponse:
    """
    Monte Carlo sensitivity — samples triangular distributions over
    revenue, feedstock cost, CAPEX, and discount rate. Returns the NPV
    distribution with P10 / P50 / P90 markers and a pre-computed
    histogram the frontend renders directly.
    """
    from app.tea.sensitivity import run_monte_carlo

    base_req = TEARunFromImportRequest(
        scenario=req.scenario, blocks=req.blocks, streams=req.streams
    )
    base_result = run_from_import(base_req).model_dump()

    mc = run_monte_carlo(
        base_result=base_result,
        base_scenario=req.scenario.model_dump(),
        samples=req.samples,
        price_spread=req.price_spread,
        capex_spread=req.capex_spread,
        rate_spread_pp=req.rate_spread_pp,
        seed=req.seed,
    )

    return MonteCarloResponse(
        samples=mc.samples,
        p10=mc.p10,
        p50=mc.p50,
        p90=mc.p90,
        mean=mc.mean,
        std=mc.std,
        probability_positive=mc.probability_positive,
        histogram=[MonteCarloHistBin(**b) for b in mc.histogram(bins=20)],
    )


@router.post("/tea/sensitivity", response_model=SensitivityResponse)
def run_sensitivity(req: SensitivityRequest) -> SensitivityResponse:
    """
    Run a deterministic ±pct tornado.

    Perturbs revenue, feedstock, CEPCI, discount rate, and materials on
    the top-3 CAPEX-contributing blocks. Each driver is a single recost
    so the whole sweep costs ~(7 + 3×2) ≈ 13 TEA runs.
    """
    from app.tea.sensitivity import build_tornado

    # Base run
    base_req = TEARunFromImportRequest(
        scenario=req.scenario, blocks=req.blocks, streams=req.streams
    )
    base_result = run_from_import(base_req).model_dump()

    # Callback used by the tornado builder to swap a single block's material
    # and re-run. Keeps the block/stream context pinned to this request.
    def _recost_with_material(block_id: str, material: str) -> dict:
        swapped = [
            ImportedBlockRef(
                **{**b.model_dump(), "material": material if b.id == block_id else b.material}
            )
            for b in req.blocks
        ]
        sub = TEARunFromImportRequest(
            scenario=req.scenario, blocks=swapped, streams=req.streams
        )
        return run_from_import(sub).model_dump()

    tornado = build_tornado(
        base_result=base_result,
        base_scenario=req.scenario.model_dump(),
        recost_with_material=_recost_with_material,
        perturbation=req.perturbation,
    )

    drivers_out = [
        SensitivityDriverOut(
            label=d.label,
            category=d.category,
            low_npv=d.low_npv,
            high_npv=d.high_npv,
            low_label=d.low_label,
            high_label=d.high_label,
            base_npv=d.base_npv,
            swing=d.swing,
        )
        for d in tornado.sorted_by_swing()
    ]

    return SensitivityResponse(base_npv=tornado.base_npv, drivers=drivers_out)


_HX_COLD_IN = {"cold-in", "cold_in", "tube-in"}
_HX_COLD_OUT = {"cold-out", "cold_out", "tube-out"}
_HX_HOT_IN = {"hot-in", "hot_in", "shell-in"}
_HX_HOT_OUT = {"hot-out", "hot_out", "shell-out"}


def _pick_inlet_outlet(
    block_type: str,
    incoming: list[ImportedStreamRef],
    outgoing: list[ImportedStreamRef],
) -> tuple[Optional[ImportedStreamRef], Optional[ImportedStreamRef]]:
    """
    Pick the "representative" inlet/outlet for a block given every edge
    that touches it. HeatExchangers have four canonical ports (cold-in /
    cold-out / hot-in / hot-out); our sizer expects ``inlet`` = cold-in
    and ``outlet`` = cold-out so LMTD reflects the process-side ΔT.
    """
    if block_type == "HeatExchanger":
        cold_in = next((s for s in incoming if (s.to_port or "").lower() in _HX_COLD_IN), None)
        cold_out = next((s for s in outgoing if (s.from_port or "").lower() in _HX_COLD_OUT), None)
        # Fall back to hot side if cold side wasn't wired.
        if cold_in is None:
            cold_in = next((s for s in incoming if (s.to_port or "").lower() in _HX_HOT_IN), None)
        if cold_out is None:
            cold_out = next((s for s in outgoing if (s.from_port or "").lower() in _HX_HOT_OUT), None)
        if cold_in is None and incoming:
            cold_in = incoming[0]
        if cold_out is None and outgoing:
            cold_out = outgoing[0]
        return cold_in, cold_out

    inlet = incoming[0] if incoming else None
    outlet = outgoing[0] if outgoing else None
    return inlet, outlet


def _to_stream_in(s: ImportedStreamRef) -> Optional[StreamIn]:
    """Convert ImportedStreamRef → StreamIn, requires at minimum T/P/flow_mol."""
    if s.T is None or s.P is None:
        return None
    flow_mol = s.flow_mol
    if flow_mol is None and s.flow_mass is not None:
        # Last-resort: assume MW 50 if none available (matches sizing fallback)
        flow_mol = s.flow_mass / 0.050  # 50 g/mol → 0.050 kg/mol
    if flow_mol is None:
        return None
    return StreamIn(
        T=s.T,
        P=s.P,
        flow_mol=flow_mol,
        flow_mass=s.flow_mass,
        composition=s.composition or {},
    )
