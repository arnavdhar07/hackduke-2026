from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class FieldCreate(BaseModel):
    farmer_id: UUID
    name: str
    polygon: dict  # GeoJSON Polygon object
    crop_type: str | None = None
    planting_date: date | None = None
    active: bool = True


class FieldResponse(BaseModel):
    id: UUID
    farmer_id: UUID
    name: str
    polygon: dict  # GeoJSON Polygon object
    crop_type: str | None
    planting_date: date | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
