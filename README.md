# Harvest

**Agentic precision agriculture platform that gives farmers zone-level, crop-specific field intelligence from real satellite imagery and AI-driven recommendations.**

---

## Problem Statement

Small and mid-scale farmers lose significant yield every season not because of bad farming, but because of delayed or missing information. Knowing *which part* of a field is stressed, *when exactly* the harvest window opens, and *what to do right now* requires either expensive agronomist consultations or manual scouting that takes days. By that time, the optimal harvest window has closed, an irrigation deficit has compounded, or a disease has spread across a zone.

Harvest solves this by autonomously processing satellite imagery and running a multi-step AI reasoning pipeline to deliver zone-level, urgency-ranked action recommendations — accessible through an interactive map dashboard, refreshed every time a farmer opens their field.

---

## What Harvest Does

Harvest lets a farmer draw their field boundary on an interactive map, enter their crop type and planting date, and immediately receive:

- A 2×2 zone breakdown of the field with NDVI, NDWI, and NDRE health scores derived from real Sentinel-2 satellite imagery
- AI-generated harvest readiness classifications per zone (not_ready / approaching / harvest_now / past_peak / stressed)
- Urgency-ranked action recommendations (harvest / irrigate / monitor / inspect) with weather-aware escalation
- Days remaining until harvest window closes, crop health ratings (1–10), and plain-English summaries per zone
- 7-day weather forecast integration that escalates urgency when rain or frost is imminent
- Live-updating sparklines of vegetation index trends over time
- Exportable HTML field reports

---

## Architecture Overview

```
[Browser] ──── Next.js 14 (App Router) ──── Mapbox GL JS interactive map
                       │
                  REST API (JSON)
                       │
[FastAPI Backend] ─────┤
   asyncpg             │──── PostgreSQL + PostGIS (Supabase)
   Redis cache         │──── Redis (zone score cache, 1hr TTL)
   BackgroundTask       │
         │
   [Synthetic Pipeline]
         │
         ├─ fetch_sentinel2_bands()    ← Element84 Earth Search STAC API
         │    HTTP range reads on S3-hosted Cloud-Optimized GeoTIFFs (COGs)
         │    No API key required
         │
         ├─ load_and_clip()            ← rasterio clips bands to field polygon
         │
         ├─ compute_pixel_indices()    ← per-pixel NDVI, NDWI, NDRE, EVI2
         │
         └─ [LangGraph AI Agent] ──────────────────────────────────────────┐
                 │                                                          │
          ┌──────▼──────────────────────────────────────────────────┐      │
          │  Node 1: context_builder                                 │      │
          │  • Queries fields + zones + ndvi_timeseries from DB      │      │
          │  • Fetches 7-day forecast from Open-Meteo API            │      │
          │  • Computes EVI2 from NDVI, ndvi_delta (7-day change)    │      │
          │  • Calculates days_since_planting, days_since_pass       │      │
          └──────┬──────────────────────────────────────────────────┘      │
                 │                                                          │
          ┌──────▼──────────────────────────────────────────────────┐      │
          │  Node 2: zone_classifier (Claude API, tool_use)          │      │
          │  • Classifies each zone: not_ready / approaching /       │      │
          │    harvest_now / past_peak / stressed                     │      │
          │  • Returns days_remaining, crop_health_rating (1-10),    │      │
          │    crop_health_summary (2-sentence plain English)         │      │
          │  • Crop-specific NDVI/NDWI/NDRE thresholds per species   │      │
          └──────┬──────────────────────────────────────────────────┘      │
                 │                                                          │
          ┌──────▼──────────────────────────────────────────────────┐      │
          │  Node 3: risk_evaluator (deterministic rules)            │      │
          │  • Escalates urgency to critical if:                     │      │
          │    – precipitation > 5mm within next 72h (harvest risk)  │      │
          │    – min temp < 2°C within next 72h (frost risk)         │      │
          └──────┬──────────────────────────────────────────────────┘      │
                 │                                                          │
          ┌──────▼──────────────────────────────────────────────────┐      │
          │  Node 4: action_generator (Claude API, tool_use)         │      │
          │  • Generates one recommendation per zone:                │      │
          │    action_type: harvest | irrigate | monitor | inspect   │      │
          │  • Estimates yield in bushels per zone (crop-specific    │      │
          │    base yields × area × NDVI adjustment)                 │      │
          │  • 2-sentence plain-English reason per recommendation    │      │
          └──────┬──────────────────────────────────────────────────┘      │
                 │                                                          │
          ┌──────▼──────────────────────────────────────────────────┐      │
          │  Node 5: output_formatter                                │      │
          │  • Writes recommendations to PostgreSQL                  │      │
          │  • Inserts critical-urgency alerts to alerts table       │      │
          │  • Persists full reasoning_trace as JSONB                │      │
          │  • Invalidates Redis zone score cache                    │      │
          └─────────────────────────────────────────────────────────┘      │
                                                                            │
          ──────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Flow

### 1. Field Creation
The farmer draws a polygon on the Mapbox GL JS map, selects their crop type and planting date, and submits. The `POST /api/v1/fields` endpoint inserts the field geometry into PostGIS and immediately launches a `BackgroundTask`.

### 2. Satellite Imagery Fetch
The background task (`run_synthetic_pipeline`) calls `fetch_sentinel2_bands()`, which queries the Element84 Earth Search STAC API for the least-cloudy Sentinel-2 L2A scene within the last 45 days. Band URLs (B02, B03, B04, B05, B08, B8A) from S3-hosted Cloud-Optimized GeoTIFF files are opened via `rasterio` HTTP virtual filesystem — only the spatial window intersecting the field polygon is read, not the full scene.

### 3. Index Computation
`load_and_clip()` reprojects all bands to a common CRS and clips them to the field polygon. `compute_pixel_indices()` computes per-pixel indices:
- **NDVI** = (NIR − Red) / (NIR + Red) — biomass and greenness
- **NDWI** = (Green − NIR) / (Green + NIR) — water content and stress
- **NDRE** = (NIR − RedEdge) / (NIR + RedEdge) — chlorophyll and early stress indicator
- **EVI2** = 2.5 × NDVI_raw / (1 + 2.4 × |NDVI_raw|) — enhanced vegetation index, more accurate at high canopy density

### 4. Zone Seeding
The field bbox is split into a 2×2 grid. Each quadrant is intersected with the actual drawn polygon (some may be clipped). Per-zone index averages are computed from the raster pixel masks. Two timeseries points are inserted into `ndvi_timeseries`: one from today and one from 10 days prior (5% higher, giving the AI a plausible `ndvi_delta` trend signal). If satellite fetch fails at any step, deterministic fallback values seeded from the field's UUID are used.

### 5. AI Agent Pipeline
Once zones are seeded, the five-node LangGraph agent runs:

1. **context_builder** — reads zones + timeseries from DB, fetches Open-Meteo 7-day forecast, computes EVI2 and zone areas via PostGIS, builds the full `AgentState`
2. **zone_classifier** — sends all zones to Claude (`claude-sonnet-4-20250514`) with forced `tool_use` structured output. Claude returns harvest readiness status, confidence, urgency, days remaining, crop health rating, and a 2-sentence health summary per zone
3. **risk_evaluator** — deterministic rules escalate urgency to `critical` if precipitation > 5mm or frost < 2°C is forecast within 72h
4. **action_generator** — sends classifications + weather context to Claude via `tool_use`. Returns one action recommendation per zone with reason, confidence, and estimated yield in bushels
5. **output_formatter** — writes recommendations to PostgreSQL, inserts alert rows for critical-urgency zones, persists the full `reasoning_trace` JSON to `agent_traces`, and invalidates the Redis zone score cache

### 6. Frontend Polling
The Next.js frontend polls `GET /api/v1/fields/{id}/recommendations` every 3 seconds while loading (via TanStack Query). Once recommendations land in the database, they appear in the Action Queue sidebar sorted by urgency. The map renders zone polygons colored by NDVI health, with pulsing red urgency indicators for critical zones.

### 7. Farmer Actions
The farmer reviews each recommendation card showing: zone label, action type, urgency, days remaining until harvest window closes, crop health rating, weather countdown, confidence bar, and yield estimate. They can Accept, Defer, or Dismiss each recommendation. Accepted actions are tracked in the database; the action queue updates optimistically.

---

## Features

- **Real satellite imagery** — Sentinel-2 L2A via Element84 Earth Search STAC, COG HTTP range reads (no full scene downloads, no API key required)
- **Multi-band vegetation analysis** — NDVI, NDWI, NDRE, EVI2 computed per pixel then averaged per zone
- **Five-node LangGraph AI agent** — deterministic rules + two Claude API calls with forced structured output
- **Crop-specific reasoning** — zone classifier and action generator are prompted with crop type; thresholds and yield estimates are species-specific
- **Weather-aware risk escalation** — Open-Meteo 7-day forecast triggers critical urgency for imminent rain or frost
- **Interactive geospatial map** — Mapbox GL JS with draw tools, zone overlays colored by NDVI, tooltips, urgency pulse animations
- **Live-updating dashboard** — TanStack Query polling (3–60s adaptive intervals) with optimistic UI updates
- **Zone sparklines** — NDVI trend history plotted at the bottom of the dashboard
- **Detailed zone panel** — click any zone to see full index breakdown in a slide-in panel
- **Exportable reports** — one-click HTML field report with zone health table and recommendation summary
- **Redis zone cache** — zone scores cached for 1 hour (key: `zone_scores:{field_id}`), invalidated on agent completion
- **Full agent trace** — complete reasoning trace per node stored as JSONB; accessible via `GET /fields/{id}/agent/trace`
- **Graceful fallback** — if satellite fetch fails, deterministic values seeded from the field UUID ensure the dashboard always shows data

---

## Tech Stack

**Frontend**
- Next.js 14 (App Router), React, TypeScript
- Mapbox GL JS + @mapbox/mapbox-gl-draw (polygon drawing, zone overlays)
- TanStack Query (data fetching, polling, optimistic updates)
- Tailwind CSS
- Custom SVG sparklines, animated loading states

**Backend**
- FastAPI (Python), asyncpg (async PostgreSQL driver)
- LangGraph (five-node stateful agent pipeline)
- Anthropic Claude API (`claude-sonnet-4-20250514`) via Python SDK — structured output via `tool_use`
- Celery + Redis (background tasks and caching)
- httpx (async HTTP for Open-Meteo and STAC API)

**Database**
- PostgreSQL 15 + PostGIS 3.4 (hosted on Supabase)
- PostGIS functions: `ST_Intersection`, `ST_Area`, `ST_Transform`, `ST_Centroid`, `ST_GeomFromGeoJSON`, `ST_AsGeoJSON`

**Satellite & Geospatial**
- Element84 Earth Search STAC API (Sentinel-2 L2A scene search)
- rasterio + GDAL (Cloud-Optimized GeoTIFF HTTP range reads, band clipping, reprojection)
- numpy (per-pixel index computation)
- Shapely, PyProj (coordinate transforms and polygon operations)

**Infrastructure**
- Docker Compose (Redis, FastAPI backend, Celery worker)
- Supabase (managed PostgreSQL + PostGIS, no self-hosted DB)
- Open-Meteo API (7-day weather forecast, no API key required)

---

## Database Schema

```sql
fields           — field polygon, crop type, planting date (PostGIS geometry)
zones            — 2×2 quadrant polygons clipped to field boundary
ndvi_timeseries  — per-zone NDVI/NDWI/NDRE measurements with timestamps
recommendations  — AI-generated actions per zone (action_type, urgency, status)
alerts           — critical-urgency notifications
agent_traces     — full LangGraph reasoning trace as JSONB per agent run
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/fields` | Create field, trigger satellite pipeline |
| `GET` | `/api/v1/fields` | List all fields |
| `GET` | `/api/v1/fields/{id}` | Get single field |
| `DELETE` | `/api/v1/fields/{id}` | Delete field and all related data |
| `GET` | `/api/v1/fields/{id}/zones` | Zone scores (Redis cache → DB) |
| `GET` | `/api/v1/fields/{id}/recommendations` | AI recommendations |
| `PATCH` | `/api/v1/recommendations/{id}` | Update recommendation status |
| `GET` | `/api/v1/fields/{id}/agent/trace` | Full LangGraph reasoning trace |
| `GET` | `/api/v1/fields/{id}/weather` | 7-day weather forecast |

---

## Local Development

```bash
# Prerequisites: Docker, Node.js 20+, Python 3.11+, uv

# 1. Copy environment variables
cp harvest/backend/.env.example harvest/backend/.env
# Fill in: DATABASE_URL, ANTHROPIC_API_KEY, MAPBOX_TOKEN

# 2. Start backend services (Redis + FastAPI + Celery)
cd harvest
docker compose up

# 3. Start frontend
cd harvest/frontend
pnpm install
pnpm dev

# Open http://localhost:3000
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (Supabase) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `REDIS_URL` | Redis connection URL |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Mapbox public access token |
| `NEXT_PUBLIC_API_BASE` | Backend API base URL |

---

Built for HackDuke 2026.
