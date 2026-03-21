"""Database writer for the satellite pipeline.

Persists zone polygons and NDVI timeseries rows to the Supabase PostgreSQL DB
after each satellite pipeline run (real or mock).

This module is called by pipeline/tasks.py BEFORE the LangGraph agent runs,
so the agent always has fresh data to read from.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_SQL_UPSERT_ZONE = """
    INSERT INTO zones (id, field_id, polygon, label, created_at)
    VALUES ($1, $2, ST_GeomFromGeoJSON($3), $4, $5)
    ON CONFLICT (id) DO UPDATE
        SET polygon = EXCLUDED.polygon,
            label = EXCLUDED.label
    RETURNING id
"""

_SQL_INSERT_NDVI = """
    INSERT INTO ndvi_timeseries (zone_id, ndvi, ndwi, ndre, captured_at)
    VALUES ($1, $2, $3, $4, $5)
"""


async def write_zones_and_indices(
    conn_or_pool: asyncpg.Pool | asyncpg.Connection,
    field_id: str,
    zones_with_indices: list[dict[str, Any]],
    captured_at: datetime | None = None,
) -> list[str]:
    """Upsert zones and insert NDVI timeseries rows for a field.

    Args:
        conn_or_pool: asyncpg pool or connection.
        field_id: UUID string of the parent field.
        zones_with_indices: List of dicts:
            {
                "zone_id": str (optional — generated if absent),
                "label": str,
                "polygon": GeoJSON Polygon dict,
                "ndvi": float,
                "ndwi": float,
                "ndre": float,
            }
        captured_at: Timestamp for this observation (defaults to now UTC).

    Returns:
        List of zone_id strings that were written.
    """
    if captured_at is None:
        captured_at = datetime.now(tz=timezone.utc)

    field_uuid = uuid.UUID(field_id)
    zone_ids: list[str] = []

    if isinstance(conn_or_pool, asyncpg.Pool):
        async with conn_or_pool.acquire() as conn:
            return await _write(conn, field_uuid, zones_with_indices, captured_at, zone_ids)
    else:
        return await _write(conn_or_pool, field_uuid, zones_with_indices, captured_at, zone_ids)


async def _write(
    conn: asyncpg.Connection,
    field_uuid: uuid.UUID,
    zones: list[dict[str, Any]],
    captured_at: datetime,
    zone_ids: list[str],
) -> list[str]:
    async with conn.transaction():
        for zone in zones:
            zone_id_str = zone.get("zone_id") or str(uuid.uuid4())
            zone_uuid = uuid.UUID(zone_id_str)
            polygon_json = json.dumps(zone["polygon"]) if isinstance(zone["polygon"], dict) else zone["polygon"]

            await conn.fetchval(
                _SQL_UPSERT_ZONE,
                zone_uuid,
                field_uuid,
                polygon_json,
                str(zone.get("label", f"Zone {zone_id_str[:4]}")),
                captured_at,
            )

            await conn.execute(
                _SQL_INSERT_NDVI,
                zone_uuid,
                float(zone.get("ndvi", 0.0)),
                float(zone.get("ndwi", 0.0)),
                float(zone.get("ndre", 0.0)),
                captured_at,
            )
            zone_ids.append(zone_id_str)
            logger.debug(
                "Wrote zone %s (ndvi=%.3f) for field %s",
                zone_id_str,
                zone.get("ndvi", 0.0),
                field_uuid,
            )

    logger.info("Wrote %d zones for field %s", len(zone_ids), field_uuid)
    return zone_ids


async def seed_mock_data(
    conn_or_pool: asyncpg.Pool | asyncpg.Connection,
    field_id: str,
    fixture_path: Path | None = None,
) -> list[str]:
    """Seed the DB with mock NDVI data from fixtures/mock_zones.json.

    Writes multiple timestamped rows to simulate a 14-day historical series.

    Returns:
        List of zone_id strings written.
    """
    from datetime import timedelta

    if fixture_path is None:
        fixture_path = Path(__file__).parent / "fixtures" / "mock_zones.json"

    with open(fixture_path) as f:
        fixture = json.load(f)

    now = datetime.now(tz=timezone.utc)
    zone_ids: list[str] = []

    # Pre-assign stable zone UUIDs so timeseries rows link to same zones
    stable_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{field_id}:zone:{i}")) for i in range(len(fixture["zones"]))]

    for ts_index in range(len(fixture["zones"][0]["ndvi_timeseries"])):
        batch: list[dict[str, Any]] = []
        for i, zone in enumerate(fixture["zones"]):
            entry = zone["ndvi_timeseries"][ts_index]
            days_ago = entry.get("days_ago", 0)
            batch.append({
                "zone_id": stable_ids[i],
                "label": zone["label"],
                "polygon": zone["polygon"],
                "ndvi": entry["ndvi"],
                "ndwi": entry["ndwi"],
                "ndre": entry["ndre"],
            })
        ts = now - timedelta(days=batch[0].get("days_ago", 0))
        # Re-read days_ago per zone
        for j, zone in enumerate(fixture["zones"]):
            entry = zone["ndvi_timeseries"][ts_index]
            ts = now - timedelta(days=entry.get("days_ago", 0))
            single = [batch[j]]
            ids = await write_zones_and_indices(conn_or_pool, field_id, single, ts)
            if ids and ids[0] not in zone_ids:
                zone_ids.extend(ids)

    logger.info("Seeded mock data: %d zones for field %s", len(set(zone_ids)), field_id)
    return list(set(zone_ids))
