"""Raster processing utilities for Sentinel-2 imagery.

Handles:
- Opening GeoTIFF/JP2 files downloaded by sentinel.py
- Clipping bands to a field polygon
- Reading individual Sentinel-2 bands (B03, B04, B08, B8A)
- Returning numpy arrays for index calculation

Dependencies: rasterio, numpy, shapely
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from shapely.geometry import mapping, shape

logger = logging.getLogger(__name__)

# Sentinel-2 L2A band filename suffixes (10m and 20m bands)
BAND_FILES = {
    "B03": "B03_10m",   # Green
    "B04": "B04_10m",   # Red
    "B08": "B08_10m",   # NIR
    "B8A": "B8A_20m",   # Red-Edge
}


def clip_band_to_polygon(
    band_path: Path,
    polygon_geojson: dict[str, Any],
) -> np.ndarray:
    """Clip a single raster band to the given GeoJSON polygon.

    Args:
        band_path: Path to .jp2 or .tif file.
        polygon_geojson: GeoJSON Polygon dict in EPSG:4326.

    Returns:
        Clipped band as float32 2-D numpy array, or empty array on error.
    """
    geom = shape(polygon_geojson)
    geoms = [mapping(geom)]

    try:
        with rasterio.open(band_path) as src:
            if str(src.crs) != "EPSG:4326":
                from rasterio.warp import transform_geom
                geoms = [transform_geom("EPSG:4326", src.crs, g) for g in geoms]

            clipped, _ = rasterio_mask(src, geoms, crop=True, nodata=0)
            return clipped[0].astype(np.float32)
    except Exception:
        logger.exception("Failed to clip band %s", band_path)
        return np.array([], dtype=np.float32)


def read_sentinel_bands(
    safe_dir: Path,
    polygon_geojson: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Read and clip all required Sentinel-2 bands from a SAFE directory.

    Raises:
        FileNotFoundError: if any required band file is missing.
    """
    bands: dict[str, np.ndarray] = {}
    for band_key, band_suffix in BAND_FILES.items():
        matches = list(safe_dir.rglob(f"*{band_suffix}*.jp2"))
        if not matches:
            matches = list(safe_dir.rglob(f"*{band_suffix}*.tif"))
        if not matches:
            raise FileNotFoundError(f"Band {band_key} ({band_suffix}) not found in {safe_dir}")
        logger.info("Reading band %s from %s", band_key, matches[0].name)
        bands[band_key] = clip_band_to_polygon(matches[0], polygon_geojson)
    return bands


def create_zone_mask(
    reference_band: np.ndarray,
    reference_transform: Any,
    reference_crs: Any,
    zone_polygon_geojson: dict[str, Any],
) -> np.ndarray:
    """Create a boolean mask for a zone polygon aligned to a raster band.

    Returns True where pixels fall inside the zone.
    """
    import rasterio.features
    from rasterio.warp import transform_geom

    geom_projected = transform_geom("EPSG:4326", reference_crs, zone_polygon_geojson)
    height, width = reference_band.shape
    return rasterio.features.geometry_mask(
        [geom_projected],
        out_shape=(height, width),
        transform=reference_transform,
        invert=True,
    )
