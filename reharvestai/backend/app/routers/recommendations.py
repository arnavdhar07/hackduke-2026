from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import database
from app.models.field import RecommendationResponse, RecommendationUpdate

router = APIRouter(tags=["recommendations"])
logger = logging.getLogger("api.recommendations")


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
                r.id, r.field_id, r.zone_id, r.action_type, r.urgency,
                r.reason, r.confidence, r.status, r.created_at,
                r.estimated_yield_bushels, r.days_remaining,
                r.crop_health_rating, r.crop_health_summary,
                COALESCE(z.label, '') AS zone_label
            FROM recommendations r
            LEFT JOIN zones z ON z.id = r.zone_id
            WHERE r.field_id = $1
              AND r.status = 'pending'
            ORDER BY r.created_at DESC
            """,
            field_id,
        )
    except Exception as exc:
        logger.error("DB error fetching recommendations for %s: %s", field_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch recommendations")

    logger.info(
        "recommendations for field %s → %d pending rows",
        field_id, len(rows),
    )

    if not rows:
        # Check if there are any recommendations at all (any status) so we know why
        try:
            pool2 = await database.get_pool()
            all_rows = await pool2.fetch(
                "SELECT status, COUNT(*) FROM recommendations WHERE field_id = $1 GROUP BY status",
                field_id,
            )
            if all_rows:
                summary = {dict(r)["status"]: dict(r)["count"] for r in all_rows}
                logger.info("  → non-pending recs exist for field %s: %s", field_id, summary)
            else:
                logger.info("  → NO recommendations at all for field %s (pipeline hasn't run yet?)", field_id)
        except Exception:
            pass

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
            UPDATE recommendations SET status = $1 WHERE id = $2
            RETURNING id, field_id, zone_id, action_type, urgency,
                      reason, confidence, status, created_at,
                      estimated_yield_bushels, days_remaining,
                      crop_health_rating, crop_health_summary,
                      (SELECT label FROM zones WHERE id = zone_id) AS zone_label
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

    rec = dict(row)

    if body.status == "accepted":
        # Get field name for the todo
        field_row = await pool.fetchrow(
            "SELECT name FROM fields WHERE id = $1", rec["field_id"]
        )
        field_name = field_row["name"] if field_row else "Unknown Field"
        await pool.execute(
            """INSERT INTO todos
               (field_id, recommendation_id, action_type, zone_label, field_name, urgency)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT DO NOTHING""",
            rec["field_id"],
            rec["id"],
            rec["action_type"],
            rec.get("zone_label", ""),
            field_name,
            rec["urgency"],
        )

    return _row_to_rec(rec)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _row_to_rec(row: dict) -> RecommendationResponse:
    return RecommendationResponse(
        id=row["id"],
        field_id=row["field_id"],
        zone_id=row["zone_id"],
        zone_label=row.get("zone_label") or "",
        action_type=row["action_type"],
        urgency=row["urgency"],
        reason=row["reason"],
        confidence=row["confidence"],
        status=row["status"],
        created_at=row["created_at"],
        estimated_yield_bushels=row.get("estimated_yield_bushels") or 0.0,
        days_remaining=row.get("days_remaining") if row.get("days_remaining") is not None else -1,
        crop_health_rating=row.get("crop_health_rating") or 0,
        crop_health_summary=row.get("crop_health_summary") or "",
    )
