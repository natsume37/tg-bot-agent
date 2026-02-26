from app.core.types import MCPToolResult
from app.services.weather_service import WeatherService


def create_weather_handlers(service: WeatherService):
    async def get_weather(_user_id: str, arguments: dict) -> MCPToolResult:
        city = str(arguments.get("city", "")).strip()
        if not city:
            return MCPToolResult(success=False, message="城市不能为空")
        weather = await service.get_weather(city)
        if weather.get("message"):
            return MCPToolResult(success=False, data=weather, message=weather["message"])
        return MCPToolResult(success=True, data=weather, message="天气获取成功")

    return {"get_weather": get_weather}
