import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import get_settings
from app.repositories.db import Database


async def init_db() -> None:
    settings = get_settings()
    db = Database(settings.database_url)
    try:
        await db.init_models()
        print("✅ 数据库初始化完成（表结构已创建）")
        print(f"DATABASE_URL={settings.database_url}")
    except SQLAlchemyError as exc:
        message = str(exc)
        print("❌ 数据库初始化失败")
        print(f"DATABASE_URL={settings.database_url}")

        if "InvalidPasswordError" in message or "password authentication failed" in message:
            print("原因：PostgreSQL 用户名或密码错误。")
            print("请检查 .env 中的 DATABASE_URL，确认用户名/密码与本机 PostgreSQL 一致。")
        elif "ConnectionRefusedError" in message or "Connect call failed" in message:
            print("原因：无法连接 PostgreSQL，服务可能未启动。")
            print("请先启动 PostgreSQL，再执行初始化脚本。")
        elif "database \"" in message and "does not exist" in message:
            print("原因：目标数据库不存在。")
            print("请先创建数据库，例如：createdb tgbot")
        else:
            print(f"详细错误：{message}")
        raise


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
