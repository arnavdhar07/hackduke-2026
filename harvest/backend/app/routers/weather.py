"""weather.py — GET /fields/{field_id}/weather

Fetches a 3-day forecast from Open-Meteo (free, no API key) using the
field's centroid lat/lon from the database.

Response shape matches the frontend WeatherForecast type exactly:
  { field_id, days: [{ date, temp_high_c, temp_low_c, precip_mm, condition, wind_kph }] }
"""
from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database

router = APIRouter(tags=["weather"])
logger = logging.getLogger("api.weather")

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_FORECAST_DAYS = 3


# ---------------------------------------------------------------------------
# Response models (mirrors frontend types/api.ts exactly)
# ---------------------------------------------------------------------------

class WeatherDay(BaseModel):
    date: str
    temp_high_c: float
    temp_low_c: float
    precip_mm: float
    condition: str        # "clear" | "cloudy" | "rain" | "storm"
    wind_kph: float


class WeatherForecast(BaseModel):
    field_id: str
    days: list[WeatherDay]


# ---------------------------------------------------------------------------
# WMO weather code → condition string
# ---------------------------------------------------------------------------

def _wmo_to_condition(code: int) -> str:
    """Map a WMO weather interpretation code to one of: clear/cloudy/rain/storm."""
    if code in (0, 1):
        return "clear"
    if code in (2, 3, 45, 48):
        return "cloudy"
    if 51 <= code <= 67 or 80 <= code <= 82 or 85 <= code <= 86:
        return "rain"
    if code in (71, 72, 73, 74, 75, 77):
        return "cloudy"   # snow — show as cloudy for non-snow regions
    if code in (95, 96, 99):
        return "storm"
    return "cloudy"       # safe fallback


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/fields/{field_id}/weather", response_model=WeatherForecast)
async def get_weather(field_id: uuid.UUID) -> WeatherForecast:
    """Return a 3-day weather forecast for the field's location."""
    pool = await database.get_pool()

    # Get field centroid from DB
    try:
        row = await pool.fetchrow(
            """
            SELECT
                ST_Y(ST_Centroid(polygon)) AS lat,
                ST_X(ST_Centroid(polygon)) AS lon
            FROM fields
            WHERE id = $1
            """,
            field_id,
        )
    except Exception as exc:
        logger.error("DB error fetching field centroid for %s: %s", field_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch field location")

    if row is None:
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found")

    lat = float(row["lat"])
    lon = float(row["lon"])
    logger.info("weather: field=%s lat=%.4f lon=%.4f", field_id, lat, lon)

    # Fetch from Open-Meteo
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _OPEN_METEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
                    "forecast_days": _FORECAST_DAYS,
                    "timezone": "auto",
                    "wind_speed_unit": "kmh",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Open-Meteo request failed for field %s: %s", field_id, exc)
        raise HTTPException(status_code=502, detail="Weather service unavailable")

    daily = data.get("daily", {})
    times: list[str] = daily.get("time", [])
    temp_max: list[float] = daily.get("temperature_2m_max", [])
    temp_min: list[float] = daily.get("temperature_2m_min", [])
    precip: list[float] = daily.get("precipitation_sum", [])
    codes: list[int] = daily.get("weathercode", [])
    wind: list[float] = daily.get("windspeed_10m_max", [])

    days: list[WeatherDay] = []
    for i in range(min(_FORECAST_DAYS, len(times))):
        days.append(WeatherDay(
            date=times[i],
            temp_high_c=round(temp_max[i] if i < len(temp_max) else 20.0, 1),
            temp_low_c=round(temp_min[i] if i < len(temp_min) else 10.0, 1),
            precip_mm=round(precip[i] if i < len(precip) else 0.0, 1),
            condition=_wmo_to_condition(int(codes[i]) if i < len(codes) else 0),
            wind_kph=round(wind[i] if i < len(wind) else 0.0, 1),
        ))

    logger.info("weather: field=%s → %d days fetched", field_id, len(days))
    return WeatherForecast(field_id=str(field_id), days=days)
