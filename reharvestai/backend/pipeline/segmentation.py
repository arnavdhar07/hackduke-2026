"""Field zone segmentation using SAM2 (Meta) or bbox-derived mock zones.

In REAL mode (USE_MOCK_SATELLITE=False):
  - Uses the SAM2 model to segment the NDVI raster into distinct crop zones.
  - Requires GPU (or slow CPU inference) and SAM2 installed.

In MOCK mode (USE_MOCK_SATELLITE=True) or on SAM2 import failure:
  - Divides the field bounding box into N equal horizontal strips.
  - Returns pre-labeled zone polygons without any model inference.

Dependencies (real mode only): torch, sam2
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock segmentation
# ---------------------------------------------------------------------------

def segment_zones_mock(
    field_polygon_geojson: dict[str, Any],
    n_zones: int = 3,
) -> list[dict[str, Any]]:
    """Divide the field bounding box into N equal horizontal strips.

    Returns a list of GeoJSON Polygon dicts (EPSG:4326) with labels
    Zone A, Zone B, ... Zone N.
    """
    geom = shape(field_polygon_geojson)
    minx, miny, maxx, maxy = geom.bounds
    step = (maxy - miny) / n_zones

    zones = []
    labels = [chr(65 + i) for i in range(n_zones)]  # A, B, C, ...
    directions = ["North", "Center", "South"] if n_zones == 3 else labels

    for i in range(n_zones):
        strip_miny = miny + i * step
        strip_maxy = miny + (i + 1) * step
        strip = box(minx, strip_miny, maxx, strip_maxy)
        zone_poly = strip.intersection(geom)
        direction = directions[i] if i < len(directions) else labels[i]
        zones.append({
            "label": f"Zone {labels[i]} – {direction}",
            "polygon": mapping(zone_poly),
        })

    # Return in North → South order (reverse so Zone A is northernmost)
    return list(reversed(zones))


# ---------------------------------------------------------------------------
# Real SAM2 segmentation
# ---------------------------------------------------------------------------

def segment_zones_sam2(
    ndvi_array: np.ndarray,
    field_polygon_geojson: dict[str, Any],
    n_zones: int = 3,
) -> list[dict[str, Any]]:
    """Segment the NDVI raster into zones using SAM2.

    Args:
        ndvi_array: 2-D float32 array of NDVI values clipped to field bounds.
        field_polygon_geojson: GeoJSON Polygon in EPSG:4326.
        n_zones: Target number of zones (approximate — SAM2 may return more).

    Returns:
        List of dicts with keys 'label' and 'polygon' (GeoJSON Polygon).
    """
    try:
        import torch
        from sam2.build_sam import build_sam2
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    except ImportError:
        logger.warning("SAM2 not available — falling back to mock segmentation")
        return segment_zones_mock(field_polygon_geojson, n_zones)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Running SAM2 segmentation on %s", device)

    # Normalise NDVI to uint8 RGB (SAM2 expects 3-channel images)
    ndvi_norm = np.clip((ndvi_array - ndvi_array.min()) / (ndvi_array.ptp() + 1e-8), 0, 1)
    ndvi_uint8 = (ndvi_norm * 255).astype(np.uint8)
    rgb = np.stack([ndvi_uint8, ndvi_uint8, ndvi_uint8], axis=-1)

    try:
        # SAM2 model checkpoint must be present at this path or set via env var
        import os
        checkpoint = os.environ.get(
            "SAM2_CHECKPOINT", "models/sam2_hiera_large.pt"
        )
        model_cfg = os.environ.get(
            "SAM2_MODEL_CFG", "sam2_hiera_l.yaml"
        )
        sam2_model = build_sam2(model_cfg, checkpoint, device=device)
        mask_generator = SAM2AutomaticMaskGenerator(
            sam2_model,
            points_per_side=16,
            pred_iou_thresh=0.8,
            stability_score_thresh=0.9,
            min_mask_region_area=500,
        )
        masks = mask_generator.generate(rgb)
    except Exception:
        logger.exception("SAM2 inference failed — falling back to mock segmentation")
        return segment_zones_mock(field_polygon_geojson, n_zones)

    if not masks:
        logger.warning("SAM2 returned no masks — falling back to mock segmentation")
        return segment_zones_mock(field_polygon_geojson, n_zones)

    # Convert top-N masks to GeoJSON polygons (approximate — no proper georeference)
    # For production: apply the raster affine transform to project pixel coords → EPSG:4326
    masks_sorted = sorted(masks, key=lambda m: m["area"], reverse=True)[:n_zones]
    field_geom = shape(field_polygon_geojson)
    minx, miny, maxx, maxy = field_geom.bounds
    h, w = ndvi_array.shape

    zones = []
    labels = [chr(65 + i) for i in range(len(masks_sorted))]
    for i, mask_data in enumerate(masks_sorted):
        # Approximate: scale mask bounding box to field extent
        x0, y0, bw, bh = mask_data["bbox"]  # pixel coords
        geo_minx = minx + (x0 / w) * (maxx - minx)
        geo_maxx = minx + ((x0 + bw) / w) * (maxx - minx)
        geo_miny = miny + (y0 / h) * (maxy - miny)
        geo_maxy = miny + ((y0 + bh) / h) * (maxy - miny)
        zone_poly = box(geo_minx, geo_miny, geo_maxx, geo_maxy).intersection(field_geom)
        zones.append({
            "label": f"Zone {labels[i]}",
            "polygon": mapping(zone_poly),
        })

    return zones


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def segment_field(
    field_polygon_geojson: dict[str, Any],
    ndvi_array: np.ndarray | None = None,
    n_zones: int = 3,
) -> list[dict[str, Any]]:
    """Segment a field into zones. Uses SAM2 if ndvi_array is provided and SAM2
    is available; otherwise falls back to bbox-derived mock zones.
    """
    from app.config import settings

    if settings.use_mock_satellite or ndvi_array is None:
        logger.info("Using mock zone segmentation")
        return segment_zones_mock(field_polygon_geojson, n_zones)

    return segment_zones_sam2(ndvi_array, field_polygon_geojson, n_zones)
