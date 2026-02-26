from app.core.types import MCPToolResult
from app.services.analytics_service import AnalyticsService


def create_analytics_handlers(service: AnalyticsService):
    def parse_limit(value: object, default: int = 200) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = default
        return max(1, min(parsed, 1000))

    def parse_days(value: object, default: int = 0) -> int:
        if value is None:
            return default

        if isinstance(value, int):
            return max(0, value)

        text = str(value).strip()
        if not text:
            return default

        try:
            return max(0, int(text))
        except ValueError:
            pass

        mappings = {
            "近期": 30,
            "最近": 30,
            "最近一个月": 30,
            "近一月": 30,
            "近一个月": 30,
            "本月": 30,
            "近一周": 7,
            "最近一周": 7,
            "本周": 7,
            "今天": 1,
            "昨日": 1,
            "昨天": 1,
        }

        for key, mapped_days in mappings.items():
            if key in text:
                return mapped_days

        return default

    async def analyze_expenses(user_id: str, arguments: dict) -> MCPToolResult:
        limit = parse_limit(arguments.get("limit", 200))
        days = parse_days(arguments.get("days", 0))
        summary = await service.analyze_expenses(user_id=user_id, limit=limit, days=days)
        if summary.get("count", 0) == 0:
            return MCPToolResult(success=True, data=summary, message="暂无消费数据")
        return MCPToolResult(success=True, data=summary, message="消费分析完成")

    async def visualize_expenses(user_id: str, arguments: dict) -> MCPToolResult:
        limit = parse_limit(arguments.get("limit", 200))
        days = parse_days(arguments.get("days", 0))
        chart_types = arguments.get("chart_types")
        if chart_types and not isinstance(chart_types, list):
            return MCPToolResult(success=False, message="chart_types 必须是数组")

        payload = await service.visualize_expenses(
            user_id=user_id,
            chart_types=chart_types,
            limit=limit,
            days=days,
        )
        if payload.get("count", 0) == 0:
            return MCPToolResult(success=True, data=payload, message="暂无消费数据，无法生成图表")
        return MCPToolResult(success=True, data=payload, message="消费可视化生成成功")

    return {
        "analyze_expenses": analyze_expenses,
        "visualize_expenses": visualize_expenses,
    }
