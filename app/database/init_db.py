import asyncio

from .db import Base, engine
from . import models


async def init_database():
    print("🗄️ Initializing NOVA database...")

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    print("✅ NOVA database tables are ready!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
