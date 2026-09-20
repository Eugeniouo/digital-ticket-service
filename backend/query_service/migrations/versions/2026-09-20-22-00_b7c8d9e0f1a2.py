"""Add staff table and window.current_operator_id FK.

Revision ID: b7c8d9e0f1a2
Revises: c4a7e19b2d01
Create Date: 2026-09-20 22:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "c4a7e19b2d01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.create_table(
        "staff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("operator", "admin", "root", name="staff_role"),
            nullable=False,
        ),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "(role IN ('operator', 'admin') AND department_id IS NOT NULL)"
            " OR (role = 'root' AND department_id IS NULL)",
            name="ck_staff_role_department",
        ),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_foreign_key(
        "fk_window_current_operator_id",
        "window",
        "staff",
        ["current_operator_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_constraint("fk_window_current_operator_id", "window", type_="foreignkey")
    op.drop_table("staff")
    op.execute("DROP TYPE staff_role")
