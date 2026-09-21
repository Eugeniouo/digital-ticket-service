"""Index tickets for day analytics.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-21 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.create_index(
        "ix_tickets_department_completed_at",
        "tickets",
        ["department_id", "completed_at"],
        unique=False,
        postgresql_where=sa.text("completed_at IS NOT NULL"),
    )
    op.create_index(
        "ix_tickets_department_created_at",
        "tickets",
        ["department_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_index("ix_tickets_department_created_at", table_name="tickets")
    op.drop_index("ix_tickets_department_completed_at", table_name="tickets")
