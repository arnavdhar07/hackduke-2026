"""output_formatter node — fifth and final node in the harvest-agent pipeline.

THIS IS THE ONLY NODE THAT WRITES TO THE DATABASE.

Steps:
1. Insert all recommendations into `recommendations` table via asyncpg
2. Delete Redis key `zone_scores:{field_id}` (invalidate cache)
3. For each recommendation with urgency = "critical" → insert row into `alerts`
4. Insert full reasoning_trace as JSONB into `agent_traces` table

Uses a sync Redis client (redis-py) because this node runs inside a Celery
task via asyncio.run() — no existing aioredis event loop is available.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import redis as redis_sync

logger = logging.getLogger("api.output_formatter")

from app.agent.state import AgentState, RecommendationOutput
from app.config import settings


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_SQL_INSERT_RECOMMENDATION = """
    INSERT INTO recommendations
        (field_id, zone_id, action_type, urgency, reason, confidence)
    VALUES ($1, $2, $3, $4, $5, $6)
"""

_SQL_INSERT_ALERT = """
    INSERT INTO alerts
        (field_id, zone_id, type, message, severity)
    VALUES ($1, $2, $3, $4, $5)
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alert_message(rec: RecommendationOutput) -> str:
    """Construct a human-readable alert message from a recommendation."""
    return (
        f"CRITICAL action required for zone '{rec['zone_label']}': "
        f"{rec['action_type'].upper()}. {rec['reason']}"
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def output_formatter(state: AgentState) -> AgentState:
    """Persist recommendations, alerts, and trace to the database; invalidate cache."""
    field_id: str = state["field_id"]
    recommendations: list[RecommendationOutput] = state.get("recommendations", [])
    reasoning_trace: list[dict] = state.get("reasoning_trace", [])

    # --- DB writes via asyncpg ---
    from app.database import pool as _pool

    if _pool is None:
        conn_pool: asyncpg.Pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=1,
            max_size=3,
            command_timeout=30,
        )
        _own_pool = True
    else:
        conn_pool = _pool
        _own_pool = False

    inserted_recommendations = 0
    inserted_alerts = 0

    logger.info("=== output_formatter: field=%s ===", field_id)
    logger.info("  recommendations (%d):", len(recommendations))
    for rec in recommendations:
        logger.info("    [%s] %s — %s (confidence=%.2f): %s",
                    rec["urgency"], rec.get("zone_label"), rec["action_type"],
                    rec["confidence"], rec["reason"])
    logger.info("  reasoning_trace nodes: %s", [e.get("node_name") for e in reasoning_trace])

    try:
        async with conn_pool.acquire() as conn:
            async with conn.transaction():
                # 1. Insert recommendations
                for rec in recommendations:
                    await conn.execute(
                        _SQL_INSERT_RECOMMENDATION,
                        field_id,
                        rec["zone_id"],
                        rec["action_type"],
                        rec["urgency"],
                        rec["reason"],
                        rec["confidence"],
                    )
                    inserted_recommendations += 1

                # 3. Insert alerts for critical urgency
                for rec in recommendations:
                    if rec["urgency"] == "critical":
                        await conn.execute(
                            _SQL_INSERT_ALERT,
                            field_id,
                            rec["zone_id"],
                            rec["action_type"],
                            _alert_message(rec),
                            "critical",
                        )
                        inserted_alerts += 1

                # 4. Insert agent trace (same transaction, before pool closes)
                await conn.execute(
                    """
                    INSERT INTO agent_traces (id, field_id, run_at, trace)
                    VALUES ($1, $2, now(), $3)
                    """,
                    uuid.uuid4(),
                    uuid.UUID(field_id),
                    json.dumps(reasoning_trace),
                )
                logger.info("output_formatter: wrote trace (%d nodes) for field %s", len(reasoning_trace), field_id)

    finally:
        if _own_pool:
            await conn_pool.close()

    # 2. Invalidate Redis cache (sync redis-py client — safe from Celery context)
    try:
        r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
        r.delete(f"zone_scores:{field_id}")
        r.close()
        cache_invalidated = True
    except Exception:
        # Non-fatal — cache will expire naturally via TTL
        cache_invalidated = False

    # Trace entry for this node itself
    trace_entry: dict = {
        "node_name": "output_formatter",
        "inputs": {
            "recommendation_count": len(recommendations),
            "reasoning_trace_length": len(reasoning_trace),
        },
        "outputs": {
            "inserted_recommendations": inserted_recommendations,
            "inserted_alerts": inserted_alerts,
            "cache_invalidated": cache_invalidated,
        },
    }

    return {
        **state,
        "reasoning_trace": [*reasoning_trace, trace_entry],
    }
