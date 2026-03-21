"""context_builder node — first node in the harvest-agent pipeline.

Responsibilities:
1. Query `fields` table for field metadata (lat, lon, crop_type, planting_date)
2. Query `zones` + `ndvi_timeseries` to build ZoneScore list, including
   ndvi_delta = (latest ndvi) − (ndvi ~7 days ago), defaulting to 0.0
3. Fetch 7-day weather forecast from Open-Meteo (no API key required)
4. Calculate days_since_planting from planting_date
5. Append entry to reasoning_trace

The node is async so it can be used with graph.ainvoke() from Celery via
asyncio.run().  DB access uses the asyncpg pool from app.database.
"""
from __future__ import annotations

import asyncio
from datetime import date, timezone

import asyncpg
import httpx

from app.agent.state import AgentState, ZoneScore
from app.config import settings


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

_SQL_FIELD = """
    SELECT
        id,
        crop_type,
        planting_date,
        ST_Y(ST_Centroid(polygon)) AS lat,
        ST_X(ST_Centroid(polygon)) AS lon
    FROM fields
    WHERE id = $1
"""

_SQL_ZONES_LATEST = """
    SELECT
        z.id         AS zone_id,
        z.label,
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
"""

_SQL_NDVI_7D = """
    SELECT ndvi
    FROM ndvi_timeseries
    WHERE zone_id = $1
    ORDER BY ABS(EXTRACT(EPOCH FROM (captured_at - (now() - INTERVAL '7 days'))))
    LIMIT 1
"""


# ---------------------------------------------------------------------------
# Weather fetch
# ---------------------------------------------------------------------------

async def _fetch_weather(lat: float, lon: float) -> dict:
    """Fetch 7-day forecast from Open-Meteo.  Returns raw JSON dict."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum,temperature_2m_min",
        "forecast_days": 7,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def context_builder(state: AgentState) -> AgentState:
    """Build full context from DB and weather API for the given field_id."""
    field_id: str = state["field_id"]

    # Lazily import pool — it may be initialised inside the Celery task runner
    # rather than via FastAPI lifespan, so we import at call-time.
    from app.database import pool as _pool

    if _pool is None:
        # Celery path: create a short-lived pool for this invocation
        conn_pool: asyncpg.Pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=3,
            command_timeout=30,
        )
        _own_pool = True
    else:
        conn_pool = _pool
        _own_pool = False

    try:
        async with conn_pool.acquire() as conn:
            # 1. Field metadata
            field_row = await conn.fetchrow(_SQL_FIELD, field_id)
            if field_row is None:
                raise ValueError(f"Field {field_id!r} not found in database")

            crop_type: str = field_row["crop_type"] or "unknown"
            planting_date_raw = field_row["planting_date"]  # may be datetime.date
            if isinstance(planting_date_raw, date):
                planting_date_str: str = planting_date_raw.isoformat()
            else:
                planting_date_str = str(planting_date_raw)

            field_lat: float = float(field_row["lat"])
            field_lon: float = float(field_row["lon"])

            # 2. days_since_planting
            today = date.today()
            planting_date_obj = date.fromisoformat(planting_date_str)
            days_since_planting: int = (today - planting_date_obj).days

            # 3. Zone scores
            zone_rows = await conn.fetch(_SQL_ZONES_LATEST, field_id)
            zones: list[ZoneScore] = []
            for row in zone_rows:
                zone_id: str = str(row["zone_id"])
                # Latest NDVI
                latest_ndvi: float = float(row["ndvi"]) if row["ndvi"] is not None else 0.0
                # NDVI from ~7 days ago
                prior_row = await conn.fetchrow(_SQL_NDVI_7D, row["zone_id"])
                prior_ndvi: float = float(prior_row["ndvi"]) if (prior_row and prior_row["ndvi"] is not None) else 0.0
                ndvi_delta: float = round(latest_ndvi - prior_ndvi, 6)

                captured_at = row["captured_at"]
                # Ensure ISO string (no datetime objects in state)
                if hasattr(captured_at, "isoformat"):
                    captured_at_str: str = captured_at.isoformat()
                else:
                    captured_at_str = str(captured_at)

                zones.append(ZoneScore(
                    zone_id=zone_id,
                    label=str(row["label"]),
                    ndvi=float(row["ndvi"]) if row["ndvi"] is not None else 0.0,
                    ndwi=float(row["ndwi"]) if row["ndwi"] is not None else 0.0,
                    ndre=float(row["ndre"]) if row["ndre"] is not None else 0.0,
                    ndvi_delta=ndvi_delta,
                    captured_at=captured_at_str,
                ))
    finally:
        if _own_pool:
            await conn_pool.close()

    # 4. Weather forecast
    weather_forecast: dict = await _fetch_weather(field_lat, field_lon)

    # 5. Trace entry — inputs/outputs must be JSON-serializable
    trace_entry: dict = {
        "node_name": "context_builder",
        "inputs": {"field_id": field_id},
        "outputs": {
            "field_lat": field_lat,
            "field_lon": field_lon,
            "crop_type": crop_type,
            "planting_date": planting_date_str,
            "days_since_planting": days_since_planting,
            "zone_count": len(zones),
            "weather_days": len(weather_forecast.get("daily", {}).get("time", [])),
        },
    }

    return {
        **state,
        "field_lat": field_lat,
        "field_lon": field_lon,
        "crop_type": crop_type,
        "planting_date": planting_date_str,
        "days_since_planting": days_since_planting,
        "zones": zones,
        "weather_forecast": weather_forecast,
        "reasoning_trace": [*state.get("reasoning_trace", []), trace_entry],
    }
