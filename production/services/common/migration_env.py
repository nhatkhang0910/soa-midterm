import asyncio
import importlib
import os

from alembic import context
from common import Base, engine


def configure(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    async with engine.connect() as connection:
        await connection.run_sync(configure)
    await engine.dispose()


def run():
    importlib.import_module(os.environ["SERVICE_NAME"] + ".models")
    asyncio.run(migrate())
