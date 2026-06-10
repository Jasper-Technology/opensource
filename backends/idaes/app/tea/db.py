"""
Cost-DB connection layer.

Lazy and optional: if ``DATABASE_URL`` is unset the backend still boots and
serves the stateless simulate/optimize/units routes; only the TEA cost routes
require a database. Mirrors the existing optional-IDAES pattern in main.py.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str | None:
    """The configured cost-DB URL, or None when running stateless."""
    url = os.getenv("DATABASE_URL") or None
    if url and url.startswith("postgresql://"):
        # Railway's reference variable uses the bare scheme; we need psycopg3.
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def is_configured() -> bool:
    return database_url() is not None


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = database_url()
    if url is None:
        raise RuntimeError(
            "DATABASE_URL is not set — cost DB is unavailable. "
            "Set it (Railway Postgres in prod, local Docker in dev) to enable TEA."
        )
    # pool_pre_ping survives the idaes-backend sleep/wake cycle without stale
    # connections; the Postgres service itself never sleeps.
    return create_engine(url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
