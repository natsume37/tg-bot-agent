from app.config.settings import get_settings
from app.core.time_parser import parse_spent_at
from app.core.types import MCPToolResult
from app.services.expense_service import ExpenseService


def create_expense_handlers(service: ExpenseService):
    settings = get_settings()

    def parse_limit(value: object, default: int) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = default
        return max(1, min(parsed, 1000))

    async def record_expense(user_id: str, arguments: dict) -> MCPToolResult:
        amount = float(arguments.get("amount", 0))
        if amount <= 0:
            return MCPToolResult(success=False, message="金额必须大于0")
        category = arguments.get("category", "其他")
        description = arguments.get("description", "")
        currency = arguments.get("currency", "CNY")
        spent_at_raw = arguments.get("spent_at") or description
        spent_at = parse_spent_at(str(spent_at_raw), settings.timezone) if spent_at_raw else None
        record = await service.record_expense(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            currency=currency,
            spent_at=spent_at,
        )
        return MCPToolResult(
            success=True,
            data={
                "id": record.id,
                "amount": record.amount,
                "category": record.category,
                "description": record.description,
                "spent_at": record.spent_at.isoformat(),
            },
            message="开销记录成功",
        )

    async def query_expenses(user_id: str, arguments: dict) -> MCPToolResult:
        limit = parse_limit(arguments.get("limit", 10), default=10)
        records = await service.query_expenses(user_id=user_id, limit=limit)
        payload = [
            {
                "id": row.id,
                "amount": row.amount,
                "category": row.category,
                "description": row.description,
                "spent_at": row.spent_at.isoformat(),
            }
            for row in records
        ]
        return MCPToolResult(success=True, data={"items": payload}, message=f"返回 {len(payload)} 条记录")

    async def record_expenses_batch(user_id: str, arguments: dict) -> MCPToolResult:
        items = arguments.get("items") or []
        if not isinstance(items, list) or not items:
            return MCPToolResult(success=False, message="items 必须是非空数组")

        records: list[dict] = []
        total = 0.0
        for idx, row in enumerate(items):
            try:
                amount = float(row.get("amount", 0))
            except Exception:
                amount = 0
            if amount <= 0:
                return MCPToolResult(success=False, message=f"第 {idx + 1} 笔金额无效")

            category = str(row.get("category", "其他")).strip() or "其他"
            description = str(row.get("description", "")).strip() or f"消费{idx + 1}"
            currency = str(row.get("currency", "CNY")).strip() or "CNY"
            spent_at_raw = row.get("spent_at") or description
            spent_at = parse_spent_at(str(spent_at_raw), settings.timezone) if spent_at_raw else None
            record = await service.record_expense(
                user_id=user_id,
                amount=amount,
                category=category,
                description=description,
                currency=currency,
                spent_at=spent_at,
            )
            total += amount
            records.append(
                {
                    "id": record.id,
                    "amount": record.amount,
                    "category": record.category,
                    "description": record.description,
                    "spent_at": record.spent_at.isoformat(),
                }
            )

        return MCPToolResult(
            success=True,
            data={"count": len(records), "total": round(total, 2), "items": records},
            message="批量记账成功",
        )

    async def summarize_expenses(user_id: str, arguments: dict) -> MCPToolResult:
        limit = parse_limit(arguments.get("limit", 30), default=30)
        summary = await service.summarize_expenses(user_id=user_id, limit=limit)
        return MCPToolResult(success=True, data=summary, message="汇总完成")

    return {
        "record_expense": record_expense,
        "record_expenses_batch": record_expenses_batch,
        "query_expenses": query_expenses,
        "summarize_expenses": summarize_expenses,
    }
