"""Add staff.display_name.

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-21 20:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.add_column(
        "staff",
        sa.Column("display_name", sa.String(), server_default="", nullable=False),
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_column("staff", "display_name")
