from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import UserConfigRecord


class UserConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_config(self, user_id: str, key: str, value: str) -> UserConfigRecord:
        statement = select(UserConfigRecord).where(
            UserConfigRecord.user_id == user_id,
            UserConfigRecord.config_key == key,
        )
        result = await self.session.execute(statement)
        row = result.scalar_one_or_none()
        if not row:
            row = UserConfigRecord(user_id=user_id, config_key=key, config_value=value)
            self.session.add(row)
        else:
            row.config_value = value
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_config(self, user_id: str, key: str) -> UserConfigRecord | None:
        statement = select(UserConfigRecord).where(
            UserConfigRecord.user_id == user_id,
            UserConfigRecord.config_key == key,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_configs(self, user_id: str) -> list[UserConfigRecord]:
        statement = select(UserConfigRecord).where(UserConfigRecord.user_id == user_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def delete_config(self, user_id: str, key: str) -> bool:
        statement = delete(UserConfigRecord).where(
            UserConfigRecord.user_id == user_id,
            UserConfigRecord.config_key == key,
        )
        result = await self.session.execute(statement)
        await self.session.commit()
        return bool(result.rowcount)
