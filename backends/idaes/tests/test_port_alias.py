"""Tests for the canonical port-name alias resolver."""
from __future__ import annotations
import pytest

from app.data.port_alias import (
    CANONICAL_PORTS,
    ResolvedPort,
    UnknownPortError,
    is_canonical,
    resolve,
    try_resolve,
)


class TestCanonicalDetection:
    def test_known_canonical_names(self) -> None:
        for name in ["in", "out", "vapor", "liquid", "hot-in", "cold-out", "overhead", "bottoms"]:
            assert is_canonical(name), f"{name} should be canonical"

    def test_dynamic_canonical_names(self) -> None:
        for name in ["in1", "in2", "in10", "out1", "out50"]:
            assert is_canonical(name), f"{name} should be canonical (dynamic)"

    def test_legacy_names_are_not_canonical(self) -> None:
        for name in ["distillate", "inlet", "outlet", "vap", "hot_inlet", "tube-in"]:
            assert not is_canonical(name), f"{name} must not be canonical"


class TestResolveStaticAliases:
    def test_distillate_resolves_to_overhead(self) -> None:
        got = resolve("distillate")
        assert got.canonical == "overhead"
        assert got.was_alias is True
        assert got.original == "distillate"

    def test_inlet_resolves_to_in(self) -> None:
        # No valid_ports context — resolver takes first candidate for
        # single-alias keys, but "inlet" has two targets. Needs context.
        got = resolve("inlet", valid_ports=["in", "out"])
        assert got.canonical == "in"

    def test_inlet_resolves_to_feed_on_column(self) -> None:
        got = resolve("inlet", valid_ports=["feed", "overhead", "bottoms"])
        assert got.canonical == "feed"

    def test_ambiguous_alias_without_context_picks_first_target(self) -> None:
        # "inlet" maps to ("in", "feed"); without valid_ports the resolver
        # takes the first target as a best-effort default (safe for
        # single-port blocks and migrations).
        got = resolve("inlet")
        assert got.canonical == "in"
        assert got.was_alias is True

    def test_canonical_name_returns_self(self) -> None:
        got = resolve("overhead")
        assert got.canonical == "overhead"
        assert got.was_alias is False

    def test_hx_port_aliases(self) -> None:
        hx_ports = ["hot-in", "hot-out", "cold-in", "cold-out"]
        assert resolve("hot_inlet", valid_ports=hx_ports).canonical == "hot-in"
        assert resolve("shell-in", valid_ports=hx_ports).canonical == "hot-in"
        assert resolve("tube-in", valid_ports=hx_ports).canonical == "cold-in"

    def test_column_port_aliases(self) -> None:
        col_ports = ["feed", "overhead", "bottoms"]
        assert resolve("top", valid_ports=col_ports).canonical == "overhead"
        assert resolve("tops", valid_ports=col_ports).canonical == "overhead"
        assert resolve("distillate", valid_ports=col_ports).canonical == "overhead"
        assert resolve("btms", valid_ports=col_ports).canonical == "bottoms"


class TestResolveDynamicAliases:
    def test_inlet_number_maps_to_in_number(self) -> None:
        got = resolve("inlet3")
        assert got.canonical == "in3"
        assert got.was_alias is True

    def test_outlet_underscore_number(self) -> None:
        assert resolve("outlet_5").canonical == "out5"

    def test_feed_number(self) -> None:
        assert resolve("feed2").canonical == "in2"

    def test_product_number(self) -> None:
        assert resolve("product7").canonical == "out7"

    def test_canonical_dynamic_returns_self(self) -> None:
        got = resolve("in3")
        assert got.canonical == "in3"
        assert got.was_alias is False


class TestUnknownNames:
    def test_unknown_raises(self) -> None:
        with pytest.raises(UnknownPortError) as exc_info:
            resolve("banana")
        assert "banana" in str(exc_info.value)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(UnknownPortError):
            resolve("")

    def test_error_includes_unit_context(self) -> None:
        with pytest.raises(UnknownPortError) as exc_info:
            resolve("phantom", unit_type="Reactor")
        assert "Reactor" in str(exc_info.value)

    def test_try_resolve_returns_none_on_unknown(self) -> None:
        assert try_resolve("banana") is None


class TestCanonicalPortsSet:
    """Sanity — no duplicates with aliases, no dynamic forms leaked in."""

    def test_no_digits_in_canonical_set(self) -> None:
        for name in CANONICAL_PORTS:
            assert not any(c.isdigit() for c in name), f"{name} has digits (dynamic leaked in)"

    def test_every_canonical_resolves_to_itself(self) -> None:
        for name in CANONICAL_PORTS:
            got = resolve(name, valid_ports=[name])
            assert got.canonical == name
            assert got.was_alias is False


class TestResolvedPortStruct:
    def test_resolved_port_is_frozen_dataclass(self) -> None:
        got = resolve("distillate")
        assert isinstance(got, ResolvedPort)
        with pytest.raises(Exception):
            got.canonical = "something"  # type: ignore[misc]
