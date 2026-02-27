from __future__ import annotations

import html
import re

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def format_message_for_telegram(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return "🤖 已完成处理。"

    normalized = _normalize_bullets(text)
    escaped = html.escape(normalized)
    rendered = _render_markdown_like(escaped)
    compact = _compact_blank_lines(rendered)

    if len(compact) > MAX_TELEGRAM_MESSAGE_LENGTH:
        compact = compact[: MAX_TELEGRAM_MESSAGE_LENGTH - 1] + "…"
    return compact


def _normalize_bullets(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("- "):
            indent = len(line) - len(stripped)
            lines.append(" " * indent + "• " + stripped[2:])
            continue
        lines.append(line)
    return "\n".join(lines)


def _render_markdown_like(text: str) -> str:
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    return rendered


def _compact_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
