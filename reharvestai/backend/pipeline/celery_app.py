"""
celery_app.py — Celery application instance and beat schedule.

Both the worker and beat processes import this module to get the shared
celery_app object. Person 2's agent task (run_harvest_agent) is defined in
tasks.py in the same Celery app so it can be called from the pipeline.
"""
import os

from celery import Celery

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "reharvestai",
    broker=_REDIS_URL,
    backend=_REDIS_URL,
    include=["pipeline.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks with exponential back-off by default.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ─── Beat schedule ────────────────────────────────────────────────────────────
# A single dispatcher task fans out to all active fields every 5 days.
# This avoids needing to enumerate fields at beat startup time.
celery_app.conf.beat_schedule = {
    "dispatch-active-fields-every-5-days": {
        "task": "pipeline.dispatch_active_fields",
        "schedule": 5 * 24 * 60 * 60,  # seconds
        "options": {"queue": "celery"},
    }
}
