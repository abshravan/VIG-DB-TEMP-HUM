import pytest

from app.models.configuration import Configuration
from app.repositories import ConfigurationRepository

pytestmark = pytest.mark.asyncio


async def test_get_by_key_and_list_all(session):
    repo = ConfigurationRepository(session)
    await repo.create(Configuration(key="poll_interval_seconds", value="5", value_type="int"))
    await repo.create(Configuration(key="session_timeout_minutes", value="30", value_type="int"))
    await session.commit()

    found = await repo.get_by_key("poll_interval_seconds")
    assert found is not None
    assert found.value == "5"

    assert await repo.get_by_key("does_not_exist") is None
    assert {c.key for c in await repo.list_all()} == {"poll_interval_seconds", "session_timeout_minutes"}
