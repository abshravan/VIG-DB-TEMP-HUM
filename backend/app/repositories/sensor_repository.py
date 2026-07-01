from sqlalchemy import select

from app.models.sensor import Sensor
from app.repositories.base import BaseRepository


class SensorRepository(BaseRepository[Sensor]):
    model = Sensor

    async def get_by_tag_name(self, tag_name: str) -> Sensor | None:
        result = await self.session.execute(select(Sensor).where(Sensor.tag_name == tag_name))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Sensor]:
        result = await self.session.execute(select(Sensor).where(Sensor.is_active.is_(True)))
        return list(result.scalars().all())
