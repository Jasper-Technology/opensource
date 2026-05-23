"""Tests for the sensitivity tornado."""
from __future__ import annotations
import pytest

from app.tea.sensitivity import build_tornado, SensitivityResult


def _base_result() -> dict:
    """CAPEX 12M, OPEX 6M, Rev 10M, r=10%, 20yr → base NPV ≈ 22.06M."""
    # Keep internally consistent so the sensitivity drivers' base_npv field
    # matches what _npv_from_totals recomputes.
    capex = 12_000_000.0
    opex = 6_000_000.0
    rev = 10_000_000.0
    life = 20
    r = 0.10
    net = rev - opex
    npv_base = -capex + sum(net / (1 + r) ** t for t in range(1, life + 1))
    return {
        "economics": {"npv_usd": npv_base, "irr": 0.15, "payback_years": 5, "tac_usd": 0.0, "lcop": -1},
        "totals": {
            "capex_bare_module_usd": 8_000_000.0,
            "capex_total_module_usd": capex,
            "opex_annual_usd": opex,
            "opex_utilities_usd": 0.0,
            "opex_labor_usd": 0.0,
            "opex_maintenance_usd": 0.0,
            "opex_feedstock_usd": 2_000_000.0,
            "revenue_annual_usd": rev,
        },
        "blocks": [
            {"id": "P1", "type": "Pump", "equipment_class": "Pump", "subtype": "Centrifugal",
             "material": "CarbonSteel", "total_module_usd": 500_000.0},
        ],
        "status": "ok",
        "warnings": [],
    }


def _base_scenario() -> dict:
    return {
        "cepci": 800,
        "contingency": 0.18,
        "discount_rate": 0.10,
        "project_life_years": 20,
        "default_material": "CarbonSteel",
    }


def _stub_recost(block_id: str, material: str) -> dict:
    """Deterministic stub — swap material scales CAPEX by Fm ratio."""
    r = _base_result()
    ratios = {"CarbonSteel": 1.0, "StainlessSteel": 1.5, "NiAlloy": 2.5}
    delta = (ratios.get(material, 1.0) - 1.0) * 500_000
    r["totals"]["capex_total_module_usd"] += delta
    # Recompute NPV with the new CAPEX (simple project shape)
    capex = r["totals"]["capex_total_module_usd"]
    revenue = r["totals"]["revenue_annual_usd"]
    opex = r["totals"]["opex_annual_usd"]
    net = revenue - opex
    life = 20
    rate = 0.10
    npv = -capex + sum(net / (1 + rate) ** t for t in range(1, life + 1))
    r["economics"]["npv_usd"] = npv
    return r


def test_tornado_builds_core_drivers() -> None:
    result = build_tornado(
        base_result=_base_result(),
        base_scenario=_base_scenario(),
        recost_with_material=_stub_recost,
    )
    labels = [d.label for d in result.drivers]
    # Every tornado has revenue, feedstock, CEPCI, discount + top-block material
    assert "Product revenue" in labels
    assert "Feedstock cost" in labels
    assert "CEPCI (cost index)" in labels
    assert "Discount rate" in labels


def test_revenue_swing_is_symmetric() -> None:
    result = build_tornado(
        base_result=_base_result(),
        base_scenario=_base_scenario(),
        recost_with_material=_stub_recost,
    )
    rev = next(d for d in result.drivers if d.label == "Product revenue")
    # -20% is below base; +20% is above
    assert rev.low_npv < rev.base_npv < rev.high_npv
    # Approximately symmetric (±20% of 10M revenue → ±2M annual, PV over 20yr ~17M)
    below = rev.base_npv - rev.low_npv
    above = rev.high_npv - rev.base_npv
    assert abs(below - above) / max(below, above) < 0.02


def test_feedstock_swing_is_inverted() -> None:
    """Higher feedstock cost → lower NPV (low_npv < base < high_npv)."""
    result = build_tornado(
        base_result=_base_result(),
        base_scenario=_base_scenario(),
        recost_with_material=_stub_recost,
    )
    fs = next(d for d in result.drivers if d.label == "Feedstock cost")
    assert fs.low_npv < fs.base_npv < fs.high_npv


def test_sorted_by_swing() -> None:
    result = build_tornado(
        base_result=_base_result(),
        base_scenario=_base_scenario(),
        recost_with_material=_stub_recost,
    )
    sorted_ = result.sorted_by_swing()
    # Confirm monotonically decreasing swing
    for i in range(1, len(sorted_)):
        assert sorted_[i].swing <= sorted_[i - 1].swing


def test_material_driver_uses_top_block() -> None:
    result = build_tornado(
        base_result=_base_result(),
        base_scenario=_base_scenario(),
        recost_with_material=_stub_recost,
    )
    # P1 is the only costed block; material driver should reference it
    mats = [d for d in result.drivers if d.category == "material"]
    assert any("P1" in d.label for d in mats)
