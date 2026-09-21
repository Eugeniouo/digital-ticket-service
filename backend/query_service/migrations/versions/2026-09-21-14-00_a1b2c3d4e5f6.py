"""Add ticket_status_history table.

Revision ID: a1b2c3d4e5f6
Revises: 956d1793ec6c
Create Date: 2026-09-21 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "956d1793ec6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    ticket_status = postgresql.ENUM(
        "queued",
        "called",
        "serving",
        "completed",
        "canceled",
        name="ticket_status",
        create_type=False,
    )
    change_reason = postgresql.ENUM(
        "issued",
        "called",
        "started",
        "completed",
        "canceled",
        "noshow",
        "requeued",
        "redirected",
        name="ticket_status_change_reason",
        create_type=False,
    )
    change_reason.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", ticket_status, nullable=True),
        sa.Column("new_status", ticket_status, nullable=False),
        sa.Column("reason", change_reason, nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=True),
        sa.Column("window_id", sa.Uuid(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["window_id"], ["window.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_status_history_ticket_id_changed_at_id",
        "ticket_status_history",
        ["ticket_id", "changed_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_index(
        "ix_ticket_status_history_ticket_id_changed_at_id",
        table_name="ticket_status_history",
    )
    op.drop_table("ticket_status_history")
    op.execute("DROP TYPE ticket_status_change_reason")
