"""
raster.py — Load Sentinel-2 band GeoTIFFs and clip them to a field polygon.

Returns numpy arrays for each band, all resampled to a common shape, plus
the rasterio affine transform so downstream steps can convert pixel ↔ geo
coordinates.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
import rasterio.mask
import rasterio.warp
from pyproj import Transformer
from shapely import from_wkt, to_wkt
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform

from pipeline.sentinel import BANDS

logger = logging.getLogger(__name__)

# Type alias: band name → 2-D float32 array
BandArrays = dict[str, np.ndarray]


# ─── Public API ──────────────────────────────────────────────────────────────

def load_and_clip(
    band_dir: Path,
    field_polygon_wkt: str,
    target_crs: str = "EPSG:4326",
) -> tuple[BandArrays, dict]:
    """Open each band GeoTIFF, clip to field polygon, return aligned arrays.

    Args:
        band_dir: Directory containing {BAND}.tif files (one per band in BANDS).
        field_polygon_wkt: Field boundary in WKT, assumed EPSG:4326.
        target_crs: CRS of the returned arrays' spatial reference (default 4326).

    Returns:
        (band_arrays, meta) where
        - band_arrays maps band name → (H, W) float32 ndarray (masked to field,
          nodata pixels are np.nan)
        - meta is {"transform": Affine, "crs": str, "height": int, "width": int}
    """
    band_dir = Path(band_dir)
    field_polygon = from_wkt(field_polygon_wkt)

    band_arrays: BandArrays = {}
    reference_meta: dict | None = None

    for band in BANDS:
        tif_path = band_dir / f"{band}.tif"
        if not tif_path.exists():
            logger.warning("Band file missing: %s — skipping", tif_path)
            continue

        with rasterio.open(tif_path) as src:
            # Reproject field polygon from EPSG:4326 to the raster CRS.
            if src.crs.to_epsg() != 4326:
                transformer = Transformer.from_crs(
                    "EPSG:4326", src.crs.to_string(), always_xy=True
                )
                clipped_polygon = shapely_transform(
                    transformer.transform, field_polygon
                )
            else:
                clipped_polygon = field_polygon

            geom = [mapping(clipped_polygon)]
            try:
                out_image, out_transform = rasterio.mask.mask(
                    src, geom, crop=True, nodata=0, all_touched=True
                )
            except ValueError:
                # Polygon doesn't intersect raster extent — use full raster.
                logger.warning(
                    "band=%s polygon outside raster extent; using full extent", band
                )
                out_image = src.read()
                out_transform = src.transform

            arr = out_image[0].astype(np.float32)
            # Replace no-data (0 for uint16 imagery) with NaN.
            arr[arr == 0] = np.nan

            if reference_meta is None:
                reference_meta = {
                    "transform": out_transform,
                    "crs": src.crs.to_string(),
                    "height": arr.shape[0],
                    "width": arr.shape[1],
                }
                band_arrays[band] = arr
            else:
                # Resample to the reference shape if sizes differ.
                ref_h = reference_meta["height"]
                ref_w = reference_meta["width"]
                if arr.shape != (ref_h, ref_w):
                    arr = _resize(arr, ref_h, ref_w)
                band_arrays[band] = arr

    if reference_meta is None:
        raise RuntimeError(f"No band files found in {band_dir}")

    return band_arrays, reference_meta


def bbox_from_polygon(polygon_wkt: str) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) from a WKT polygon."""
    poly = from_wkt(polygon_wkt)
    minx, miny, maxx, maxy = poly.bounds
    return minx, miny, maxx, maxy


# ─── Internal helpers ────────────────────────────────────────────────────────

def _resize(arr: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Nearest-neighbour resize of a 2-D array to (target_h, target_w)."""
    src_h, src_w = arr.shape
    row_idx = (np.arange(target_h) * src_h / target_h).astype(int)
    col_idx = (np.arange(target_w) * src_w / target_w).astype(int)
    return arr[np.ix_(row_idx, col_idx)]
