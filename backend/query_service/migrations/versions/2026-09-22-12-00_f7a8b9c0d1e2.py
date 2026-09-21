"""Add unique short code on department.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-22 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.add_column("department", sa.Column("code", sa.String(length=16), nullable=True))
    op.execute(
        """
        UPDATE department AS d
        SET code = lpad(s.rn::text, 6, '0')
        FROM (
            SELECT id, row_number() OVER (ORDER BY name, id) AS rn
            FROM department
        ) AS s
        WHERE d.id = s.id
        """,
    )
    op.alter_column("department", "code", nullable=False)
    op.create_unique_constraint("uq_department_code", "department", ["code"])


def downgrade() -> None:
    """Undo the migration."""
    op.drop_constraint("uq_department_code", "department", type_="unique")
    op.drop_column("department", "code")
