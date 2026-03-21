-- ReHarvestAI Database Schema
-- Applied to Supabase (PostgreSQL 17 + PostGIS)
-- This file is for reference; migrations are managed by Alembic.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE fields (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id    uuid NOT NULL,
  name         text NOT NULL,
  polygon      geometry(Polygon, 4326) NOT NULL,
  crop_type    text NOT NULL,
  planting_date date NOT NULL,
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX idx_fields_farmer_id ON fields(farmer_id);

CREATE TABLE zones (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id   uuid REFERENCES fields(id) ON DELETE CASCADE,
  polygon    geometry(Polygon, 4326) NOT NULL,
  label      text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_zones_field_id ON zones(field_id);

CREATE TABLE ndvi_timeseries (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  zone_id     uuid REFERENCES zones(id) ON DELETE CASCADE,
  ndvi        float NOT NULL,
  ndwi        float NOT NULL,
  ndre        float NOT NULL,
  captured_at timestamptz NOT NULL
);
CREATE INDEX idx_ndvi_zone_captured ON ndvi_timeseries(zone_id, captured_at DESC);

CREATE TABLE recommendations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id    uuid REFERENCES fields(id) ON DELETE CASCADE,
  zone_id     uuid REFERENCES zones(id) ON DELETE CASCADE,
  action_type text NOT NULL,
  urgency     text NOT NULL,
  reason      text NOT NULL,
  confidence  float NOT NULL,
  status      text DEFAULT 'pending',
  created_at  timestamptz DEFAULT now()
);
CREATE INDEX idx_recommendations_field_status ON recommendations(field_id, status);

CREATE TABLE alerts (
  id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id uuid REFERENCES fields(id) ON DELETE CASCADE,
  zone_id  uuid REFERENCES zones(id) ON DELETE CASCADE,
  type     text NOT NULL,
  message  text NOT NULL,
  severity text NOT NULL,
  sent_at  timestamptz DEFAULT now()
);
CREATE INDEX idx_alerts_field_id ON alerts(field_id);

CREATE TABLE agent_traces (
  id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id uuid REFERENCES fields(id) ON DELETE CASCADE,
  run_at   timestamptz DEFAULT now(),
  trace    jsonb NOT NULL
);
CREATE INDEX idx_agent_traces_field_id ON agent_traces(field_id);
