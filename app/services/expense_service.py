from datetime import datetime

from app.repositories.db import Database
from app.repositories.expense_repository import ExpenseRepository


class ExpenseService:
    def __init__(self, db: Database):
        self.db = db

    async def record_expense(
        self,
        user_id: str,
        amount: float,
        category: str = "其他",
        description: str = "",
        currency: str = "CNY",
        spent_at: datetime | None = None,
    ):
        async for session in self.db.get_session():
            repository = ExpenseRepository(session)
            return await repository.create(
                user_id=user_id,
                amount=amount,
                category=category,
                description=description,
                currency=currency,
                spent_at=spent_at,
            )

    async def query_expenses(self, user_id: str, limit: int = 10):
        async for session in self.db.get_session():
            repository = ExpenseRepository(session)
            return await repository.list_recent(user_id=user_id, limit=limit)
        return []

    async def get_expense(self, user_id: str, expense_id: int):
        async for session in self.db.get_session():
            repository = ExpenseRepository(session)
            return await repository.get_by_id(user_id=user_id, expense_id=expense_id)
        return None

    async def update_expense(
        self,
        user_id: str,
        expense_id: int,
        amount: float | None = None,
        category: str | None = None,
        description: str | None = None,
        spent_at: datetime | None = None,
    ):
        async for session in self.db.get_session():
            repository = ExpenseRepository(session)
            return await repository.update(
                user_id=user_id,
                expense_id=expense_id,
                amount=amount,
                category=category,
                description=description,
                spent_at=spent_at,
            )
        return None

    async def delete_expense(self, user_id: str, expense_id: int) -> bool:
        async for session in self.db.get_session():
            repository = ExpenseRepository(session)
            return await repository.delete(user_id=user_id, expense_id=expense_id)
        return False

    async def summarize_expenses(self, user_id: str, limit: int = 30) -> dict:
        records = await self.query_expenses(user_id=user_id, limit=limit)
        total = sum(item.amount for item in records)
        by_category: dict[str, float] = {}
        for item in records:
            by_category[item.category] = by_category.get(item.category, 0) + item.amount
        return {
            "count": len(records),
            "total": round(total, 2),
            "by_category": {key: round(value, 2) for key, value in by_category.items()},
        }
