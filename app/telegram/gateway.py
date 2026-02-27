import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
import logging
from pathlib import Path

from telegram.error import Conflict
from telegram.error import BadRequest
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.core.runtime import AgentRuntime
from app.telegram.formatting import format_message_for_telegram


logger = logging.getLogger(__name__)


class TelegramGateway:
    def __init__(self, token: str, runtime_builder: Callable[[], Awaitable[AgentRuntime]], message_timeout_seconds: int = 45):
        self.token = token
        self.runtime_builder = runtime_builder
        self.runtime: AgentRuntime | None = None
        self._runtime_lock = asyncio.Lock()
        self._user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending_tasks: dict[str, asyncio.Task] = {}
        self._message_timeout_seconds = max(10, int(message_timeout_seconds))
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
        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info("Incoming message user=%s locale=%s text=%s", user_id, locale, text)

        if chat_id is None:
            return

        user_lock = self._user_locks[user_id]
        async with user_lock:
            pending = self._pending_tasks.get(user_id)
            if pending and not pending.done():
                await update.message.reply_text("上一条消息仍在处理中，请稍等几秒。")
                return

            task = asyncio.create_task(self.runtime.handle_message(user_id=user_id, text=text, locale=locale))
            self._pending_tasks[user_id] = task

            try:
                reply = await asyncio.wait_for(asyncio.shield(task), timeout=self._message_timeout_seconds)
                await self._send_reply(chat_id=chat_id, reply_text=reply.text, image_paths=reply.image_paths)
            except asyncio.TimeoutError:
                logger.warning("Message handling timeout user=%s timeout=%ss", user_id, self._message_timeout_seconds)
                await update.message.reply_text("请求处理中，结果生成后会自动发送给你。")
                task.add_done_callback(
                    lambda done_task, uid=user_id, cid=chat_id: self.application.create_task(
                        self._deliver_background_result(user_id=uid, chat_id=cid, task=done_task)
                    )
                )
            except Exception as exc:
                logger.exception("Failed to handle message user=%s: %s", user_id, exc)
                await update.message.reply_text("服务暂时异常，请稍后重试。")
                self._pending_tasks.pop(user_id, None)
            else:
                self._pending_tasks.pop(user_id, None)

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

    async def _deliver_background_result(self, user_id: str, chat_id: int, task: asyncio.Task) -> None:
        try:
            reply = task.result()
            await self._send_reply(chat_id=chat_id, reply_text=reply.text, image_paths=reply.image_paths)
        except Exception as exc:
            logger.exception("Background message handling failed user=%s: %s", user_id, exc)
            await self.application.bot.send_message(chat_id=chat_id, text="处理失败，请稍后重试。")
        finally:
            self._pending_tasks.pop(user_id, None)

    async def _send_reply(self, chat_id: int, reply_text: str, image_paths: list[str]) -> None:
        logger.info("Outgoing reply chat_id=%s reply=%s image_count=%s", chat_id, reply_text, len(image_paths))
        text = format_message_for_telegram(reply_text)
        await self.application.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)

        for image_path in image_paths[:10]:
            path = Path(image_path)
            if not path.exists():
                logger.warning("Image file not found for telegram send: %s", image_path)
                continue
            try:
                if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    await self._send_document(chat_id=chat_id, path=path)
                    continue
                file_size = await asyncio.to_thread(path.stat)
                if file_size.st_size > 10 * 1024 * 1024:
                    await self._send_document(chat_id=chat_id, path=path)
                else:
                    await self._send_photo(chat_id=chat_id, path=path)
            except BadRequest as exc:
                logger.warning("send_photo failed, fallback to send_document path=%s err=%s", image_path, exc)
                await self._send_document(chat_id=chat_id, path=path)
            finally:
                if self._is_temp_web_screenshot(path):
                    try:
                        await asyncio.to_thread(path.unlink, True)
                    except Exception as cleanup_exc:
                        logger.warning("Failed to cleanup temp screenshot path=%s err=%s", image_path, cleanup_exc)

    async def _send_photo(self, chat_id: int, path: Path) -> None:
        def _open_photo() -> bytes:
            return path.read_bytes()

        data = await asyncio.to_thread(_open_photo)
        await self.application.bot.send_photo(chat_id=chat_id, photo=data)

    async def _send_document(self, chat_id: int, path: Path) -> None:
        def _open_document() -> bytes:
            return path.read_bytes()

        data = await asyncio.to_thread(_open_document)
        await self.application.bot.send_document(chat_id=chat_id, document=data, filename=path.name)

    def _is_temp_web_screenshot(self, path: Path) -> bool:
        normalized = path.as_posix()
        return "/outputs/web/temp/" in normalized or normalized.startswith("outputs/web/temp/")
