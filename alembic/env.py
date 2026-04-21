"""Alembic environment configuration.

Supports async SQLAlchemy engine (asyncpg driver).
DATABASE_URL is read from environment — never hardcoded here.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base and all ORM models so Alembic can detect tables.
# Each ORM model must be imported here — order does not matter.
from src.db_models.base import Base  # noqa: F401
from src.db_models.job_orm import JobORM  # noqa: F401
from src.db_models.candidate_orm import CandidateORM  # noqa: F401
from src.db_models.batch_orm import BatchORM  # noqa: F401
from src.core.config.settings import settings

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Override sqlalchemy.url with value from environment via settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Setup Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no DB connection needed).

    Useful for generating SQL scripts without a live DB.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode (live DB connection)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
