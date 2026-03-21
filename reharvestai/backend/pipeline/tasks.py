"""Celery tasks for ReHarvestAI backend pipeline.

run_harvest_agent(field_id):
    Bootstraps an asyncpg pool (since FastAPI lifespan is not running in Celery),
    invokes the LangGraph harvest pipeline via asyncio.run(), then tears down
    the pool.  The task is idempotent — safe to retry.
"""
from __future__ import annotations

import asyncio
import logging

from pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_harvest_agent(self, field_id: str) -> dict:
    """Trigger the full LangGraph harvest-recommendation pipeline for a field.

    Args:
        field_id: UUID string of the field to run the agent against.

    Returns:
        A JSON-serializable summary dict with recommendation and alert counts.
    """
    try:
        result = asyncio.run(_run_pipeline(field_id))
        return result
    except Exception as exc:
        logger.exception("run_harvest_agent failed for field_id=%s: %s", field_id, exc)
        raise self.retry(exc=exc)


async def _run_pipeline(field_id: str) -> dict:
    """Async implementation — runs in a fresh event loop via asyncio.run()."""
    # Import here to avoid circular imports at module load time
    import app.database as db_module
    from app.agent.graph import build_graph
    from app.agent.state import AgentState
    from app.config import settings

    # Initialise a short-lived DB pool for this Celery worker invocation.
    # FastAPI lifespan is not running here, so we must set up our own pool.
    await db_module.init_db_pool()

    try:
        pool = await db_module.get_pool()

        # ── Satellite pipeline step ────────────────────────────────────────
        # Populate zones + NDVI timeseries before the agent reads them.
        if settings.use_mock_satellite:
            logger.info("Mock satellite mode — seeding fixture data for field %s", field_id)
            from pipeline.db_writer import seed_mock_data
            await seed_mock_data(pool, field_id)
        else:
            # Real Sentinel-2 pipeline
            try:
                from pipeline.sentinel import fetch_sentinel_scene
                from pipeline.raster import clip_and_extract_bands
                from pipeline.indices import compute_indices
                from pipeline.segmentation import segment_field
                from pipeline.db_writer import write_zones_and_indices

                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT ST_AsGeoJSON(polygon)::json AS polygon FROM fields WHERE id=$1",
                        field_id,
                    )
                if row is None:
                    raise ValueError(f"Field {field_id} not found")
                field_polygon = row["polygon"]

                scene_path = fetch_sentinel_scene(field_polygon)
                bands = clip_and_extract_bands(scene_path, field_polygon)
                ndvi_array, indices_list = compute_indices(bands)
                zones = segment_field(field_polygon, ndvi_array)
                for z, idx in zip(zones, indices_list):
                    z.update(idx)
                await write_zones_and_indices(pool, field_id, zones)
            except Exception as exc:
                logger.warning("Real pipeline failed (%s) — falling back to mock", exc)
                from pipeline.db_writer import seed_mock_data
                await seed_mock_data(pool, field_id)

        # ── LangGraph agent ────────────────────────────────────────────────
        graph = build_graph()

        # Minimal initial state — context_builder will fill the rest
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

        recommendations = final_state.get("recommendations", [])
        critical_count = sum(
            1 for r in recommendations if r.get("urgency") == "critical"
        )

        logger.info(
            "run_harvest_agent completed for field_id=%s: "
            "%d recommendations, %d critical alerts",
            field_id,
            len(recommendations),
            critical_count,
        )

        return {
            "field_id": field_id,
            "recommendation_count": len(recommendations),
            "critical_alert_count": critical_count,
        }

    finally:
        # Always close the pool we opened, even if the pipeline raises
        await db_module.close_db_pool()
