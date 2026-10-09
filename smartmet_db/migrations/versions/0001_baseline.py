"""Baseline: batches, readings, alerts (the schema of phases 2-5).

Databases created before migrations existed already have these tables;
`python -m smartmet_db migrate` marks them as being at this revision.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("product", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'finished', 'aborted')", name="batch_status_valid"),
    )
    op.create_table(
        "readings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("temperature_c", sa.Float()),
        sa.Column("ph", sa.Float()),
        sa.Column("brix", sa.Float()),
        sa.Column("turbidity_ntu", sa.Float()),
        sa.Column("ethanol_percent", sa.Float()),
        sa.Column("simulation", postgresql.JSONB()),
        sa.UniqueConstraint("batch_id", "measured_at", "source", name="reading_unique"),
        sa.CheckConstraint("source IN ('simulated', 'device', 'manual')", name="reading_source_valid"),
        sa.CheckConstraint("temperature_c BETWEEN -50 AND 150", name="temperature_range"),
        sa.CheckConstraint("ph BETWEEN 0 AND 14", name="ph_range"),
        sa.CheckConstraint("brix BETWEEN 0 AND 100", name="brix_range"),
        sa.CheckConstraint("turbidity_ntu >= 0", name="turbidity_range"),
        sa.CheckConstraint("ethanol_percent BETWEEN 0 AND 100", name="ethanol_range"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule", sa.String(40), nullable=False),
        sa.Column("measurement", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="alert_severity_valid"),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="alert_status_valid"),
    )
    op.create_index("ix_alerts_batch_id", "alerts", ["batch_id"])
    op.create_index("one_open_alert", "alerts", ["batch_id", "rule", "measurement"], unique=True,
                    postgresql_where=sa.text("status = 'open'"))


def downgrade():
    op.drop_table("alerts")
    op.drop_table("readings")
    op.drop_table("batches")
