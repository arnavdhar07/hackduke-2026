"""
stac_sentinel.py — Fetch Sentinel-2 L2A band clips via Earth Search STAC + Cloud-Optimized GeoTIFF.

No API key required. Uses Element84 Earth Search (https://earth-search.aws.element84.com/v1)
to find scenes and reads band windows directly from S3-hosted COGs via rasterio/GDAL.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

# GDAL/AWS env vars must be set before rasterio is imported so that the GDAL
# HTTP transport picks them up at driver-registration time.
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_REQUESTS", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")

import rasterio
import rasterio.warp
import rasterio.windows

logger = logging.getLogger(__name__)

_EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"

# Earth Search sentinel-2-l2a asset name for each band we need.
BAND_ASSETS: dict[str, str] = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B08": "nir",
    "B8A": "nir08",
}


# ─── Public API ───────────────────────────────────────────────────────────────


def fetch_sentinel2_bands(
    bbox: tuple[float, float, float, float],
    output_dir: Path,
    lookback_days: int = 45,
    max_cloud_pct: float = 40.0,
) -> Path | None:
    """Search Earth Search for the least-cloudy Sentinel-2 L2A scene and clip each band.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.
        output_dir: Directory to write ``{BAND}.tif`` files into.
        lookback_days: How many days back to search from today.
        max_cloud_pct: Maximum acceptable cloud cover percentage.

    Returns:
        ``output_dir`` (Path) when all bands were written successfully,
        or ``None`` if no matching scene was found or any band read failed.
    """
    import httpx

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    min_lon, min_lat, max_lon, max_lat = bbox

    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=lookback_days)
    datetime_str = f"{start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "datetime": datetime_str,
        "query": {"eo:cloud_cover": {"lt": max_cloud_pct}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        "limit": 5,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_EARTH_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("stac_sentinel: STAC search failed: %s", exc)
        return None

    features = data.get("features", [])
    if not features:
        logger.info(
            "stac_sentinel: no scenes found for bbox=%s lookback=%d days cloud<%.0f%%",
            bbox, lookback_days, max_cloud_pct,
        )
        return None

    # Pick the item with the lowest cloud cover (already sorted, but be explicit).
    best = min(
        features,
        key=lambda f: f.get("properties", {}).get("eo:cloud_cover", 999),
    )
    cloud = best.get("properties", {}).get("eo:cloud_cover", "?")
    scene_id = best.get("id", "unknown")
    logger.info("stac_sentinel: selected scene %s (cloud_cover=%.1f%%)", scene_id, float(cloud) if cloud != "?" else 0)

    assets = best.get("assets", {})

    for band, asset_name in BAND_ASSETS.items():
        asset = assets.get(asset_name)
        if asset is None:
            logger.warning("stac_sentinel: asset '%s' (band %s) missing from scene %s", asset_name, band, scene_id)
            return None

        href = asset.get("href")
        if not href:
            logger.warning("stac_sentinel: asset '%s' has no href", asset_name)
            return None

        out_path = output_dir / f"{band}.tif"
        try:
            _read_cog_clip(href, bbox, out_path)
        except Exception as exc:
            logger.warning("stac_sentinel: failed to clip band %s from %s: %s", band, href, exc)
            return None

    logger.info("stac_sentinel: all bands written to %s", output_dir)
    return output_dir


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _read_cog_clip(
    url: str,
    bbox: tuple[float, float, float, float],
    out_path: Path,
    target_size: int = 256,
) -> None:
    """Read a window from a Cloud-Optimized GeoTIFF via HTTP and save as uint16 GeoTIFF.

    The COG is typically in a UTM projection; we reproject the bbox corners into
    the raster CRS for windowed reading, then warp the clipped array back to
    EPSG:4326 before writing.

    Args:
        url: HTTP(S) URL to the COG (rasterio handles vsicurl automatically).
        bbox: (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.
        out_path: Destination path for the output GeoTIFF.
        target_size: Approximate output raster dimension (used as height/width hint).
    """
    from pyproj import Transformer

    min_lon, min_lat, max_lon, max_lat = bbox

    with rasterio.open(url) as src:
        # Reproject bbox corners from EPSG:4326 to the raster's native CRS.
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x1, y1 = transformer.transform(min_lon, min_lat)
        x2, y2 = transformer.transform(max_lon, max_lat)

        # Build the window in native CRS coordinates.
        win = rasterio.windows.from_bounds(
            min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2),
            transform=src.transform,
        )

        # Read the window as float32 so we can reproject without integer overflow.
        arr = src.read(1, window=win, out_dtype="float32")
        win_transform = src.window_transform(win)
        src_crs = src.crs

    # Reproject arr from the UTM CRS to EPSG:4326.
    dst_crs = rasterio.crs.CRS.from_epsg(4326)
    dst_transform, dst_width, dst_height = rasterio.warp.calculate_default_transform(
        src_crs, dst_crs,
        arr.shape[1], arr.shape[0],
        left=min(x1, x2), bottom=min(y1, y2), right=max(x1, x2), top=max(y1, y2),
    )

    dst_arr = np.zeros((dst_height, dst_width), dtype=np.float32)
    rasterio.warp.reproject(
        source=arr,
        destination=dst_arr,
        src_transform=win_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=rasterio.warp.Resampling.bilinear,
    )

    # Convert float32 to uint16 (Sentinel-2 L2A values are typically 0–10000).
    out_arr = np.clip(dst_arr, 0, 65535).astype(np.uint16)

    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=dst_height,
        width=dst_width,
        count=1,
        dtype="uint16",
        crs=dst_crs,
        transform=dst_transform,
    ) as dst:
        dst.write(out_arr, 1)
