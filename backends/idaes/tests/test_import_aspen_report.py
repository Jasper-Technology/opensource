"""Tests for the Aspen Plus .rep parser."""
from __future__ import annotations

from app.import_ import parse_aspen_report


def _parse(text: str):
    return parse_aspen_report(text.encode("utf-8"), filename="test.rep")


class TestAspenRep:
    def test_empty_emits_error(self) -> None:
        r = _parse("")
        assert r.project is None
        assert any(d.severity == "error" for d in r.diagnostics)

    def test_stream_table(self) -> None:
        text = """
STREAM ID               S1          S2
TEMPERATURE     K      300.0       400.0
PRESSURE        PA     100000      200000
MOLE FLOW       MOL/S  1.0         0.5
MOLE FRAC
  H2                   0.67        0.00
  CO                   0.33        0.00
  METHANOL             0.00        1.00
"""
        r = _parse(text)
        assert r.project is not None
        streams = {s.id: s for s in r.project.streams}
        s1 = streams["S1"]
        assert abs(s1.T - 300.0) < 0.01
        assert abs(s1.P - 100_000.0) < 1.0
        assert abs(s1.flow_mol - 1.0) < 1e-6
        assert s1.composition["H2"] == 0.67
        assert streams["S2"].composition["METHANOL"] == 1.00

    def test_unit_conversion_c_bar_kmolh(self) -> None:
        text = """
STREAM ID               S1
TEMPERATURE     C       25
PRESSURE        BAR     1
MOLE FLOW       KMOL/HR 3.6
"""
        r = _parse(text)
        assert r.project is not None
        s1 = r.project.streams[0]
        assert abs(s1.T - 298.15) < 0.01
        assert abs(s1.P - 100_000.0) < 1.0
        assert abs(s1.flow_mol - 1.0) < 1e-6

    def test_block_section(self) -> None:
        text = """
BLOCK:  R1     MODEL: RSTOIC
  HEAT DUTY   KW   1234.5
  PRESSURE DROP BAR 0.5

BLOCK:  P1     MODEL: PUMP
  BRAKE HORSEPOWER   KW   50.0
"""
        r = _parse(text)
        assert r.project is not None
        blocks = {b.id: b for b in r.project.blocks}
        assert blocks["R1"].type == "RStoic"
        assert blocks["R1"].duty == 1234.5
        assert blocks["P1"].type == "Pump"
        assert blocks["P1"].work == 50.0

    def test_unmapped_model_emits_info(self) -> None:
        text = """
BLOCK:  X1     MODEL: FORTRAN
"""
        r = _parse(text)
        assert any(
            d.severity == "info" and "FORTRAN" in d.message.upper()
            for d in r.diagnostics
        )

    def test_oversized_rejected(self) -> None:
        big = b"X" * (26 * 1024 * 1024)
        r = parse_aspen_report(big, filename="big.rep")
        assert r.project is None
