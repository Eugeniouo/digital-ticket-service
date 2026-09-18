"""Create department table.

Revision ID: d37a91c2b604
Revises: 4e0998e40b2b
"""

import sqlalchemy as sa
from alembic import op

revision = "d37a91c2b604"
down_revision = "4e0998e40b2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "department",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("department")
