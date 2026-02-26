from app.repositories.db import Database
from app.repositories.user_config_repository import UserConfigRepository


class UserConfigService:
    def __init__(self, db: Database):
        self.db = db

    async def set_config(self, user_id: str, key: str, value: str):
        async for session in self.db.get_session():
            repository = UserConfigRepository(session)
            return await repository.set_config(user_id=user_id, key=key, value=value)

    async def get_config(self, user_id: str, key: str):
        async for session in self.db.get_session():
            repository = UserConfigRepository(session)
            return await repository.get_config(user_id=user_id, key=key)
        return None

    async def list_configs(self, user_id: str):
        async for session in self.db.get_session():
            repository = UserConfigRepository(session)
            return await repository.list_configs(user_id=user_id)
        return []

    async def delete_config(self, user_id: str, key: str) -> bool:
        async for session in self.db.get_session():
            repository = UserConfigRepository(session)
            return await repository.delete_config(user_id=user_id, key=key)
        return False
