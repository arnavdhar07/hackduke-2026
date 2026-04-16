from __future__ import annotations

from typing import List, TypedDict


class ZoneScore(TypedDict):
    zone_id: str
    label: str
    ndvi: float
    ndwi: float
    ndre: float
    evi: float               # EVI2 — better than NDVI for dense canopies
    gndvi: float             # Green NDVI — late-season chlorophyll sensitivity
    savi: float              # Soil-Adjusted VI — better for sparse/early-season canopy
    cig: float               # Chlorophyll Index Green — nitrogen/chlorophyll status (0–100)
    zone_area_acres: float   # polygon area in acres for yield estimation
    ndvi_delta: float        # current ndvi minus ndvi from 7 days ago
    captured_at: str         # ISO string


class ZoneClassification(TypedDict):
    zone_id: str
    label: str
    status: str              # not_ready|approaching|harvest_now|past_peak|stressed
    confidence: float
    urgency: str             # low|medium|high|critical
    risk_reason: str         # empty string if no escalation
    days_remaining: int      # estimated days until harvest window closes (-1 if N/A)
    crop_health_rating: int  # 1-10 overall health score
    crop_health_summary: str # 2-sentence natural language health summary


class RecommendationOutput(TypedDict):
    zone_id: str
    zone_label: str
    action_type: str             # harvest|irrigate|monitor|inspect|fertilize|spray|scout|soil_sample
    urgency: str                 # low|medium|high|critical
    reason: str                  # 2 plain English sentences
    confidence: float
    estimated_yield_bushels: float  # estimated yield at risk in bushels
    days_remaining: int             # passed through from classification
    crop_health_rating: int         # passed through
    crop_health_summary: str        # passed through


class AgentState(TypedDict):
    field_id: str
    field_lat: float
    field_lon: float
    crop_type: str
    planting_date: str               # ISO date string, NOT datetime object
    days_since_planting: int
    days_since_satellite_pass: int   # days since last valid satellite observation
    growth_stage: str                # e.g. "vegetative", "grain_fill", "maturity"
    zones: List[ZoneScore]
    weather_forecast: dict           # raw Open-Meteo response
    zone_classifications: List[ZoneClassification]
    recommendations: List[RecommendationOutput]
    reasoning_trace: List[dict]      # one entry per node
