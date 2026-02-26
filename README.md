# Telegram MCP Bot（Python）

这是一个按 MCP 思路实现的 Telegram AI Agent 骨架，支持：

- Tool 标准化注册与发现
- Runtime 与 Tool 解耦
- 短期记忆（内存/Redis）
- 业务存储（SQLite/PostgreSQL via SQLAlchemy）
- 费用、任务、天气工具模块化扩展

## 1. 目录结构

```text
app/
	config/          # .env 配置加载
	core/            # MCP 类型、Agent Runtime
	llm/             # 模型路由（OpenAI/Heuristic）
	memory/          # Memory 接口及实现（InMemory/Redis）
	repositories/    # 数据模型与仓储
	services/        # 业务服务层
	tools/           # MCP Tool 定义、注册中心、处理器
	telegram/        # Telegram 网关
main.py            # 启动入口
```

## 2. 分步实现映射

对应你的需求文档，已落地如下：

1) MCP Gateway / Agent Runtime
- `app/core/runtime.py`

2) Tool Registry + Tool Schema
- `app/tools/definitions.py`
- `app/tools/registry.py`

3) 功能 MCP 化
- Expense: `app/tools/handlers/expense_handler.py`
- Analytics: `app/tools/handlers/analytics_handler.py`
- Task: `app/tools/handlers/task_handler.py`
- Weather: `app/tools/handlers/weather_handler.py`

4) Memory
- `app/memory/base.py`
- `app/memory/in_memory.py`
- `app/memory/redis_store.py`

5) 存储层
- `app/repositories/models.py`
- `app/repositories/expense_repository.py`
- `app/repositories/task_repository.py`

6) Telegram Gateway
- `app/telegram/gateway.py`

## 3. 环境配置（.env）

```bash
cp .env.example .env
```

至少配置：

```env
TELEGRAM_BOT_TOKEN=你的token
LLM_PROVIDER=heuristic
```

可选：

- `LLM_PROVIDER=openai` + `LLM_API_KEY=...`
- `USE_REDIS_MEMORY=true`
- `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname`

PostgreSQL 默认配置示例：

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot
```

## 4. 初始化数据库

```bash
uv run python -m scripts.init_db
```

该命令会根据 `DATABASE_URL` 自动创建项目所需表结构。

## 5. 安装与运行

```bash
uv python install 3.11
uv sync
uv run playwright install chromium
uv run python main.py
```

## 6. Google 搜索与网页截图（AI 意图识别）

- 无需固定命令或关键词，直接自然语言描述需求即可。
- 示例：
	- `帮我搜一下 Python asyncio 教程`
	- `把 https://example.com 截个图给我`
- 机器人会由模型自动判断意图并调用：
	- `google_search`
	- `capture_website_screenshot`

说明：

- 网页截图依赖 Playwright 浏览器，首次部署需要执行：`uv run playwright install chromium`
- 建议使用 `LLM_PROVIDER=openai`（或其它已接入模型）以获得稳定的意图识别效果。
- 截图默认不落地持久化：仅临时生成并发送到 Telegram，发送后自动清理本地临时文件。
- 用户可通过配置切换截图存储策略（`none/local/database`）：
	- `set_user_config key=web_screenshot_storage value=database`
	- `set_user_config key=web_screenshot_storage value=local`
	- `set_user_config key=web_screenshot_storage value=none`

## 7. 新增一个 Tool 的方式（可扩展）

1. 在 `app/tools/definitions.py` 增加 schema
2. 在 `app/tools/handlers/` 添加处理函数
3. 在 `app/bootstrap.py` 注册 handler

无需修改 Runtime 核心。

## 8. 说明

- 默认 `LLM_PROVIDER=heuristic` 可离线跑通基础流程。
- 如果切到 OpenAI，`app/llm/router.py` 会优先用模型规划 tool call。
- 如果启动时报 `Conflict: terminated by other getUpdates request`，说明同一个 Token 在其它进程/机器也在运行，请先停掉其它实例再启动当前服务。
- 当前已采用 MCP Agent Loop：AI 先意图识别并决定是否调用工具；可调用 `record_expenses_batch` 一次写入多笔消费；工具执行后由 AI 汇总最终回复。

## 9. 日志排查（模型无输出/回复异常）

- 日志默认写入 `logs/app.log`，级别由 `LOG_LEVEL` 控制。
- 若要看 SQL 查询细节，设置 `SQL_ECHO=true`。
- 常用排查：

```bash
tail -f logs/app.log
```

重点关注以下日志：

- `LLM planning start`：是否进入模型规划
- `LLM raw output length`：模型是否有返回文本
- `LLM returned no valid tool call`：模型返回不可解析，已回退 heuristic
- `Tool result ...`：工具调用是否成功
- `No data for tool=...`：确认为数据为空导致“暂无数据”

## 10. 入账时间支持

- 记账工具支持 `spent_at` 参数（单笔与批量都支持）。
- 用户描述包含相对时间时（如“昨天晚上买雨伞25”），系统会自动解析并写入 `spent_at`。
- 也支持模型直接传 ISO 时间，例如 `2026-02-26T12:30:00`。

## 11. 消费智能分析与可视化

- `analyze_expenses`：返回消费统计、均值、最高消费、Top 分类。
- `visualize_expenses`：生成图表文件，支持：
	- `category_bar`（分类柱状图）
	- `category_pie`（分类占比饼图）
	- `daily_trend`（日趋势折线图）
	- `top_expenses`（Top 支出图）
- 图表默认输出到 `ANALYTICS_OUTPUT_DIR`（默认 `outputs/charts`）。
- Telegram 侧会在文本总结后自动发送生成的图表图片。

