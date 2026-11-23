import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from proofscan import handoff_models  # noqa: F401
from proofscan.config import settings
from proofscan.db import Base


def run_online(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    engine = create_async_engine(settings().database_url, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_online)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings().database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(migrate())
