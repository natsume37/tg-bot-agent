import logging

from app.bootstrap import Container
from app.config.settings import get_settings
from app.core.logging import setup_logging
from app.telegram.gateway import TelegramGateway


def main() -> None:
    settings = get_settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file)
    logger = logging.getLogger(__name__)
    logger.info("Application startup env=%s llm_provider=%s model=%s", settings.env, settings.llm_provider, settings.llm_model)

    if not settings.telegram_bot_token:
        raise RuntimeError("请先在 .env 中配置 TELEGRAM_BOT_TOKEN")

    container = Container(settings)
    gateway = TelegramGateway(token=settings.telegram_bot_token, runtime_builder=container.build_runtime)
    gateway.start()


if __name__ == "__main__":
    main()
