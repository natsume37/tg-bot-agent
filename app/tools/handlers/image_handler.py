from app.core.types import MCPToolResult
from app.services.image_analysis_service import ImageAnalysisService


def create_image_handlers(service: ImageAnalysisService):
    async def analyze_image(user_id: str, arguments: dict) -> MCPToolResult:
        image_url = str(arguments.get("image_url", "")).strip()
        prompt = str(arguments.get("prompt", "")).strip() or None
        if not image_url:
            return MCPToolResult(success=False, message="image_url 不能为空")
        try:
            payload = await service.analyze_from_url(user_id=user_id, image_url=image_url, prompt=prompt)
        except Exception as exc:
            return MCPToolResult(success=False, message=f"图片分析失败: {exc}")
        if not payload.get("success"):
            return MCPToolResult(success=False, message=payload.get("message", "图片分析失败"), data=payload)
        return MCPToolResult(
            success=True,
            message=payload.get("message", "图片分析完成"),
            data={
                "analysis_text": payload.get("analysis_text", ""),
                "storage_uri": payload.get("storage_uri", ""),
                "record_id": payload.get("record_id"),
            },
        )

    return {"analyze_image": analyze_image}
