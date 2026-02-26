from app.core.types import MCPToolResult
from app.services.user_config_service import UserConfigService
from app.services.web_service import WebService


def create_web_handlers(service: WebService, config_service: UserConfigService | None = None):
    def parse_int(value: object, default: int, min_value: int, max_value: int) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = default
        return max(min_value, min(parsed, max_value))

    def parse_bool(value: object, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on", "是"}:
            return True
        if text in {"0", "false", "no", "n", "off", "否"}:
            return False
        return default

    async def google_search(_user_id: str, arguments: dict) -> MCPToolResult:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return MCPToolResult(success=False, message="query 不能为空")

        limit = parse_int(arguments.get("limit", 5), default=5, min_value=1, max_value=10)
        language = str(arguments.get("language", "zh-CN")).strip() or "zh-CN"

        data = await service.google_search(query=query, limit=limit, language=language)
        if data.get("count", 0) == 0:
            return MCPToolResult(success=True, data=data, message="未找到搜索结果")
        return MCPToolResult(success=True, data=data, message="Google 搜索完成")

    async def capture_website_screenshot(user_id: str, arguments: dict) -> MCPToolResult:
        url = str(arguments.get("url", "")).strip()
        if not url:
            return MCPToolResult(success=False, message="url 不能为空")

        full_page = parse_bool(arguments.get("full_page", True), default=True)
        width = parse_int(arguments.get("width", 1366), default=1366, min_value=320, max_value=3840)
        height = parse_int(arguments.get("height", 900), default=900, min_value=320, max_value=3840)

        storage_mode = str(arguments.get("storage_mode", "")).strip().lower()
        if not storage_mode and config_service is not None:
            row = await config_service.get_config(user_id=user_id, key="web_screenshot_storage")
            if row and row.config_value:
                storage_mode = row.config_value.strip().lower()
        if storage_mode not in {"none", "local", "database"}:
            storage_mode = "none"

        try:
            data = await service.capture_website_screenshot(
                user_id=user_id,
                url=url,
                full_page=full_page,
                width=width,
                height=height,
                storage_mode=storage_mode,
            )
        except Exception as exc:
            return MCPToolResult(success=False, message=str(exc))

        return MCPToolResult(success=True, data=data, message="网页截图完成")

    return {
        "google_search": google_search,
        "capture_website_screenshot": capture_website_screenshot,
    }
