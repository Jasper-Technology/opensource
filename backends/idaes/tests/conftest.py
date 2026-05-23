"""Shared test fixtures."""
import os

import pytest
from fastapi.testclient import TestClient

# Ensure a dev API key is set for testing
os.environ.setdefault("BACKEND_API_KEY", "test-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": os.environ["BACKEND_API_KEY"]}
