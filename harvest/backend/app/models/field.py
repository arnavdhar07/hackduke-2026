from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# GeoJSON primitives
# ---------------------------------------------------------------------------

class GeoJSON(BaseModel):
    type: str
    coordinates: Any


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------

class FieldCreate(BaseModel):
    name: str
    polygon: GeoJSON
    crop_type: str
    planting_date: date
    farmer_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))


class FieldResponse(BaseModel):
    id: UUID
    farmer_id: UUID
    name: str
    polygon: GeoJSON
    crop_type: str
    planting_date: date
    created_at: datetime


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

class ZoneScore(BaseModel):
    ndvi: float
    ndwi: float
    ndre: float
    captured_at: datetime


class ZoneResponse(BaseModel):
    id: UUID
    field_id: UUID
    label: str
    polygon: GeoJSON
    latest_scores: ZoneScore
    timeseries: list[ZoneScore]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class RecommendationResponse(BaseModel):
    id: UUID
    field_id: UUID
    zone_id: UUID | None
    zone_label: str | None
    action_type: str
    urgency: str
    reason: str
    confidence: float
    status: str
    estimated_yield_bushels: float = 0.0
    days_remaining: int = -1
    crop_health_rating: int = 0
    crop_health_summary: str = ""
    created_at: datetime


class RecommendationUpdate(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Agent trace
# ---------------------------------------------------------------------------

class AgentTraceNodeEntry(BaseModel):
    name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]


class AgentTraceResponse(BaseModel):
    field_id: UUID
    run_at: datetime
    nodes: list[AgentTraceNodeEntry]
