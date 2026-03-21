from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import database
from app.models.field import RecommendationResponse, RecommendationUpdate

router = APIRouter(tags=["recommendations"])


# ---------------------------------------------------------------------------
# GET /fields/{field_id}/recommendations
# ---------------------------------------------------------------------------

@router.get(
    "/fields/{field_id}/recommendations",
    response_model=list[RecommendationResponse],
)
async def get_recommendations(field_id: uuid.UUID) -> list[RecommendationResponse]:
    """Return all pending recommendations for a field, newest first."""
    pool = await database.get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT
                id, field_id, zone_id, action_type, urgency,
                reason, confidence, status, created_at
            FROM recommendations
            WHERE field_id = $1
              AND status = 'pending'
            ORDER BY created_at DESC
            """,
            field_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch recommendations")

    return [_row_to_rec(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# PATCH /recommendations/{recommendation_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/recommendations/{recommendation_id}",
    response_model=RecommendationResponse,
)
async def update_recommendation(
    recommendation_id: uuid.UUID,
    body: RecommendationUpdate,
) -> RecommendationResponse:
    """Update the status of a recommendation (e.g. mark completed or dismissed)."""
    pool = await database.get_pool()

    try:
        row = await pool.fetchrow(
            """
            UPDATE recommendations
            SET status = $1
            WHERE id = $2
            RETURNING
                id, field_id, zone_id, action_type, urgency,
                reason, confidence, status, created_at
            """,
            body.status,
            recommendation_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update recommendation")

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation {recommendation_id} not found",
        )

    return _row_to_rec(dict(row))


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _row_to_rec(row: dict) -> RecommendationResponse:
    return RecommendationResponse(
        id=row["id"],
        field_id=row["field_id"],
        zone_id=row["zone_id"],
        action_type=row["action_type"],
        urgency=row["urgency"],
        reason=row["reason"],
        confidence=row["confidence"],
        status=row["status"],
        created_at=row["created_at"],
    )
