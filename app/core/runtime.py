import logging

from app.agent.loop import AgentLoopEngine
from app.config.settings import Settings
from app.core.types import AgentReply, MCPContext, MCPConversation, MCPMemory, MCPUser
from app.llm.router import LLMRouter
from app.memory.base import MemoryStore
from app.services.image_analysis_service import ImageAnalysisService
from app.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(
        self,
        settings: Settings,
        memory_store: MemoryStore,
        tool_registry: ToolRegistry,
        llm_router: LLMRouter,
        image_analysis_service: ImageAnalysisService | None = None,
    ):
        self.settings = settings
        self.memory_store = memory_store
        self.tool_registry = tool_registry
        self.llm_router = llm_router
        self.image_analysis_service = image_analysis_service
        self.agent_loop = AgentLoopEngine(
            settings=settings,
            memory_store=memory_store,
            tool_registry=tool_registry,
            llm_router=llm_router,
        )

    async def build_context(self, user_id: str, locale: str | None = None) -> MCPContext:
        memory = await self.memory_store.get_memory(user_id)
        history = await self.memory_store.get_history(user_id)
        logger.debug("Build context user=%s locale=%s history_count=%s", user_id, locale, len(history))
        return MCPContext(
            user=MCPUser(
                id=user_id,
                locale=locale or self.settings.default_locale,
                timezone=self.settings.timezone,
            ),
            conversation=MCPConversation(history=history),
            memory=memory or MCPMemory(),
        )

    async def handle_message(self, user_id: str, text: str, locale: str | None = None) -> AgentReply:
        logger.info("Handle message user=%s text=%s", user_id, text)
        context = await self.build_context(user_id=user_id, locale=locale)
        await self.memory_store.append_history(user_id, "user", text)

        reply = await self.agent_loop.run(user_id=user_id, text=text, context=context)

        logger.info("Reply generated user=%s reply=%s image_count=%s", user_id, reply.text, len(reply.image_paths))

        await self.memory_store.append_history(user_id, "assistant", reply.text)
        return reply

    async def handle_image(
        self,
        user_id: str,
        image_bytes: bytes,
        mime_type: str,
        source_file_id: str = "",
        caption: str | None = None,
    ) -> AgentReply:
        if not self.image_analysis_service:
            return AgentReply(text="🖼️ 图片分析服务未启用。")

        result = await self.image_analysis_service.analyze_from_bytes(
            user_id=user_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
            source_file_id=source_file_id,
            prompt=caption,
        )
        if not result.get("success"):
            return AgentReply(text=f"❌ {result.get('message', '图片分析失败')}")

        lines = ["🖼️ 图片分析完成", "", result.get("analysis_text", "")]
        if result.get("record_id"):
            lines.append(f"\n🧾 已存档记录ID：{result['record_id']}")
        if result.get("storage_uri"):
            lines.append(f"📦 存储位置：{result['storage_uri']}")
        return AgentReply(text="\n".join(lines).strip())
