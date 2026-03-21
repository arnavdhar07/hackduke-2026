# ReHarvestAI — Satellite Pipeline & Database

## My scope
backend/pipeline/        ← all satellite + sam3 processing
backend/schema.sql       ← canonical PostgreSQL schema (I own this)
backend/app/models/      ← shared Pydantic v2 models (I define these first)
backend/alembic/         ← DB migrations

## My job
Fetch Sentinel-2 satellite imagery for a farm field, compute crop health
indexes per pixel, segment the field into zones using sam3, and write
zone scores into PostgreSQL every 5 days via Celery.

## Database schema I maintain

### fields
id uuid PK, farmer_id uuid, name text, polygon geometry(Polygon,4326),
crop_type text, planting_date date, active boolean default true, created_at timestamptz

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

## Sentinel-2 bands I use
B2 blue, B3 green, B4 red, B5 red-edge, B8 NIR, B8A narrow NIR, B11 SWIR

## Index formulas
NDVI = (B8 - B4) / (B8 + B4)   → vegetation health, primary ripeness signal
NDWI = (B3 - B8) / (B3 + B8)   → water stress
NDRE = (B8A - B5) / (B8A + B5) → early stress, more sensitive than NDVI

All indexes normalized to 0–100 for storage.

## sam3 usage
Run in automatic mask generation mode on RGB bands (B4/B3/B2).
Seed with a uniform grid of points across the field bounding box.
Returns a list of polygon masks — each becomes a zone.

## Pipeline flow (run_field_analysis task)
1. sentinel.py  — fetch GeoTIFF for field bbox
2. raster.py    — clip to field polygon, extract band arrays
3. indices.py   — compute NDVI/NDWI/NDRE per pixel
4. segmentation.py — sam3 → polygon masks
5. indices.py   — compute mean score per mask
6. db_writer.py — upsert zones + ndvi_timeseries
7. tasks.py     — emit run_harvest_agent(field_id) signal

## Celery
App instantiated in celery_app.py.
Beat schedule: run_field_analysis for every active field every 5 days.
Person 2 adds run_harvest_agent task to tasks.py — same Celery app instance.

## Pydantic models I write (backend/app/models/)
These are imported by Person 2's API and used to generate Person 3's
TypeScript types. Write them before anyone else starts.

field.py        — FieldCreate, FieldResponse
zone.py         — ZoneResponse (includes latest_scores and timeseries list)
recommendation.py — RecommendationResponse, RecommendationUpdate
alert.py        — AlertResponse

## Key dependencies
rasterio, numpy, scipy, pyproj, shapely, requests, pystac-client,
sam3 (segment-anything-3), asyncpg, celery[redis], redis,
sqlalchemy (for alembic only), pydantic-settings

## What I do NOT touch
backend/app/routers/   ← Person 2
backend/app/agent/     ← Person 2
frontend/              ← Person 3