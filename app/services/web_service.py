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

        items: list[dict[str, str]] = self._extract_google_items(html=html, limit=safe_limit)
        if not items and self._is_wikipedia_query(q):
            wiki_items = await self._search_wikipedia(query=q, language=language, limit=safe_limit)
            items.extend(wiki_items)

        return {"query": q, "count": len(items), "items": items}

    async def deep_web_search(
        self,
        query: str,
        language: str = "zh-CN",
        per_query_limit: int = 5,
        max_sources: int = 8,
    ) -> dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {"query": q, "count": 0, "sources": []}

        search_queries = self._build_deep_queries(q)
        collected_urls: list[str] = []
        seen_urls: set[str] = set()

        for candidate in search_queries:
            search_result = await self.google_search(query=candidate, limit=per_query_limit, language=language)
            for item in search_result.get("items", []):
                url = str(item.get("url", "")).strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                collected_urls.append(url)
                if len(collected_urls) >= max_sources:
                    break
            if len(collected_urls) >= max_sources:
                break

        if not collected_urls:
            return {
                "query": q,
                "count": 0,
                "search_queries": search_queries,
                "sources": [],
            }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            tasks = [self._fetch_source(client=client, url=url) for url in collected_urls]
            results = await self._gather_sources(tasks)

        sources = [row for row in results if row]
        return {
            "query": q,
            "count": len(sources),
            "search_queries": search_queries,
            "sources": sources,
        }

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
        attempt_configs = [
            {
                "wait_until": "networkidle",
                "full_page": full_page,
                "width": max(320, width),
                "height": max(320, height),
                "goto_timeout": self.screenshot_timeout_ms,
                "screenshot_timeout": min(30000, self.screenshot_timeout_ms),
            },
            {
                "wait_until": "domcontentloaded",
                "full_page": False,
                "width": min(max(320, width), 1024),
                "height": min(max(320, height), 768),
                "goto_timeout": max(8000, self.screenshot_timeout_ms // 2),
                "screenshot_timeout": 15000,
            },
        ]

        last_error: Exception | None = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    for config in attempt_configs:
                        try:
                            page = await browser.new_page(
                                viewport={"width": config["width"], "height": config["height"]}
                            )
                            await page.goto(
                                target_url,
                                wait_until=config["wait_until"],
                                timeout=config["goto_timeout"],
                            )
                            page_title = await page.title()
                            final_url = page.url
                            await page.screenshot(
                                path=str(output_path),
                                full_page=bool(config["full_page"]),
                                timeout=int(config["screenshot_timeout"]),
                            )
                            await page.close()
                            last_error = None
                            break
                        except PlaywrightError as exc:
                            last_error = exc
                            try:
                                await page.close()
                            except Exception:
                                pass
                            continue
                finally:
                    await browser.close()
        except PlaywrightError as exc:
            last_error = exc

        if last_error is not None:
            raise RuntimeError(f"网页截图失败: {last_error}") from last_error

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

    def _build_deep_queries(self, query: str) -> list[str]:
        base = query.strip()
        candidates = [
            base,
            f"{base} 官方",
            f"{base} 最新",
            f"{base} 深度解读",
        ]
        seen: set[str] = set()
        unique: list[str] = []
        for row in candidates:
            key = row.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        return unique

    async def _gather_sources(self, tasks: list[Any]) -> list[dict[str, Any]]:
        import asyncio

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        rows: list[dict[str, Any]] = []
        for result in raw_results:
            if isinstance(result, Exception):
                continue
            if result:
                rows.append(result)
        return rows

    async def _fetch_source(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
        except Exception:
            return {}

        title = self._extract_title(html) or url
        snippet = self._extract_snippet(html)
        return {
            "title": title,
            "url": str(response.url),
            "snippet": snippet,
        }

    def _extract_title(self, html: str) -> str:
        matched = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not matched:
            return ""
        return self._clean_html_text(matched.group(1))

    def _extract_snippet(self, html: str, max_length: int = 280) -> str:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = self._clean_html_text(text)
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip() + "..."

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

    def _extract_google_items(self, html: str, limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        seen: set[str] = set()

        pattern = re.compile(
            r"<a[^>]+href=\"([^\"]+)\"[^>]*>\s*(.*?)\s*</a>",
            flags=re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            href = unescape(match.group(1))
            inner_html = match.group(2)
            title_match = re.search(r"<h3[^>]*>(.*?)</h3>", inner_html, flags=re.IGNORECASE | re.DOTALL)
            if not title_match:
                continue

            title = self._clean_html_text(title_match.group(1))
            link = self._normalize_search_link(href)
            if not title or not link:
                continue
            if "google.com" in urlparse(link).netloc or link in seen:
                continue

            seen.add(link)
            results.append({"title": title, "url": link})
            if len(results) >= limit:
                break

        return results

    def _is_wikipedia_query(self, query: str) -> bool:
        lowered = query.lower()
        return "维基" in query or "wikipedia" in lowered

    async def _search_wikipedia(self, query: str, language: str, limit: int) -> list[dict[str, str]]:
        lang = "zh" if language.lower().startswith("zh") else "en"
        api_url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": max(1, min(limit, 10)),
        }
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []

        items: list[dict[str, str]] = []
        for row in payload.get("query", {}).get("search", []) or []:
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            url_title = quote_plus(title.replace(" ", "_"))
            items.append({"title": title, "url": f"https://{lang}.wikipedia.org/wiki/{url_title}"})
        return items
