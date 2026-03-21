"""synthetic_pipeline.py — seeds fake zone + NDVI data then runs the AI agent.

Called as a FastAPI BackgroundTask immediately after POST /fields so that the
dashboard shows recommendations without needing Celery or real satellite imagery.

Zone layout: 2×2 grid of the field bbox, matching the frontend mock profiles.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from app import database

logger = logging.getLogger("api.synthetic_pipeline")

# NDVI/NDWI/NDRE profiles matching the frontend mock zones
_ZONE_PROFILES = [
    {"label": "Zone A", "ndvi": 88.0, "ndwi": 72.0, "ndre": 81.0,
     "trend": [30, 52, 71, 85, 88]},   # NW — healthy
    {"label": "Zone B", "ndvi": 71.0, "ndwi": 58.0, "ndre": 65.0,
     "trend": [28, 45, 60, 68, 71]},   # NE — watch
    {"label": "Zone C", "ndvi": 48.0, "ndwi": 35.0, "ndre": 42.0,
     "trend": [25, 38, 44, 47, 48]},   # SW — stressed
    {"label": "Zone D", "ndvi": 22.0, "ndwi": 14.0, "ndre": 18.0,
     "trend": [55, 48, 35, 28, 22]},   # SE — critical
]


async def run_synthetic_pipeline(field_id: str) -> None:
    """Seed zones + NDVI timeseries, then run the LangGraph agent."""
    logger.info("synthetic_pipeline: starting for field %s", field_id)

    try:
        await _seed_zones(field_id)
    except Exception as exc:
        logger.error("synthetic_pipeline: zone seeding failed for %s: %s", field_id, exc)
        return

    try:
        from app.agent.graph import build_graph
        from app.agent.state import AgentState

        graph = build_graph()
        initial_state: AgentState = {
            "field_id": field_id,
            "field_lat": 0.0,
            "field_lon": 0.0,
            "crop_type": "",
            "planting_date": "",
            "days_since_planting": 0,
            "zones": [],
            "weather_forecast": {},
            "zone_classifications": [],
            "recommendations": [],
            "reasoning_trace": [],
        }
        final_state: AgentState = await graph.ainvoke(initial_state)
        recs = final_state.get("recommendations", [])
        logger.info(
            "synthetic_pipeline: agent done for field %s — %d recommendations",
            field_id, len(recs),
        )
    except Exception as exc:
        logger.error("synthetic_pipeline: agent failed for %s: %s", field_id, exc)


async def _seed_zones(field_id: str) -> None:
    """Create 4 quadrant zones + 5-point NDVI timeseries from the field bbox."""
    pool = await database.get_pool()
    field_uuid = uuid.UUID(field_id)

    # Fetch bbox of the field polygon
    row = await pool.fetchrow(
        """
        SELECT
            ST_XMin(ST_Envelope(polygon)) AS min_lng,
            ST_XMax(ST_Envelope(polygon)) AS max_lng,
            ST_YMin(ST_Envelope(polygon)) AS min_lat,
            ST_YMax(ST_Envelope(polygon)) AS max_lat
        FROM fields WHERE id = $1
        """,
        field_uuid,
    )
    if row is None:
        raise ValueError(f"Field {field_id} not found")

    min_lng = float(row["min_lng"])
    max_lng = float(row["max_lng"])
    min_lat = float(row["min_lat"])
    max_lat = float(row["max_lat"])
    mid_lng = (min_lng + max_lng) / 2
    mid_lat = (min_lat + max_lat) / 2

    # 2×2 grid: (w, s, e, n) for each quadrant
    quads = [
        (min_lng, mid_lat, mid_lng, max_lat),   # NW → Zone A
        (mid_lng, mid_lat, max_lng, max_lat),   # NE → Zone B
        (min_lng, min_lat, mid_lng, mid_lat),   # SW → Zone C
        (mid_lng, min_lat, max_lng, mid_lat),   # SE → Zone D
    ]

    now = datetime.now(tz=timezone.utc)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for i, (w, s, e, n) in enumerate(quads):
                profile = _ZONE_PROFILES[i]
                zone_id = uuid.uuid4()
                wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

                await conn.execute(
                    """
                    INSERT INTO zones (id, field_id, polygon, label, created_at)
                    VALUES ($1, $2, ST_GeomFromText($3, 4326), $4, $5)
                    """,
                    zone_id, field_uuid, wkt, profile["label"], now,
                )

                # 5 timeseries points, spaced 10 days apart, ending now
                trend: list[int] = profile["trend"]
                ndwi_ratio = profile["ndwi"] / profile["ndvi"]
                ndre_ratio = profile["ndre"] / profile["ndvi"]
                for j, ndvi_val in enumerate(trend):
                    captured_at = now - timedelta(days=(len(trend) - 1 - j) * 10)
                    await conn.execute(
                        """
                        INSERT INTO ndvi_timeseries (id, zone_id, ndvi, ndwi, ndre, captured_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        uuid.uuid4(),
                        zone_id,
                        float(ndvi_val),
                        round(ndvi_val * ndwi_ratio, 2),
                        round(ndvi_val * ndre_ratio, 2),
                        captured_at,
                    )

    logger.info("synthetic_pipeline: seeded 4 zones for field %s", field_id)
