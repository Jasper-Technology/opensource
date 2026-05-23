"""Tests for the Aspen Plus .inp parser."""
from __future__ import annotations

from app.import_ import parse_aspen_inp


def _parse(text: str):
    return parse_aspen_inp(text.encode("utf-8"), filename="test.inp")


class TestAspenInpBasics:
    def test_empty_file_emits_error(self) -> None:
        r = _parse("")
        assert r.project is None
        assert any(d.severity == "error" for d in r.diagnostics)

    def test_minimal_block_and_stream(self) -> None:
        text = """
TITLE "Methanol Synthesis"
COMPONENTS
  H2 H2 /
  CO CO /
  METHANOL CH4O /

FLOWSHEET
  BLOCK R1 IN=S1 OUT=S2

BLOCK R1 RSTOIC

STREAM S1 TEMP=250 PRES=50 MOLE-FLOW=100
"""
        r = _parse(text)
        assert r.project is not None
        assert r.project.name == "Methanol Synthesis"
        assert "H2" in r.project.components
        assert "METHANOL" in r.project.components
        blocks = {b.id: b for b in r.project.blocks}
        assert blocks["R1"].type == "RStoic"

    def test_block_type_mapping(self) -> None:
        text = """
BLOCK P1 PUMP
BLOCK C1 COMPR
BLOCK H1 HEATER
BLOCK M1 MIXER
BLOCK D1 RADFRAC
"""
        r = _parse(text)
        assert r.project is not None
        types = {b.id: b.type for b in r.project.blocks}
        assert types == {
            "P1": "Pump",
            "C1": "Compressor",
            "H1": "Heater",
            "M1": "Mixer",
            "D1": "DistillationColumn",
        }

    def test_unmapped_type_emits_info_diagnostic(self) -> None:
        r = _parse("BLOCK X1 FORTRAN\n")
        assert any(
            d.severity == "info" and "FORTRAN" in d.message.upper()
            for d in r.diagnostics
        )

    def test_in_units_conversion_c_to_k(self) -> None:
        text = """
IN-UNITS SI TEMPERATURE=C PRESSURE=bar MOLE-FLOW=kmol/hr

STREAM S1 TEMP=25 PRES=1 MOLE-FLOW=3.6
"""
        r = _parse(text)
        assert r.project is not None
        s = r.project.streams[0]
        assert s.T is not None and abs(s.T - 298.15) < 0.01
        assert s.P is not None and abs(s.P - 100_000.0) < 1.0
        # 3.6 kmol/h = 1 mol/s
        assert s.flow_mol is not None and abs(s.flow_mol - 1.0) < 1e-6

    def test_stream_composition(self) -> None:
        text = """
STREAM S1 TEMP=300 PRES=100000 MOLE-FLOW=1
  MOLE-FRAC H2 0.67 / CO 0.33
"""
        r = _parse(text)
        assert r.project is not None
        s = r.project.streams[0]
        assert s.composition == {"H2": 0.67, "CO": 0.33}

    def test_flowsheet_wires_streams_to_block(self) -> None:
        text = """
FLOWSHEET
  BLOCK R1 IN=S1 OUT=S2

BLOCK R1 RSTOIC

STREAM S1 TEMP=300 PRES=100000 MOLE-FLOW=1
STREAM S2 TEMP=400 PRES=100000 MOLE-FLOW=1
"""
        r = _parse(text)
        assert r.project is not None
        streams = {s.id: s for s in r.project.streams}
        assert streams["S1"].to_block == "R1"
        assert streams["S2"].from_block == "R1"

    def test_oversized_file_rejected(self) -> None:
        big = b"X" * (26 * 1024 * 1024)
        r = parse_aspen_inp(big, filename="big.inp")
        assert r.project is None
        assert any("limit" in d.message.lower() for d in r.diagnostics)

    def test_pump_with_inline_power_param(self) -> None:
        text = """
BLOCK P1 PUMP PARAM POWER=50000
"""
        r = _parse(text)
        assert r.project is not None
        p1 = r.project.blocks[0]
        assert p1.type == "Pump"
        assert p1.work == 50000.0
