"""Migration environment shares the application's DB_URL."""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.db_url.replace("%", "%%"))
target_metadata = Base.metadata


def do_run_migrations(connection: Connection):
    context.configure(
        connection=connection, target_metadata=target_metadata,
        compare_type=True, render_as_batch=connection.dialect.name == "sqlite"
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async():
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.db_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    import asyncio
    asyncio.run(run_async())
