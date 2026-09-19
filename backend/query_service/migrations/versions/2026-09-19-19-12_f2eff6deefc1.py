"""Add partial unique: one active ticket per window.

Revision ID: f2eff6deefc1
Revises: ec1cfc5ccb6d
Create Date: 2026-09-19 19:12:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f2eff6deefc1"
down_revision = "ec1cfc5ccb6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.create_index(
        "uq_ticket_one_active_per_window",
        "tickets",
        ["window_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('called', 'serving') AND window_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_index(
        "uq_ticket_one_active_per_window",
        table_name="tickets",
        postgresql_where=sa.text("status IN ('called', 'serving') AND window_id IS NOT NULL"),
    )
