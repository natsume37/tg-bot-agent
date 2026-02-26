from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import ExpenseRecord


class ExpenseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        amount: float,
        category: str,
        description: str,
        currency: str,
        spent_at: datetime | None = None,
    ) -> ExpenseRecord:
        record = ExpenseRecord(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            currency=currency,
            spent_at=spent_at or datetime.utcnow(),
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_recent(self, user_id: str, limit: int = 10) -> list[ExpenseRecord]:
        statement = (
            select(ExpenseRecord)
            .where(ExpenseRecord.user_id == user_id)
            .order_by(desc(ExpenseRecord.spent_at))
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, user_id: str, expense_id: int) -> ExpenseRecord | None:
        statement = select(ExpenseRecord).where(ExpenseRecord.id == expense_id, ExpenseRecord.user_id == user_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(
        self,
        user_id: str,
        expense_id: int,
        amount: float | None = None,
        category: str | None = None,
        description: str | None = None,
        spent_at: datetime | None = None,
    ) -> ExpenseRecord | None:
        record = await self.get_by_id(user_id=user_id, expense_id=expense_id)
        if not record:
            return None
        if amount is not None:
            record.amount = amount
        if category is not None:
            record.category = category
        if description is not None:
            record.description = description
        if spent_at is not None:
            record.spent_at = spent_at
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete(self, user_id: str, expense_id: int) -> bool:
        record = await self.get_by_id(user_id=user_id, expense_id=expense_id)
        if not record:
            return False
        await self.session.delete(record)
        await self.session.commit()
        return True
