"""Simulation endpoint for running IDAES flowsheet simulations."""
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.models.jasper_schema import JasperProject, SimulationOptions
from app.models.results import SimulationResult, StreamResult, UnitResult
from app.core.model_builder import IdaesModelBuilder
from app.core.result_extractor import ResultExtractor
from app.core.simulation_queue import simulation_queue

logger = logging.getLogger(__name__)
router = APIRouter()


class SimulateRequest(BaseModel):
    """Request body for simulation endpoint."""
    project: JasperProject
    options: Optional[SimulationOptions] = None
    specs: Optional[list[dict]] = None  # design specs (optional)


class SimulateSubmitResponse(BaseModel):
    """Returned immediately when a simulation job is accepted."""
    job_id: str
    status: str       # 'queued' or 'running'
    position: int     # 0 = started immediately, 1+ = waiting in line
    queue_length: int # total jobs ahead


def _run_simulation_sync(
    project: JasperProject,
    options: SimulationOptions,
    specs: Optional[list[dict]] = None,
) -> dict:
    """
    Synchronous simulation logic run inside a thread-pool worker.

    IPOPT and IDAES model construction are CPU-bound; running them in a
    thread prevents blocking the asyncio event loop.
    """
    start_time = time.time()
    messages = []

    # Validate feed stream compositions sum to ~1.0
    for edge in project.flowsheet.edges:
        if edge.spec and edge.spec.composition:
            total = sum(edge.spec.composition.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(
                    f"Stream {edge.id}: composition sums to {total:.4f} "
                    f"(must be within 0.999–1.001). "
                    f"Adjust mole fractions before running."
                )
    for node in project.flowsheet.nodes:
        if node.type == "Feed" and "composition" in node.params:
            comp = node.params.get("composition")
            if isinstance(comp, dict):
                # ParamValue format: { kind: 'composition', comp: {...} }
                comp_data = comp.get("comp", comp)
                if isinstance(comp_data, dict):
                    def _extract_num(v):
                        if isinstance(v, (int, float)):
                            return float(v)
                        if isinstance(v, dict):
                            return float(v.get("x", v.get("value", 0)))
                        return 0.0
                    total = sum(_extract_num(v) for v in comp_data.values())
                    if abs(total - 1.0) > 0.001:
                        raise ValueError(
                            f"Feed {node.id} ({node.name}): composition sums to "
                            f"{total:.4f} (must be within 0.999–1.001)."
                        )

    # Warn when activity coefficient models are requested
    pm = project.thermodynamics.propertyMethod
    if pm in ("NRTL", "UNIQUAC"):
        messages.append(
            f"Note: {pm} requires binary interaction parameters not yet in the "
            "component database. Simulation will use Peng-Robinson (PR) instead."
        )

    # Build IDAES model
    try:
        builder = IdaesModelBuilder(project)
        model = builder.build()
        messages.append("Model built successfully")
        messages.extend(builder.arc_warnings)
    except Exception as exc:
        raise RuntimeError(f"Model build failed: {exc}") from exc

    # Check degrees of freedom
    dof = 0
    try:
        from idaes.core.util.model_statistics import degrees_of_freedom
        dof = degrees_of_freedom(model)
        if dof != 0:
            messages.append(f"Warning: Model has {dof} degrees of freedom (should be 0)")
    except Exception as exc:
        messages.append(f"Warning: Could not compute degrees of freedom: {exc}")

    # Initialize
    try:
        builder.initialize()
        messages.append("Model initialized")
    except Exception as exc:
        messages.append(f"Warning: Initialization failed: {exc}. Attempting solve anyway.")

    # Attach design specs (optional)
    spec_records: list[dict] = []
    if specs:
        try:
            from app.core.design_specs import attach_design_specs
            spec_records = attach_design_specs(builder, specs)
            attached = sum(1 for r in spec_records if r.get("status") == "attached")
            skipped = sum(1 for r in spec_records if r.get("status") == "skipped")
            messages.append(f"Design specs: {attached} attached, {skipped} skipped")
            for r in spec_records:
                if r.get("status") == "skipped":
                    messages.append(
                        f"  spec {r.get('specId')}: {r.get('reason','unknown')}"
                    )
        except Exception as exc:
            messages.append(f"Warning: Could not attach design specs: {exc}")

    # Solve
    try:
        result = builder.solve(
            solver=options.solver,
            max_iterations=options.max_iterations,
            tolerance=options.tolerance,
        )
    except Exception as exc:
        raise RuntimeError(f"Solver failed: {exc}") from exc

    solve_time = time.time() - start_time

    # Extract results
    extractor = ResultExtractor(model, builder.unit_map, builder.arc_map,
                                 builder.arc_phase_map)
    streams = extractor.extract_streams()
    units = extractor.extract_units()

    converged = str(result.solver.termination_condition) == "optimal"

    # Evaluate design specs post-solve
    spec_results: list[dict] = []
    if spec_records:
        try:
            from app.core.design_specs import evaluate_design_specs
            spec_results = evaluate_design_specs(spec_records, builder, specs or [])
        except Exception as exc:
            messages.append(f"Warning: Could not evaluate design specs: {exc}")

    return {
        "status": "success" if converged else "warning",
        "converged": converged,
        "solver_status": str(result.solver.termination_condition),
        "iterations": result.solver.iterations if hasattr(result.solver, "iterations") else 0,
        "solve_time": solve_time,
        "streams": [s.model_dump() for s in streams],
        "units": [u.model_dump() for u in units],
        "degrees_of_freedom": dof,
        "messages": messages,
        "spec_results": spec_results,
    }


@router.post("/simulate", response_model=SimulateSubmitResponse)
async def submit_simulation(
    request: Request,
    body: SimulateRequest,
    _key: str = Depends(require_api_key),
):
    """
    Submit a simulation job.

    Returns immediately with a job_id and queue position.
    Poll GET /api/jobs/{job_id} to retrieve the result when done.
    """
    # Rate limit: 10 simulate submissions per IP per minute
    from app.core.rate_limiter import rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too many simulation requests. Please wait before submitting again.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    options = body.options or SimulationOptions()

    # Per-solve timeout. The thread can't be killed, but releasing the queue
    # slot lets other clients proceed instead of hanging forever.
    SOLVE_TIMEOUT_SECONDS = 300

    async def simulation_coro():
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_run_simulation_sync, body.project, options, body.specs),
                timeout=SOLVE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            logger.error("Simulation exceeded %ss timeout", SOLVE_TIMEOUT_SECONDS)
            raise HTTPException(
                status_code=504,
                detail={"error": f"Simulation exceeded {SOLVE_TIMEOUT_SECONDS}s timeout", "messages": []},
            ) from exc
        except ValueError as exc:
            # Composition or other validation errors → surface as 400
            raise HTTPException(
                status_code=400,
                detail={"error": str(exc), "messages": []},
            ) from exc
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error("Simulation thread failed: %s\n%s", exc, tb)
            raise

    job = await simulation_queue.enqueue_and_run(simulation_coro())

    return SimulateSubmitResponse(
        job_id=job.id,
        status=job.status,
        position=job.position,
        queue_length=simulation_queue.queue_depth(),
    )
