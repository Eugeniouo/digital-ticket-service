"""Scope staff username uniqueness to a department.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-09-22 16:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.drop_constraint("staff_username_key", "staff", type_="unique")
    op.create_index(
        "uq_staff_username_department",
        "staff",
        ["username", "department_id"],
        unique=True,
        postgresql_where=sa.text("department_id IS NOT NULL"),
    )
    op.create_index(
        "uq_staff_root_username",
        "staff",
        ["username"],
        unique=True,
        postgresql_where=sa.text("department_id IS NULL"),
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_index(
        "uq_staff_root_username",
        table_name="staff",
        postgresql_where=sa.text("department_id IS NULL"),
    )
    op.drop_index(
        "uq_staff_username_department",
        table_name="staff",
        postgresql_where=sa.text("department_id IS NOT NULL"),
    )
    op.create_unique_constraint("staff_username_key", "staff", ["username"])
