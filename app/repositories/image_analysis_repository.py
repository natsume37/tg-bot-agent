from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import ImageAnalysisRecord


class ImageAnalysisRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        source_file_id: str,
        mime_type: str,
        storage_uri: str,
        prompt: str,
        analysis_text: str,
        raw_response: str,
    ) -> ImageAnalysisRecord:
        row = ImageAnalysisRecord(
            user_id=user_id,
            source_file_id=source_file_id,
            mime_type=mime_type,
            storage_uri=storage_uri,
            prompt=prompt,
            analysis_text=analysis_text,
            raw_response=raw_response,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
