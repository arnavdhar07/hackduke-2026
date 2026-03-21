"""Initial schema — applied via Supabase MCP.

Revision ID: 0001
Revises:
Create Date: 2026-03-21

NOTE: The schema was created directly via the Supabase MCP tool.
This migration file documents the schema as code and can be used to
re-apply it to a fresh PostgreSQL instance (e.g., local Docker or CI).
It is marked as already-applied by default via `alembic stamp 0001`.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute("""
        CREATE TABLE IF NOT EXISTS fields (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            farmer_id     uuid NOT NULL,
            name          text NOT NULL,
            polygon       geometry(Polygon, 4326) NOT NULL,
            crop_type     text NOT NULL,
            planting_date date NOT NULL,
            created_at    timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_fields_farmer_id ON fields(farmer_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS zones (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            field_id   uuid REFERENCES fields(id) ON DELETE CASCADE,
            polygon    geometry(Polygon, 4326) NOT NULL,
            label      text NOT NULL,
            created_at timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_zones_field_id ON zones(field_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ndvi_timeseries (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            zone_id     uuid REFERENCES zones(id) ON DELETE CASCADE,
            ndvi        float NOT NULL,
            ndwi        float NOT NULL,
            ndre        float NOT NULL,
            captured_at timestamptz NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ndvi_zone_captured ON ndvi_timeseries(zone_id, captured_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            field_id    uuid REFERENCES fields(id) ON DELETE CASCADE,
            zone_id     uuid REFERENCES zones(id) ON DELETE CASCADE,
            action_type text NOT NULL,
            urgency     text NOT NULL,
            reason      text NOT NULL,
            confidence  float NOT NULL,
            status      text DEFAULT 'pending',
            created_at  timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_field_status ON recommendations(field_id, status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            field_id uuid REFERENCES fields(id) ON DELETE CASCADE,
            zone_id  uuid REFERENCES zones(id) ON DELETE CASCADE,
            type     text NOT NULL,
            message  text NOT NULL,
            severity text NOT NULL,
            sent_at  timestamptz DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_field_id ON alerts(field_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_traces (
            id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            field_id uuid REFERENCES fields(id) ON DELETE CASCADE,
            run_at   timestamptz DEFAULT now(),
            trace    jsonb NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_traces_field_id ON agent_traces(field_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_traces CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS recommendations CASCADE")
    op.execute("DROP TABLE IF EXISTS ndvi_timeseries CASCADE")
    op.execute("DROP TABLE IF EXISTS zones CASCADE")
    op.execute("DROP TABLE IF EXISTS fields CASCADE")
