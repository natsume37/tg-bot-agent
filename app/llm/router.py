from __future__ import annotations

import json
import logging
import re
import base64
from typing import Any

from openai import APIError, AsyncOpenAI

from app.core.types import MCPContext, MCPToolCall, MCPToolDefinition


logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(self, provider: str, api_key: str, model: str, base_url: str | None = None):
        self.provider = provider
        self.model = model
        self.client = None
        if provider in {"openai", "deepseek"} and api_key:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def next_step(self, messages: list[dict[str, Any]], tools: list[MCPToolDefinition]) -> dict[str, Any]:
        if not self.client:
            return self._heuristic_step(messages[-1].get("content", ""))

        try:
            tool_payload = self._to_openai_tools(tools)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_payload,
                tool_choice="auto",
                temperature=0,
            )
            message = response.choices[0].message if response.choices else None
            if not message:
                return {"content": "", "tool_calls": []}

            tool_calls: list[dict[str, Any]] = []
            for call in message.tool_calls or []:
                raw_arguments = call.function.arguments or "{}"
                try:
                    parsed_args = json.loads(raw_arguments)
                except Exception:
                    parsed_args = {}
                tool_calls.append(
                    {
                        "id": call.id,
                        "name": call.function.name,
                        "arguments": parsed_args,
                        "raw_arguments": raw_arguments,
                    }
                )

            content = (message.content or "").strip()
            logger.info("LLM next step content_len=%s tool_calls=%s", len(content), len(tool_calls))
            return {"content": content, "tool_calls": tool_calls}
        except APIError as exc:
            logger.exception("LLM next step failed: %s", exc)
            return self._heuristic_step(messages[-1].get("content", ""))

    async def summarize_after_tools(self, messages: list[dict[str, Any]]) -> str:
        if not self.client:
            return "已完成工具执行。"

        prompt_messages = messages + [
            {
                "role": "system",
                "content": "请根据工具执行结果，用中文给用户返回最终总结。要简洁，明确给出记录条数和金额。",
            }
        ]
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=prompt_messages,
                temperature=0.2,
            )
            if response.choices and response.choices[0].message:
                return (response.choices[0].message.content or "").strip()
            return "已完成处理。"
        except APIError as exc:
            logger.exception("LLM summarize failed: %s", exc)
            return "已完成处理。"

    async def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str, model: str | None = None) -> tuple[str, str]:
        if not self.client:
            return "当前模型未配置，无法进行图片分析。", ""

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"
        target_model = model or self.model
        try:
            response = await self.client.chat.completions.create(
                model=target_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0.2,
            )
            text = (response.choices[0].message.content or "").strip() if response.choices else ""
            raw = response.model_dump_json(indent=None)
            return text or "未获取到图片分析结果。", raw
        except APIError as exc:
            logger.exception("Image analysis failed: %s", exc)
            return "图片分析失败，请稍后重试。", str(exc)

    def build_system_prompt(self) -> str:
        return (
            "你是 Telegram 记账 MCP Agent。"
            "先做意图识别，再决定是否调用工具。"
            "规则："
            "1) 普通闲聊直接回复，不调用工具。"
            "2) 记账场景必须调用工具；若一句话有多笔消费，优先调用 record_expenses_batch。"
            "3) 当用户提到时间（如昨天晚上、今天中午、2026-02-26 12:30）时，在参数中填写 spent_at。"
            "4) 任务、天气按需调用对应工具。"
            "5) 当用户要消费分析时调用 analyze_expenses。"
            "6) 当用户要求图表/可视化时调用 visualize_expenses，并可设置 chart_types。"
            "7) 用户要求配置时调用 set_user_config/get_user_config/list_user_configs/delete_user_config。"
            "8) 用户提供图片URL并要求分析时调用 analyze_image。"
            "9) 当用户有网页搜索意图时调用 google_search。"
            "10) 当用户有网页截图意图时调用 capture_website_screenshot。"
            "11) 调用工具时参数尽量完整准确。"
            "12) 输出风格要清晰好看：使用短段落、项目符号和少量emoji。"
        )

    def build_user_prompt(self, message: str, context: MCPContext) -> str:
        return json.dumps(
            {
                "message": message,
                "context": context.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )

    def _to_openai_tools(self, tools: list[MCPToolDefinition]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for tool in tools:
            payload.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema.model_dump(),
                    },
                }
            )
        return payload

    def _heuristic_step(self, text: str) -> dict[str, Any]:
        message = (text or "").strip()
        lowered = message.lower()

        if any(word in lowered for word in ["你好", "hello", "hi"]):
            return {"content": "你好，我可以帮你记账、查天气和管理任务。", "tool_calls": []}

        if any(word in lowered for word in ["可视化", "图表", "趋势图", "柱状图", "饼图", "分析图"]):
            args = {"days": 30, "chart_types": ["all"]}
            return {
                "content": "",
                "tool_calls": [{"id": "heuristic-viz", "name": "visualize_expenses", "arguments": args, "raw_arguments": json.dumps(args, ensure_ascii=False)}],
            }

        if any(word in lowered for word in ["分析", "消费分析", "开销分析", "统计"]):
            args = {"days": 30, "limit": 200}
            return {
                "content": "",
                "tool_calls": [{"id": "heuristic-analyze", "name": "analyze_expenses", "arguments": args, "raw_arguments": json.dumps(args, ensure_ascii=False)}],
            }

        if "配置" in lowered or "设置" in lowered:
            if any(word in lowered for word in ["查看", "列出", "list"]):
                return {
                    "content": "",
                    "tool_calls": [{"id": "heuristic-list-config", "name": "list_user_configs", "arguments": {}, "raw_arguments": "{}"}],
                }

        if "http" in lowered and ("图片" in lowered or "图像" in lowered):
            matched = re.search(r"https?://\S+", message)
            if matched:
                args = {"image_url": matched.group(0)}
                return {
                    "content": "",
                    "tool_calls": [{"id": "heuristic-image-url", "name": "analyze_image", "arguments": args, "raw_arguments": json.dumps(args, ensure_ascii=False)}],
                }


        amount_matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(?:元|块)?", message))
        if len(amount_matches) >= 2:
            items = []
            for idx, matched in enumerate(amount_matches):
                start = 0 if idx == 0 else amount_matches[idx - 1].end()
                desc = message[start:matched.start()].strip() or f"消费{idx + 1}"
                items.append({"amount": float(matched.group(1)), "category": "其他", "description": desc})
            call = MCPToolCall(name="record_expenses_batch", arguments={"items": items})
            return {
                "content": "",
                "tool_calls": [{"id": "heuristic-batch", "name": call.name, "arguments": call.arguments, "raw_arguments": json.dumps(call.arguments, ensure_ascii=False)}],
            }

        if any(word in lowered for word in ["天气", "weather"]):
            city = message.replace("天气", "").replace("weather", "").strip() or "Singapore"
            return {
                "content": "",
                "tool_calls": [{"id": "heuristic-weather", "name": "get_weather", "arguments": {"city": city}, "raw_arguments": json.dumps({"city": city}, ensure_ascii=False)}],
            }

        amount = self._first_float(message)
        if amount > 0:
            args = {"amount": amount, "category": "其他", "description": message}
            return {
                "content": "",
                "tool_calls": [{"id": "heuristic-expense", "name": "record_expense", "arguments": args, "raw_arguments": json.dumps(args, ensure_ascii=False)}],
            }

        return {"content": "我在的，你可以告诉我需要记录什么开销。", "tool_calls": []}

    def _first_float(self, text: str) -> float:
        matched = re.search(r"(\d+(?:\.\d+)?)", text)
        return float(matched.group(1)) if matched else 0
