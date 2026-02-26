import asyncio
from collections.abc import Awaitable, Callable
import logging
from pathlib import Path

from telegram.error import Conflict
from telegram.error import BadRequest
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.core.runtime import AgentRuntime


logger = logging.getLogger(__name__)


class TelegramGateway:
    def __init__(self, token: str, runtime_builder: Callable[[], Awaitable[AgentRuntime]]):
        self.token = token
        self.runtime_builder = runtime_builder
        self.runtime: AgentRuntime | None = None
        self._runtime_lock = asyncio.Lock()
        self.application = Application.builder().token(token).build()

    def start(self) -> None:
        self.application.add_handler(MessageHandler(filters.TEXT, self.on_text_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.on_photo_message))
        self.application.add_error_handler(self.on_error)
        try:
            logger.info("Telegram polling started")
            self.application.run_polling()
        except Conflict as exc:
            raise RuntimeError(
                "检测到同一个 Bot Token 有多个实例在轮询，请关闭其它运行中的 Bot 进程后重试。"
            ) from exc

    async def on_text_message(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        if self.runtime is None:
            async with self._runtime_lock:
                if self.runtime is None:
                    logger.info("Runtime lazy initialization started")
                    self.runtime = await self.runtime_builder()
                    logger.info("Runtime lazy initialization finished")

        text = update.message.text or ""
        user_id = f"tg_{update.effective_user.id}"
        locale = update.effective_user.language_code or "zh-CN"
        logger.info("Incoming message user=%s locale=%s text=%s", user_id, locale, text)
        try:
            reply = await self.runtime.handle_message(user_id=user_id, text=text, locale=locale)
            logger.info("Outgoing reply user=%s reply=%s image_count=%s", user_id, reply.text, len(reply.image_paths))
            await update.message.reply_text(reply.text)

            for image_path in reply.image_paths[:10]:
                path = Path(image_path)
                if not path.exists():
                    logger.warning("Image file not found for telegram send: %s", image_path)
                    continue
                try:
                    if path.stat().st_size > 10 * 1024 * 1024:
                        with path.open("rb") as document:
                            await update.message.reply_document(document=document, filename=path.name)
                    else:
                        with path.open("rb") as photo:
                            await update.message.reply_photo(photo=photo)
                except BadRequest as exc:
                    logger.warning("send_photo failed, fallback to send_document path=%s err=%s", image_path, exc)
                    with path.open("rb") as document:
                        await update.message.reply_document(document=document, filename=path.name)
                finally:
                    if self._is_temp_web_screenshot(path):
                        try:
                            path.unlink(missing_ok=True)
                        except Exception as cleanup_exc:
                            logger.warning("Failed to cleanup temp screenshot path=%s err=%s", image_path, cleanup_exc)
        except Exception as exc:
            logger.exception("Failed to handle message user=%s: %s", user_id, exc)
            await update.message.reply_text("服务暂时异常，请稍后重试。")

    async def on_photo_message(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.message.photo:
            return

        if self.runtime is None:
            async with self._runtime_lock:
                if self.runtime is None:
                    logger.info("Runtime lazy initialization started")
                    self.runtime = await self.runtime_builder()
                    logger.info("Runtime lazy initialization finished")

        user_id = f"tg_{update.effective_user.id}"
        caption = update.message.caption or ""
        largest = update.message.photo[-1]

        try:
            file = await largest.get_file()
            bytearray_data = await file.download_as_bytearray()
            mime_type = "image/jpeg"
            reply = await self.runtime.handle_image(
                user_id=user_id,
                image_bytes=bytes(bytearray_data),
                mime_type=mime_type,
                source_file_id=largest.file_id,
                caption=caption,
            )
            await update.message.reply_text(reply.text)
        except Exception as exc:
            logger.exception("Failed to handle photo message user=%s: %s", user_id, exc)
            await update.message.reply_text("图片分析失败，请稍后重试。")

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Unhandled telegram error update=%s error=%s", update, context.error)

    def _is_temp_web_screenshot(self, path: Path) -> bool:
        normalized = path.as_posix()
        return "/outputs/web/temp/" in normalized or normalized.startswith("outputs/web/temp/")
