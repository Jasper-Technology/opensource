"""API key authentication for IDAES backend endpoints."""
import os
import logging

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
VALID_API_KEY = os.getenv("BACKEND_API_KEY")


async def require_api_key(key: str | None = Security(API_KEY_HEADER)) -> str:
    """Validate the API key from the X-API-Key header.

    Returns the validated key on success; raises 403 otherwise.
    """
    if not VALID_API_KEY:
        logger.warning("BACKEND_API_KEY is not set — all requests will be rejected")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service is not configured for access",
        )
    if not key or key != VALID_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return key
