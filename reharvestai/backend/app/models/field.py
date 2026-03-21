from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Shared ────────────────────────────────────────────────────────────────────

class GeoJSON(BaseModel):
    type: str
    coordinates: Any


# ── Field ─────────────────────────────────────────────────────────────────────

class FieldCreate(BaseModel):
    farmer_id: uuid.UUID
    name: str
    polygon: GeoJSON
    crop_type: str
    planting_date: date


class FieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    farmer_id: uuid.UUID
    name: str
    polygon: GeoJSON
    crop_type: str
    planting_date: date
    created_at: datetime


# ── Zone ──────────────────────────────────────────────────────────────────────

class ZoneScore(BaseModel):
    ndvi: float
    ndwi: float
    ndre: float
    captured_at: str  # ISO string


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_id: uuid.UUID
    label: str
    polygon: GeoJSON
    latest_scores: ZoneScore | None = None
    timeseries: list[ZoneScore] = Field(default_factory=list)


# ── Recommendation ────────────────────────────────────────────────────────────

class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_id: uuid.UUID
    zone_id: uuid.UUID
    action_type: str   # harvest | irrigate | monitor | inspect
    urgency: str       # low | medium | high | critical
    reason: str
    confidence: float
    status: str        # pending | completed | dismissed
    created_at: datetime


class RecommendationUpdate(BaseModel):
    status: str


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_id: uuid.UUID
    zone_id: uuid.UUID
    type: str
    message: str
    severity: str
    sent_at: datetime


# ── Agent Trace ───────────────────────────────────────────────────────────────

class AgentTraceNodeEntry(BaseModel):
    # "name" matches the frontend shape; "node_name" is what our agent writes
    name: str = Field(alias="node_name", serialization_alias="name")
    inputs: dict[str, Any]
    outputs: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class AgentTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_id: uuid.UUID
    run_at: datetime
    # "nodes" matches the frontend shape
    nodes: list[AgentTraceNodeEntry] = Field(alias="trace", serialization_alias="nodes")
