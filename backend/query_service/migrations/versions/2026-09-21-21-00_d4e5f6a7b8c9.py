"""Keep the issued channel after redirect.

Revision ID: d4e5f6a7b8c9
Revises: d5e6f7a8b9c0
Create Date: 2026-09-21 21:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    ticket_source = postgresql.ENUM(
        "web",
        "qr",
        "walk-in",
        name="ticket_source",
        create_type=False,
    )
    op.add_column("tickets", sa.Column("origin_source", ticket_source, nullable=True))
    op.add_column("tickets", sa.Column("origin_slot_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tickets_origin_slot_id_slot",
        "tickets",
        "slot",
        ["origin_slot_id"],
        ["id"],
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_constraint("fk_tickets_origin_slot_id_slot", "tickets", type_="foreignkey")
    op.drop_column("tickets", "origin_slot_id")
    op.drop_column("tickets", "origin_source")
