"""
heatmap_generator.py — Generate crop-health heatmap PNG and segment a field
into organic health zones based on vegetation index values.

Composite health score (0–100):
  NDVI  35% — biomass baseline
  NDRE  30% — early stress proxy
  CIg   20% — nitrogen / chlorophyll
  NDWI  15% — water stress

Public API
----------
compute_health_score(index_arrays)
    → H×W float32 composite score from real index pixel arrays.

generate_synthetic_health_score(field_id, size)
    → H×W float32 seeded noise score (no satellite data needed).

generate_synthetic_index_arrays(health_score, field_id)
    → dict of H×W float32 index arrays derived from synthetic health score.

segment_health_zones(health_score, index_arrays, polygon_wkt, bbox)
    → list of zone dicts with organic polygon, label, mean metrics.

generate_sentinel2_heatmap(index_arrays, polygon_wkt, bbox)
generate_synthetic_heatmap(field_id, polygon_wkt, bbox)
    → {"image_png_b64": str, "bounds": list, "source": str}
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_IMG_SIZE = 256  # PNG output dimension

# Composite health score weights
_WEIGHTS = {"ndvi": 0.35, "ndre": 0.30, "cig": 0.20, "ndwi": 0.15}

# Health band thresholds and labels (hi inclusive at 100)
_BANDS = [
    (75.0, 100.0, "Healthy"),
    (50.0,  75.0, "Moderate"),
    (25.0,  50.0, "Stressed"),
    ( 0.0,  25.0, "Critical"),
]


# ─── Health score computation ─────────────────────────────────────────────────

def compute_health_score(index_arrays: dict[str, np.ndarray]) -> np.ndarray:
    """Composite health score 0–100 from real Sentinel-2 index pixel arrays."""
    health = np.zeros_like(next(iter(index_arrays.values())), dtype=np.float32)
    for key, weight in _WEIGHTS.items():
        arr = index_arrays.get(key)
        if arr is not None:
            health += np.where(np.isnan(arr), 0.0, arr.astype(np.float32)) * weight
    return np.clip(health, 0.0, 100.0)


def generate_synthetic_health_score(field_id: str, size: int = 128) -> np.ndarray:
    """Seeded synthetic health score array (H×W float32, 0–100).

    Gaussian-smoothed noise biased by quadrant:
      NW → healthy (~88), NE → moderate (~71),
      SW → stressed (~48), SE → critical (~22).
    """
    from scipy.ndimage import gaussian_filter

    seed = int(hashlib.md5(field_id.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    noise = rng.random((size, size)).astype(np.float32)
    noise = gaussian_filter(noise, sigma=size / 6)
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-8)

    half = size // 2
    bias = np.zeros((size, size), dtype=np.float32)
    bias[:half, :half] = 0.88   # NW
    bias[:half, half:] = 0.71   # NE
    bias[half:, :half] = 0.48   # SW
    bias[half:, half:] = 0.22   # SE
    bias = gaussian_filter(bias, sigma=size / 10)

    return np.clip((bias * 0.70 + noise * 0.30) * 100, 0.0, 100.0)


def generate_synthetic_index_arrays(
    health_score: np.ndarray,
    field_id: str,
) -> dict[str, np.ndarray]:
    """Per-pixel synthetic index arrays derived from a health score array.

    Uses fixed agronomic ratios with small gaussian noise so each index
    is spatially coherent and consistent with the health pattern.
    """
    seed = int(hashlib.md5((field_id + "_idx").encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    H, W = health_score.shape

    def noisy(ratio: float) -> np.ndarray:
        n = rng.normal(0.0, 2.5, (H, W)).astype(np.float32)
        return np.clip(health_score * ratio + n, 0.0, 100.0).astype(np.float32)

    return {
        "ndvi":  noisy(0.95),
        "ndwi":  noisy(0.78),
        "ndre":  noisy(0.88),
        "evi":   noisy(0.92),
        "gndvi": noisy(0.90),
        "savi":  noisy(0.87),
        "cig":   noisy(0.82),
    }


# ─── Organic zone segmentation ────────────────────────────────────────────────

def segment_health_zones(
    health_score: np.ndarray,
    index_arrays: dict[str, np.ndarray],
    polygon_wkt: str,
    bbox: tuple[float, float, float, float],
    min_zone_fraction: float = 0.04,
) -> list[dict]:
    """Segment field into organic health zones via band quantisation + connected components.

    Algorithm:
      1. Smooth health score (gaussian σ=3) to reduce noise artifacts.
      2. Mask pixels outside field polygon to NaN.
      3. Quantise into 4 bands: Healthy / Moderate / Stressed / Critical.
      4. Find connected components per band (scipy.ndimage.label).
      5. Drop components < min_zone_fraction of total field pixels.
      6. Convert each component mask → geographic polygon (rasterio.features.shapes).
      7. Simplify polygon edges (shapely.simplify).
      8. Compute mean metrics per component (indices.compute_mask_mean_scores).
      9. Label zones A, B, C, … by descending health score.

    Returns list sorted healthiest → least healthy.
    Each entry: {polygon_wkt, label, metrics, health_score, pixel_count}
    """
    from scipy.ndimage import label as nd_label, gaussian_filter
    from rasterio.features import shapes, rasterize
    from rasterio.transform import from_bounds
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely import wkt as shapely_wkt
    from pipeline.indices import compute_mask_mean_scores

    H, W = health_score.shape
    min_lng, min_lat, max_lng, max_lat = bbox
    transform = from_bounds(min_lng, min_lat, max_lng, max_lat, W, H)

    # Build field polygon mask in pixel space
    try:
        field_geom = shapely_wkt.loads(polygon_wkt)
        field_mask = rasterize(
            [(field_geom, 1)],
            out_shape=(H, W),
            transform=transform,
            fill=0,
            dtype=np.uint8,
        )
    except Exception as exc:
        logger.warning("segment_health_zones: polygon rasterize failed (%s), using full bbox", exc)
        field_mask = np.ones((H, W), dtype=np.uint8)

    total_pixels = int(field_mask.sum())
    if total_pixels == 0:
        return []

    min_pixels = max(8, int(total_pixels * min_zone_fraction))

    # Smooth for cleaner band boundaries
    smooth = gaussian_filter(health_score.astype(np.float32), sigma=3.0)
    smooth = np.where(field_mask.astype(bool), smooth, np.nan)

    raw_zones: list[dict] = []

    for lo, hi, band_label in _BANDS:
        # Top band is closed at hi=100
        if hi >= 100.0:
            band_mask = (smooth >= lo) & field_mask.astype(bool)
        else:
            band_mask = (smooth >= lo) & (smooth < hi) & field_mask.astype(bool)

        if not band_mask.any():
            continue

        labeled_arr, n_comps = nd_label(band_mask)

        for comp_idx in range(1, n_comps + 1):
            comp_mask = labeled_arr == comp_idx
            pixel_count = int(comp_mask.sum())
            if pixel_count < min_pixels:
                continue

            try:
                mask_u8 = comp_mask.astype(np.uint8)
                geom_list = [
                    shape(g)
                    for g, v in shapes(mask_u8, mask=mask_u8, transform=transform)
                    if v == 1
                ]
                if not geom_list:
                    continue

                poly = unary_union(geom_list) if len(geom_list) > 1 else geom_list[0]
                # Simplify: ~5m tolerance in degrees at equator
                poly = poly.simplify(0.00002, preserve_topology=True)
                if poly.is_empty:
                    continue

                metrics = compute_mask_mean_scores(index_arrays, comp_mask)
                mean_health = float(np.nanmean(smooth[comp_mask]))

                raw_zones.append({
                    "polygon_wkt": poly.wkt,
                    "band_label":  band_label,
                    "metrics":     metrics,
                    "health_score": mean_health,
                    "pixel_count": pixel_count,
                })
            except Exception as exc:
                logger.warning(
                    "segment_health_zones: component %d band=%s polygon failed: %s",
                    comp_idx, band_label, exc,
                )

    # Fallback: single zone covering the whole field
    if not raw_zones:
        logger.warning("segment_health_zones: no zones found, falling back to full-field zone")
        try:
            metrics = compute_mask_mean_scores(index_arrays, field_mask.astype(bool))
            raw_zones.append({
                "polygon_wkt":  polygon_wkt,
                "band_label":   "Zone",
                "metrics":      metrics,
                "health_score": float(np.nanmean(smooth[field_mask.astype(bool)])),
                "pixel_count":  total_pixels,
            })
        except Exception:
            pass

    # Sort healthiest first, then assign Zone A, B, C, … labels
    raw_zones.sort(key=lambda z: z["health_score"], reverse=True)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, zone in enumerate(raw_zones):
        suffix = alphabet[i] if i < len(alphabet) else str(i + 1)
        zone["label"] = f"Zone {suffix}"

    logger.info(
        "segment_health_zones: %d organic zones (%s)",
        len(raw_zones),
        ", ".join(f"{z['label']}={z['band_label']}({z['health_score']:.0f})" for z in raw_zones),
    )
    return raw_zones


# ─── PNG colorization helpers ─────────────────────────────────────────────────

def _health_to_rgba(score: np.ndarray) -> np.ndarray:
    """Map 0–100 health score to RGBA via red → amber → green ramp."""
    t = np.clip(score / 100.0, 0.0, 1.0)

    # Low half: red (#ef4444) → amber (#f59e0b)
    low = np.clip(t * 2.0, 0.0, 1.0)
    r_low = 239 + (245 - 239) * low
    g_low =  68 + (158 -  68) * low
    b_low =  68 + ( 11 -  68) * low

    # High half: amber (#f59e0b) → green (#16a34a)
    high = np.clip((t - 0.5) * 2.0, 0.0, 1.0)
    r_high = 245 + ( 22 - 245) * high
    g_high = 158 + (163 - 158) * high
    b_high =  11 + ( 74 -  11) * high

    in_low = t <= 0.5
    return np.stack([
        np.clip(np.where(in_low, r_low, r_high), 0, 255).astype(np.uint8),
        np.clip(np.where(in_low, g_low, g_high), 0, 255).astype(np.uint8),
        np.clip(np.where(in_low, b_low, b_high), 0, 255).astype(np.uint8),
        np.full(score.shape, 255, dtype=np.uint8),
    ], axis=-1)


def _apply_polygon_mask(
    rgba: np.ndarray,
    polygon_wkt: str,
    bbox: tuple[float, float, float, float],
) -> np.ndarray:
    """Set alpha=0 for pixels outside the field polygon."""
    try:
        from shapely import wkt as shapely_wkt
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds

        H, W = rgba.shape[:2]
        min_lng, min_lat, max_lng, max_lat = bbox
        transform = from_bounds(min_lng, min_lat, max_lng, max_lat, W, H)
        field_geom = shapely_wkt.loads(polygon_wkt)
        mask = rasterize(
            [(field_geom, 1)],
            out_shape=(H, W),
            transform=transform,
            fill=0,
            dtype=np.uint8,
        )
        out = rgba.copy()
        out[mask == 0, 3] = 0
        return out
    except Exception as exc:
        logger.warning("_apply_polygon_mask failed (%s), returning full bbox image", exc)
        return rgba


def _to_png_b64(rgba: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ─── Public heatmap generation ────────────────────────────────────────────────

def generate_heatmap_from_health_score(
    health_score: np.ndarray,
    polygon_wkt: str,
    bbox: tuple[float, float, float, float],
    source: str = "synthetic",
    size: int = _IMG_SIZE,
) -> dict:
    """Generate heatmap PNG from a pre-computed health score array.

    Applies the same gaussian smoothing (sigma=3) used in segment_health_zones
    so the heatmap color transitions exactly match the zone polygon edges.
    """
    from scipy.ndimage import gaussian_filter, zoom

    score = health_score.copy().astype(np.float32)
    # Same smoothing kernel as segment_health_zones — ensures color/polygon alignment
    score = gaussian_filter(score, sigma=3.0)
    score = np.clip(score, 0.0, 100.0)

    H, W = score.shape
    if H != size or W != size:
        sy, sx = size / H, size / W
        score = zoom(score, (sy, sx), order=1)

    rgba = _health_to_rgba(score)
    rgba = _apply_polygon_mask(rgba, polygon_wkt, bbox)
    return {"image_png_b64": _to_png_b64(rgba), "bounds": list(bbox), "source": source}


def generate_synthetic_heatmap(
    field_id: str,
    polygon_wkt: str,
    bbox: tuple[float, float, float, float],
    size: int = _IMG_SIZE,
) -> dict:
    """Generate synthetic heatmap PNG (seeded noise biased by quadrant).

    Kept for the /heatmap endpoint fallback; pipeline uses generate_heatmap_from_health_score.
    """
    score = generate_synthetic_health_score(field_id, size)
    return generate_heatmap_from_health_score(score, polygon_wkt, bbox, source="synthetic", size=size)


def generate_sentinel2_heatmap(
    index_arrays: dict[str, np.ndarray],
    polygon_wkt: str,
    bbox: tuple[float, float, float, float],
    size: int = _IMG_SIZE,
) -> dict:
    """Generate heatmap PNG from real Sentinel-2 index arrays."""
    health = compute_health_score(index_arrays)
    return generate_heatmap_from_health_score(health, polygon_wkt, bbox, source="sentinel2", size=size)
