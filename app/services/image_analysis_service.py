from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

import httpx

from app.config.settings import Settings
from app.llm.router import LLMRouter
from app.repositories.db import Database
from app.repositories.image_analysis_repository import ImageAnalysisRepository


class ImageAnalysisService:
    def __init__(self, settings: Settings, llm_router: LLMRouter, default_db: Database):
        self.settings = settings
        self.llm_router = llm_router
        db_url = settings.image_analysis_database_url or settings.database_url
        self.db = Database(db_url, echo=settings.sql_echo)
        self.default_db = default_db

    async def init(self) -> None:
        if self.settings.image_analysis_store_to_db:
            await self.db.init_models()

    async def analyze_from_bytes(
        self,
        user_id: str,
        image_bytes: bytes,
        mime_type: str,
        source_file_id: str = "",
        prompt: str | None = None,
    ) -> dict:
        if not self.settings.image_analysis_enabled:
            return {"success": False, "message": "图片分析未启用"}

        effective_prompt = prompt or self.settings.image_analysis_prompt
        analysis_text, raw = await self.llm_router.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=effective_prompt,
            model=self.settings.image_analysis_model,
        )

        storage_uri = ""
        if self.settings.image_storage_mode == "local":
            storage_uri = self._save_local_image(user_id=user_id, image_bytes=image_bytes, mime_type=mime_type)
        elif self.settings.image_storage_channel_url:
            storage_uri = self.settings.image_storage_channel_url

        record_id = None
        if self.settings.image_analysis_store_to_db:
            async for session in self.db.get_session():
                repository = ImageAnalysisRepository(session)
                row = await repository.create(
                    user_id=user_id,
                    source_file_id=source_file_id,
                    mime_type=mime_type,
                    storage_uri=storage_uri,
                    prompt=effective_prompt,
                    analysis_text=analysis_text,
                    raw_response=raw,
                )
                record_id = row.id
                break

        return {
            "success": True,
            "message": "图片分析完成",
            "analysis_text": analysis_text,
            "storage_uri": storage_uri,
            "record_id": record_id,
        }

    async def analyze_from_url(self, user_id: str, image_url: str, prompt: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            mime_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return await self.analyze_from_bytes(
                user_id=user_id,
                image_bytes=response.content,
                mime_type=mime_type,
                source_file_id=image_url,
                prompt=prompt,
            )

    def _save_local_image(self, user_id: str, image_bytes: bytes, mime_type: str) -> str:
        ext = ".jpg"
        if "png" in mime_type:
            ext = ".png"
        elif "webp" in mime_type:
            ext = ".webp"

        folder = Path(self.settings.image_storage_dir) / user_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"
        target = folder / filename
        target.write_bytes(image_bytes)
        return str(target)
