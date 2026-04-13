from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app import database
from app.models.field import FieldCreate, FieldResponse, GeoJSON
from app.synthetic_pipeline import run_synthetic_pipeline

router = APIRouter(prefix="/fields", tags=["fields"])


# -----------------------------------------------------------------
# ----------
# POST /fields — create a new field
# ---------------------------------------------------------------------------

@router.post("", response_model=FieldResponse, status_code=201)
async def create_field(body: FieldCreate, background_tasks: BackgroundTasks) -> FieldResponse:
    """Insert a new field polygon into the database and return the persisted row."""
    pool = await database.get_pool()

    polygon_json = body.polygon.model_dump_json()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO fields (farmer_id, name, polygon, crop_type, planting_date)
            VALUES ($1, $2, ST_GeomFromGeoJSON($3), $4, $5)
            RETURNING
                id,
                farmer_id,
                name,
                ST_AsGeoJSON(polygon)::json AS polygon,
                crop_type,
                planting_date,
                created_at
            """,
            body.farmer_id,
            body.name,
            polygon_json,
            body.crop_type,
            body.planting_date,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create field")

    if row is None:
        raise HTTPException(status_code=500, detail="Insert returned no row")

    field_response = _row_to_field_response(dict(row))
    background_tasks.add_task(run_synthetic_pipeline, str(field_response.id))
    return field_response


# ---------------------------------------------------------------------------
# GET /fields/{field_id} — fetch a single field
# ---------------------------------------------------------------------------

@router.get("/{field_id}", response_model=FieldResponse)
async def get_field(field_id: uuid.UUID) -> FieldResponse:
    """Fetch a single field by its UUID."""
    pool = await database.get_pool()

    try:
        row = await pool.fetchrow(
            """
            SELECT
                id,
                farmer_id,
                name,
                ST_AsGeoJSON(polygon)::json AS polygon,
                crop_type,
                planting_date,
                created_at
            FROM fields
            WHERE id = $1
            """,
            field_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch field")

    if row is None:
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found")

    return _row_to_field_response(dict(row))


# ---------------------------------------------------------------------------
# GET /fields — list all fields
# ---------------------------------------------------------------------------

@router.get("", response_model=list[FieldResponse])
async def list_fields() -> list[FieldResponse]:
    """Return all fields ordered by creation time (newest first)."""
    pool = await database.get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT
                id,
                farmer_id,
                name,
                ST_AsGeoJSON(polygon)::json AS polygon,
                crop_type,
                planting_date,
                created_at
            FROM fields
            ORDER BY created_at DESC
            """
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list fields")

    return [_row_to_field_response(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# DELETE /fields/{field_id} — delete a field and its cascaded data
# ---------------------------------------------------------------------------

@router.delete("/{field_id}", status_code=204)
async def delete_field(field_id: uuid.UUID) -> None:
    """Delete a field and all associated zones, timeseries, recommendations, alerts."""
    pool = await database.get_pool()
    result = await pool.execute("DELETE FROM fields WHERE id = $1", field_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"Field {field_id} not found")


# ---------------------------------------------------------------------------
# POST /fields/{field_id}/analyze — re-run the satellite pipeline
# ---------------------------------------------------------------------------

@router.post("/{field_id}/analyze", status_code=202)
async def trigger_analysis(field_id: uuid.UUID, background_tasks: BackgroundTasks) -> dict:
    """Re-run the satellite pipeline + AI agent for a field."""
    pool = await database.get_pool()
    row = await pool.fetchrow("SELECT id FROM fields WHERE id = $1", field_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Field not found")
    background_tasks.add_task(run_synthetic_pipeline, str(field_id))
    return {"status": "analysis_started", "field_id": str(field_id)}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _row_to_field_response(row: dict) -> FieldResponse:
    """Convert a raw asyncpg row dict to a FieldResponse.

    asyncpg returns:
    - ``id`` / ``farmer_id`` as ``uuid.UUID`` objects
    - ``polygon`` as the result of ``::json`` cast — asyncpg decodes it to a
      plain Python dict automatically when the column alias type is json/jsonb
    """
    polygon_raw = row["polygon"]
    if isinstance(polygon_raw, str):
        polygon_raw = json.loads(polygon_raw)

    return FieldResponse(
        id=row["id"],
        farmer_id=row["farmer_id"],
        name=row["name"],
        polygon=GeoJSON(**polygon_raw),
        crop_type=row["crop_type"],
        planting_date=row["planting_date"],
        created_at=row["created_at"],
    )
