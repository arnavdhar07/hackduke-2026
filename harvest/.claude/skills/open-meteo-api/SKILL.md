---
description: Inject when writing the context_builder node that fetches
  weather forecast data from Open-Meteo for risk evaluation.
---

## Open-Meteo forecast call
```python
import httpx

async def fetch_weather_forecast(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum,temperature_2m_min",
        "forecast_days": 7,
        "timezone": "auto"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
```

## Response shape
```json
{
  "latitude": 52.5,
  "longitude": 13.4,
  "daily": {
    "time": ["2025-03-21", "2025-03-22", "2025-03-23", "..."],
    "precipitation_sum": [0.0, 2.3, 8.1, 0.0, 1.2, 0.0, 0.0],
    "temperature_2m_min": [5.2, 4.1, 1.8, 3.0, 6.2, 7.1, 5.5]
  }
}
```

## Risk evaluator logic using this data
```python
def check_72hr_risk(forecast: dict) -> tuple[bool, bool, str]:
    """Returns (rain_risk, frost_risk, risk_reason)"""
    daily = forecast["daily"]
    # Only check first 3 days (72 hours)
    precip_3day = daily["precipitation_sum"][:3]
    temp_3day = daily["temperature_2m_min"][:3]

    rain_risk = any(p is not None and p > 5.0 for p in precip_3day)
    frost_risk = any(t is not None and t < 2.0 for t in temp_3day)

    reasons = []
    if rain_risk:
        max_rain = max(p for p in precip_3day if p is not None)
        reasons.append(f"Rain forecast {max_rain:.1f}mm within 72 hours")
    if frost_risk:
        min_temp = min(t for t in temp_3day if t is not None)
        reasons.append(f"Frost risk {min_temp:.1f}°C within 72 hours")

    return rain_risk, frost_risk, ". ".join(reasons)
```

## Gotchas
- timezone=auto is required — without it dates return in UTC which may
  misalign with local harvest windows
- precipitation_sum can be None (null) in the response if data is unavailable
  — always guard: p is not None and p > 5.0
- The daily arrays always have exactly forecast_days entries — safe to slice [:3]
- No API key needed — Open-Meteo is free with no auth
