from __future__ import annotations

import asyncpg

from app.config import settings

pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Create the asyncpg connection pool.  Called once during app lifespan startup."""
    global pool
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )

    # Add new recommendation columns if they don't exist (idempotent migration)
    async with pool.acquire() as conn:
        await conn.execute("""
            ALTER TABLE recommendations
                ADD COLUMN IF NOT EXISTS estimated_yield_bushels FLOAT DEFAULT 0.0,
                ADD COLUMN IF NOT EXISTS days_remaining INTEGER DEFAULT -1,
                ADD COLUMN IF NOT EXISTS crop_health_rating INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS crop_health_summary TEXT DEFAULT ''
        """)


async def close_db_pool() -> None:
    """Gracefully close the connection pool.  Called during app lifespan shutdown."""
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def get_pool() -> asyncpg.Pool:
    """Return the live pool.  Raises RuntimeError if called before init_db_pool()."""
    if pool is None:
        raise RuntimeError("Database pool has not been initialised. Call init_db_pool() first.")
    return pool
