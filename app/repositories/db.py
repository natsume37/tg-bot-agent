from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, database_url: str, echo: bool = False):
        self.engine = create_async_engine(database_url, future=True, echo=echo)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_models(self) -> None:
        from app.repositories.models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await self._reconcile_legacy_schema(conn)

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def _reconcile_legacy_schema(self, conn) -> None:
        dialect = self.engine.dialect.name

        async def get_columns(table_name: str) -> set[str]:
            def _inspect_columns(sync_conn) -> set[str]:
                return {item["name"] for item in inspect(sync_conn).get_columns(table_name)}

            return await conn.run_sync(_inspect_columns)

        async def add_column_if_missing(table_name: str, column_name: str, ddl_sql: str) -> None:
            columns = await get_columns(table_name)
            if column_name in columns:
                return
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl_sql}"))

        updated_at_sql = (
            "updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL"
            if dialect == "postgresql"
            else "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

        await add_column_if_missing("expenses", "updated_at", updated_at_sql)
        await add_column_if_missing("user_configs", "updated_at", updated_at_sql)
