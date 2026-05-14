"""initial schema — batches, stations, operational_events

Revision ID: 001
Revises: (none)
Create Date: 2026-05-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── batches ────────────────────────────────────────────────────────────
    op.create_table(
        "batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("batch_code", sa.String(50), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("batch_code", name="uq_batches_batch_code"),
    )
    op.create_index("idx_batches_tenant", "batches", ["tenant_id"])

    # ── stations ───────────────────────────────────────────────────────────
    op.create_table(
        "stations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sequence_order", sa.Integer, nullable=False),
    )
    op.create_index("idx_stations_tenant", "stations", ["tenant_id"])

    # ── operational_events ─────────────────────────────────────────────────
    op.create_table(
        "operational_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("batches.id"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stations.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("device_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", UUID(as_uuid=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_status", sa.String(20), nullable=False, server_default="synced"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("idempotency_key", name="uq_events_idempotency_key"),
    )
    op.create_index("idx_events_tenant", "operational_events", ["tenant_id"])
    op.create_index("idx_events_batch_ts", "operational_events", ["batch_id", "ts"])
    op.create_index("idx_events_station_ts", "operational_events", ["station_id", "ts"])


def downgrade() -> None:
    op.drop_index("idx_events_station_ts", table_name="operational_events")
    op.drop_index("idx_events_batch_ts", table_name="operational_events")
    op.drop_index("idx_events_tenant", table_name="operational_events")
    op.drop_table("operational_events")

    op.drop_index("idx_stations_tenant", table_name="stations")
    op.drop_table("stations")

    op.drop_index("idx_batches_tenant", table_name="batches")
    op.drop_table("batches")
