"""synthetic_pipeline.py — seeds organic health zones + NDVI data then runs the AI agent.

Called as a FastAPI BackgroundTask immediately after POST /fields.

Zone creation:
  1. Fetch real Sentinel-2 L2A bands via Element84 STAC (no auth).
  2. Clip to field polygon, compute 7 vegetation indices per pixel.
  3. Compute composite health score (NDVI 35% + NDRE 30% + CIg 20% + NDWI 15%).
  4. Quantise into health bands, find connected components → organic zone polygons.
  5. Each zone gets mean metrics from its pixel region.

Fallback (satellite unavailable):
  Generate seeded synthetic health score array, derive synthetic per-pixel index
  arrays from it, then run the same organic segmentation pipeline.
"""
from __future__ import annotations

import json as _json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app import database

logger = logging.getLogger("api.synthetic_pipeline")


async def run_synthetic_pipeline(field_id: str) -> None:
    """Seed organic zones + timeseries, then run the LangGraph agent."""
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
            "days_since_satellite_pass": 0,
            "growth_stage": "",
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
    """Segment field into organic health zones and seed timeseries data."""
    import tempfile
    from pathlib import Path

    pool = await database.get_pool()
    field_uuid = uuid.UUID(field_id)

    # ── Fetch bbox + polygon from DB ──────────────────────────────────────────
    row = await pool.fetchrow(
        """
        SELECT
            ST_XMin(ST_Envelope(polygon)) AS min_lng,
            ST_XMax(ST_Envelope(polygon)) AS max_lng,
            ST_YMin(ST_Envelope(polygon)) AS min_lat,
            ST_YMax(ST_Envelope(polygon)) AS max_lat,
            ST_AsText(polygon) AS polygon_wkt
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
    polygon_wkt: str = row["polygon_wkt"]
    bbox = (min_lng, min_lat, max_lng, max_lat)

    # ── Attempt real Sentinel-2 fetch ─────────────────────────────────────────
    use_real = False
    index_arrays: dict | None = None

    try:
        from pipeline.stac_sentinel import fetch_sentinel2_bands
        from pipeline.raster import load_and_clip
        from pipeline.indices import compute_pixel_indices
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            band_dir = fetch_sentinel2_bands(bbox, Path(tmpdir))
            if band_dir is not None:
                band_arrays, _meta = load_and_clip(band_dir, polygon_wkt)
                raw_indices = compute_pixel_indices(band_arrays)
                # Force-copy so arrays survive tempdir cleanup
                index_arrays = {k: np.array(v) for k, v in raw_indices.items()}
                use_real = True
                logger.info("synthetic_pipeline: using real Sentinel-2 data for field %s", field_id)
            else:
                logger.info("synthetic_pipeline: no Sentinel-2 scene, using synthetic for %s", field_id)
    except Exception as exc:
        logger.warning(
            "synthetic_pipeline: Sentinel-2 fetch failed for %s (%s), using synthetic",
            field_id, exc,
        )
        use_real = False

    # ── Build health score + index arrays ─────────────────────────────────────
    from pipeline.heatmap_generator import (
        compute_health_score,
        generate_synthetic_health_score,
        generate_synthetic_index_arrays,
        segment_health_zones,
        generate_heatmap_from_health_score,
    )

    if use_real and index_arrays is not None:
        health_score = compute_health_score(index_arrays)
    else:
        # Generate at display resolution (256) so segmentation and heatmap
        # use the SAME spatial pattern — eliminates border mismatch.
        health_score = generate_synthetic_health_score(field_id, size=256)
        index_arrays = generate_synthetic_index_arrays(health_score, field_id)

    # ── Organic segmentation ──────────────────────────────────────────────────
    zone_segments = segment_health_zones(health_score, index_arrays, polygon_wkt, bbox)
    logger.info(
        "synthetic_pipeline: %d organic zones for field %s",
        len(zone_segments), field_id,
    )

    now = datetime.now(tz=timezone.utc)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for seg in zone_segments:
                zone_id = uuid.uuid4()
                m = seg["metrics"]

                ndvi_val  = float(m.get("ndvi",  0.0))
                ndwi_val  = float(m.get("ndwi",  0.0))
                ndre_val  = float(m.get("ndre",  0.0))
                evi_val   = float(m.get("evi",   0.0))
                gndvi_val = float(m.get("gndvi", 0.0))
                savi_val  = float(m.get("savi",  0.0))
                cig_val   = float(m.get("cig",   0.0))

                await conn.execute(
                    """
                    INSERT INTO zones (id, field_id, polygon, label, created_at)
                    VALUES ($1, $2, ST_GeomFromText($3, 4326), $4, $5)
                    """,
                    zone_id, field_uuid, seg["polygon_wkt"], seg["label"], now,
                )

                # Historical point (10 days ago) — 5% higher to give agent plausible delta
                await conn.execute(
                    """
                    INSERT INTO ndvi_timeseries
                        (id, zone_id, ndvi, ndwi, ndre, evi, gndvi, savi, cig, captured_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    uuid.uuid4(), zone_id,
                    round(min(100.0, ndvi_val  * 1.05), 2),
                    round(min(100.0, ndwi_val  * 1.05), 2),
                    round(min(100.0, ndre_val  * 1.05), 2),
                    round(min(100.0, evi_val   * 1.05), 2),
                    round(min(100.0, gndvi_val * 1.05), 2),
                    round(min(100.0, savi_val  * 1.05), 2),
                    round(min(100.0, cig_val   * 1.05), 2),
                    now - timedelta(days=10),
                )

                # Current point
                await conn.execute(
                    """
                    INSERT INTO ndvi_timeseries
                        (id, zone_id, ndvi, ndwi, ndre, evi, gndvi, savi, cig, captured_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    uuid.uuid4(), zone_id,
                    round(ndvi_val,  2),
                    round(ndwi_val,  2),
                    round(ndre_val,  2),
                    round(evi_val,   2),
                    round(gndvi_val, 2),
                    round(savi_val,  2),
                    round(cig_val,   2),
                    now,
                )

    # ── Generate + cache heatmap while arrays are still in memory ─────────────
    # Use the same health_score array that drove segmentation → color regions
    # align exactly with zone polygon edges.
    try:
        source = "sentinel2" if use_real else "synthetic"
        heatmap_result = generate_heatmap_from_health_score(
            health_score, polygon_wkt, bbox, source=source
        )

        try:
            from app.redis import get_redis
            redis = get_redis()
            await redis.setex(f"heatmap:{field_id}", 3600, _json.dumps(heatmap_result))
            logger.info(
                "synthetic_pipeline: cached %s heatmap for field %s",
                heatmap_result["source"], field_id,
            )
        except Exception as exc:
            logger.warning("synthetic_pipeline: heatmap cache failed for %s: %s", field_id, exc)
    except Exception as exc:
        logger.warning("synthetic_pipeline: heatmap generation failed for %s: %s", field_id, exc)

    data_source = "real Sentinel-2" if use_real else "synthetic"
    logger.info(
        "synthetic_pipeline: done — %d organic zones for field %s (%s)",
        len(zone_segments), field_id, data_source,
    )
