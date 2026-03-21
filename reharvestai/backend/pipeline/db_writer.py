"""
db_writer.py — asyncpg-based database writer for the satellite pipeline.

Handles:
  - Connection pool lifecycle (module-level singleton)
  - Querying active fields for the Celery dispatcher
  - Upserting zones and ndvi_timeseries rows in a single transaction
  - Writing agent traces
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from pipeline.indices import compute_mask_mean_scores
from pipeline.segmentation import ZoneMask

logger = logging.getLogger(__name__)

# Module-level pool — created once per worker process via get_pool().
_pool: asyncpg.Pool | None = None


# ─── Connection pool ─────────────────────────────────────────────────────────

async def get_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Return (creating if necessary) the module-level asyncpg connection pool.

    Args:
        dsn: PostgreSQL DSN. Defaults to settings.DATABASE_URL if not provided.
             asyncpg requires the postgresql:// scheme (not postgresql+asyncpg://).
    """
    global _pool
    if _pool is None or _pool._closed:  # type: ignore[attr-defined]
        if dsn is None:
            from app.config import settings

            dsn = settings.DATABASE_URL
        # Strip SQLAlchemy dialect prefix if present.
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        logger.info("asyncpg pool created")
    return _pool


# ─── Field queries ───────────────────────────────────────────────────────────

async def get_active_fields(pool: asyncpg.Pool) -> list[dict]:
    """Return all active fields as dicts with id and polygon_wkt."""
    rows = await pool.fetch(
        "SELECT id::text, ST_AsText(polygon) AS polygon_wkt FROM fields WHERE active = true"
    )
    return [dict(row) for row in rows]


async def get_field_polygon(pool: asyncpg.Pool, field_id: str) -> str | None:
    """Return the WKT polygon for a single field, or None if not found."""
    row = await pool.fetchrow(
        "SELECT ST_AsText(polygon) AS polygon_wkt FROM fields WHERE id = $1",
        uuid.UUID(field_id),
    )
    return row["polygon_wkt"] if row else None


# ─── Zone + timeseries upsert ────────────────────────────────────────────────

async def upsert_zones_and_scores(
    pool: asyncpg.Pool,
    field_id: str,
    zone_masks: list[ZoneMask],
    index_arrays: dict[str, object],
    captured_at: datetime,
) -> list[str]:
    """Insert zones and ndvi_timeseries rows for one pipeline run.

    Each pipeline run inserts a fresh set of zone rows (no spatial dedup —
    zones are immutable once written, and timeseries accumulates across runs).

    Args:
        pool: asyncpg connection pool.
        field_id: UUID string of the field being processed.
        zone_masks: Segmentation results from segmentation.segment_field().
        index_arrays: {"ndvi": ndarray, "ndwi": ndarray, "ndre": ndarray}
        captured_at: Timestamp to tag this batch of observations.

    Returns:
        List of zone_id strings that were inserted.
    """
    field_uuid = uuid.UUID(field_id)
    zone_ids: list[str] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for i, zm in enumerate(zone_masks):
                zone_id = uuid.uuid4()
                label = f"zone-{i}"

                await conn.execute(
                    """
                    INSERT INTO zones (id, field_id, polygon, label, created_at)
                    VALUES (
                        $1, $2,
                        ST_GeomFromText($3, 4326),
                        $4, $5
                    )
                    """,
                    zone_id,
                    field_uuid,
                    zm.polygon_wkt,
                    label,
                    captured_at,
                )

                scores = compute_mask_mean_scores(index_arrays, zm.mask)  # type: ignore[arg-type]

                await conn.execute(
                    """
                    INSERT INTO ndvi_timeseries (id, zone_id, ndvi, ndwi, ndre, captured_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.uuid4(),
                    zone_id,
                    scores["ndvi"],
                    scores["ndwi"],
                    scores["ndre"],
                    captured_at,
                )

                zone_ids.append(str(zone_id))
                logger.debug(
                    "Wrote zone %s (label=%s, ndvi=%.1f, ndwi=%.1f, ndre=%.1f)",
                    zone_id, label, scores["ndvi"], scores["ndwi"], scores["ndre"],
                )

    logger.info(
        "field=%s inserted %d zones at %s", field_id, len(zone_ids), captured_at.isoformat()
    )
    return zone_ids


# ─── Agent traces ────────────────────────────────────────────────────────────

async def write_agent_trace(
    pool: asyncpg.Pool,
    field_id: str,
    trace: dict,
) -> None:
    """Insert a single agent trace row."""
    await pool.execute(
        """
        INSERT INTO agent_traces (id, field_id, run_at, trace)
        VALUES ($1, $2, now(), $3)
        """,
        uuid.uuid4(),
        uuid.UUID(field_id),
        json.dumps(trace),
    )
