from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException

from app import database
from app.redis import get_redis
from app.models.field import GeoJSON, ZoneResponse, ZoneScore

router = APIRouter(tags=["zones"])

_CACHE_TTL = 3600  # seconds


# ---------------------------------------------------------------------------
# GET /fields/{field_id}/zones
# ---------------------------------------------------------------------------

@router.get("/fields/{field_id}/zones", response_model=list[ZoneResponse])
async def get_zones(field_id: uuid.UUID) -> list[ZoneResponse]:
    """Return zones with latest NDVI scores and 14-point timeseries.

    Strategy: check Redis cache first; on miss, query DB and populate cache.
    """
    field_id_str = str(field_id)
    cache_key = f"zone_scores:{field_id_str}"

    # ── Cache read ──────────────────────────────────────────────────────────
    try:
        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached:
            raw_list: list[dict] = json.loads(cached)
            return [ZoneResponse.model_validate(z) for z in raw_list]
    except RuntimeError:
        # Redis not available — skip cache, fall through to DB
        redis = None  # type: ignore[assignment]
        cached = None

    # ── DB query ────────────────────────────────────────────────────────────
    zones = await _get_zones_from_db(field_id)

    # ── Cache write ─────────────────────────────────────────────────────────
    if redis is not None and zones:
        try:
            payload = json.dumps(
                [z.model_dump() for z in zones],
                default=_json_default,
            )
            await redis.setex(cache_key, _CACHE_TTL, payload)
        except Exception:
            pass  # best-effort cache write — don't fail the request

    return zones


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

async def _get_zones_from_db(field_id: uuid.UUID) -> list[ZoneResponse]:
    """Query zones + latest NDVI score + timeseries from PostgreSQL."""
    pool = await database.get_pool()

    # ── Step 1: zones + latest score via LATERAL join ──────────────────────
    try:
        rows = await pool.fetch(
            """
            SELECT
                z.id,
                z.field_id,
                z.label,
                ST_AsGeoJSON(z.polygon)::json AS polygon,
                n.ndvi,
                n.ndwi,
                n.ndre,
                n.captured_at
            FROM zones z
            JOIN LATERAL (
                SELECT ndvi, ndwi, ndre, captured_at
                FROM ndvi_timeseries
                WHERE zone_id = z.id
                ORDER BY captured_at DESC
                LIMIT 1
            ) n ON true
            WHERE z.field_id = $1
            ORDER BY z.created_at
            """,
            field_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch zones")

    if not rows:
        return []

    # ── Step 2: timeseries per zone ─────────────────────────────────────────
    results: list[ZoneResponse] = []
    for row in rows:
        r = dict(row)
        zone_id: uuid.UUID = r["id"]

        try:
            ts_rows = await pool.fetch(
                """
                SELECT ndvi, ndwi, ndre, captured_at
                FROM ndvi_timeseries
                WHERE zone_id = $1
                ORDER BY captured_at DESC
                LIMIT 14
                """,
                zone_id,
            )
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to fetch zone timeseries")

        latest = ZoneScore(
            ndvi=r["ndvi"],
            ndwi=r["ndwi"],
            ndre=r["ndre"],
            captured_at=r["captured_at"].isoformat() if hasattr(r["captured_at"], "isoformat") else str(r["captured_at"]),
        )

        timeseries = [
            ZoneScore(
                ndvi=dict(ts)["ndvi"],
                ndwi=dict(ts)["ndwi"],
                ndre=dict(ts)["ndre"],
                captured_at=(
                    dict(ts)["captured_at"].isoformat()
                    if hasattr(dict(ts)["captured_at"], "isoformat")
                    else str(dict(ts)["captured_at"])
                ),
            )
            for ts in ts_rows
        ]

        polygon_raw = r["polygon"]
        if isinstance(polygon_raw, str):
            polygon_raw = json.loads(polygon_raw)

        results.append(
            ZoneResponse(
                id=zone_id,
                field_id=r["field_id"],
                label=r["label"],
                polygon=GeoJSON(**polygon_raw),
                latest_scores=latest,
                timeseries=timeseries,
            )
        )

    return results


def _json_default(obj: object) -> str:
    """Fallback JSON serialiser for uuid.UUID and datetime objects."""
    import datetime
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")
