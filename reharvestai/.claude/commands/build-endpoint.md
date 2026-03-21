---
description: Build a complete FastAPI endpoint from scratch — stub first,
  then real DB implementation, then cache layer if applicable.
argument-hint: "<endpoint description e.g. GET /fields/{field_id}/zones>"
---

Build this endpoint: $ARGUMENTS

Follow this exact sequence using subagents:

Step 1 — Read first (main context):
Read backend/app/models/ to find the relevant Pydantic response model.
Read backend/schema.sql to understand the tables involved.

Step 2 — @api-router stub:
Build the stub version of the endpoint returning hardcoded mock data
that exactly matches the Pydantic response model shape.
Confirm the stub is reachable at the correct path before proceeding.

Step 3 — @api-router real implementation:
Replace mock data with real asyncpg query.
If this is a GET endpoint for zones or scores, add Redis cache layer.
Add error handling: 404 if field not found, 500 with safe error message on DB error.

Step 4 — verify:
Run: cd backend && python -c "from app.routers import *; print('imports ok')"
Confirm no import errors before finishing.

Return: the final route handler code and the curl command to test it.
