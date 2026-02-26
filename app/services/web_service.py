from __future__ import annotations

from datetime import datetime
from html import unescape
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from app.repositories.db import Database
from app.repositories.web_screenshot_repository import WebScreenshotRepository


class WebService:
    def __init__(
        self,
        output_dir: str,
        google_search_base_url: str,
        screenshot_timeout_ms: int = 15000,
        db: Database | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.google_search_base_url = google_search_base_url
        self.screenshot_timeout_ms = screenshot_timeout_ms
        self.db = db

    async def google_search(self, query: str, limit: int = 5, language: str = "zh-CN") -> dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {"query": q, "count": 0, "items": []}

        safe_limit = max(1, min(limit, 10))
        url = f"{self.google_search_base_url}?q={quote_plus(q)}&hl={quote_plus(language)}&num={safe_limit}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": language,
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text

        items: list[dict[str, str]] = []
        for match in re.finditer(r'<a\s+href="/url\?q=([^"&]+)[^"]*"[^>]*>\s*(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL):
            raw_link = unquote(unescape(match.group(1)))
            inner_html = match.group(2)
            title_match = re.search(r"<h3[^>]*>(.*?)</h3>", inner_html, flags=re.IGNORECASE | re.DOTALL)
            if not title_match:
                continue

            title = self._clean_html_text(title_match.group(1))
            link = self._normalize_search_link(raw_link)

            if not title or not link:
                continue
            if "google.com" in urlparse(link).netloc:
                continue

            items.append({"title": title, "url": link})
            if len(items) >= safe_limit:
                break

        return {"query": q, "count": len(items), "items": items}

    async def capture_website_screenshot(
        self,
        user_id: str,
        url: str,
        full_page: bool = True,
        width: int = 1366,
        height: int = 900,
        storage_mode: str = "none",
    ) -> dict[str, Any]:
        target_url = self._normalize_url(url)
        if not target_url:
            raise ValueError("无效的 URL")

        mode = (storage_mode or "none").strip().lower()
        if mode not in {"none", "local", "database"}:
            mode = "none"

        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError("未安装 playwright，请先执行: uv add playwright && uv run playwright install chromium") from exc

        folder = (self.output_dir / "screenshots" / user_id) if mode == "local" else (self.output_dir / "temp" / user_id)
        folder.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        output_path = folder / filename

        page_title = ""
        final_url = target_url
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": max(320, width), "height": max(320, height)})
                await page.goto(target_url, wait_until="networkidle", timeout=self.screenshot_timeout_ms)
                page_title = await page.title()
                final_url = page.url
                await page.screenshot(path=str(output_path), full_page=full_page)
                await browser.close()
        except PlaywrightError as exc:
            raise RuntimeError(f"网页截图失败: {exc}") from exc

        screenshot_id = None
        if mode == "database":
            if not self.db:
                raise RuntimeError("数据库未配置，无法保存截图到数据库")
            image_bytes = output_path.read_bytes()
            async for session in self.db.get_session():
                repository = WebScreenshotRepository(session)
                row = await repository.create(
                    user_id=user_id,
                    url=final_url,
                    title=page_title,
                    mime_type="image/png",
                    image_bytes=image_bytes,
                )
                screenshot_id = row.id
                break

        return {
            "url": final_url,
            "title": page_title,
            "path": str(output_path),
            "storage_mode": mode,
            "screenshot_id": screenshot_id,
        }

    def _normalize_url(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if not re.match(r"^https?://", text, flags=re.IGNORECASE):
            text = f"https://{text}"
        parsed = urlparse(text)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return text

    def _normalize_search_link(self, value: str) -> str:
        link = (value or "").strip()
        if not link:
            return ""
        if link.startswith("http://") or link.startswith("https://"):
            return link
        if link.startswith("/url?"):
            params = parse_qs(urlparse(link).query)
            q_values = params.get("q") or []
            return q_values[0] if q_values else ""
        return ""

    def _clean_html_text(self, value: str) -> str:
        no_tags = re.sub(r"<[^>]+>", "", value)
        compact = re.sub(r"\s+", " ", no_tags).strip()
        return unescape(compact)
