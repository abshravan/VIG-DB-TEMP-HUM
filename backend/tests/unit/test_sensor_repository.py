import pytest

from app.models.enums import SensorType
from app.models.sensor import Sensor
from app.repositories import SensorRepository

pytestmark = pytest.mark.asyncio


async def test_create_and_get_by_tag_name(session):
    repo = SensorRepository(session)
    created = await repo.create(
        Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
    )
    await session.commit()

    found = await repo.get_by_tag_name("temp_a")
    assert found is not None
    assert found.id == created.id
    assert found.sensor_type == SensorType.TEMPERATURE


async def test_get_by_tag_name_missing_returns_none(session):
    repo = SensorRepository(session)
    assert await repo.get_by_tag_name("does_not_exist") is None


async def test_list_active_excludes_inactive(session):
    repo = SensorRepository(session)
    await repo.create(
        Sensor(tag_name="active_1", display_name="Active", sensor_type=SensorType.HUMIDITY, is_active=True)
    )
    await repo.create(
        Sensor(
            tag_name="inactive_1",
            display_name="Inactive",
            sensor_type=SensorType.HUMIDITY,
            is_active=False,
        )
    )
    await session.commit()

    active = await repo.list_active()
    assert {s.tag_name for s in active} == {"active_1"}


async def test_tag_name_unique_constraint(session):
    repo = SensorRepository(session)
    await repo.create(Sensor(tag_name="dup", display_name="One", sensor_type=SensorType.DOOR))
    await session.commit()

    with pytest.raises(Exception):
        await repo.create(Sensor(tag_name="dup", display_name="Two", sensor_type=SensorType.DOOR))
