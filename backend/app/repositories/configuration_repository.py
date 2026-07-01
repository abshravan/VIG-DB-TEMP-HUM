from sqlalchemy import select

from app.models.configuration import Configuration
from app.repositories.base import BaseRepository


class ConfigurationRepository(BaseRepository[Configuration]):
    model = Configuration

    async def get_by_key(self, key: str) -> Configuration | None:
        return await self.session.get(Configuration, key)

    async def list_all(self) -> list[Configuration]:
        result = await self.session.execute(select(Configuration))
        return list(result.scalars().all())
