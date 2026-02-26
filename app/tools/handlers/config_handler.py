from app.core.types import MCPToolResult
from app.services.user_config_service import UserConfigService


def create_config_handlers(service: UserConfigService):
    async def set_user_config(user_id: str, arguments: dict) -> MCPToolResult:
        key = str(arguments.get("key", "")).strip()
        value = str(arguments.get("value", "")).strip()
        if not key:
            return MCPToolResult(success=False, message="key 不能为空")
        row = await service.set_config(user_id=user_id, key=key, value=value)
        return MCPToolResult(success=True, message="配置已保存", data={"key": row.config_key, "value": row.config_value})

    async def get_user_config(user_id: str, arguments: dict) -> MCPToolResult:
        key = str(arguments.get("key", "")).strip()
        if not key:
            return MCPToolResult(success=False, message="key 不能为空")
        row = await service.get_config(user_id=user_id, key=key)
        if not row:
            return MCPToolResult(success=False, message="配置不存在")
        return MCPToolResult(success=True, message="查询成功", data={"key": row.config_key, "value": row.config_value})

    async def list_user_configs(user_id: str, arguments: dict) -> MCPToolResult:
        rows = await service.list_configs(user_id=user_id)
        data = [{"key": row.config_key, "value": row.config_value} for row in rows]
        return MCPToolResult(success=True, message=f"返回 {len(data)} 条配置", data={"items": data})

    async def delete_user_config(user_id: str, arguments: dict) -> MCPToolResult:
        key = str(arguments.get("key", "")).strip()
        if not key:
            return MCPToolResult(success=False, message="key 不能为空")
        ok = await service.delete_config(user_id=user_id, key=key)
        if not ok:
            return MCPToolResult(success=False, message="配置不存在")
        return MCPToolResult(success=True, message="配置已删除", data={"key": key})

    return {
        "set_user_config": set_user_config,
        "get_user_config": get_user_config,
        "list_user_configs": list_user_configs,
        "delete_user_config": delete_user_config,
    }
