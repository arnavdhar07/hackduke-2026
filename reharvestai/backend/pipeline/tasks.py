"""
tasks.py — Celery tasks for the ReHarvestAI satellite pipeline.

Task graph:
  dispatch_active_fields   (beat, every 5 days)
      └─► run_field_analysis(field_id)     (one per active field)
              └─► run_harvest_agent(field_id)  (Person 2 fills in body)
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="pipeline.dispatch_active_fields")
def dispatch_active_fields(self) -> dict:
    """Query all active fields and fan out run_field_analysis for each."""
    from pipeline.db_writer import get_active_fields

    async def _run():
        import asyncpg
        from app.config import settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        try:
            return await get_active_fields(pool)
        finally:
            await pool.close()

    fields = asyncio.run(_run())
    logger.info("Dispatching analysis for %d active fields", len(fields))

    for field in fields:
        run_field_analysis.delay(field["id"])

    return {"dispatched": len(fields)}


# ─── Main pipeline task ───────────────────────────────────────────────────────

@celery_app.task(bind=True, name="pipeline.run_field_analysis", max_retries=3)
def run_field_analysis(self, field_id: str) -> dict:
    """Run the full satellite pipeline for one field.

    All async DB operations are collected into a single asyncio.run() call
    so they share one event loop and one connection pool.

    Steps:
      1. Fetch field polygon from DB.
      2. Fetch Sentinel-2 band GeoTIFFs (real or synthetic).
      3. Clip bands to field polygon.
      4. Compute NDVI/NDWI/NDRE per pixel.
      5. Segment field into zones with SAM3.
      6. Compute per-zone mean scores and write to DB.
      7. Signal the AI agent task.

    Returns:
        {"field_id": str, "zones_written": int, "captured_at": str}
    """
    from app.config import settings
    from pipeline import raster, sentinel
    from pipeline.db_writer import get_field_polygon, upsert_zones_and_scores
    from pipeline.indices import compute_pixel_indices
    from pipeline.segmentation import segment_field

    try:
        # ── All async DB work in one event loop ──────────────────────────────
        async def _run_async():
            import asyncpg
            dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
            try:
                polygon_wkt = await get_field_polygon(pool, field_id)
                if polygon_wkt is None:
                    return None, None

                bbox = raster.bbox_from_polygon(polygon_wkt)
                date_range = sentinel.build_date_range(settings.SENTINEL_LOOKBACK_DAYS)

                # ── 2–5: sync pipeline steps (CPU-bound) ─────────────────────
                with tempfile.TemporaryDirectory(prefix="reharvest_") as tmp:
                    band_dir = Path(tmp) / field_id
                    band_dir.mkdir()

                    sentinel.fetch_field_imagery(
                        field_id=field_id,
                        bbox=bbox,
                        date_range=date_range,
                        output_dir=band_dir,
                        max_cloud_pct=settings.SENTINEL_MAX_CLOUD_PCT,
                    )
                    band_arrays, meta = raster.load_and_clip(band_dir, polygon_wkt)
                    index_arrays = compute_pixel_indices(band_arrays)
                    zones = segment_field(
                        band_arrays=band_arrays,
                        transform=meta["transform"],
                        src_crs=meta["crs"],
                        field_polygon_wkt=polygon_wkt,
                    )

                    # ── 6: write results ──────────────────────────────────────
                    captured_at = datetime.now(tz=timezone.utc)
                    zone_ids = await upsert_zones_and_scores(
                        pool=pool,
                        field_id=field_id,
                        zone_masks=zones,
                        index_arrays=index_arrays,
                        captured_at=captured_at,
                    )

                return zone_ids, captured_at
            finally:
                await pool.close()

        zone_ids, captured_at = asyncio.run(_run_async())

        if zone_ids is None:
            logger.error("field=%s not found in DB", field_id)
            return {"error": f"field {field_id} not found"}

        # ── 7. Trigger AI agent ───────────────────────────────────────────────
        run_harvest_agent.delay(field_id)

        result = {
            "field_id": field_id,
            "zones_written": len(zone_ids),
            "captured_at": captured_at.isoformat(),
        }
        logger.info("run_field_analysis complete: %s", result)
        return result

    except Exception as exc:
        countdown = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
        logger.warning(
            "field=%s pipeline failed (attempt %d): %s — retrying in %ds",
            field_id, self.request.retries + 1, exc, countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)


# ─── AI agent task (stub for Person 2) ───────────────────────────────────────

@celery_app.task(bind=True, name="pipeline.run_harvest_agent", max_retries=2)
def run_harvest_agent(self, field_id: str) -> None:
    """Trigger the AI agent after a pipeline run completes.

    Person 2 implements the body of this task. The signature is fixed:
    it receives a field_id (str UUID) and should query the DB for latest
    zone scores, run the LangGraph agent, and write recommendations/alerts.
    """
    pass
