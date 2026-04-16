"""
field_detector.py — SAM3 text-prompt field boundary detection.

Uses HuggingFace transformers Sam3Model + Sam3Processor (CPU/GPU compatible).
facebook/sam3 is a composite model: the outer sam3_video wrapper handles video
tracking; the inner Sam3Model handles text-prompted concept segmentation (PCS).

Usage: prompt "agricultural field" → get all field masks → pick the one that
contains the clicked pixel → return as GeoJSON polygon.

Set HF_TOKEN in .env if the checkpoint is gated.
Model is cached after first download via HuggingFace Hub.

Fallback: if SAM3 or satellite fetch unavailable, returns a ~300m bbox polygon.
"""
from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path
from typing import TypedDict

import numpy as np

logger = logging.getLogger(__name__)

_HF_MODEL_ID = "facebook/sam3"
_TEXT_PROMPT = "agricultural field"

# Module-level SAM3 singletons — loaded once per worker process.
_sam_model = None
_sam_processor = None


class DetectionResult(TypedDict):
    polygon: dict          # GeoJSON Polygon dict
    confidence: float      # 0.0–1.0
    source: str            # "sam3" | "fallback"


# ─── Public API ──────────────────────────────────────────────────────────────

def detect_field_from_point(lat: float, lng: float) -> DetectionResult:
    """Return GeoJSON polygon of the field containing (lat, lng)."""
    delta = 0.01  # ~1 km in each direction
    bbox = (lng - delta, lat - delta, lng + delta, lat + delta)

    try:
        return _sam_detect(lat, lng, bbox)
    except Exception as exc:
        logger.warning("SAM3 field detection failed (%s) — using fallback", exc)
        return _fallback_bbox(lat, lng, radius_km=0.3)


# ─── SAM3 path ────────────────────────────────────────────────────────────────

def _sam_detect(lat: float, lng: float, bbox: tuple) -> DetectionResult:
    from PIL import Image as PILImage
    from pipeline.stac_sentinel import fetch_sentinel2_bands
    from pipeline.raster import load_and_clip
    from pipeline.segmentation import _build_rgb_image, _mask_to_polygon

    import torch

    min_lng, min_lat, max_lng, max_lat = bbox
    bbox_wkt = (
        f"POLYGON(({min_lng} {min_lat},{max_lng} {min_lat},"
        f"{max_lng} {max_lat},{min_lng} {max_lat},{min_lng} {min_lat}))"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        band_dir = fetch_sentinel2_bands(bbox, Path(tmpdir))
        if band_dir is None:
            raise RuntimeError("No Sentinel-2 scene found for this location")
        band_arrays, meta = load_and_clip(band_dir, bbox_wkt)

    rgb_np = _build_rgb_image(band_arrays)   # (H, W, 3) uint8
    H, W = rgb_np.shape[:2]
    transform = meta["transform"]
    src_crs = meta.get("crs", "EPSG:32617")

    # Convert lat/lng → pixel (col, row) to find which mask contains this point
    import rasterio.transform as rio_transform
    px_row, px_col = rio_transform.rowcol(transform, lng, lat)
    px_row = int(max(0, min(H - 1, px_row)))
    px_col = int(max(0, min(W - 1, px_col)))

    model, processor = _get_sam3()

    pil_image = PILImage.fromarray(rgb_np)

    # Sam3Processor: text-prompted concept segmentation
    inputs = processor(
        images=pil_image,
        text=_TEXT_PROMPT,
        return_tensors="pt",
    )
    device = next(model.parameters()).device
    inputs = inputs.to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    # Post-process: get binary masks resized to original image size.
    # Use low thresholds — Sentinel-2 imagery differs from natural photos
    # so SAM3 detection scores are typically lower than on COCO-style images.
    results = processor.post_process_instance_segmentation(
        outputs,
        threshold=0.1,
        mask_threshold=0.3,
        target_sizes=inputs.get("original_sizes").tolist(),
    )[0]

    masks = results["masks"]      # list of (H, W) bool tensors or ndarray
    scores = results["scores"]    # confidence per mask

    logger.info(
        "SAM3 raw results: %d masks, scores=%s",
        len(masks),
        [round(float(s.item() if hasattr(s, "item") else s), 3) for s in scores],
    )

    if len(masks) == 0:
        raise RuntimeError("SAM3 returned no masks for prompt")

    # Convert to numpy if needed
    masks_np = [
        (m.numpy() if hasattr(m, "numpy") else np.array(m)).astype(bool)
        for m in masks
    ]
    scores_np = [
        float(s.item() if hasattr(s, "item") else s)
        for s in scores
    ]

    # Pick the mask that contains the clicked pixel; fall back to highest-score mask
    best_mask = None
    best_score = 0.0

    for mask, score in zip(masks_np, scores_np):
        if mask[px_row, px_col]:
            # Prefer the highest-confidence mask that contains the point
            if score > best_score:
                best_mask = mask
                best_score = score

    if best_mask is None:
        # No mask covers the exact pixel — use highest-confidence mask overall
        best_idx = int(np.argmax(scores_np))
        best_mask = masks_np[best_idx]
        best_score = scores_np[best_idx]
        logger.warning(
            "No SAM3 mask covers clicked pixel (%d,%d) — using highest-score mask (%.2f)",
            px_col, px_row, best_score,
        )

    wkt = _mask_to_polygon(best_mask, transform, src_crs)
    geojson_polygon = _wkt_to_geojson(wkt)

    logger.info("SAM3 field detection success at (%.5f, %.5f) score=%.3f", lat, lng, best_score)
    return DetectionResult(polygon=geojson_polygon, confidence=best_score, source="sam3")


def _get_sam3():
    """Return (model, processor) using Sam3Model for text-prompted concept segmentation."""
    global _sam_model, _sam_processor
    if _sam_model is None:
        from transformers import Sam3Model, Sam3Processor
        from app.config import settings
        import torch

        token = settings.HF_TOKEN or None
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading SAM3 from HF Hub on %s (first run downloads checkpoint)…", device)

        _sam_processor = Sam3Processor.from_pretrained(_HF_MODEL_ID, token=token)
        _sam_model = Sam3Model.from_pretrained(_HF_MODEL_ID, token=token).to(device)
        _sam_model.eval()
        logger.info("SAM3 loaded on %s", device)

    return _sam_model, _sam_processor


# ─── Fallback ─────────────────────────────────────────────────────────────────

def _fallback_bbox(lat: float, lng: float, radius_km: float = 0.3) -> DetectionResult:
    d_lat = radius_km / 111.0
    d_lng = radius_km / (111.0 * math.cos(math.radians(lat)))
    coords = [
        [lng - d_lng, lat - d_lat],
        [lng + d_lng, lat - d_lat],
        [lng + d_lng, lat + d_lat],
        [lng - d_lng, lat + d_lat],
        [lng - d_lng, lat - d_lat],
    ]
    return DetectionResult(
        polygon={"type": "Polygon", "coordinates": [coords]},
        confidence=0.5,
        source="fallback",
    )


# ─── Geometry helpers ─────────────────────────────────────────────────────────

def _wkt_to_geojson(wkt: str) -> dict:
    from shapely import from_wkt
    from shapely.geometry import mapping
    return dict(mapping(from_wkt(wkt)))
