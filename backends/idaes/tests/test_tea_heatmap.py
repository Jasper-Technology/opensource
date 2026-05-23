"""Tests for the 2D NPV heatmap."""
from __future__ import annotations
import pytest

from app.tea.sensitivity import HeatmapAxis, run_heatmap


def _base() -> dict:
    return {
        "totals": {
            "capex_total_module_usd": 10_000_000,
            "opex_annual_usd": 3_000_000,
            "revenue_annual_usd": 6_000_000,
        },
    }


def _scn() -> dict:
    return {"discount_rate": 0.10, "project_life_years": 20}


class TestRunHeatmap:
    def test_grid_shape(self) -> None:
        r = run_heatmap(
            base_result=_base(),
            base_scenario=_scn(),
            x_axis=HeatmapAxis("revenue", -0.2, 0.2, 11),
            y_axis=HeatmapAxis("capex", -0.2, 0.2, 7),
        )
        assert len(r.x_labels) == 11
        assert len(r.y_labels) == 7
        assert len(r.npv_grid) == 7
        assert all(len(row) == 11 for row in r.npv_grid)

    def test_revenue_up_increases_npv(self) -> None:
        r = run_heatmap(
            base_result=_base(),
            base_scenario=_scn(),
            x_axis=HeatmapAxis("revenue", -0.2, 0.2, 11),
            y_axis=HeatmapAxis("capex", 0, 0, 3),
        )
        # Each row: higher x (revenue) → higher NPV → grid monotone increasing along x
        for row in r.npv_grid:
            for i in range(1, len(row)):
                assert row[i] >= row[i - 1]

    def test_capex_up_decreases_npv(self) -> None:
        r = run_heatmap(
            base_result=_base(),
            base_scenario=_scn(),
            x_axis=HeatmapAxis("revenue", 0, 0, 3),
            y_axis=HeatmapAxis("capex", -0.2, 0.2, 11),
        )
        # Higher y (capex) → lower NPV → grid monotone decreasing along y
        for col_idx in range(len(r.x_labels)):
            column = [r.npv_grid[y_idx][col_idx] for y_idx in range(len(r.y_labels))]
            for i in range(1, len(column)):
                assert column[i] <= column[i - 1]

    def test_min_max_match_grid_extrema(self) -> None:
        r = run_heatmap(
            base_result=_base(),
            base_scenario=_scn(),
            x_axis=HeatmapAxis("revenue", -0.3, 0.3, 7),
            y_axis=HeatmapAxis("capex", -0.3, 0.3, 7),
        )
        all_values = [v for row in r.npv_grid for v in row]
        assert r.min_npv == min(all_values)
        assert r.max_npv == max(all_values)

    def test_too_few_steps_raises(self) -> None:
        with pytest.raises(ValueError):
            run_heatmap(
                base_result=_base(),
                base_scenario=_scn(),
                x_axis=HeatmapAxis("revenue", -0.2, 0.2, 2),
                y_axis=HeatmapAxis("capex", -0.2, 0.2, 5),
            )

    def test_too_many_steps_raises(self) -> None:
        with pytest.raises(ValueError):
            run_heatmap(
                base_result=_base(),
                base_scenario=_scn(),
                x_axis=HeatmapAxis("revenue", -0.2, 0.2, 100),
                y_axis=HeatmapAxis("capex", -0.2, 0.2, 5),
            )

    def test_unknown_variable_raises(self) -> None:
        with pytest.raises(ValueError):
            run_heatmap(
                base_result=_base(),
                base_scenario=_scn(),
                x_axis=HeatmapAxis("banana", -0.2, 0.2, 5),
                y_axis=HeatmapAxis("capex", -0.2, 0.2, 5),
            )

    def test_discount_axis(self) -> None:
        """Discount +2pp should lower NPV."""
        r = run_heatmap(
            base_result=_base(),
            base_scenario=_scn(),
            x_axis=HeatmapAxis("revenue", 0, 0, 3),
            y_axis=HeatmapAxis("discount", -0.02, 0.02, 3),
        )
        # Higher y = higher discount = lower NPV
        for col_idx in range(3):
            column = [r.npv_grid[y_idx][col_idx] for y_idx in range(3)]
            assert column[0] > column[-1]
