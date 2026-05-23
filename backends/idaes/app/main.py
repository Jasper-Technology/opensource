"""
Jasper IDAES Backend - Main FastAPI Application

This backend provides IDAES-powered simulation capabilities for Jasper.
Hosted on Railway with automatic sleep/wake functionality.
"""
import asyncio
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, components, units, jobs, tea
from app.api.routes import import_ as import_route

# Optional — heavy IDAES/pyomo-backed routes. Allow local dev without pyomo.
try:
    from app.api.routes import simulate, optimize, properties  # type: ignore
    from app.core.simulation_queue import simulation_queue  # type: ignore
    _HAS_IDAES = True
except ImportError as _idaes_exc:  # pragma: no cover - env-dependent
    simulate = optimize = properties = None  # type: ignore[assignment]
    simulation_queue = None  # type: ignore[assignment]
    _HAS_IDAES = False
    logging.getLogger(__name__).warning(
        "IDAES/pyomo routes unavailable (%s) — TEA + import + units endpoints will still serve.",
        _idaes_exc,
    )

logger = logging.getLogger(__name__)

# Sweep stale (completed/failed) jobs from the in-memory queue every 10 minutes.
# Without this, a long-lived Railway instance accumulates job records forever.
_CLEANUP_INTERVAL_SECONDS = 600


async def _periodic_cleanup() -> None:
    while True:
        try:
            await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
            if simulation_queue is not None:
                simulation_queue.cleanup_old_jobs()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Periodic cleanup failed: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cleanup_task = (
        asyncio.create_task(_periodic_cleanup()) if simulation_queue is not None else None
    )
    try:
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

_is_production = os.getenv("ENVIRONMENT", "production") == "production"

app = FastAPI(
    title="Jasper IDAES Backend",
    description="IDAES-powered simulation engine for Jasper",
    version="1.0.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    lifespan=lifespan,
)

# CORS configuration for Jasper frontend
_cors_raw = os.getenv("CORS_ORIGINS", "")
if _cors_raw:
    cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    cors_origins = []

if _is_production and not cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS must be set in production. Refusing to start with no allowlist."
    )

# In development, default to every vite/next/storybook dev port so the
# common "forgot to set CORS_ORIGINS" papercut goes away. Production still
# requires an explicit allowlist (guard above).
if not _is_production and not cors_origins:
    cors_origins = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (3000, 4173, 5173, 5174, 5175, 6006, 8080)
    ]
    logger.info("CORS_ORIGINS unset in development — defaulting to %d local dev origins", len(cors_origins))
elif not cors_origins:
    logger.warning("CORS_ORIGINS is not set — no cross-origin requests will be allowed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=bool(cors_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
if _HAS_IDAES:
    app.include_router(simulate.router, prefix="/api", tags=["simulation"])
    app.include_router(optimize.router, prefix="/api", tags=["optimization"])
    app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(components.router, prefix="/api", tags=["components"])
app.include_router(units.router, prefix="/api", tags=["units"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(tea.router, prefix="/api", tags=["tea"])
app.include_router(import_route.router, prefix="/api", tags=["import"])


@app.get("/")
async def root():
    """Root endpoint - basic service info."""
    return {
        "status": "ok",
        "service": "jasper-idaes-backend",
    }
