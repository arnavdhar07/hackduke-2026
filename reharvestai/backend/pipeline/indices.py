"""
indices.py — Compute per-pixel and per-mask vegetation indices.

Formulas (raw range −1 to +1, stored as 0–100 after normalization):
  NDVI = (B08 − B04) / (B08 + B04)  → vegetation health / ripeness
  NDWI = (B03 − B08) / (B03 + B08)  → water stress
  NDRE = (B8A − B05) / (B8A + B05)  → early stress (more sensitive than NDVI)
"""
from __future__ import annotations

import numpy as np

from pipeline.raster import BandArrays

# Sentinel-2 reflectance scale factor (raw uint16 → physical reflectance)
_REFL_SCALE = 10_000.0


# ─── Public API ──────────────────────────────────────────────────────────────

def compute_pixel_indices(bands: BandArrays) -> dict[str, np.ndarray]:
    """Compute NDVI, NDWI, NDRE for every pixel.

    Args:
        bands: Dict mapping band name → (H, W) float32 array (raw uint16 values).

    Returns:
        Dict with keys "ndvi", "ndwi", "ndre", each a (H, W) float32 array
        in the range [0, 100]. Pixels where the denominator is zero are NaN.
    """
    # Scale to physical reflectance (0.0–1.0 range).
    def _refl(name: str) -> np.ndarray:
        arr = bands[name] / _REFL_SCALE
        return arr.astype(np.float32)

    b03 = _refl("B03")
    b04 = _refl("B04")
    b05 = _refl("B05")
    b08 = _refl("B08")
    b8a = _refl("B8A")

    ndvi = _ratio(b08, b04)
    ndwi = _ratio(b03, b08)
    ndre = _ratio(b8a, b05)

    return {
        "ndvi": normalize_index(ndvi),
        "ndwi": normalize_index(ndwi),
        "ndre": normalize_index(ndre),
    }


def compute_mask_mean_scores(
    index_arrays: dict[str, np.ndarray],
    mask: np.ndarray,
) -> dict[str, float]:
    """Compute the mean of each index over pixels where mask is True.

    Args:
        index_arrays: {"ndvi": arr, "ndwi": arr, "ndre": arr} — values 0–100.
        mask: Boolean (H, W) array selecting pixels to average.

    Returns:
        {"ndvi": float, "ndwi": float, "ndre": float}  — means in [0, 100].
        Fully-masked (all NaN) zones return 0.0 as a safe fallback.
    """
    result: dict[str, float] = {}
    for key, arr in index_arrays.items():
        pixels = arr[mask]
        mean = float(np.nanmean(pixels)) if pixels.size > 0 else 0.0
        result[key] = 0.0 if np.isnan(mean) else mean
    return result


def normalize_index(arr: np.ndarray) -> np.ndarray:
    """Map raw index values from [−1, 1] → [0, 100], clipped to valid range.

    Formula: ((arr + 1) / 2) * 100, clipped to [0, 100].
    NaN values are preserved.
    """
    normalized = ((arr + 1.0) / 2.0) * 100.0
    return np.clip(normalized, 0.0, 100.0).astype(np.float32)


# ─── Internal helpers ────────────────────────────────────────────────────────

def _ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute (a − b) / (a + b), with NaN where the denominator is zero."""
    denom = a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(denom != 0, (a - b) / denom, np.nan)
    return result.astype(np.float32)
