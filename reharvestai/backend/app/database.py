from __future__ import annotations

import asyncpg

from app.config import settings

pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Create the asyncpg connection pool.  Called once during app lifespan startup."""
    global pool
    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


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
