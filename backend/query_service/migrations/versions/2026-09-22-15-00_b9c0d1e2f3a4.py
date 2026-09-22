"""Add window_open_service for the operator shift subset.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-09-22 12:15:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.create_table(
        "window_open_service",
        sa.Column("window_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["service.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["window_id"], ["window.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("window_id", "service_id"),
    )
    op.create_index("ix_window_open_service_service_id", "window_open_service", ["service_id"], unique=False)
    op.create_foreign_key(
        "fk_window_open_service_catalog",
        "window_open_service",
        "window_service",
        ["window_id", "service_id"],
        ["window_id", "service_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_constraint("fk_window_open_service_catalog", "window_open_service", type_="foreignkey")
    op.drop_index("ix_window_open_service_service_id", table_name="window_open_service")
    op.drop_table("window_open_service")
