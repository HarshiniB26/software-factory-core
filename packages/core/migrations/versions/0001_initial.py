"""Initial schema: append-only events, requests, registry, state.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=200), nullable=False),
        sa.Column("module", sa.String(length=200), nullable=True),
        sa.Column("config_hash", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "seq", name="uq_events_request_seq"),
    )
    op.create_index("ix_events_request_id", "events", ["request_id"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION factory_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'events are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_append_only
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION factory_reject_mutation()
        """
    )
    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=500), nullable=True),
        sa.Column("requester", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "agent_specs",
        sa.Column("agent_id", sa.String(length=200), primary_key=True),
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "skill_pins",
        sa.Column("skill_id", sa.String(length=200), primary_key=True),
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "state",
        sa.Column("key", sa.String(length=500), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("state")
    op.drop_table("skill_pins")
    op.drop_table("agent_specs")
    op.drop_table("requests")
    op.execute("DROP TRIGGER IF EXISTS events_append_only ON events")
    op.execute("DROP FUNCTION IF EXISTS factory_reject_mutation()")
    op.drop_index("ix_events_request_id", table_name="events")
    op.drop_table("events")
