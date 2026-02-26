from collections.abc import Awaitable, Callable
from typing import Any

from app.core.types import MCPToolDefinition, MCPToolResult

ToolHandler = Callable[[str, dict[str, Any]], Awaitable[MCPToolResult]]


class ToolRegistry:
    def __init__(self, definitions: list[MCPToolDefinition]):
        self._definitions = {definition.name: definition for definition in definitions}
        self._handlers: dict[str, ToolHandler] = {}

    def register_handler(self, tool_name: str, handler: ToolHandler) -> None:
        if tool_name not in self._definitions:
            raise ValueError(f"Tool not found in definitions: {tool_name}")
        self._handlers[tool_name] = handler

    def list_tools(self) -> list[MCPToolDefinition]:
        return list(self._definitions.values())

    async def call(self, tool_name: str, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        handler = self._handlers.get(tool_name)
        if not handler:
            return MCPToolResult(success=False, message=f"Tool handler not registered: {tool_name}")
        return await handler(user_id, arguments)
