"""Sentinel-2 satellite data acquisition via sentinelsat / Copernicus Data Space.

Downloads the most recent cloud-free Sentinel-2 L2A product for a given
field polygon and returns the path to the SAFE directory.

Falls back gracefully: if no product is found within the lookback window,
or if credentials are missing, raises SentinelDataUnavailable so the caller
can switch to mock data.

Dependencies: sentinelsat, shapely
Credentials: COPERNICUS_USER + COPERNICUS_PASSWORD in .env
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# How far back to look for a cloud-free image (days)
LOOKBACK_DAYS = 30
MAX_CLOUD_COVER = 20  # percent


class SentinelDataUnavailable(Exception):
    """Raised when no suitable Sentinel-2 product can be retrieved."""


def download_latest_scene(
    polygon_geojson: dict[str, Any],
    output_dir: Path | None = None,
) -> Path:
    """Download the most recent Sentinel-2 L2A scene covering the polygon.

    Args:
        polygon_geojson: GeoJSON Polygon dict in EPSG:4326.
        output_dir: Where to save the SAFE directory (defaults to a temp dir).

    Returns:
        Path to the downloaded .SAFE directory.

    Raises:
        SentinelDataUnavailable: if no suitable product is found or credentials
            are missing/invalid.
    """
    from app.config import settings

    user = settings.copernicus_user
    password = settings.copernicus_password

    if not user or not password:
        raise SentinelDataUnavailable(
            "COPERNICUS_USER and COPERNICUS_PASSWORD are not set"
        )

    try:
        from sentinelsat import SentinelAPI, geojson_to_wkt, read_geojson
    except ImportError:
        raise SentinelDataUnavailable("sentinelsat is not installed")

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="sentinel_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    api = SentinelAPI(user, password, "https://apihub.copernicus.eu/apihub")

    # Build WKT footprint from polygon
    from shapely.geometry import shape
    footprint = shape(polygon_geojson).wkt

    date_end = date.today()
    date_start = date_end - timedelta(days=LOOKBACK_DAYS)

    logger.info(
        "Querying Sentinel-2 L2A scenes from %s to %s (cloud ≤ %d%%)",
        date_start.isoformat(),
        date_end.isoformat(),
        MAX_CLOUD_COVER,
    )

    products = api.query(
        area=footprint,
        date=(date_start.strftime("%Y%m%d"), date_end.strftime("%Y%m%d")),
        platformname="Sentinel-2",
        producttype="S2MSI2A",
        cloudcoverpercentage=(0, MAX_CLOUD_COVER),
    )

    if not products:
        raise SentinelDataUnavailable(
            f"No Sentinel-2 L2A products found in the last {LOOKBACK_DAYS} days "
            f"with cloud cover ≤ {MAX_CLOUD_COVER}%"
        )

    # Pick most recent product
    products_df = api.to_dataframe(products).sort_values("ingestiondate", ascending=False)
    latest_product_id = products_df.index[0]
    product_info = products_df.loc[latest_product_id]
    logger.info("Downloading product: %s", product_info.get("title", latest_product_id))

    api.download(latest_product_id, directory_path=str(output_dir))

    safe_dirs = list(output_dir.glob("*.SAFE"))
    if not safe_dirs:
        raise SentinelDataUnavailable("Download succeeded but no .SAFE directory found")

    return safe_dirs[0]
