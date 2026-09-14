import asyncio

from sqlalchemy import text

from .db import engine


async def test_connection():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT 1")
            )

            print("✅ Supabase database connection successful!")
            print(f"📊 Test result: {result.scalar()}")

    except Exception as error:
        print("❌ Database connection failed!")
        print(f"{type(error).__name__}: {error}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())
