import logging
import json

from app.config.settings import Settings
from app.core.types import AgentReply, MCPContext, MCPConversation, MCPMemory, MCPToolResult, MCPUser
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

        reply = await self._run_agent_loop(user_id=user_id, text=text, context=context)

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

    async def _run_agent_loop(self, user_id: str, text: str, context: MCPContext) -> AgentReply:
        max_steps = getattr(self.settings, "agent_max_steps", 6)
        tools = self.tool_registry.list_tools()

        messages: list[dict] = [
            {"role": "system", "content": self.llm_router.build_system_prompt()},
            {"role": "user", "content": self.llm_router.build_user_prompt(message=text, context=context)},
        ]

        used_tools = False
        last_tool_results: list[dict] = []

        for _ in range(max_steps):
            step = await self.llm_router.next_step(messages=messages, tools=tools)
            tool_calls = step.get("tool_calls", [])
            content = (step.get("content") or "").strip()

            if not tool_calls:
                if used_tools:
                    summary = await self.llm_router.summarize_after_tools(messages)
                    if summary:
                        return AgentReply(text=summary, image_paths=self._collect_image_paths(last_tool_results))
                    return AgentReply(
                        text=self._fallback_tool_summary(last_tool_results),
                        image_paths=self._collect_image_paths(last_tool_results),
                    )
                return AgentReply(text=content or "我在的，你可以告诉我想记录什么开销，或问我天气。")

            used_tools = True
            assistant_tool_calls = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                raw_arguments = tool_call.get("raw_arguments", json.dumps(tool_args, ensure_ascii=False))
                tool_id = tool_call.get("id", f"tool-{tool_name}")

                assistant_tool_calls.append(
                    {
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": raw_arguments},
                    }
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": assistant_tool_calls,
                }
            )

            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                tool_id = tool_call.get("id", f"tool-{tool_name}")
                logger.info("Tool call decided tool=%s args=%s", tool_name, tool_args)
                result = await self.tool_registry.call(tool_name, user_id, tool_args)
                logger.info("Tool result tool=%s success=%s message=%s", tool_name, result.success, result.message)
                await self._update_memory(user_id=user_id, context=context, result=result)

                last_tool_results.append(
                    {
                        "tool_name": tool_name,
                        "success": result.success,
                        "message": result.message,
                        "data": result.data,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps(
                            {
                                "success": result.success,
                                "message": result.message,
                                "data": result.data,
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

        logger.warning("Agent loop exceeded max steps=%s", max_steps)
        if last_tool_results:
            return AgentReply(
                text=self._fallback_tool_summary(last_tool_results),
                image_paths=self._collect_image_paths(last_tool_results),
            )
        return AgentReply(text="处理步骤过多，请简化描述后重试。")

    def _collect_image_paths(self, tool_results: list[dict]) -> list[str]:
        paths: list[str] = []
        for row in tool_results:
            tool_name = row.get("tool_name")
            data = row.get("data", {}) or {}
            if tool_name == "visualize_expenses":
                for chart in data.get("charts", []) or []:
                    path = chart.get("path")
                    if path:
                        paths.append(path)
            if tool_name == "capture_website_screenshot":
                path = data.get("path")
                if path:
                    paths.append(path)
        seen: set[str] = set()
        unique = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique.append(path)
        return unique

    def _fallback_tool_summary(self, tool_results: list[dict]) -> str:
        if not tool_results:
            return "✅ 已完成处理。"

        success_results = [row for row in tool_results if row.get("success")]
        if not success_results:
            return "❌ 工具执行失败，请稍后重试。"

        batch_rows = [row for row in success_results if row.get("tool_name") == "record_expenses_batch"]
        if batch_rows:
            last_batch = batch_rows[-1]
            data = last_batch.get("data", {})
            return (
                f"✅ 批量记账成功\n"
                f"• 笔数：{data.get('count', 0)}\n"
                f"• 合计：{data.get('total', 0)} 元"
            )

        single_rows = [row for row in success_results if row.get("tool_name") == "record_expense"]
        if single_rows:
            last = single_rows[-1].get("data", {})
            return f"✅ 记账成功\n• 金额：{last.get('amount')} 元\n• 分类：{last.get('category')}"

        viz_rows = [row for row in success_results if row.get("tool_name") == "visualize_expenses"]
        if viz_rows:
            last_viz = viz_rows[-1].get("data", {})
            charts = last_viz.get("charts", [])
            return f"📈 可视化已生成\n• 图表数量：{len(charts)}\n• 目录：{last_viz.get('output_dir', '')}"

        analyze_rows = [row for row in success_results if row.get("tool_name") == "analyze_expenses"]
        if analyze_rows:
            data = analyze_rows[-1].get("data", {})
            return f"📊 消费分析完成\n• 笔数：{data.get('count', 0)}\n• 合计：{data.get('total', 0)} 元"

        search_rows = [row for row in success_results if row.get("tool_name") == "google_search"]
        if search_rows:
            data = search_rows[-1].get("data", {})
            items = data.get("items", []) or []
            if not items:
                return f"🔎 未找到结果：{data.get('query', '')}"
            lines = [f"🔎 Google 搜索结果（{len(items)} 条）"]
            for idx, item in enumerate(items[:5], 1):
                lines.append(f"{idx}. {item.get('title', '')}\n{item.get('url', '')}")
            return "\n".join(lines)

        shot_rows = [row for row in success_results if row.get("tool_name") == "capture_website_screenshot"]
        if shot_rows:
            data = shot_rows[-1].get("data", {})
            lines = [
                "📸 网页截图完成",
                f"• 标题：{data.get('title', '')}",
                f"• 地址：{data.get('url', '')}",
                f"• 存储：{data.get('storage_mode', 'none')}",
            ]
            screenshot_id = data.get("screenshot_id")
            if screenshot_id:
                lines.append(f"• 数据库ID：{screenshot_id}")
            return "\n".join(lines)

        return "✅ 处理完成。"

    async def _update_memory(self, user_id: str, context: MCPContext, result: MCPToolResult) -> None:
        memory = context.memory
        if result.success and result.data.get("category"):
            category = result.data["category"]
            if category not in memory.frequent_categories:
                memory.frequent_categories.append(category)
        await self.memory_store.save_memory(user_id, memory)

    def _format_reply(self, tool_name: str, result: MCPToolResult) -> str:
        if not result.success:
            return f"❌ {result.message}"

        if tool_name == "record_expense":
            return (
                f"✅ 记账成功：{result.data.get('amount')} 元，"
                f"分类 {result.data.get('category')}，备注 {result.data.get('description', '')}"
            )
        if tool_name in {"query_expenses", "list_tasks"}:
            items = result.data.get("items", [])
            if not items:
                logger.info("No data for tool=%s, returning empty message", tool_name)
                return "暂无数据"
            lines = [f"{idx + 1}. {item}" for idx, item in enumerate(items[:8])]
            return "\n".join(lines)
        if tool_name == "summarize_expenses":
            return f"📊 共 {result.data.get('count', 0)} 笔，合计 {result.data.get('total', 0)}"
        if tool_name == "get_weather":
            return (
                f"🌤️ {result.data.get('city')} 当前 {result.data.get('temperature')}°C，"
                f"体感 {result.data.get('apparent_temperature')}°C"
            )
        return f"✅ {result.message}"
