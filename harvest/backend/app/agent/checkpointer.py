from __future__ import annotations


def get_redis_checkpointer():
    """Return None for now — LangGraph compiles fine without a checkpointer.
    Replace with a real Redis-backed checkpointer when persistence is needed."""
    return None
