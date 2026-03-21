"""
tasks.py — Celery tasks for the ReHarvestAI satellite pipeline.

Task graph (Person 3 owns dispatch + field_analysis; Person 2 owns agent):
  dispatch_active_fields   (beat, every 5 days)        ← Person 3
      └─► run_field_analysis(field_id)                  ← Person 3
              └─► run_harvest_agent(field_id)           ← Person 2 (this file)

Person 3's run_field_analysis populates zones + ndvi_timeseries in the DB,
then calls run_harvest_agent.delay(field_id). This task reads that data,
runs the LangGraph agent, and writes recommendations/alerts/traces.
"""
from __future__ import annotations

import asyncio
import logging

from pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="pipeline.run_harvest_agent", max_retries=2)
def run_harvest_agent(self, field_id: str) -> dict:
    """Run the LangGraph harvest-recommendation agent for a field.

    Called automatically by Person 3's run_field_analysis after the satellite
    pipeline has written fresh zone scores to the DB.

    Args:
        field_id: UUID string of the field to analyse.

    Returns:
        {"field_id": str, "recommendation_count": int, "critical_alert_count": int}
    """
    try:
        return asyncio.run(_run_agent(field_id))
    except Exception as exc:
        logger.exception("run_harvest_agent failed for field_id=%s: %s", field_id, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _run_agent(field_id: str) -> dict:
    """Async core — runs in a fresh event loop via asyncio.run()."""
    import app.database as db_module
    from app.agent.graph import build_graph
    from app.agent.state import AgentState

    await db_module.init_db_pool()

    try:
        graph = build_graph()

        initial_state: AgentState = {
            "field_id": field_id,
            "field_lat": 0.0,
            "field_lon": 0.0,
            "crop_type": "",
            "planting_date": "",
            "days_since_planting": 0,
            "zones": [],
            "weather_forecast": {},
            "zone_classifications": [],
            "recommendations": [],
            "reasoning_trace": [],
        }

        final_state: AgentState = await graph.ainvoke(initial_state)

        recommendations = final_state.get("recommendations", [])
        critical_count = sum(1 for r in recommendations if r.get("urgency") == "critical")

        logger.info(
            "run_harvest_agent completed for field_id=%s: %d recommendations, %d critical",
            field_id, len(recommendations), critical_count,
        )

        return {
            "field_id": field_id,
            "recommendation_count": len(recommendations),
            "critical_alert_count": critical_count,
        }

    finally:
        await db_module.close_db_pool()
