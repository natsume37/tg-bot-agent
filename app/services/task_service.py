from app.repositories.db import Database
from app.repositories.task_repository import TaskRepository


class TaskService:
    def __init__(self, db: Database):
        self.db = db

    async def create_task(self, user_id: str, title: str, due_date: str | None = None):
        async for session in self.db.get_session():
            repository = TaskRepository(session)
            return await repository.create(user_id=user_id, title=title, due_date=due_date)

    async def list_tasks(self, user_id: str, limit: int = 10):
        async for session in self.db.get_session():
            repository = TaskRepository(session)
            return await repository.list_recent(user_id=user_id, limit=limit)
        return []

    async def update_task(self, user_id: str, task_id: int, status: str):
        async for session in self.db.get_session():
            repository = TaskRepository(session)
            return await repository.update_status(user_id=user_id, task_id=task_id, status=status)

    async def delete_task(self, user_id: str, task_id: int):
        async for session in self.db.get_session():
            repository = TaskRepository(session)
            return await repository.delete(user_id=user_id, task_id=task_id)
        return False
