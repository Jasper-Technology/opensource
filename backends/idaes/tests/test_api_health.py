"""Tests for health endpoints."""


def test_health_returns_expected_fields(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "idaes_version" in data
    assert "solver_available" in data


def test_deep_health_requires_auth(client):
    response = client.get("/api/health/deep")
    assert response.status_code == 403


def test_deep_health_with_auth(client, auth_headers):
    response = client.get("/api/health/deep", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "error")
