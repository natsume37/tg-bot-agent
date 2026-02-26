from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.types import MCPMemory


class MemoryStore(ABC):
    @abstractmethod
    async def get_memory(self, user_id: str) -> MCPMemory:
        raise NotImplementedError

    @abstractmethod
    async def save_memory(self, user_id: str, memory: MCPMemory) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_history(self, user_id: str, role: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_history(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        raise NotImplementedError
