from app.config.settings import Settings
from app.core.runtime import AgentRuntime
from app.llm.router import LLMRouter
from app.memory.in_memory import InMemoryStore
from app.memory.redis_store import RedisMemoryStore
from app.repositories.db import Database
from app.services.analytics_service import AnalyticsService
from app.services.expense_service import ExpenseService
from app.services.image_analysis_service import ImageAnalysisService
from app.services.task_service import TaskService
from app.services.user_config_service import UserConfigService
from app.services.weather_service import WeatherService
from app.services.web_service import WebService
from app.tools.definitions import TOOL_DEFINITIONS
from app.tools.expense_gateway import ExpenseGateway
from app.tools.handlers.analytics_handler import create_analytics_handlers
from app.tools.handlers.config_handler import create_config_handlers
from app.tools.handlers.image_handler import create_image_handlers
from app.tools.handlers.task_handler import create_task_handlers
from app.tools.handlers.weather_handler import create_weather_handlers
from app.tools.handlers.web_handler import create_web_handlers
from app.tools.registry import ToolRegistry


class Container:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_url, echo=settings.sql_echo)

    async def build_runtime(self) -> AgentRuntime:
        await self.db.init_models()

        memory_store = (
            RedisMemoryStore(self.settings.redis_url) if self.settings.use_redis_memory else InMemoryStore()
        )

        expense_service = ExpenseService(self.db)
        config_service = UserConfigService(self.db)
        analytics_service = AnalyticsService(
            expense_service=expense_service,
            output_dir=self.settings.analytics_output_dir,
            font_candidates=self.settings.analytics_font_candidates,
        )
        task_service = TaskService(self.db)
        weather_service = WeatherService(
            geo_base_url=self.settings.weather_geo_base_url,
            weather_base_url=self.settings.weather_base_url,
        )
        web_service = WebService(
            output_dir=self.settings.web_output_dir,
            google_search_base_url=self.settings.google_search_base_url,
            screenshot_timeout_ms=self.settings.web_screenshot_timeout_ms,
            db=self.db,
        )

        llm_router = LLMRouter(
            provider=self.settings.llm_provider,
            api_key=self.settings.llm_api_key,
            model=self.settings.llm_model,
            base_url=self.settings.llm_base_url,
        )
        image_analysis_service = ImageAnalysisService(
            settings=self.settings,
            llm_router=llm_router,
            default_db=self.db,
        )
        await image_analysis_service.init()

        expense_gateway = ExpenseGateway(expense_service, timezone_name=self.settings.timezone)

        registry = ToolRegistry(definitions=TOOL_DEFINITIONS)
        for name, handler in expense_gateway.handlers().items():
            registry.register_handler(name, handler)
        for name, handler in create_analytics_handlers(analytics_service).items():
            registry.register_handler(name, handler)
        for name, handler in create_config_handlers(config_service).items():
            registry.register_handler(name, handler)
        for name, handler in create_image_handlers(image_analysis_service).items():
            registry.register_handler(name, handler)
        for name, handler in create_task_handlers(task_service).items():
            registry.register_handler(name, handler)
        for name, handler in create_weather_handlers(weather_service).items():
            registry.register_handler(name, handler)
        for name, handler in create_web_handlers(web_service, config_service=config_service).items():
            registry.register_handler(name, handler)

        return AgentRuntime(
            settings=self.settings,
            memory_store=memory_store,
            tool_registry=registry,
            llm_router=llm_router,
            image_analysis_service=image_analysis_service,
        )
