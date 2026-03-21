# ReHarvestAI — Frontend Dashboard

## Project Overview
ReHarvestAI is a precision agriculture web app that uses Sentinel-2 satellite
imagery to monitor farm fields and tell farmers exactly when and where to
harvest. It segments fields into zones, computes NDVI/NDWI/NDRE crop health
scores per zone, fuses that with weather forecasts, and runs an AI agent that
produces ranked plain-English recommendations like "harvest zone A in 72 hours
— rain is coming and it's at peak ripeness."

My job is to build everything the farmer sees and interacts with. I talk
exclusively to a FastAPI backend at http://localhost:8000. I do not touch
anything in backend/.

## My Scope
Everything under frontend/

## Stack
- Next.js 14 (App Router)
- TailwindCSS
- Mapbox GL JS + Mapbox GL Draw
- TanStack Query v5
- Recharts

## Routes
- /onboarding            → farmer draws field polygon, enters crop type + planting date
- /dashboard/[field_id]  → main dashboard, map + sidebar + zone detail panel

## Project File Structure
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                        ← redirect to /onboarding
│   │   ├── onboarding/
│   │   │   └── page.tsx
│   │   └── dashboard/
│   │       └── [field_id]/
│   │           └── page.tsx
│   ├── components/
│   │   ├── map/
│   │   │   ├── FieldMap.tsx                ← Mapbox base map
│   │   │   ├── ZoneLayer.tsx               ← GeoJSON zone polygons
│   │   │   ├── UrgencyPulse.tsx            ← animated critical zone marker
│   │   │   └── ZoneTooltip.tsx
│   │   ├── sidebar/
│   │   │   ├── ActionQueue.tsx             ← recommendation cards list
│   │   │   ├── RecommendationCard.tsx
│   │   │   └── AgentTraceModal.tsx         ← Why? reasoning trace modal
│   │   ├── panels/
│   │   │   ├── ZoneDetailPanel.tsx         ← slide-in on zone click
│   │   │   └── NDVIChart.tsx               ← Recharts timeseries chart
│   │   └── ui/
│   │       ├── Badge.tsx
│   │       ├── Toast.tsx
│   │       └── StatCard.tsx
│   ├── hooks/
│   │   ├── useZones.ts
│   │   ├── useRecommendations.ts           ← 60s polling + critical toast
│   │   └── useAgentTrace.ts
│   ├── lib/
│   │   ├── api.ts                          ← typed fetch wrapper
│   │   ├── mapbox.ts                       ← Mapbox init + NDVI color helper
│   │   └── colors.ts                       ← all color constants
│   └── types/
│       └── api.ts                          ← auto-generated from OpenAPI spec

## API Base URL
http://localhost:8000
All calls go through src/lib/api.ts

## TypeScript Types
Auto-generated from FastAPI OpenAPI spec once backend is running:
  npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
Until then, manually maintain types in src/types/api.ts using the shapes below.

## API Endpoints

### POST /fields
body:    { name: string, polygon: GeoJSON.Polygon, crop_type: string, planting_date: string }
returns: { id: string, name: string, polygon: GeoJSON.Polygon, crop_type: string, planting_date: string }

### GET /fields/{field_id}
returns: { id: string, name: string, polygon: GeoJSON.Polygon, crop_type: string, planting_date: string }

### GET /fields/{field_id}/zones
returns: Zone[]

Zone shape:
{
  id: string
  field_id: string
  label: string
  polygon: GeoJSON.Polygon
  latest_scores: {
    ndvi: number        // 0–100
    ndwi: number        // 0–100
    ndre: number        // 0–100
    captured_at: string // ISO datetime
  }
  timeseries: {
    ndvi: number
    ndwi: number
    ndre: number
    captured_at: string
  }[]
}

### GET /fields/{field_id}/recommendations
returns: Recommendation[]

Recommendation shape:
{
  id: string
  field_id: string
  zone_id: string
  zone_label: string
  action_type: "harvest" | "irrigate" | "monitor" | "inspect"
  urgency: "low" | "medium" | "high" | "critical"
  reason: string        // 2 sentences, plain English
  confidence: number    // 0–1
  status: "pending" | "accepted" | "deferred" | "dismissed"
  created_at: string
}

### PATCH /recommendations/{id}
body:    { status: "accepted" | "deferred" | "dismissed" }
returns: Recommendation

### GET /fields/{field_id}/agent/trace
returns:
{
  field_id: string
  run_at: string
  nodes: {
    name: string      // e.g. "context_builder", "zone_classifier"
    inputs: object
    outputs: object
  }[]
}

## Color Constants (src/lib/colors.ts)

NDVI color ramp (scores 0–100):
  0–40   → #ef4444  red
  40–65  → #f59e0b  amber
  65–80  → #84cc16  yellow-green
  80–100 → #16a34a  deep green

function ndviColor(score: number): string {
  if (score < 40) return "#ef4444"
  if (score < 65) return "#f59e0b"
  if (score < 80) return "#84cc16"
  return "#16a34a"
}

Urgency colors:
  low      → #6b7280  grey
  medium   → #3b82f6  blue
  high     → #f97316  orange
  critical → #ef4444  red + Tailwind animate-pulse

## Mapbox Config
Basemap style: mapbox://styles/mapbox/dark-v11
Token: process.env.NEXT_PUBLIC_MAPBOX_TOKEN

## Component Responsibilities

### FieldMap.tsx
Mapbox base map. Handles map initialization, ref, and exposes map instance
to child components. Used on both onboarding and dashboard.

### ZoneLayer.tsx
Fetches zones via useZones hook. Renders each zone as a GeoJSON fill layer
on the Mapbox map. Colors each polygon using ndviColor(zone.latest_scores.ndvi).
On zone click, calls onZoneSelect callback to open ZoneDetailPanel.

### UrgencyPulse.tsx
For each recommendation with urgency = critical, renders an animated pulsing
circle on the map centered on that zone's polygon centroid.

### ZoneTooltip.tsx
Hover tooltip on zone polygons showing zone label and current NDVI score.

### ActionQueue.tsx
Scrollable list of RecommendationCards. Fetches from useRecommendations hook.
Renders cards ordered by urgency descending.

### RecommendationCard.tsx
Single recommendation card showing: zone label, action_type as colored Badge,
urgency indicator, 2-sentence reason text. Three buttons: Accept, Defer,
Dismiss — each calls PATCH /recommendations/{id} with optimistic UI update.
Why? button opens AgentTraceModal.

### AgentTraceModal.tsx
Modal opened by Why? button. Fetches /fields/{field_id}/agent/trace.
Renders each LangGraph node (context_builder, zone_classifier, risk_evaluator,
action_generator, output_formatter) as a collapsible section showing name,
inputs, and outputs. Styled readable for a non-technical farmer, not a
raw JSON dump.

### ZoneDetailPanel.tsx
Slide-in panel triggered by zone click on the map. Shows three StatCards
for current NDVI, NDWI, NDRE scores. Below that renders NDVIChart with the
zone's full season timeseries data.

### NDVIChart.tsx
Recharts LineChart of NDVI over the full season. X axis is captured_at dates,
Y axis is NDVI score 0–100. Uses #16a34a as line color.

### Badge.tsx
Colored pill badge. Used for action_type on recommendation cards.

### StatCard.tsx
Small card showing a label and a number. Used for NDVI/NDWI/NDRE in the
zone detail panel.

### Toast.tsx
Bottom-right toast notification. Triggered when a new critical recommendation
appears in the polling cycle.

## Hook Responsibilities

### useZones.ts
React Query fetch of /fields/{field_id}/zones. No polling, refetch on
field_id change.

### useRecommendations.ts
React Query fetch of /fields/{field_id}/recommendations with refetchInterval
of 60000ms. On each refetch, compare new results against previous — if any
new item has urgency = critical that wasn't in the prior result set, fire
Toast with that recommendation's reason text.

### useAgentTrace.ts
React Query fetch of /fields/{field_id}/agent/trace. Fetches on demand
(enabled: false by default, triggered by Why? button click).

## Page Responsibilities

### /onboarding/page.tsx
Full-screen Mapbox map with dark basemap. Mapbox GL Draw enabled in polygon
mode. Form overlay (bottom or side) with fields: farm name, crop type
(select), planting date (date picker). On submit: POST /fields with polygon
from Draw + form values. On success: router.push(/dashboard/{id}).

### /dashboard/[field_id]/page.tsx
Main dashboard. Layout: 65% left = FieldMap with ZoneLayer + UrgencyPulse,
35% right = ActionQueue sidebar. When a zone is clicked, ZoneDetailPanel
slides in below or alongside the sidebar. Mobile responsive. Page fetches
field data on load to get lat/lon for map centering.

## Mocking Strategy
In src/lib/api.ts maintain a MOCK_MODE boolean flag. When true, all API
functions return hardcoded mock data matching the shapes above so the UI
can be built and tested before the backend is ready. Set MOCK_MODE = false
once Person 2's endpoints are live at http://localhost:8000.

Mock data should include:
- 1 field with a realistic polygon
- 3–4 zones with varying NDVI scores (one red, one amber, one green, one critical)
- 4 recommendations with mixed urgency levels including one critical
- 1 agent trace with all 5 nodes populated

## What I Do NOT Touch
backend/   ← Person 1 owns pipeline + schema, Person 2 owns API + agent
