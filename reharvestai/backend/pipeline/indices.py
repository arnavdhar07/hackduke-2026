"""Vegetation index calculations from Sentinel-2 bands.

Sentinel-2 band mapping used here:
    B04 = Red (665 nm)
    B08 = NIR (842 nm)
    B8A = Red-Edge (865 nm)
    B03 = Green (560 nm)
    B11 = SWIR (1610 nm)  — used for NDWI

All inputs are numpy float32 arrays.  Division is safe because we clamp
denominators to avoid divide-by-zero.
"""
from __future__ import annotations

import numpy as np


def _safe_divide(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Element-wise division, returning 0.0 where denominator == 0."""
    denominator = np.where(b == 0, np.finfo(float).eps, b)
    return a / denominator


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalised Difference Vegetation Index.

    NDVI = (NIR − Red) / (NIR + Red)
    Range: −1 to 1.  Healthy vegetation: 0.2 – 0.9
    """
    return _safe_divide(nir - red, nir + red)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalised Difference Water Index.

    NDWI = (Green − NIR) / (Green + NIR)
    Range: −1 to 1.  Water content increases toward +1.
    """
    return _safe_divide(green - nir, green + nir)


def ndre(red_edge: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalised Difference Red-Edge Index.

    NDRE = (RedEdge − Red) / (RedEdge + Red)
    Range: −1 to 1.  Sensitive to chlorophyll during late growth stages.
    """
    return _safe_divide(red_edge - red, red_edge + red)


def compute_all(
    red: np.ndarray,
    nir: np.ndarray,
    green: np.ndarray,
    red_edge: np.ndarray,
) -> dict[str, np.ndarray]:
    """Compute NDVI, NDWI, and NDRE from raw band arrays.

    Returns:
        dict with keys 'ndvi', 'ndwi', 'ndre' — each a float32 numpy array
        the same shape as the input bands.
    """
    red_f = red.astype(np.float32)
    nir_f = nir.astype(np.float32)
    green_f = green.astype(np.float32)
    red_edge_f = red_edge.astype(np.float32)

    return {
        "ndvi": ndvi(red_f, nir_f),
        "ndwi": ndwi(green_f, nir_f),
        "ndre": ndre(red_edge_f, red_f),
    }


def zone_mean(index_array: np.ndarray, mask: np.ndarray) -> float:
    """Compute mean index value within a binary mask.

    Args:
        index_array: 2-D float array of index values.
        mask: Boolean array (True = pixels inside zone).

    Returns:
        Mean float value, or 0.0 if the mask is empty.
    """
    pixels = index_array[mask]
    if pixels.size == 0:
        return 0.0
    return float(np.mean(pixels))
