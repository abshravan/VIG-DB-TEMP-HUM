import pytest

from app.models.enums import UserRole
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def test_login_succeeds_with_correct_credentials(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct-horse"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_rejects_wrong_password(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_user(api_client):
    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "x"}
    )
    assert response.status_code == 401


async def test_me_requires_authentication(api_client):
    response = await api_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "correct-horse")

    response = await api_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["role"] == "ADMIN"


async def test_refresh_issues_new_tokens(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)
    login_response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct-horse"}
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await api_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_access_token_used_as_refresh_token(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)
    login_response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct-horse"}
    )
    access_token = login_response.json()["access_token"]

    response = await api_client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


async def test_logout_returns_no_content(api_client):
    response = await api_client.post("/api/v1/auth/logout")
    assert response.status_code == 204


async def test_invalid_token_is_rejected(api_client):
    response = await api_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
