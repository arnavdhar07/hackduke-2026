-- ReHarvestAI PostgreSQL Schema
-- Requires PostGIS extension (postgis/postgis Docker image or manual install)

CREATE EXTENSION IF NOT EXISTS postgis;

-- ─── Fields ──────────────────────────────────────────────────────────────────
CREATE TABLE fields (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id     uuid        NOT NULL,
    name          text        NOT NULL,
    polygon       geometry(Polygon, 4326) NOT NULL,
    crop_type     text,
    planting_date date,
    active        boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- ─── Zones ───────────────────────────────────────────────────────────────────
-- Each pipeline run produces a fresh set of zones per field.
-- Zones are immutable once written; timeseries rows accumulate over runs.
CREATE TABLE zones (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id   uuid        NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    polygon    geometry(Polygon, 4326) NOT NULL,
    label      text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX zones_field_id_idx ON zones(field_id);

-- ─── NDVI Timeseries ─────────────────────────────────────────────────────────
-- All index values normalized to 0–100 before storage.
CREATE TABLE ndvi_timeseries (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id     uuid        NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    ndvi        float       NOT NULL,
    ndwi        float       NOT NULL,
    ndre        float       NOT NULL,
    captured_at timestamptz NOT NULL
);
CREATE INDEX ndvi_zone_time_idx ON ndvi_timeseries(zone_id, captured_at DESC);

-- ─── Recommendations ─────────────────────────────────────────────────────────
CREATE TABLE recommendations (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id    uuid        NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    zone_id     uuid        REFERENCES zones(id) ON DELETE SET NULL,
    action_type text        NOT NULL,
    urgency     text        NOT NULL,
    reason      text        NOT NULL,
    confidence  float       NOT NULL,
    status      text        NOT NULL DEFAULT 'pending',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recs_field_status_idx ON recommendations(field_id, status);

-- ─── Alerts ──────────────────────────────────────────────────────────────────
CREATE TABLE alerts (
    id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id uuid        NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    zone_id  uuid        REFERENCES zones(id) ON DELETE SET NULL,
    type     text        NOT NULL,
    message  text        NOT NULL,
    severity text        NOT NULL,
    sent_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX alerts_field_time_idx ON alerts(field_id, sent_at DESC);

-- ─── Agent Traces ─────────────────────────────────────────────────────────────
CREATE TABLE agent_traces (
    id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id uuid        NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    run_at   timestamptz NOT NULL DEFAULT now(),
    trace    jsonb       NOT NULL DEFAULT '{}'
);
CREATE INDEX agent_traces_field_idx ON agent_traces(field_id);
CREATE INDEX agent_traces_gin_idx   ON agent_traces USING GIN (trace);
