"""Tests for the describe-in-English import path."""
from __future__ import annotations
import os

import pytest

from app.import_.describe import describe_to_project


class TestFallback:
    """When ANTHROPIC_API_KEY is absent, the rule-based fallback runs."""

    @pytest.fixture(autouse=True)
    def unset_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def test_empty_description_errors(self) -> None:
        result = describe_to_project("")
        assert result.project is None
        assert result.has_errors

    def test_whitespace_only_errors(self) -> None:
        result = describe_to_project("   \n  ")
        assert result.has_errors

    def test_oversize_description_rejected(self) -> None:
        result = describe_to_project("x" * 10_000)
        assert result.has_errors

    def test_reactor_keyword_produces_reactor_block(self) -> None:
        result = describe_to_project("Methanol synthesis with a CSTR reactor")
        assert result.project is not None
        types = {b.type for b in result.project.blocks}
        assert "Reactor" in types
        assert "Feed" in types

    def test_column_keyword_produces_column_block(self) -> None:
        result = describe_to_project("Distillation column for ethanol-water")
        types = {b.type for b in result.project.blocks}
        assert "DistillationColumn" in types

    def test_returns_sink_even_for_empty_keywords(self) -> None:
        result = describe_to_project("something opaque the rules don't match")
        types = {b.type for b in result.project.blocks}
        assert "Product" in types or "Sink" in types

    def test_diagnostic_notes_missing_api_key(self) -> None:
        result = describe_to_project("foo")
        assert any("ANTHROPIC_API_KEY" in d.message for d in result.diagnostics)

    def test_streams_connect_feed_to_product(self) -> None:
        result = describe_to_project("reactor then distillation")
        # Every block except the terminal Product is the source of at least one
        # outbound stream.
        sources = {s.from_block for s in result.project.streams}
        assert "F1" in sources
        # Sink/Product is the destination of the last stream
        last = result.project.streams[-1]
        assert last.to_block in ("P1",)


class TestPayloadMapping:
    """Directly exercise the Claude-payload → project mapping."""

    def test_valid_payload_maps_cleanly(self) -> None:
        from app.import_.describe import _payload_to_project

        payload = {
            "name": "Methanol",
            "components": ["H2", "CO", "Methanol"],
            "blocks": [
                {"id": "F1", "type": "Feed", "name": "Syngas"},
                {"id": "R1", "type": "Reactor", "name": "Synth reactor", "duty": -1.5e6},
                {"id": "P1", "type": "Product", "name": "Methanol out"},
            ],
            "streams": [
                {
                    "id": "S1", "from_block": "F1", "to_block": "R1",
                    "T": 300, "P": 1e5, "flow_mol": 10,
                    "composition": {"H2": 0.67, "CO": 0.33},
                },
            ],
        }
        result = _payload_to_project(payload, [])
        assert result.project is not None
        assert result.project.name == "Methanol"
        assert len(result.project.blocks) == 3
        assert result.project.blocks[1].duty == -1.5e6
        assert result.project.streams[0].composition == {"H2": 0.67, "CO": 0.33}

    def test_malformed_payload_returns_error(self) -> None:
        from app.import_.describe import _payload_to_project

        # Missing required 'type' field
        payload = {"blocks": [{"id": "F1"}], "streams": []}
        result = _payload_to_project(payload, [])
        assert result.project is None
        assert result.has_errors

    def test_numeric_coercion(self) -> None:
        from app.import_.describe import _payload_to_project

        payload = {
            "blocks": [
                {"id": "P1", "type": "Pump", "name": "Pump", "work": "50000"},
            ],
            "streams": [],
        }
        result = _payload_to_project(payload, [])
        assert result.project.blocks[0].work == 50000.0
