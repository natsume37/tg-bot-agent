from collections import defaultdict

from app.core.types import MCPMemory
from app.memory.base import MemoryStore


class InMemoryStore(MemoryStore):
    def __init__(self):
        self.memory_map: dict[str, MCPMemory] = {}
        self.history_map: dict[str, list[dict[str, str]]] = defaultdict(list)

    async def get_memory(self, user_id: str) -> MCPMemory:
        return self.memory_map.get(user_id, MCPMemory())

    async def save_memory(self, user_id: str, memory: MCPMemory) -> None:
        self.memory_map[user_id] = memory

    async def append_history(self, user_id: str, role: str, content: str) -> None:
        self.history_map[user_id].append({"role": role, "content": content})
        self.history_map[user_id] = self.history_map[user_id][-50:]

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        return self.history_map[user_id][-limit:]
