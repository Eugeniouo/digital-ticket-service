"""Drop unused department name.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-22 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.drop_column("department", "name")


def downgrade() -> None:
    """Undo the migration."""
    op.add_column("department", sa.Column("name", sa.String(), nullable=False, server_default=""))
    op.alter_column("department", "name", server_default=None)
