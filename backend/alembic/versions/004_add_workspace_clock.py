"""Add plant clock to workspace model and table.

Revision ID: 004_add_workspace_clock
Revises: 003_add_lifecycle_clock
Create Date: 2026-10-19 17:00:00.000000

Governed by DATA_AND_API.md Section 1.1, ARCHITECTURE.md, and Milestone 15A.1.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_add_workspace_clock"
down_revision: str | None = "003_add_lifecycle_clock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add current_time_minute column and check constraint to workspaces table."""
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(
            sa.Column("current_time_minute", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "chk_workspace_current_time_non_negative",
            "current_time_minute >= 0",
        )


def downgrade() -> None:
    """Revert current_time_minute column and check constraint on workspaces table."""
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_constraint("chk_workspace_current_time_non_negative", type_="check")
        batch_op.drop_column("current_time_minute")
