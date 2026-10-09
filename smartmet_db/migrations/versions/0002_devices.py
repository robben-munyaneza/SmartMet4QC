"""Devices with API keys; readings remember which device measured them.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.String(64), unique=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batches.id", ondelete="SET NULL")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("readings", sa.Column(
        "device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL")))
    # Two devices may now measure the same batch at the same moment.
    op.drop_constraint("reading_unique", "readings", type_="unique")
    op.create_unique_constraint("reading_unique", "readings", ["batch_id", "measured_at", "source", "device_id"],
                                postgresql_nulls_not_distinct=True)


def downgrade():
    op.drop_constraint("reading_unique", "readings", type_="unique")
    op.create_unique_constraint("reading_unique", "readings", ["batch_id", "measured_at", "source"])
    op.drop_column("readings", "device_id")
    op.drop_table("devices")
