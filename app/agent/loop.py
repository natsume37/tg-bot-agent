from __future__ import annotations

import json
import logging
from typing import Any

from app.config.settings import Settings
from app.core.types import AgentReply, MCPContext, MCPToolResult
from app.llm.router import LLMRouter
from app.memory.base import MemoryStore
from app.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


class AgentLoopEngine:
    def __init__(
        self,
        settings: Settings,
        memory_store: MemoryStore,
        tool_registry: ToolRegistry,
        llm_router: LLMRouter,
    ):
        self.settings = settings
        self.memory_store = memory_store
        self.tool_registry = tool_registry
        self.llm_router = llm_router

    async def run(self, user_id: str, text: str, context: MCPContext) -> AgentReply:
        max_steps = getattr(self.settings, "agent_max_steps", 6)
        tools = self.tool_registry.list_tools()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.llm_router.build_system_prompt()},
            {"role": "user", "content": self.llm_router.build_user_prompt(message=text, context=context)},
        ]

        used_tools = False
        last_tool_results: list[dict[str, Any]] = []
        failed_call_signatures: set[str] = set()

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
                call_signature = self._build_call_signature(tool_name=tool_name, tool_args=tool_args)

                if call_signature in failed_call_signatures:
                    logger.info("Skip repeated failed tool call tool=%s args=%s", tool_name, tool_args)
                    result = MCPToolResult(success=False, message="检测到重复失败调用，已停止重复重试。", data={})
                else:
                    logger.info("Tool call decided tool=%s args=%s", tool_name, tool_args)
                    result = await self.tool_registry.call(tool_name, user_id, tool_args)
                    logger.info("Tool result tool=%s success=%s message=%s", tool_name, result.success, result.message)
                    if not result.success:
                        failed_call_signatures.add(call_signature)
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

    def _collect_image_paths(self, tool_results: list[dict[str, Any]]) -> list[str]:
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
        unique: list[str] = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique.append(path)
        return unique

    def _fallback_tool_summary(self, tool_results: list[dict[str, Any]]) -> str:
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

        deep_search_rows = [row for row in success_results if row.get("tool_name") == "deep_web_search"]
        if deep_search_rows:
            data = deep_search_rows[-1].get("data", {})
            sources = data.get("sources", []) or []
            lines = [f"🧠 深度搜索完成（来源 {len(sources)} 条）"]
            for index, item in enumerate(sources[:5], 1):
                lines.append(f"{index}. {item.get('title', '')}\n{item.get('url', '')}")
            return "\n".join(lines)

        search_rows = [row for row in success_results if row.get("tool_name") == "google_search"]
        if search_rows:
            data = search_rows[-1].get("data", {})
            items = data.get("items", []) or []
            if not items:
                return f"🔎 未找到结果：{data.get('query', '')}"
            lines = [f"🔎 Google 搜索结果（{len(items)} 条）"]
            for index, item in enumerate(items[:5], 1):
                lines.append(f"{index}. {item.get('title', '')}\n{item.get('url', '')}")
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

    def _build_call_signature(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        try:
            normalized_args = json.dumps(tool_args, ensure_ascii=False, sort_keys=True)
        except Exception:
            normalized_args = str(tool_args)
        return f"{tool_name}:{normalized_args}"

    async def _update_memory(self, user_id: str, context: MCPContext, result: MCPToolResult) -> None:
        memory = context.memory
        if result.success and result.data.get("category"):
            category = result.data["category"]
            if category not in memory.frequent_categories:
                memory.frequent_categories.append(category)
        await self.memory_store.save_memory(user_id, memory)
