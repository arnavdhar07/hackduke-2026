"""synthetic_pipeline.py — seeds zone + NDVI data (from real Sentinel-2 or fallback) then runs the AI agent.

Called as a FastAPI BackgroundTask immediately after POST /fields so that the
dashboard shows recommendations without needing Celery or real satellite imagery.

Zone layout: 2×2 grid of the field bbox, matching the frontend mock profiles.

Real data path:
  1. Fetch real Sentinel-2 L2A bands via Element84 Earth Search STAC (no auth).
  2. Clip bands to the field polygon with pipeline.raster.load_and_clip.
  3. Compute NDVI/NDWI/NDRE per pixel with pipeline.indices.compute_pixel_indices.
  4. Average each index over the quadrant pixel mask.

Fallback path (any step above fails):
  Use the field_id-seeded deterministic values from _get_zone_profiles.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app import database

logger = logging.getLogger("api.synthetic_pipeline")

# Per-zone NDVI/NDWI/NDRE ranges: (min, max) — seed interpolates within these.
_ZONE_RANGES = [
    {"ndvi": (80, 92), "ndwi": (65, 78), "ndre": (74, 86)},   # Zone A
    {"ndvi": (62, 76), "ndwi": (48, 64), "ndre": (58, 70)},   # Zone B
    {"ndvi": (38, 54), "ndwi": (28, 42), "ndre": (34, 50)},   # Zone C
    {"ndvi": (14, 28), "ndwi": (9,  20), "ndre": (12, 24)},   # Zone D
]

# Base profiles used only to derive the trend scale factor in _get_zone_profiles.
_ZONE_PROFILES_BASE = [
    {"label": "Zone A", "ndvi": 88.0, "ndwi": 72.0, "ndre": 81.0,
     "trend": [30, 52, 71, 85, 88]},   # NW — healthy
    {"label": "Zone B", "ndvi": 71.0, "ndwi": 58.0, "ndre": 65.0,
     "trend": [28, 45, 60, 68, 71]},   # NE — watch
    {"label": "Zone C", "ndvi": 48.0, "ndwi": 35.0, "ndre": 42.0,
     "trend": [25, 38, 44, 47, 48]},   # SW — stressed
    {"label": "Zone D", "ndvi": 22.0, "ndwi": 14.0, "ndre": 18.0,
     "trend": [62, 55, 42, 32, 22]},   # SE — critical
]


def _field_seed_factor(field_id: str) -> float:
    """Return a 0.0–1.0 interpolation factor derived deterministically from field_id."""
    seed_int = int(hashlib.md5(field_id.encode()).hexdigest()[:8], 16) % 100
    return seed_int / 99.0


def _get_zone_profiles(field_id: str) -> list[dict]:
    """Build per-field zone profiles by interpolating within agronomic ranges."""
    t = _field_seed_factor(field_id)
    profiles = []
    for base, ranges in zip(_ZONE_PROFILES_BASE, _ZONE_RANGES):
        ndvi = ranges["ndvi"][0] + t * (ranges["ndvi"][1] - ranges["ndvi"][0])
        ndwi = ranges["ndwi"][0] + t * (ranges["ndwi"][1] - ranges["ndwi"][0])
        ndre = ranges["ndre"][0] + t * (ranges["ndre"][1] - ranges["ndre"][0])
        orig_final_ndvi = base["trend"][-1]
        scale = ndvi / orig_final_ndvi if orig_final_ndvi != 0 else 1.0
        trend = [round(v * scale) for v in base["trend"]]
        profiles.append({
            "label": base["label"],
            "ndvi": ndvi,
            "ndwi": ndwi,
            "ndre": ndre,
            "trend": trend,
        })
    return profiles


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
            "days_since_satellite_pass": 0,
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
    """Create 4 quadrant zones + 2-point NDVI timeseries from real or seeded data."""
    import tempfile
    from pathlib import Path

    import numpy as np

    pool = await database.get_pool()
    field_uuid = uuid.UUID(field_id)

    # Fetch bbox AND full polygon WKT in one query.
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

    mid_lng = (min_lng + max_lng) / 2
    mid_lat = (min_lat + max_lat) / 2

    # 2×2 grid: (w, s, e, n) for each quadrant
    quads = [
        (min_lng, mid_lat, mid_lng, max_lat),   # NW → Zone A
        (mid_lng, mid_lat, max_lng, max_lat),   # NE → Zone B
        (min_lng, min_lat, mid_lng, mid_lat),   # SW → Zone C
        (mid_lng, min_lat, max_lng, mid_lat),   # SE → Zone D
    ]

    # ── Attempt real Sentinel-2 fetch ─────────────────────────────────────────
    use_real = False
    band_arrays: dict | None = None
    index_arrays: dict | None = None
    meta: dict | None = None

    try:
        from pipeline.stac_sentinel import fetch_sentinel2_bands
        from pipeline.raster import load_and_clip
        from pipeline.indices import compute_pixel_indices

        with tempfile.TemporaryDirectory() as tmpdir:
            band_dir = fetch_sentinel2_bands(bbox, Path(tmpdir))
            if band_dir is not None:
                band_arrays, meta = load_and_clip(band_dir, polygon_wkt)
                index_arrays = compute_pixel_indices(band_arrays)
                use_real = True
                logger.info("synthetic_pipeline: using real Sentinel-2 data for field %s", field_id)
            else:
                logger.info("synthetic_pipeline: no Sentinel-2 scene found, using seeded values for field %s", field_id)
    except Exception as exc:
        logger.warning(
            "synthetic_pipeline: real data fetch failed for field %s (%s), falling back to seeded values",
            field_id, exc,
        )
        use_real = False

    # ── Seeded fallback profiles (always computed; used when use_real is False) ──
    zone_profiles = _get_zone_profiles(field_id)

    now = datetime.now(tz=timezone.utc)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for i, (w, s, e, n) in enumerate(quads):
                profile = zone_profiles[i]
                zone_id = uuid.uuid4()
                quad_wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

                # Clip the quadrant rectangle to the actual drawn field polygon.
                geom_row = await conn.fetchrow(
                    """
                    SELECT
                        ST_AsText(ST_Intersection(
                            (SELECT polygon FROM fields WHERE id = $1),
                            ST_GeomFromText($2, 4326)
                        )) AS geom,
                        ST_IsEmpty(ST_Intersection(
                            (SELECT polygon FROM fields WHERE id = $1),
                            ST_GeomFromText($2, 4326)
                        )) AS is_empty
                    """,
                    field_uuid, quad_wkt,
                )
                if geom_row is None or geom_row["is_empty"]:
                    logger.info("synthetic_pipeline: quad %d empty intersection, skipping", i)
                    continue

                await conn.execute(
                    """
                    INSERT INTO zones (id, field_id, polygon, label, created_at)
                    VALUES ($1, $2, ST_GeomFromText($3, 4326), $4, $5)
                    """,
                    zone_id, field_uuid, geom_row["geom"], profile["label"], now,
                )

                # ── Compute current index values ──────────────────────────────
                if use_real and index_arrays is not None and meta is not None and band_arrays is not None:
                    try:
                        import rasterio.transform as rio_transform

                        H, W = next(iter(band_arrays.values())).shape
                        transform = meta["transform"]

                        # Map quadrant bbox corners to pixel coordinates.
                        r1, c1 = rio_transform.rowcol(transform, w, n)  # top-left
                        r2, c2 = rio_transform.rowcol(transform, e, s)  # bottom-right

                        # Clamp to valid raster extent.
                        row_min = max(0, min(r1, r2))
                        row_max = min(H, max(r1, r2))
                        col_min = max(0, min(c1, c2))
                        col_max = min(W, max(c1, c2))

                        mask = np.zeros((H, W), dtype=bool)
                        if row_max > row_min and col_max > col_min:
                            mask[row_min:row_max, col_min:col_max] = True

                        from pipeline.indices import compute_mask_mean_scores
                        scores = compute_mask_mean_scores(index_arrays, mask)

                        ndvi_val = scores["ndvi"]
                        ndwi_val = scores["ndwi"]
                        ndre_val = scores["ndre"]
                    except Exception as exc:
                        logger.warning(
                            "synthetic_pipeline: mask scoring failed for quad %d field %s (%s), using seeded",
                            i, field_id, exc,
                        )
                        ndvi_val = profile["ndvi"]
                        ndwi_val = profile["ndwi"]
                        ndre_val = profile["ndre"]
                else:
                    ndvi_val = profile["ndvi"]
                    ndwi_val = profile["ndwi"]
                    ndre_val = profile["ndre"]

                # ── Insert 2 timeseries points ────────────────────────────────
                # Point 1 (historical, 10 days ago): slightly higher values to give
                # the agent a plausible ndvi_delta (positive = recovering,
                # negative = declining).
                historical_ndvi = min(100.0, ndvi_val * 1.05)
                historical_ndwi = min(100.0, ndwi_val * 1.05)
                historical_ndre = min(100.0, ndre_val * 1.05)

                await conn.execute(
                    """
                    INSERT INTO ndvi_timeseries (id, zone_id, ndvi, ndwi, ndre, captured_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.uuid4(),
                    zone_id,
                    round(historical_ndvi, 2),
                    round(historical_ndwi, 2),
                    round(historical_ndre, 2),
                    now - timedelta(days=10),
                )

                # Point 2 (current / today).
                await conn.execute(
                    """
                    INSERT INTO ndvi_timeseries (id, zone_id, ndvi, ndwi, ndre, captured_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.uuid4(),
                    zone_id,
                    round(float(ndvi_val), 2),
                    round(float(ndwi_val), 2),
                    round(float(ndre_val), 2),
                    now,
                )

    data_source = "real Sentinel-2" if use_real else "seeded"
    logger.info(
        "synthetic_pipeline: seeded 4 zones for field %s using %s data",
        field_id, data_source,
    )
