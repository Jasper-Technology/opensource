"""Tests for the IDAES model builder.

Requires IDAES + IPOPT to be installed.
"""
import pytest

try:
    import idaes  # noqa: F401
    HAS_IDAES = True
except ImportError:
    HAS_IDAES = False

pytestmark = pytest.mark.skipif(not HAS_IDAES, reason="IDAES not installed")


def _make_seed_project():
    """Minimal Feed → Flash → 2×Sink project dict."""
    return {
        "name": "Test Flash",
        "thermodynamics": {"propertyMethod": "Ideal"},
        "components": [
            {"id": "water", "name": "Water", "formula": "H2O"},
            {"id": "co2", "name": "Carbon Dioxide", "formula": "CO2"},
            {"id": "n2", "name": "Nitrogen", "formula": "N2"},
        ],
        "flowsheet": {
            "nodes": [
                {"id": "feed1", "type": "Feed", "name": "Feed", "x": 0, "y": 0, "params": {}},
                {"id": "flash1", "type": "Flash", "name": "Flash", "x": 100, "y": 0, "params": {
                    "T": {"kind": "quantity", "q": {"value": 350, "unit": "K"}},
                    "P": {"kind": "quantity", "q": {"value": 1, "unit": "bar"}},
                }},
                {"id": "sink_v", "type": "Sink", "name": "Vapor Out", "x": 200, "y": -50, "params": {}},
                {"id": "sink_l", "type": "Sink", "name": "Liquid Out", "x": 200, "y": 50, "params": {}},
            ],
            "edges": [
                {
                    "id": "s1",
                    "from": {"nodeId": "feed1", "portName": "out"},
                    "to": {"nodeId": "flash1", "portName": "in"},
                    "spec": {
                        "T": {"kind": "quantity", "value": 300, "unit": "K"},
                        "P": {"kind": "quantity", "value": 101325, "unit": "Pa"},
                        "flow": {"kind": "quantity", "value": 1, "unit": "kmol/h"},
                        "composition": {"water": 0.5, "co2": 0.3, "n2": 0.2},
                    },
                },
                {
                    "id": "s2",
                    "from": {"nodeId": "flash1", "portName": "overhead"},
                    "to": {"nodeId": "sink_v", "portName": "in"},
                },
                {
                    "id": "s3",
                    "from": {"nodeId": "flash1", "portName": "bottoms"},
                    "to": {"nodeId": "sink_l", "portName": "in"},
                },
            ],
        },
    }


def test_build_model():
    from app.models.jasper_schema import JasperProject
    from app.core.model_builder import IdaesModelBuilder

    project = JasperProject(**_make_seed_project())
    builder = IdaesModelBuilder(project)
    model = builder.build()
    assert model is not None
    assert hasattr(model, 'fs')
    assert len(builder.unit_map) == 4


def test_topological_order():
    from app.models.jasper_schema import JasperProject
    from app.core.model_builder import IdaesModelBuilder

    project = JasperProject(**_make_seed_project())
    builder = IdaesModelBuilder(project)
    builder.build()
    order = builder._topological_order()
    # feed1 should come before flash1
    assert order.index("feed1") < order.index("flash1")
