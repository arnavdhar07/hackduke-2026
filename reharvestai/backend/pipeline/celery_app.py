"""Celery application instance for ReHarvestAI.

Person 1 owns this file — only import from here, never re-instantiate.
Import pattern everywhere else:
    from pipeline.celery_app import celery_app
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "reharvestai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["pipeline.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # ack after task completes (safer for retries)
    worker_prefetch_multiplier=1,  # one task at a time per worker process
    result_expires=3600,
)
