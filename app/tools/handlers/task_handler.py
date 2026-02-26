from app.core.types import MCPToolResult
from app.services.task_service import TaskService


def create_task_handlers(service: TaskService):
    def parse_int(value: object, default: int = 0, *, min_value: int | None = None, max_value: int | None = None) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = default

        if min_value is not None and parsed < min_value:
            parsed = min_value
        if max_value is not None and parsed > max_value:
            parsed = max_value
        return parsed

    async def create_task(user_id: str, arguments: dict) -> MCPToolResult:
        title = str(arguments.get("title", "")).strip()
        if not title:
            return MCPToolResult(success=False, message="任务标题不能为空")
        due_date = arguments.get("due_date")
        task = await service.create_task(user_id=user_id, title=title, due_date=due_date)
        return MCPToolResult(
            success=True,
            data={"id": task.id, "title": task.title, "status": task.status, "due_date": task.due_date},
            message="任务创建成功",
        )

    async def list_tasks(user_id: str, arguments: dict) -> MCPToolResult:
        limit = parse_int(arguments.get("limit", 10), default=10, min_value=1, max_value=1000)
        tasks = await service.list_tasks(user_id=user_id, limit=limit)
        data = [{"id": t.id, "title": t.title, "status": t.status, "due_date": t.due_date} for t in tasks]
        return MCPToolResult(success=True, data={"items": data}, message=f"返回 {len(data)} 个任务")

    async def update_task(user_id: str, arguments: dict) -> MCPToolResult:
        task_id = parse_int(arguments.get("task_id", 0), default=0, min_value=0)
        status = str(arguments.get("status", "todo")).strip()
        task = await service.update_task(user_id=user_id, task_id=task_id, status=status)
        if not task:
            return MCPToolResult(success=False, message="任务不存在")
        return MCPToolResult(success=True, data={"id": task.id, "status": task.status}, message="任务更新成功")

    async def delete_task(user_id: str, arguments: dict) -> MCPToolResult:
        task_id = parse_int(arguments.get("task_id", 0), default=0, min_value=0)
        ok = await service.delete_task(user_id=user_id, task_id=task_id)
        if not ok:
            return MCPToolResult(success=False, message="任务不存在")
        return MCPToolResult(success=True, data={"task_id": task_id}, message="任务删除成功")

    return {
        "create_task": create_task,
        "list_tasks": list_tasks,
        "update_task": update_task,
        "delete_task": delete_task,
    }
