"""
Simulation job queue with concurrency limiting.

Limits simultaneous IPOPT/IDAES solves to MAX_CONCURRENT.
Jobs exceeding the limit are queued and their position is tracked
so the frontend can display a waitlist.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Maximum simultaneous IDAES solves. IPOPT is CPU-bound; more than
# 2 concurrent solves on a single Railway instance degrades performance.
MAX_CONCURRENT = 2

# Keep completed/failed jobs in memory for this long before cleaning up.
JOB_TTL_SECONDS = 3600


@dataclass
class SimJob:
    id: str
    created_at: float = field(default_factory=time.time)
    status: str = "queued"          # queued | running | done | error
    position: int = 0               # 0 = running, 1+ = position in queue
    queue_length: int = 0           # snapshot of total queue depth when submitted
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    messages: list[str] = field(default_factory=list)


class SimulationQueue:
    """
    Async job queue backed by asyncio.Semaphore.

    Callers submit a coroutine via `enqueue_and_run`. The coroutine is
    scheduled as an asyncio background task and will wait for a semaphore
    slot before executing. The returned SimJob object is updated in-place
    as the job progresses; callers poll it via `get_job`.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._jobs: dict[str, SimJob] = {}
        self._pending: list[str] = []   # ordered list of waiting job IDs
        self._lock = asyncio.Lock()

    async def enqueue_and_run(self, coro) -> SimJob:
        """
        Register a new job and immediately schedule it as a background task.

        Returns the SimJob with its initial position. The job status and
        result are updated asynchronously; poll via get_job().
        """
        job_id = str(uuid.uuid4())
        async with self._lock:
            job = SimJob(id=job_id)
            self._jobs[job_id] = job
            self._pending.append(job_id)
            job.position = len(self._pending)
            job.queue_length = len(self._pending)

        asyncio.create_task(self._run(job, coro))
        return job

    async def _run(self, job: SimJob, coro) -> None:
        """Wait for a semaphore slot, then execute the coroutine."""
        async with self._semaphore:
            async with self._lock:
                # Remove from pending and update remaining positions
                try:
                    self._pending.remove(job.id)
                except ValueError:
                    pass
                for i, jid in enumerate(self._pending):
                    self._jobs[jid].position = i + 1
                job.status = "running"
                job.position = 0

            logger.info("Job %s started", job.id)
            try:
                job.result = await coro
                job.status = "done"
                logger.info("Job %s completed", job.id)
            except Exception as exc:
                import traceback as tb_mod
                job.error = str(exc)
                job.traceback = tb_mod.format_exc()
                job.status = "error"
                logger.error("Job %s failed: %s", job.id, exc)

    def get_job(self, job_id: str) -> Optional[SimJob]:
        return self._jobs.get(job_id)

    def queue_depth(self) -> int:
        """Number of jobs currently waiting (not yet running)."""
        return len(self._pending)

    def cleanup_old_jobs(self) -> None:
        """Remove completed/failed jobs older than JOB_TTL_SECONDS."""
        cutoff = time.time() - JOB_TTL_SECONDS
        stale = [
            jid for jid, job in self._jobs.items()
            if job.status in ("done", "error") and job.created_at < cutoff
        ]
        for jid in stale:
            del self._jobs[jid]
        if stale:
            logger.debug("Cleaned up %d stale jobs", len(stale))


# Module-level singleton shared across all requests
simulation_queue = SimulationQueue()
