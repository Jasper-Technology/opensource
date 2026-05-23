"""Job status endpoint for polling async simulation results."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from app.core.auth import require_api_key
from app.core.simulation_queue import simulation_queue

logger = logging.getLogger(__name__)
router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: str
    status: str          # queued | running | done | error
    position: int        # 0 = running, 1+ = place in queue
    queue_length: int    # total jobs ahead + running
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    messages: list[str] = []


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, _key: str = Depends(require_api_key)):
    """
    Poll a simulation job by ID.

    Returns immediately with current status. When status is 'done',
    result contains the full SimulateResponse payload. When 'error',
    error and traceback are populated.
    """
    job = simulation_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    simulation_queue.cleanup_old_jobs()

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        position=job.position,
        queue_length=simulation_queue.queue_depth(),
        result=job.result,
        error=job.error,
        traceback=job.traceback,
        messages=job.messages,
    )
