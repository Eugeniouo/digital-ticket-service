"""Store queue priority rules on department.

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-09-21 23:54:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.add_column("department", sa.Column("queue_bonus_web", sa.Integer(), nullable=False, server_default="300"))
    op.add_column("department", sa.Column("queue_bonus_qr", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("department", sa.Column("queue_bonus_walk_in", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("department", sa.Column("queue_max_wait_web", sa.Integer(), nullable=False, server_default="900"))
    op.add_column("department", sa.Column("queue_max_wait_qr", sa.Integer(), nullable=False, server_default="1200"))
    op.add_column("department", sa.Column("queue_max_wait_walk_in", sa.Integer(), nullable=False, server_default="1200"))

    # Existing WEB keys stored slot_start - env bonus (300). Store slot_start only.
    op.execute("UPDATE tickets SET priority_key = priority_key + 300 WHERE source = 'web'")


def downgrade() -> None:
    """Undo the migration."""
    op.execute("UPDATE tickets SET priority_key = priority_key - 300 WHERE source = 'web'")

    op.drop_column("department", "queue_max_wait_walk_in")
    op.drop_column("department", "queue_max_wait_qr")
    op.drop_column("department", "queue_max_wait_web")
    op.drop_column("department", "queue_bonus_walk_in")
    op.drop_column("department", "queue_bonus_qr")
    op.drop_column("department", "queue_bonus_web")
