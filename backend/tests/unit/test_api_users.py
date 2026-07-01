import pytest

from app.models.enums import UserRole
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def test_users_endpoints_require_admin(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403


async def test_admin_can_list_and_create_users(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    create_response = await api_client.post(
        "/api/v1/users",
        json={"username": "new_operator", "password": "pw12345678", "role": "OPERATOR"},
        headers=headers,
    )
    assert create_response.status_code == 201
    assert create_response.json()["role"] == "OPERATOR"

    list_response = await api_client.get("/api/v1/users", headers=headers)
    usernames = {u["username"] for u in list_response.json()}
    assert usernames == {"admin", "new_operator"}


async def test_create_user_rejects_duplicate_username(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.post(
        "/api/v1/users",
        json={"username": "admin", "password": "pw12345678", "role": "VIEWER"},
        headers=headers,
    )
    assert response.status_code == 409


async def test_admin_can_update_and_delete_user(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    target = await create_user(session_maker, "target", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "admin", "pw12345678")

    update_response = await api_client.patch(
        f"/api/v1/users/{target.id}", json={"role": "OPERATOR"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "OPERATOR"

    delete_response = await api_client.delete(f"/api/v1/users/{target.id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = await api_client.get("/api/v1/users", headers=headers)
    assert all(u["username"] != "target" for u in list_response.json())


async def test_update_missing_user_returns_404(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.patch("/api/v1/users/9999", json={"role": "VIEWER"}, headers=headers)
    assert response.status_code == 404
