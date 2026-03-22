---
description: Generate stub versions of all 7 API endpoints so Person 3
  can start frontend development immediately. Run this as the very first
  command at the start of the project.
---

Generate stub implementations for all 7 API endpoints in one pass.

Read backend/app/models/ first to get exact response model shapes.

Then spawn these subagents in parallel — they own different router files
with no overlap:

@api-router — build stubs for fields.py:
  POST /fields → return hardcoded FieldResponse with a fake UUID
  GET /fields/{field_id} → return hardcoded FieldResponse
  GET /fields → return list of 2 hardcoded FieldResponse objects

@api-router — build stubs for zones.py:
  GET /fields/{field_id}/zones → return list of 3 ZoneResponse objects
  with hardcoded NDVI scores: 85, 52, 31 (one per urgency tier)
  each with a 5-point timeseries array

@api-router — build stubs for recommendations.py:
  GET /fields/{field_id}/recommendations → return list of 3 recommendations
  with urgency: critical, high, low respectively
  PATCH /recommendations/{id} → accept body, return updated recommendation

@api-router — build stubs for agent.py:
  GET /fields/{field_id}/agent/trace → return hardcoded trace with all 5
  node names, dummy inputs and outputs per node

After all stubs are built, verify FastAPI starts:
  cd backend && uvicorn app.main:app --port 8000

Then message Person 3 that http://localhost:8000/openapi.json is ready
for type generation.
