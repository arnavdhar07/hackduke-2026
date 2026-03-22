from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import database
from app.models.field import AgentTraceNodeEntry, AgentTraceResponse

router = APIRouter(tags=["agent"])
logger = logging.getLogger("api.agent")


# ---------------------------------------------------------------------------
# GET /fields/{field_id}/agent/trace
# ---------------------------------------------------------------------------

@router.get(
    "/fields/{field_id}/agent/trace",
    response_model=AgentTraceResponse,
)
async def get_agent_trace(field_id: uuid.UUID) -> AgentTraceResponse:
    """Return the most recent LangGraph reasoning trace for a field.

    The ``trace`` column is stored as JSONB — asyncpg returns it as a Python
    list/dict already decoded, so no extra json.loads() is needed.
    """
    pool = await database.get_pool()

    try:
        row = await pool.fetchrow(
            """
            SELECT id, field_id, run_at, trace
            FROM agent_traces
            WHERE field_id = $1
            ORDER BY run_at DESC
            LIMIT 1
            """,
            field_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch agent trace")

    if row is None:
        logger.warning("agent/trace: no row in agent_traces for field %s", field_id)
        raise HTTPException(
            status_code=404,
            detail=f"No agent trace found for field {field_id}",
        )

    r = dict(row)

    # trace is jsonb — asyncpg decodes it to list[dict] automatically
    raw_trace = r["trace"]
    logger.info("agent/trace: field=%s raw_trace type=%s len=%s",
                field_id, type(raw_trace).__name__,
                len(raw_trace) if isinstance(raw_trace, (list, dict)) else "?")
    logger.info("agent/trace: raw content: %s", raw_trace)

    if isinstance(raw_trace, dict):
        raw_trace = raw_trace.get("nodes", [])
    if not isinstance(raw_trace, list):
        raw_trace = []

    trace_entries = [
        AgentTraceNodeEntry(
            node_name=entry.get("node_name", entry.get("name", "unknown")),
            inputs=entry.get("inputs", {}),
            outputs=entry.get("outputs", {}),
        )
        for entry in raw_trace
    ]

    return AgentTraceResponse(
        field_id=r["field_id"],
        run_at=r["run_at"],
        trace=trace_entries,
    )
