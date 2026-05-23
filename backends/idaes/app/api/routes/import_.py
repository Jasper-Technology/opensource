"""Import endpoint — multipart upload → ImportedProject JSON."""
from __future__ import annotations
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.comprehend import annotate as comprehend_annotate
from app.import_ import (
    parse_excel,
    parse_dwxml,
    describe_to_project,
    parse_aspen_inp,
    parse_aspen_report,
)
from app.import_.models import ImportedBlock, ImportedStream, ImportResult

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response shapes ─────────────────────────────────────────────────────────


class DiagnosticOut(BaseModel):
    severity: Literal["error", "warning", "info"]
    message: str
    location: Optional[str] = None


class ImportedStreamOut(BaseModel):
    id: str
    from_block: Optional[str]
    from_port: Optional[str]
    to_block: Optional[str]
    to_port: Optional[str]
    T: Optional[float]
    P: Optional[float]
    flow_mol: Optional[float]
    flow_mass: Optional[float]
    composition: dict[str, float]


class ImportedBlockOut(BaseModel):
    id: str
    type: str
    name: str
    duty: Optional[float]
    work: Optional[float]
    pressure_drop: Optional[float]


class BlockAnnotationOut(BaseModel):
    block_id: str
    role: str
    notes: Optional[str] = None


class AnnotationsOut(BaseModel):
    process_name: str
    product_block_id: Optional[str] = None
    product_stream_id: Optional[str] = None
    feedstock_block_id: Optional[str] = None
    feedstock_stream_id: Optional[str] = None
    block_annotations: dict[str, BlockAnnotationOut] = {}
    flags: list[str] = []


class ImportResponse(BaseModel):
    project_name: Optional[str]
    blocks: list[ImportedBlockOut]
    streams: list[ImportedStreamOut]
    components: list[str]
    diagnostics: list[DiagnosticOut]
    summary: dict[str, int]
    annotations: Optional[AnnotationsOut] = None


def _to_out(
    blocks: list[ImportedBlock],
    streams: list[ImportedStream],
) -> tuple[list[ImportedBlockOut], list[ImportedStreamOut]]:
    b_out = [
        ImportedBlockOut(
            id=b.id, type=b.type, name=b.name,
            duty=b.duty, work=b.work, pressure_drop=b.pressure_drop,
        )
        for b in blocks
    ]
    s_out = [
        ImportedStreamOut(
            id=s.id,
            from_block=s.from_block, from_port=s.from_port,
            to_block=s.to_block, to_port=s.to_port,
            T=s.T, P=s.P, flow_mol=s.flow_mol, flow_mass=s.flow_mass,
            composition=s.composition,
        )
        for s in streams
    ]
    return b_out, s_out


# ── Endpoint ───────────────────────────────────────────────────────────────


def _result_to_response(result: ImportResult) -> ImportResponse:
    diagnostics = [
        DiagnosticOut(severity=d.severity, message=d.message, location=d.location)
        for d in result.diagnostics
    ]
    if result.project is None:
        return ImportResponse(
            project_name=None,
            blocks=[],
            streams=[],
            components=[],
            diagnostics=diagnostics,
            summary={
                "blocks": 0,
                "streams": 0,
                "components": 0,
                "errors": result.count("error"),
                "warnings": result.count("warning"),
            },
        )

    b_out, s_out = _to_out(result.project.blocks, result.project.streams)

    # Run heuristic comprehension so the frontend gets annotations without
    # a second round-trip. Cheap (pure graph walk, no LLM).
    ann = comprehend_annotate(result.project)
    annotations = AnnotationsOut(
        process_name=ann.process_name,
        product_block_id=ann.product_block_id,
        product_stream_id=ann.product_stream_id,
        feedstock_block_id=ann.feedstock_block_id,
        feedstock_stream_id=ann.feedstock_stream_id,
        block_annotations={
            bid: BlockAnnotationOut(block_id=ba.block_id, role=ba.role, notes=ba.notes)
            for bid, ba in ann.block_annotations.items()
        },
        flags=ann.flags,
    )

    return ImportResponse(
        project_name=result.project.name,
        blocks=b_out,
        streams=s_out,
        components=result.project.components,
        diagnostics=diagnostics,
        summary={
            "blocks": len(b_out),
            "streams": len(s_out),
            "components": len(result.project.components),
            "errors": result.count("error"),
            "warnings": result.count("warning"),
        },
        annotations=annotations,
    )


@router.post("/import/excel", response_model=ImportResponse)
async def import_excel(file: UploadFile = File(...)) -> ImportResponse:
    """
    Upload a Jasper Excel template. Returns the parsed ImportedProject
    plus diagnostics (per-cell errors and warnings).
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return _result_to_response(parse_excel(data, filename=file.filename or "upload.xlsx"))


@router.post("/import/dwsim", response_model=ImportResponse)
async def import_dwsim(file: UploadFile = File(...)) -> ImportResponse:
    """Upload a DWSIM .dwxml simulation export."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return _result_to_response(parse_dwxml(data, filename=file.filename or "simulation.dwxml"))


@router.post("/import/aspen-inp", response_model=ImportResponse)
async def import_aspen_inp(file: UploadFile = File(...)) -> ImportResponse:
    """Upload an Aspen Plus .inp input-summary export."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return _result_to_response(parse_aspen_inp(data, filename=file.filename or "aspen.inp"))


@router.post("/import/aspen-report", response_model=ImportResponse)
async def import_aspen_rep(file: UploadFile = File(...)) -> ImportResponse:
    """Upload an Aspen Plus .rep Results Summary report."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return _result_to_response(
        parse_aspen_report(data, filename=file.filename or "aspen.rep")
    )


class DescribeRequest(BaseModel):
    description: str


@router.post("/import/describe", response_model=ImportResponse)
def import_describe(req: DescribeRequest) -> ImportResponse:
    """
    Plain-English → starter flowsheet via Claude.

    Produces the same ImportResponse shape as the file-upload paths so
    the frontend treats it uniformly. When ANTHROPIC_API_KEY is unset,
    returns a minimal 3-block fallback template with an info diagnostic.
    """
    return _result_to_response(describe_to_project(req.description))
