import pytest

from app.api.v1 import auth as auth_module
from app.core.rate_limit import SlidingWindowRateLimiter
from app.models.enums import UserRole
from tests.conftest import create_user

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter is a module-level singleton (process-lifetime by design) — reset it around
    each test so tests don't leak state into each other.
    """
    auth_module._login_rate_limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=300)
    yield
    auth_module._login_rate_limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=300)


async def test_repeated_failed_logins_are_rate_limited(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)

    for _ in range(5):
        response = await api_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 429


async def test_rate_limit_is_case_insensitive_on_username(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)

    for _ in range(5):
        await api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "ADMIN", "password": "wrong"}
    )
    assert response.status_code == 429


async def test_successful_login_is_not_blocked_by_unrelated_failed_attempts(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)

    for _ in range(4):  # below the limit
        await api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct-horse"}
    )
    assert response.status_code == 200


async def test_rate_limit_is_per_username(api_client, session_maker):
    await create_user(session_maker, "admin", "correct-horse", UserRole.ADMIN)
    await create_user(session_maker, "viewer", "correct-horse", UserRole.VIEWER)

    for _ in range(5):
        await api_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    response = await api_client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "correct-horse"}
    )
    assert response.status_code == 200
