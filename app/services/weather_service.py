from typing import Any

import httpx


class WeatherService:
    def __init__(self, geo_base_url: str, weather_base_url: str):
        self.geo_base_url = geo_base_url
        self.weather_base_url = weather_base_url

    async def get_weather(self, city: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            geo_resp = await client.get(self.geo_base_url, params={"name": city, "count": 1, "language": "zh"})
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            if not geo_data.get("results"):
                return {"city": city, "message": "未找到城市"}

            target = geo_data["results"][0]
            lat = target["latitude"]
            lon = target["longitude"]

            weather_resp = await client.get(
                self.weather_base_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "timezone": "auto",
                },
            )
            weather_resp.raise_for_status()
            weather = weather_resp.json().get("current", {})

        return {
            "city": target.get("name", city),
            "country": target.get("country", ""),
            "temperature": weather.get("temperature_2m"),
            "apparent_temperature": weather.get("apparent_temperature"),
            "wind_speed": weather.get("wind_speed_10m"),
            "weather_code": weather.get("weather_code"),
        }
