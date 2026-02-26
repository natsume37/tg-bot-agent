from app.core.types import MCPToolDefinition, MCPToolInputSchema


TOOL_DEFINITIONS: list[MCPToolDefinition] = [
    MCPToolDefinition(
        name="record_expense",
        description="记录用户开销",
        input_schema=MCPToolInputSchema(
            properties={
                "amount": {"type": "number"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "spent_at": {"type": "string", "description": "消费时间，ISO格式或相对时间文本"},
            },
            required=["amount"],
        ),
    ),
    MCPToolDefinition(
        name="record_expenses_batch",
        description="批量记录多笔开销，适合一句话里包含多条消费信息",
        input_schema=MCPToolInputSchema(
            properties={
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number"},
                            "category": {"type": "string"},
                            "description": {"type": "string"},
                            "spent_at": {"type": "string", "description": "消费时间，ISO格式或相对时间文本"},
                        },
                        "required": ["amount"],
                    },
                    "minItems": 1,
                }
            },
            required=["items"],
        ),
    ),
    MCPToolDefinition(
        name="query_expenses",
        description="查询用户开销",
        input_schema=MCPToolInputSchema(properties={"limit": {"type": "integer"}}, required=[]),
    ),
    MCPToolDefinition(
        name="get_expense",
        description="查询单条开销详情",
        input_schema=MCPToolInputSchema(properties={"expense_id": {"type": "integer"}}, required=["expense_id"]),
    ),
    MCPToolDefinition(
        name="update_expense",
        description="更新开销记录",
        input_schema=MCPToolInputSchema(
            properties={
                "expense_id": {"type": "integer"},
                "amount": {"type": "number"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "spent_at": {"type": "string"},
            },
            required=["expense_id"],
        ),
    ),
    MCPToolDefinition(
        name="delete_expense",
        description="删除开销记录",
        input_schema=MCPToolInputSchema(properties={"expense_id": {"type": "integer"}}, required=["expense_id"]),
    ),
    MCPToolDefinition(
        name="summarize_expenses",
        description="汇总用户开销",
        input_schema=MCPToolInputSchema(properties={"limit": {"type": "integer"}}, required=[]),
    ),
    MCPToolDefinition(
        name="analyze_expenses",
        description="分析用户开销模式",
        input_schema=MCPToolInputSchema(
            properties={
                "limit": {"type": "integer"},
                "days": {"type": "integer", "description": "最近N天，0表示不限制"},
            },
            required=[],
        ),
    ),
    MCPToolDefinition(
        name="visualize_expenses",
        description="生成消费可视化图表，支持柱状图、饼图、趋势图和Top支出图",
        input_schema=MCPToolInputSchema(
            properties={
                "limit": {"type": "integer"},
                "days": {"type": "integer", "description": "最近N天，0表示不限制"},
                "chart_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选: category_bar,category_pie,daily_trend,top_expenses,all",
                },
            },
            required=[],
        ),
    ),
    MCPToolDefinition(
        name="set_user_config",
        description="设置用户配置项",
        input_schema=MCPToolInputSchema(
            properties={"key": {"type": "string"}, "value": {"type": "string"}},
            required=["key", "value"],
        ),
    ),
    MCPToolDefinition(
        name="get_user_config",
        description="获取用户配置项",
        input_schema=MCPToolInputSchema(properties={"key": {"type": "string"}}, required=["key"]),
    ),
    MCPToolDefinition(
        name="list_user_configs",
        description="列出当前用户所有配置项",
        input_schema=MCPToolInputSchema(properties={}, required=[]),
    ),
    MCPToolDefinition(
        name="delete_user_config",
        description="删除用户配置项",
        input_schema=MCPToolInputSchema(properties={"key": {"type": "string"}}, required=["key"]),
    ),
    MCPToolDefinition(
        name="analyze_image",
        description="分析一张图片内容，支持通过图片URL传入",
        input_schema=MCPToolInputSchema(
            properties={
                "image_url": {"type": "string"},
                "prompt": {"type": "string"},
            },
            required=["image_url"],
        ),
    ),
    MCPToolDefinition(
        name="create_task",
        description="创建任务",
        input_schema=MCPToolInputSchema(
            properties={"title": {"type": "string"}, "due_date": {"type": "string"}},
            required=["title"],
        ),
    ),
    MCPToolDefinition(
        name="list_tasks",
        description="查询任务",
        input_schema=MCPToolInputSchema(properties={"limit": {"type": "integer"}}, required=[]),
    ),
    MCPToolDefinition(
        name="update_task",
        description="修改任务",
        input_schema=MCPToolInputSchema(
            properties={"task_id": {"type": "integer"}, "status": {"type": "string"}},
            required=["task_id", "status"],
        ),
    ),
    MCPToolDefinition(
        name="delete_task",
        description="删除任务",
        input_schema=MCPToolInputSchema(properties={"task_id": {"type": "integer"}}, required=["task_id"]),
    ),
    MCPToolDefinition(
        name="get_weather",
        description="获取指定城市天气",
        input_schema=MCPToolInputSchema(properties={"city": {"type": "string"}}, required=["city"]),
    ),
    MCPToolDefinition(
        name="google_search",
        description="通过 Google 搜索关键词并返回结果列表",
        input_schema=MCPToolInputSchema(
            properties={
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "language": {"type": "string", "description": "语言代码，如 zh-CN,en"},
            },
            required=["query"],
        ),
    ),
    MCPToolDefinition(
        name="capture_website_screenshot",
        description="对指定网页进行截图，返回截图路径",
        input_schema=MCPToolInputSchema(
            properties={
                "url": {"type": "string"},
                "full_page": {"type": "boolean"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "storage_mode": {"type": "string", "description": "none/local/database，默认 none"},
            },
            required=["url"],
        ),
    ),
]
