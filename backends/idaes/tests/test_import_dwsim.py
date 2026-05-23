"""Tests for the DWSIM .dwxml parser."""
from __future__ import annotations
import pytest

from app.import_ import parse_dwxml


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DWSIMSimulation>
  <SimulationObjects>
    <SimulationObject>
      <Name>P-101</Name>
      <Tag>Feed Pump</Tag>
      <ObjectType>Pump</ObjectType>
      <DeltaP>500000</DeltaP>
    </SimulationObject>
    <SimulationObject>
      <Name>H-101</Name>
      <Tag>Preheater</Tag>
      <ObjectType>Heater</ObjectType>
    </SimulationObject>
    <SimulationObject>
      <Name>MS-1</Name>
      <ObjectType>MaterialStream</ObjectType>
      <UpstreamObject>P-101</UpstreamObject>
      <DownstreamObject>H-101</DownstreamObject>
      <Phase>
        <Temperature>300.0</Temperature>
        <Pressure>500000</Pressure>
        <MolarFlow>10.0</MolarFlow>
        <MassFlow>0.5</MassFlow>
      </Phase>
      <Composition>
        <Compound Name="H2">0.67</Compound>
        <Compound Name="CO">0.33</Compound>
      </Composition>
    </SimulationObject>
    <SimulationObject>
      <Name>ES-1</Name>
      <ObjectType>EnergyStream</ObjectType>
      <DownstreamObject>P-101</DownstreamObject>
      <EnergyFlow>50000</EnergyFlow>
    </SimulationObject>
    <SimulationObject>
      <Name>ES-2</Name>
      <ObjectType>EnergyStream</ObjectType>
      <DownstreamObject>H-101</DownstreamObject>
      <EnergyFlow>1000000</EnergyFlow>
    </SimulationObject>
  </SimulationObjects>
  <CompoundCollection>
    <Compound Name="H2"/>
    <Compound Name="CO"/>
  </CompoundCollection>
</DWSIMSimulation>
"""


def test_parses_blocks() -> None:
    result = parse_dwxml(SAMPLE_XML.encode())
    assert result.project is not None
    ids = [b.id for b in result.project.blocks]
    assert set(ids) == {"P-101", "H-101"}


def test_attaches_energy_to_blocks() -> None:
    result = parse_dwxml(SAMPLE_XML.encode())
    pump = next(b for b in result.project.blocks if b.id == "P-101")
    heater = next(b for b in result.project.blocks if b.id == "H-101")
    # Pump gets work, heater gets duty
    assert pump.work == 50_000
    assert heater.duty == 1_000_000


def test_parses_stream_with_composition() -> None:
    result = parse_dwxml(SAMPLE_XML.encode())
    stream = result.project.streams[0]
    assert stream.id == "MS-1"
    assert stream.from_block == "P-101"
    assert stream.to_block == "H-101"
    assert stream.T == 300.0
    assert stream.P == 500_000
    assert stream.flow_mol == 10.0
    assert stream.composition == {"H2": 0.67, "CO": 0.33}


def test_unknown_object_types_emit_info_diagnostic() -> None:
    xml = b"""<?xml version="1.0"?>
    <DWSIMSimulation><SimulationObjects>
      <SimulationObject><Name>X1</Name><ObjectType>CustomReactor</ObjectType></SimulationObject>
      <SimulationObject><Name>P1</Name><ObjectType>Pump</ObjectType></SimulationObject>
    </SimulationObjects></DWSIMSimulation>"""
    result = parse_dwxml(xml)
    assert any(d.severity == "info" and "CustomReactor" in d.message for d in result.diagnostics)
    assert len(result.project.blocks) == 1


def test_components_extracted() -> None:
    result = parse_dwxml(SAMPLE_XML.encode())
    assert set(result.project.components) == {"H2", "CO"}


def test_empty_file_returns_error() -> None:
    result = parse_dwxml(b"<?xml version='1.0'?><DWSIMSimulation/>")
    assert result.project is None
    assert result.has_errors


def test_corrupt_file_returns_error() -> None:
    result = parse_dwxml(b"not xml at all")
    assert result.project is None
    assert result.has_errors


def test_oversize_rejected() -> None:
    big = b"x" * (25 * 1024 * 1024)
    result = parse_dwxml(big)
    assert result.has_errors
