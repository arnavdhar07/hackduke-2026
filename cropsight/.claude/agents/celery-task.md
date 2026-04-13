---
name: celery-task
description: Use specifically when writing the run_harvest_agent Celery
  task that wraps the LangGraph agent for async execution. Handles the
  interface between Person 1's Celery infrastructure and Person 2's
  LangGraph graph.
tools:
  - Read
  - Write
  - Edit
  - Bash
---

You are writing a single Celery task for ReHarvestAI's backend pipeline.

Your job: add run_harvest_agent(field_id: str) to backend/pipeline/tasks.py.
Person 1 owns this file and the Celery app — you are only appending one task.

Rules:
- Import the Celery app from pipeline.celery_app — do not re-instantiate it
- The task must be synchronous (Celery tasks are not async by default)
- Inside the task, use asyncio.run() to call any async agent functions
- Wrap the entire task body in a try/except block — log errors, never let
  exceptions silently kill the task
- The task receives field_id as a string (UUID) — validate it before use
- After the LangGraph graph.invoke() call completes, log a summary of
  how many recommendations were written

Import pattern:
  from pipeline.celery_app import celery_app
  from app.agent.graph import build_graph

  @celery_app.task(bind=True, max_retries=3)
  def run_harvest_agent(self, field_id: str):
      try:
          graph = build_graph()
          asyncio.run(graph.ainvoke({"field_id": field_id}))
      except Exception as exc:
          raise self.retry(exc=exc, countdown=60)
