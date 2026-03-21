from __future__ import annotations

from typing import List, TypedDict


class ZoneScore(TypedDict):
    zone_id: str
    label: str
    ndvi: float
    ndwi: float
    ndre: float
    ndvi_delta: float        # current ndvi minus ndvi from 7 days ago
    captured_at: str         # ISO string


class ZoneClassification(TypedDict):
    zone_id: str
    label: str
    status: str              # not_ready|approaching|harvest_now|past_peak|stressed
    confidence: float
    urgency: str             # low|medium|high|critical
    risk_reason: str         # empty string if no escalation


class RecommendationOutput(TypedDict):
    zone_id: str
    zone_label: str
    action_type: str         # harvest|irrigate|monitor|inspect
    urgency: str             # low|medium|high|critical
    reason: str              # 2 plain English sentences
    confidence: float


class AgentState(TypedDict):
    field_id: str
    field_lat: float
    field_lon: float
    crop_type: str
    planting_date: str           # ISO date string, NOT datetime object
    days_since_planting: int
    zones: List[ZoneScore]
    weather_forecast: dict       # raw Open-Meteo response
    zone_classifications: List[ZoneClassification]
    recommendations: List[RecommendationOutput]
    reasoning_trace: List[dict]  # one entry per node
