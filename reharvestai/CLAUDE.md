# ReHarvestAI — Claude Code Master Instructions

## Project Overview
Full-stack precision agriculture platform. Next.js 14 frontend dashboard,
Python FastAPI backend, PostgreSQL+PostGIS database, Celery task queue,
Redis cache. AI agent layer uses LangGraph. SAM3 for field segmentation.
Sentinel-2 satellite data via sentinelsat. See /docs/architecture.md.

## Stack Quick Reference
- Frontend: Next.js 14 (App Router), Mapbox GL JS, Recharts, TailwindCSS
- Backend: FastAPI, SQLAlchemy, Alembic, Celery, Redis
- Database: PostgreSQL 15 + PostGIS 3.4
- AI/ML: LangGraph, SAM3 (Meta), Claude claude-sonnet-4-6 via Anthropic SDK
- Satellite: sentinelsat, rasterio, numpy, shapely
- Infra: Docker Compose (dev), Railway (prod)

## Commands to Know
- `make dev` — starts all services via Docker Compose
- `make test` — runs pytest (backend) and vitest (frontend)
- `make migrate` — runs Alembic migrations
- `make pipeline` — triggers a manual Celery satellite pipeline run
- `cd frontend && pnpm dev` — starts Next.js dev server

## Security Rules
- Never read .env, .env.*, or secrets/**
- Never commit API keys or tokens
- All Celery tasks must be idempotent (safe to retry)

# ReHarvestAI — Person 2: FastAPI Backend & AI Agent

## My scope
backend/app/main.py
backend/app/config.py
backend/app/database.py
backend/app/redis.py
backend/app/routers/fields.py
backend/app/routers/zones.py
backend/app/routers/recommendations.py
backend/app/routers/agent.py
backend/app/agent/state.py
backend/app/agent/graph.py
backend/app/agent/checkpointer.py
backend/app/agent/nodes/context_builder.py
backend/app/agent/nodes/zone_classifier.py
backend/app/agent/nodes/risk_evaluator.py
backend/app/agent/nodes/action_generator.py
backend/app/agent/nodes/output_formatter.py
+ run_harvest_agent() task added to backend/pipeline/tasks.py

## Do NOT touch
backend/pipeline/sentinel.py
backend/pipeline/raster.py
backend/pipeline/indices.py
backend/pipeline/segmentation.py
backend/pipeline/db_writer.py
backend/pipeline/celery_app.py
backend/app/models/          ← Person 1 owns this
backend/schema.sql           ← Person 1 owns this
frontend/                    ← Person 3 owns this

## Stack
FastAPI, asyncpg, aioredis, LangGraph, anthropic Python SDK,
pydantic-settings, uvicorn, celery (import only, Person 1 instantiates)

## Models I import (Person 1 writes these — never modify them)
from app.models.field import FieldCreate, FieldResponse
from app.models.zone import ZoneResponse
from app.models.recommendation import RecommendationResponse, RecommendationUpdate
from app.models.alert import AlertResponse

## Database schema (Person 1 owns schema.sql — I read/write against these tables)

### fields
id uuid PK, farmer_id uuid, name text, polygon geometry(Polygon,4326),
crop_type text, planting_date date, created_at timestamptz

### zones
id uuid PK, field_id uuid FK fields, polygon geometry(Polygon,4326),
label text, created_at timestamptz

### ndvi_timeseries
id uuid PK, zone_id uuid FK zones, ndvi float, ndwi float, ndre float,
captured_at timestamptz

### recommendations
id uuid PK, field_id uuid FK fields, zone_id uuid FK zones,
action_type text, urgency text, reason text, confidence float,
status text default 'pending', created_at timestamptz

### alerts
id uuid PK, field_id uuid FK fields, zone_id uuid FK zones,
type text, message text, severity text, sent_at timestamptz

### agent_traces
id uuid PK, field_id uuid FK fields, run_at timestamptz, trace jsonb

## API endpoints I own

POST   /fields
GET    /fields/{field_id}
GET    /fields
GET    /fields/{field_id}/zones        ← Redis cache first, DB fallback
GET    /fields/{field_id}/recommendations
PATCH  /recommendations/{id}
GET    /fields/{field_id}/agent/trace

## Redis caching rules
Key pattern:  zone_scores:{field_id}
TTL:          3600 seconds (1 hour)
Read pattern: check Redis → if miss, query DB → write result to Redis
Invalidation: output_formatter node clears this key after writing new recommendations
Never cache recommendations directly — always fresh from DB

## LangGraph agent node flow
context_builder → zone_classifier → risk_evaluator → action_generator → output_formatter

All nodes are in backend/app/agent/nodes/
AgentState TypedDict is in backend/app/agent/state.py
Graph is compiled in backend/app/agent/graph.py
Redis checkpointer is in backend/app/agent/checkpointer.py

## AgentState shape
field_id: str
field_lat: float
field_lon: float
crop_type: str
planting_date: str          ← ISO date string, not datetime object
days_since_planting: int
zones: list[dict]           ← each dict: zone_id, label, ndvi, ndwi, ndre, ndvi_delta
weather_forecast: dict      ← raw Open-Meteo response
zone_classifications: list[dict]
recommendations: list[dict]
reasoning_trace: list[dict] ← one entry per node: {node_name, inputs, outputs}

CRITICAL: All state values must be JSON-serializable at all times.
No numpy arrays, no datetime objects (use .isoformat()), no tensors.

## Open-Meteo API
GET https://api.open-meteo.com/v1/forecast
  ?latitude={lat}
  &longitude={lon}
  &daily=precipitation_sum,temperature_2m_min
  &forecast_days=7
Returns: { daily: { time: [], precipitation_sum: [], temperature_2m_min: [] } }
No API key required.

## LLM usage
Model: claude-sonnet-4-20250514
Client: anthropic Python SDK (sync client inside Celery tasks)
API key: from config.py → ANTHROPIC_API_KEY env var
Use structured output (tool_use) for zone_classifier and action_generator nodes
so responses are always parseable without fragile string parsing.

## Celery integration
I do NOT instantiate the Celery app — Person 1 does that in celery_app.py.
I only add run_harvest_agent(field_id) as a task to pipeline/tasks.py.
Import pattern:
  from pipeline.celery_app import celery_app
  @celery_app.task
  def run_harvest_agent(field_id: str): ...

## Zone classifier valid values
status: not_ready | approaching | harvest_now | past_peak | stressed
confidence: float 0.0–1.0

## Action generator valid values
action_type: harvest | irrigate | monitor | inspect
urgency: low | medium | high | critical

## Risk escalation rules (risk_evaluator)
Check zones with status harvest_now or approaching.
If precipitation_sum > 5mm within next 72hrs → escalate to critical
If temperature_2m_min < 2°C within next 72hrs → escalate to critical
Add risk_reason string explaining the escalation.

## Output formatter rules
1. Write all recommendations to recommendations table via asyncpg
2. Delete and rewrite Redis key zone_scores:{field_id}
3. For every recommendation with urgency = critical → insert row into alerts
4. Write full reasoning_trace list as JSONB to agent_traces table
   with field_id and current timestamp

## Stub-first strategy
Build all endpoints returning mock data before touching agent or DB logic.
Person 3 is unblocked the moment stubs exist.
Stub shape must exactly match final response shape — same field names, same types.

## Code conventions
- Type hints on every function signature, no bare dicts in return types
- asyncpg for all DB queries — no SQLAlchemy ORM at runtime
- All route handlers are async
- Pydantic v2 model_validate() not .parse_obj()
- Error responses use HTTPException with detail as a string
- Never log or return raw SQL errors to the client

