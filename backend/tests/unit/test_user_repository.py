import pytest

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import UserRepository

pytestmark = pytest.mark.asyncio


async def test_create_and_get_by_username(session):
    repo = UserRepository(session)
    await repo.create(
        User(username="admin", hashed_password=hash_password("s3cret!"), role=UserRole.ADMIN)
    )
    await session.commit()

    found = await repo.get_by_username("admin")
    assert found is not None
    assert found.role == UserRole.ADMIN
    assert verify_password("s3cret!", found.hashed_password)
    assert not verify_password("wrong", found.hashed_password)


async def test_get_by_username_missing_returns_none(session):
    assert await UserRepository(session).get_by_username("nobody") is None
