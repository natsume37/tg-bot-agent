from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MCPUser(BaseModel):
    id: str
    locale: str = "zh-CN"
    timezone: str = "Asia/Singapore"


class MCPConversation(BaseModel):
    history: list[dict[str, str]] = Field(default_factory=list)
    current_intent: str = "unknown"


class MCPMemory(BaseModel):
    monthly_budget: float | None = None
    frequent_categories: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)


class MCPContext(BaseModel):
    user: MCPUser
    conversation: MCPConversation
    memory: MCPMemory
    now: datetime = Field(default_factory=datetime.utcnow)


class MCPToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any]
    required: list[str] = Field(default_factory=list)


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: MCPToolInputSchema


class MCPToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPPlanResult(BaseModel):
    tool_call: MCPToolCall | None = None
    assistant_message: str | None = None


class MCPToolResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class AgentReply(BaseModel):
    text: str
    image_paths: list[str] = Field(default_factory=list)
