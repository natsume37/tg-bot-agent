from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import WebScreenshotRecord


class WebScreenshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        url: str,
        title: str,
        mime_type: str,
        image_bytes: bytes,
    ) -> WebScreenshotRecord:
        row = WebScreenshotRecord(
            user_id=user_id,
            url=url,
            title=title,
            mime_type=mime_type,
            image_bytes=image_bytes,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
