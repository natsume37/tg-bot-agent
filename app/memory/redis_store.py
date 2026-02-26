import json

from redis.asyncio import Redis

from app.core.types import MCPMemory
from app.memory.base import MemoryStore


class RedisMemoryStore(MemoryStore):
    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    def _memory_key(self, user_id: str) -> str:
        return f"memory:{user_id}"

    def _history_key(self, user_id: str) -> str:
        return f"history:{user_id}"

    async def get_memory(self, user_id: str) -> MCPMemory:
        payload = await self.redis.get(self._memory_key(user_id))
        if not payload:
            return MCPMemory()
        return MCPMemory.model_validate_json(payload)

    async def save_memory(self, user_id: str, memory: MCPMemory) -> None:
        await self.redis.set(self._memory_key(user_id), memory.model_dump_json())

    async def append_history(self, user_id: str, role: str, content: str) -> None:
        await self.redis.rpush(self._history_key(user_id), json.dumps({"role": role, "content": content}))
        await self.redis.ltrim(self._history_key(user_id), -50, -1)

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        rows = await self.redis.lrange(self._history_key(user_id), -limit, -1)
        return [json.loads(item) for item in rows]
