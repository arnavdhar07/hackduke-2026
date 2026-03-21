"""
segmentation.py — Segment a field into agronomic zones using SAM3.

SAM3 (Segment Anything Model 3) runs in automatic mask generation mode on
the RGB composite (B04/B03/B02). Each returned mask becomes a zone polygon.

Falls back to a deterministic grid partition when the SAM3 model is
unavailable (missing checkpoint, import error) so the pipeline can run
in any environment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import rasterio.features
import rasterio.transform
from pyproj import Transformer
from shapely import from_wkt, to_wkt
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from pipeline.raster import BandArrays

logger = logging.getLogger(__name__)


@dataclass
class ZoneMask:
    mask: np.ndarray      # Boolean (H, W) array — True inside this zone
    bbox: list[int]       # [x, y, width, height] in pixel coordinates
    area: float           # Fraction of total pixels (0.0–1.0)
    polygon_wkt: str      # Zone boundary in EPSG:4326


# Module-level singleton — loaded once per worker process.
_sam_generator = None


# ─── Public API ──────────────────────────────────────────────────────────────

def segment_field(
    band_arrays: BandArrays,
    transform,
    src_crs: str,
    field_polygon_wkt: str,
    points_per_side: int = 16,
    min_mask_area_frac: float = 0.01,
    max_masks: int = 20,
) -> list[ZoneMask]:
    """Segment the field into zones using SAM3 automatic mask generation.

    Args:
        band_arrays: Dict of band → (H, W) float32 arrays (raw uint16 values).
        transform: Rasterio affine transform for the arrays.
        src_crs: CRS string of the arrays (e.g. "EPSG:4326").
        field_polygon_wkt: Field boundary in EPSG:4326 WKT.
        points_per_side: Grid density for SAM3 prompt points (n × n).
        min_mask_area_frac: Discard masks smaller than this fraction of H×W.
        max_masks: Maximum number of zones to return.

    Returns:
        List of ZoneMask, sorted by area descending, clipped to field boundary.
    """
    rgb = _build_rgb_image(band_arrays)
    H, W = rgb.shape[:2]
    total_pixels = H * W

    try:
        generator = _get_generator(points_per_side)
        raw_masks = generator.generate(rgb)
        logger.info("SAM3 produced %d raw masks", len(raw_masks))
    except Exception as exc:
        logger.warning("SAM3 unavailable (%s) — using grid fallback", exc)
        return _grid_fallback_zones(field_polygon_wkt, transform, src_crs, H, W)

    field_polygon = from_wkt(field_polygon_wkt)
    zones: list[ZoneMask] = []

    for m in raw_masks:
        seg: np.ndarray = m["segmentation"]  # bool (H, W)
        pixel_count = int(seg.sum())
        area_frac = pixel_count / total_pixels

        if area_frac < min_mask_area_frac:
            continue

        try:
            wkt = _mask_to_polygon(seg, transform, src_crs)
            zone_poly = from_wkt(wkt)
            # Clip to field boundary to prevent bleed-over.
            clipped = zone_poly.intersection(field_polygon)
            if clipped.is_empty:
                continue
            wkt = to_wkt(clipped)
        except Exception as exc:
            logger.debug("Skipping mask (polygon error: %s)", exc)
            continue

        rx, ry, rw, rh = m.get("bbox", [0, 0, W, H])
        zones.append(ZoneMask(mask=seg, bbox=[rx, ry, rw, rh], area=area_frac, polygon_wkt=wkt))

    zones.sort(key=lambda z: z.area, reverse=True)
    zones = zones[:max_masks]

    if not zones:
        logger.warning("SAM3 returned no usable masks — using grid fallback")
        return _grid_fallback_zones(field_polygon_wkt, transform, src_crs, H, W)

    logger.info("Returning %d zones after filtering", len(zones))
    return zones


# ─── Internal helpers ────────────────────────────────────────────────────────

def _get_generator(points_per_side: int):
    """Return the module-level SAM3 generator singleton."""
    global _sam_generator
    if _sam_generator is None:
        from app.config import settings  # lazy import avoids circular deps

        from sam3 import SamAutomaticMaskGenerator, sam_model_registry  # type: ignore

        sam = sam_model_registry[settings.SAM3_MODEL_TYPE](
            checkpoint=settings.SAM3_CHECKPOINT_PATH
        )
        _sam_generator = SamAutomaticMaskGenerator(
            model=sam,
            points_per_side=points_per_side,
            pred_iou_thresh=0.86,
            stability_score_thresh=0.92,
            min_mask_region_area=100,
        )
        logger.info("SAM3 model loaded from %s", settings.SAM3_CHECKPOINT_PATH)
    return _sam_generator


def _build_rgb_image(band_arrays: BandArrays) -> np.ndarray:
    """Stack B04 (R), B03 (G), B02 (B) into a uint8 (H, W, 3) image."""
    channels = []
    for band in ("B04", "B03", "B02"):
        arr = band_arrays[band].copy()
        # Percentile clipping avoids outlier washout.
        lo, hi = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
        if hi == lo:
            hi = lo + 1.0
        arr = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
        channels.append((arr * 255).astype(np.uint8))
    return np.stack(channels, axis=-1)  # (H, W, 3)


def _mask_to_polygon(mask: np.ndarray, transform, src_crs: str) -> str:
    """Vectorize a boolean mask to a WKT polygon in EPSG:4326."""
    uint8_mask = mask.astype(np.uint8)
    shapes = list(rasterio.features.shapes(uint8_mask, mask=uint8_mask, transform=transform))
    if not shapes:
        raise ValueError("No shapes extracted from mask")

    # Take the largest contiguous polygon.
    geom_dict, _ = max(shapes, key=lambda s: shape(s[0]).area)
    poly = shape(geom_dict)

    if src_crs.upper() != "EPSG:4326":
        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        poly = shapely_transform(transformer.transform, poly)

    return to_wkt(poly)


def _grid_fallback_zones(
    field_polygon_wkt: str,
    transform,
    src_crs: str,
    H: int,
    W: int,
    n: int = 3,
) -> list[ZoneMask]:
    """Partition the field bbox into an n×n grid of rectangular zones."""
    from shapely.geometry import box

    field_poly = from_wkt(field_polygon_wkt)
    minx, miny, maxx, maxy = field_poly.bounds
    cell_w = (maxx - minx) / n
    cell_h = (maxy - miny) / n

    pixel_cell_w = W // n
    pixel_cell_h = H // n

    zones: list[ZoneMask] = []
    for row in range(n):
        for col in range(n):
            # Geographic polygon for this cell.
            cell_minx = minx + col * cell_w
            cell_miny = miny + row * cell_h
            cell_poly = box(cell_minx, cell_miny, cell_minx + cell_w, cell_miny + cell_h)
            clipped = cell_poly.intersection(field_poly)
            if clipped.is_empty:
                continue

            # Pixel mask for this cell.
            px_start_col = col * pixel_cell_w
            px_start_row = row * pixel_cell_h
            mask = np.zeros((H, W), dtype=bool)
            mask[
                px_start_row: px_start_row + pixel_cell_h,
                px_start_col: px_start_col + pixel_cell_w,
            ] = True

            area_frac = float(mask.sum()) / (H * W)
            zones.append(
                ZoneMask(
                    mask=mask,
                    bbox=[px_start_col, px_start_row, pixel_cell_w, pixel_cell_h],
                    area=area_frac,
                    polygon_wkt=to_wkt(clipped),
                )
            )

    logger.info("Grid fallback produced %d zones", len(zones))
    return zones
