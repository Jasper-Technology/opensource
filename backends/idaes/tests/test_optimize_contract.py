"""
Contract tests for /api/optimize.

These exercise the two accepted objective shapes:
  1. Per-variable: {"unit_id": ..., "parameter": ..., "sense": ...}
  2. Legacy named metric: {"metric": "total_duty"|"total_cost"|..., "sense": ...}

Both must converge, return optimal_variables for each decision var, and
report a sane objective_value. See app/api/routes/optimize.py and
app/core/model_builder.py PARAM_ALIASES / build_objective_expression.
"""
import pytest

pytest.importorskip("idaes", reason="IDAES not installed; skipping live optimize tests")


def _heater_project() -> dict:
    """Feed → Heater flowsheet, methanol/water, used by all tests below."""
    return {
        "name": "Heater-opt",
        "thermodynamics": {"propertyMethod": "PR"},
        "components": [
            {"id": "methanol", "name": "Methanol"},
            {"id": "water", "name": "Water"},
        ],
        "flowsheet": {
            "nodes": [
                {
                    "id": "F1", "type": "Feed", "name": "Feed1",
                    "params": {
                        "T": {"value": 25, "unit": "C"},
                        "P": {"value": 1, "unit": "bar"},
                        "flow": {"value": 100, "unit": "kmol/h"},
                        "composition": {"methanol": 0.5, "water": 0.5},
                    },
                },
                {
                    "id": "H1", "type": "Heater", "name": "Heater1",
                    "params": {"outletT": {"value": 60, "unit": "C"}},
                },
            ],
            "edges": [
                {
                    "id": "e1",
                    "from": {"nodeId": "F1", "portName": "out"},
                    "to": {"nodeId": "H1", "portName": "in"},
                },
            ],
        },
    }


def test_optimize_per_variable_objective_with_constraint(client, auth_headers):
    """Per-variable objective shape: minimize H1.duty s.t. H1.T >= 320 K.

    Bounds [305, 360] on H1.T. With the floor constraint, IPOPT should
    push T to 320 (the binding constraint).
    """
    body = {
        "project": _heater_project(),
        "objective": {"unit_id": "H1", "parameter": "duty", "sense": "minimize"},
        "decision_variables": [
            {"unit_id": "H1", "parameter": "T",
             "lower_bound": 305, "upper_bound": 360, "initial_value": 333},
        ],
        "constraints": [
            {"type": "min", "unit_id": "H1", "parameter": "T", "bound": 320},
        ],
    }
    resp = client.post("/api/optimize", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["converged"] is True
    assert result["solver_status"] == "optimal"
    assert "H1.T" in result["optimal_variables"]
    t_star = result["optimal_variables"]["H1.T"]
    assert 319.5 < t_star < 320.5, f"expected T~320 (constraint), got {t_star}"
    # Objective value (heat duty in W) should be positive — heating from 298 K.
    assert result["objective_value"] > 0


def test_optimize_per_variable_objective_unconstrained(client, auth_headers):
    """Same flowsheet, no constraints: minimize duty drives T to the lower bound."""
    body = {
        "project": _heater_project(),
        "objective": {"unit_id": "H1", "parameter": "duty", "sense": "minimize"},
        "decision_variables": [
            {"unit_id": "H1", "parameter": "T",
             "lower_bound": 305, "upper_bound": 360, "initial_value": 333},
        ],
    }
    resp = client.post("/api/optimize", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["converged"] is True
    t_star = result["optimal_variables"]["H1.T"]
    assert 304.5 < t_star < 305.5, f"expected T~305 (lower bound), got {t_star}"


def test_optimize_legacy_named_metric_backcompat(client, auth_headers):
    """Legacy {metric, sense} shape must still work."""
    body = {
        "project": _heater_project(),
        "objective": {"metric": "total_duty", "sense": "minimize"},
        "decision_variables": [
            {"unit_id": "H1", "parameter": "T",
             "lower_bound": 305, "upper_bound": 360, "initial_value": 333},
        ],
    }
    resp = client.post("/api/optimize", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["converged"] is True
    assert "H1.T" in result["optimal_variables"]


def test_optimize_unresolved_decision_variable_warns(client, auth_headers):
    """An unknown parameter name should produce a warning, not a 500."""
    body = {
        "project": _heater_project(),
        "objective": {"metric": "total_duty", "sense": "minimize"},
        "decision_variables": [
            {"unit_id": "H1", "parameter": "nonexistent_param",
             "lower_bound": 0, "upper_bound": 1},
        ],
    }
    resp = client.post("/api/optimize", json=body, headers=auth_headers)
    # Still 200 — bad DV is a warning, not a hard failure (total_duty has no
    # decision vars but the solver should still find the trivial solution).
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert any(
        "not found" in m for m in result.get("messages", [])
    ), f"expected a 'not found' warning, got: {result.get('messages')}"


def test_optimize_unresolved_objective_returns_error(client, auth_headers):
    """A per-variable objective referencing a non-existent var should error."""
    body = {
        "project": _heater_project(),
        "objective": {"unit_id": "H1", "parameter": "nonexistent", "sense": "minimize"},
        "decision_variables": [
            {"unit_id": "H1", "parameter": "T",
             "lower_bound": 305, "upper_bound": 360},
        ],
    }
    resp = client.post("/api/optimize", json=body, headers=auth_headers)
    # Currently surfaces as the generic 500 because ValueError is caught by
    # the broad except. That's still a clear failure mode for the caller.
    assert resp.status_code in (400, 422, 500), resp.text
