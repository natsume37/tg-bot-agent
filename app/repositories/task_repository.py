from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import TaskRecord


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, title: str, due_date: str | None = None) -> TaskRecord:
        task = TaskRecord(user_id=user_id, title=title, due_date=due_date)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def list_recent(self, user_id: str, limit: int = 10) -> list[TaskRecord]:
        statement = (
            select(TaskRecord)
            .where(TaskRecord.user_id == user_id)
            .order_by(desc(TaskRecord.created_at))
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(self, user_id: str, task_id: int, status: str) -> TaskRecord | None:
        statement = select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.user_id == user_id)
        result = await self.session.execute(statement)
        task = result.scalar_one_or_none()
        if not task:
            return None
        task.status = status
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def delete(self, user_id: str, task_id: int) -> bool:
        statement = select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.user_id == user_id)
        result = await self.session.execute(statement)
        task = result.scalar_one_or_none()
        if not task:
            return False
        await self.session.delete(task)
        await self.session.commit()
        return True
