from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "telegram-mcp-bot"
    env: str = "dev"
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    sql_echo: bool = False

    telegram_bot_token: str = ""

    llm_provider: str = "heuristic"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    llm_base_url: str | None = None
    agent_max_steps: int = 6

    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot")
    redis_url: str = "redis://localhost:6379/0"
    use_redis_memory: bool = False

    timezone: str = "Asia/Singapore"
    default_locale: str = "zh-CN"
    expense_default_currency: str = "CNY"
    analytics_output_dir: str = "outputs/charts"
    analytics_font_candidates: str = "Noto Sans CJK SC,Noto Sans CJK TC,Microsoft YaHei,SimHei,WenQuanYi Zen Hei,DejaVu Sans"

    image_analysis_enabled: bool = True
    image_analysis_model: str = "gpt-4.1-mini"
    image_analysis_prompt: str = "请识别图片中的内容，提取与消费相关的信息并给出简洁分析。"
    image_storage_mode: str = "none"
    image_storage_dir: str = "outputs/images"
    image_storage_channel_url: str = ""
    image_analysis_store_to_db: bool = False
    image_analysis_database_url: str = ""

    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_geo_base_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    web_output_dir: str = "outputs/web"
    google_search_base_url: str = "https://www.google.com/search"
    web_screenshot_timeout_ms: int = 15000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
