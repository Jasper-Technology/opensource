"""Tests for the ParamValue unwrapper utility."""
from app.core.model_builder import _unwrap_param


def test_unwrap_quantity():
    param = {"kind": "quantity", "q": {"value": 350, "unit": "K"}}
    result = _unwrap_param(param)
    assert result == {"value": 350, "unit": "K"}


def test_unwrap_number():
    param = {"kind": "number", "x": 42.5}
    assert _unwrap_param(param) == 42.5


def test_unwrap_int():
    param = {"kind": "int", "n": 7}
    assert _unwrap_param(param) == 7


def test_unwrap_string():
    param = {"kind": "string", "s": "isentropic"}
    assert _unwrap_param(param) == "isentropic"


def test_unwrap_boolean():
    param = {"kind": "boolean", "b": True}
    assert _unwrap_param(param) is True


def test_unwrap_enum():
    param = {"kind": "enum", "e": "SRK"}
    assert _unwrap_param(param) == "SRK"


def test_unwrap_composition():
    comp = {"H2O": 0.5, "CO2": 0.5}
    param = {"kind": "composition", "comp": comp}
    assert _unwrap_param(param) == comp


def test_passthrough_plain_value():
    assert _unwrap_param(42) == 42
    assert _unwrap_param("hello") == "hello"
    assert _unwrap_param(None) is None


def test_passthrough_dict_without_kind():
    d = {"value": 100, "unit": "K"}
    assert _unwrap_param(d) == d


def test_unknown_kind_returns_param():
    param = {"kind": "unknown_type", "data": 123}
    assert _unwrap_param(param) == param
