"""Tests for the heuristic comprehension layer."""
from __future__ import annotations

from app.comprehend import annotate, infer_feedstock, infer_product
from app.import_.models import ImportedBlock, ImportedProject, ImportedStream


def _methanol_project() -> ImportedProject:
    return ImportedProject(
        name="Methanol",
        components=["H2", "CO", "Methanol"],
        blocks=[
            ImportedBlock(id="F1", type="Feed", name="Syngas feed"),
            ImportedBlock(id="C1", type="Compressor", name="Compressor", work=2_500_000),
            ImportedBlock(id="R1", type="REquil", name="Reactor"),
            ImportedBlock(id="X1", type="Flash", name="Flash drum"),
            ImportedBlock(id="P1", type="Product", name="Methanol product"),
        ],
        streams=[
            ImportedStream(
                id="S1", from_block="F1", from_port="out", to_block="C1", to_port="in",
                T=300, P=1e5, flow_mol=100,
                composition={"H2": 0.67, "CO": 0.33},
            ),
            ImportedStream(
                id="S2", from_block="C1", from_port="out", to_block="R1", to_port="in",
                T=313, P=8e6, flow_mol=100,
                composition={"H2": 0.67, "CO": 0.33},
            ),
            ImportedStream(
                id="S3", from_block="R1", from_port="out", to_block="X1", to_port="in",
                T=513, P=8e6, flow_mol=60,
                composition={"H2": 0.20, "CO": 0.10, "Methanol": 0.70},
            ),
            ImportedStream(
                id="S4", from_block="X1", from_port="liquid", to_block="P1", to_port="in",
                T=313, P=5e5, flow_mol=42,
                composition={"H2": 0.01, "CO": 0.01, "Methanol": 0.98},
            ),
        ],
    )


class TestAnnotate:
    def test_assigns_role_per_block(self) -> None:
        ann = annotate(_methanol_project())
        assert ann.block_annotations["F1"].role == "Feed source"
        assert ann.block_annotations["C1"].role == "Gas compression"
        assert ann.block_annotations["X1"].role == "Vapor/liquid separation"
        assert ann.block_annotations["P1"].role == "Product sink"

    def test_identifies_methanol_product(self) -> None:
        ann = annotate(_methanol_project())
        assert ann.product_block_id == "P1"
        assert ann.product_stream_id == "S4"

    def test_identifies_syngas_feedstock(self) -> None:
        ann = annotate(_methanol_project())
        assert ann.feedstock_block_id == "F1"
        assert ann.feedstock_stream_id == "S1"

    def test_reactor_role_refined_by_outlet_composition(self) -> None:
        ann = annotate(_methanol_project())
        r_role = ann.block_annotations["R1"]
        assert "Methanol" in r_role.role  # "Methanol synthesis"
        assert r_role.notes and "Methanol" in r_role.notes


class TestInferProduct:
    def test_picks_highest_purity_non_common_gas(self) -> None:
        # Two sinks, only one terminates a methanol-rich stream
        project = ImportedProject(
            name="p", components=["Methanol", "H2O"],
            blocks=[
                ImportedBlock(id="S1", type="Sink", name="sink1"),
                ImportedBlock(id="S2", type="Sink", name="sink2"),
            ],
            streams=[
                ImportedStream(id="A", from_block=None, from_port=None,
                               to_block="S1", to_port="in",
                               T=300, P=1e5, flow_mol=10,
                               composition={"Methanol": 0.99, "H2O": 0.01}),
                ImportedStream(id="B", from_block=None, from_port=None,
                               to_block="S2", to_port="in",
                               T=300, P=1e5, flow_mol=10,
                               composition={"Methanol": 0.70, "H2O": 0.30}),
            ],
        )
        result = infer_product(project)
        assert result == ("S1", "A")

    def test_returns_none_when_no_sinks(self) -> None:
        project = ImportedProject(
            name="p", components=[], blocks=[],
            streams=[],
        )
        assert infer_product(project) is None


class TestFlags:
    def test_no_recycle_flag_for_reactor_project(self) -> None:
        ann = annotate(_methanol_project())
        # The test project has no recycle by construction
        assert any("recycle" in f.lower() for f in ann.flags)

    def test_unknown_component_flag(self) -> None:
        project = ImportedProject(
            name="p", components=["Unobtanium"],
            blocks=[ImportedBlock(id="R", type="Reactor", name="r")],
            streams=[
                ImportedStream(id="s", from_block="R", from_port="out",
                               to_block=None, to_port=None,
                               T=300, P=1e5, flow_mol=1,
                               composition={"Unobtanium": 1.0}),
            ],
        )
        ann = annotate(project)
        assert any("Unknown components" in f for f in ann.flags)

    def test_feed_no_composition_flag(self) -> None:
        project = ImportedProject(
            name="p", components=[],
            blocks=[
                ImportedBlock(id="F", type="Feed", name="f"),
                ImportedBlock(id="S", type="Sink", name="s"),
            ],
            streams=[
                ImportedStream(id="s1", from_block="F", from_port="out",
                               to_block="S", to_port="in",
                               T=300, P=1e5, flow_mol=1, composition={}),
            ],
        )
        ann = annotate(project)
        assert any("no composition" in f for f in ann.flags)
