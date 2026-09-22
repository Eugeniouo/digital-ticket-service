"""Add service.kind and widen ticket_counter.prefix.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-09-22 16:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    kind_values = (
        "parcel_receive",
        "parcel_send",
        "letters",
        "payments",
        "pension",
        "other",
    )
    postgresql.ENUM(*kind_values, name="service_kind").create(op.get_bind(), checkfirst=True)
    service_kind = postgresql.ENUM(*kind_values, name="service_kind", create_type=False)

    op.add_column(
        "service",
        sa.Column("kind", service_kind, nullable=False, server_default="other"),
    )
    op.alter_column(
        "ticket_counter",
        "prefix",
        existing_type=sa.String(length=5),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Undo the migration."""
    op.alter_column(
        "ticket_counter",
        "prefix",
        existing_type=sa.String(length=32),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
    op.drop_column("service", "kind")
    postgresql.ENUM(name="service_kind").drop(op.get_bind(), checkfirst=True)
