from fastapi.testclient import TestClient

from rest_cache_lab_backend.main import create_app


def test_resource_crud_flow() -> None:
    client = TestClient(create_app())

    create_response = client.post("/api/v1/resources", json={"id": "789", "name": "created"})
    assert create_response.status_code == 201
    assert create_response.json() == {"id": "789", "name": "created"}

    update_response = client.put("/api/v1/resources/789", json={"name": "changed"})
    assert update_response.status_code == 200
    assert update_response.json() == {"id": "789", "name": "changed"}

    get_response = client.get("/api/v1/resources/789")
    assert get_response.status_code == 200
    assert get_response.json() == {"id": "789", "name": "changed"}

    delete_response = client.delete("/api/v1/resources/789")
    assert delete_response.status_code == 204


def test_search_and_supporting_families() -> None:
    client = TestClient(create_app())

    search_response = client.get("/api/v1/resources/search?q=123")
    assert search_response.status_code == 200
    assert search_response.json()["items"] == [{"id": "123", "name": "resource-123"}]

    users_response = client.get("/api/v1/users")
    permissions_response = client.get("/api/v1/permissions")

    assert users_response.status_code == 200
    assert permissions_response.status_code == 200


def test_non_cacheable_lab_responses() -> None:
    client = TestClient(create_app())

    error_response = client.get("/api/v1/errors/503")
    cookie_response = client.get("/api/v1/cookie")

    assert error_response.status_code == 503
    assert "set-cookie" in cookie_response.headers
