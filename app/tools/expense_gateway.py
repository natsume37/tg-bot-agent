from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.time_parser import parse_spent_at
from app.core.types import MCPToolResult
from app.services.expense_service import ExpenseService


class ExpenseGateway:
    def __init__(self, service: ExpenseService, timezone_name: str):
        self.service = service
        self.timezone_name = timezone_name
        self._routes = {
            "record_expense": self.record_expense,
            "record_expenses_batch": self.record_expenses_batch,
            "query_expenses": self.query_expenses,
            "get_expense": self.get_expense,
            "update_expense": self.update_expense,
            "delete_expense": self.delete_expense,
            "summarize_expenses": self.summarize_expenses,
        }

    def handlers(self):
        return {name: self._build_handler(name) for name in self._routes.keys()}

    def _build_handler(self, route_name: str):
        async def _handler(user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
            return await self._routes[route_name](user_id, arguments)

        return _handler

    async def record_expense(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        amount = float(arguments.get("amount", 0))
        if amount <= 0:
            return MCPToolResult(success=False, message="金额必须大于0")
        category = str(arguments.get("category", "其他")).strip() or "其他"
        description = str(arguments.get("description", "")).strip()
        currency = str(arguments.get("currency", "CNY")).strip() or "CNY"
        spent_at = self._parse_spent_at(arguments.get("spent_at") or description)

        row = await self.service.record_expense(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            currency=currency,
            spent_at=spent_at,
        )
        return MCPToolResult(
            success=True,
            message="开销记录成功",
            data={
                "id": row.id,
                "amount": row.amount,
                "category": row.category,
                "description": row.description,
                "spent_at": row.spent_at.isoformat(),
            },
        )

    async def record_expenses_batch(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        items = arguments.get("items") or []
        if not isinstance(items, list) or not items:
            return MCPToolResult(success=False, message="items 必须是非空数组")

        results = []
        total = 0.0
        for idx, item in enumerate(items):
            amount = float(item.get("amount", 0))
            if amount <= 0:
                return MCPToolResult(success=False, message=f"第 {idx + 1} 笔金额无效")

            category = str(item.get("category", "其他")).strip() or "其他"
            description = str(item.get("description", "")).strip() or f"消费{idx + 1}"
            currency = str(item.get("currency", "CNY")).strip() or "CNY"
            spent_at = self._parse_spent_at(item.get("spent_at") or description)

            row = await self.service.record_expense(
                user_id=user_id,
                amount=amount,
                category=category,
                description=description,
                currency=currency,
                spent_at=spent_at,
            )
            total += amount
            results.append(
                {
                    "id": row.id,
                    "amount": row.amount,
                    "category": row.category,
                    "description": row.description,
                    "spent_at": row.spent_at.isoformat(),
                }
            )

        return MCPToolResult(
            success=True,
            message="批量记账成功",
            data={"count": len(results), "total": round(total, 2), "items": results},
        )

    async def query_expenses(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        limit = int(arguments.get("limit", 10))
        rows = await self.service.query_expenses(user_id=user_id, limit=limit)
        data = [
            {
                "id": row.id,
                "amount": row.amount,
                "category": row.category,
                "description": row.description,
                "spent_at": row.spent_at.isoformat(),
            }
            for row in rows
        ]
        return MCPToolResult(success=True, message=f"返回 {len(data)} 条记录", data={"items": data})

    async def get_expense(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        expense_id = int(arguments.get("expense_id", 0))
        row = await self.service.get_expense(user_id=user_id, expense_id=expense_id)
        if not row:
            return MCPToolResult(success=False, message="记录不存在")
        return MCPToolResult(
            success=True,
            message="查询成功",
            data={
                "id": row.id,
                "amount": row.amount,
                "category": row.category,
                "description": row.description,
                "spent_at": row.spent_at.isoformat(),
            },
        )

    async def update_expense(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        expense_id = int(arguments.get("expense_id", 0))
        amount = arguments.get("amount")
        amount_val = float(amount) if amount is not None else None
        category = arguments.get("category")
        description = arguments.get("description")
        spent_at = self._parse_spent_at(arguments.get("spent_at")) if arguments.get("spent_at") else None

        row = await self.service.update_expense(
            user_id=user_id,
            expense_id=expense_id,
            amount=amount_val,
            category=category,
            description=description,
            spent_at=spent_at,
        )
        if not row:
            return MCPToolResult(success=False, message="记录不存在")
        return MCPToolResult(
            success=True,
            message="更新成功",
            data={
                "id": row.id,
                "amount": row.amount,
                "category": row.category,
                "description": row.description,
                "spent_at": row.spent_at.isoformat(),
            },
        )

    async def delete_expense(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        expense_id = int(arguments.get("expense_id", 0))
        ok = await self.service.delete_expense(user_id=user_id, expense_id=expense_id)
        if not ok:
            return MCPToolResult(success=False, message="记录不存在")
        return MCPToolResult(success=True, message="删除成功", data={"expense_id": expense_id})

    async def summarize_expenses(self, user_id: str, arguments: dict[str, Any]) -> MCPToolResult:
        limit = int(arguments.get("limit", 30))
        summary = await self.service.summarize_expenses(user_id=user_id, limit=limit)
        return MCPToolResult(success=True, message="汇总完成", data=summary)

    def _parse_spent_at(self, value: Any) -> datetime | None:
        if value is None:
            return None
        return parse_spent_at(str(value), self.timezone_name)
