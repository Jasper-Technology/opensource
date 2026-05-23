"""Tests for components API."""


def test_get_components_requires_auth(client):
    response = client.get("/api/components")
    assert response.status_code == 403


def test_get_components(client, auth_headers):
    response = client.get("/api/components", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert "total" in data
    assert "categories" in data
    assert data["total"] >= 17


def test_search_components(client, auth_headers):
    response = client.get("/api/components?search=water", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert any(c["formula"] == "H2O" for c in data["components"])


def test_filter_by_category(client, auth_headers):
    response = client.get("/api/components?category=alkane", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(c["category"] == "alkane" for c in data["components"])


def test_get_component_by_id(client, auth_headers):
    response = client.get("/api/components/water", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["formula"] == "H2O"


def test_get_unknown_component(client, auth_headers):
    response = client.get("/api/components/nonexistent", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
