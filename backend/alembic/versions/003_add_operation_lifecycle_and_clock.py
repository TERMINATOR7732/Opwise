"""Add operation lifecycle columns and schedule plant clock.

Revision ID: 003_add_lifecycle_clock
Revises: 002_add_import_jobs_index
Create Date: 2026-10-19 14:00:00.000000

Governed by DATA_AND_API.md Section 1.1, ARCHITECTURE.md, and Milestone 15A.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_add_lifecycle_clock"
down_revision: str | None = "002_add_import_jobs_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add operation lifecycle columns and schedule plant clock."""
    with op.batch_alter_table("operations") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PLANNED")
        )
        batch_op.add_column(
            sa.Column("actual_start_minute", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("actual_end_minute", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("remaining_duration_minutes", sa.Integer(), nullable=True)
        )
        batch_op.create_check_constraint(
            "chk_op_status",
            "status IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED')",
        )
        batch_op.create_check_constraint(
            "chk_op_actual_start_non_negative",
            "actual_start_minute IS NULL OR actual_start_minute >= 0",
        )
        batch_op.create_check_constraint(
            "chk_op_actual_end_gt_start",
            "actual_end_minute IS NULL OR actual_start_minute IS NULL OR actual_end_minute > actual_start_minute",
        )
        batch_op.create_check_constraint(
            "chk_op_remaining_duration_positive",
            "remaining_duration_minutes IS NULL OR remaining_duration_minutes >= 1",
        )
        batch_op.create_check_constraint(
            "chk_op_lifecycle_consistency",
            "(status = 'PLANNED' AND actual_start_minute IS NULL AND actual_end_minute IS NULL AND remaining_duration_minutes IS NULL) OR "
            "(status = 'IN_PROGRESS' AND actual_start_minute IS NOT NULL AND actual_end_minute IS NULL AND remaining_duration_minutes IS NOT NULL) OR "
            "(status = 'COMPLETED' AND actual_start_minute IS NOT NULL AND actual_end_minute IS NOT NULL AND remaining_duration_minutes IS NULL)",
        )

    with op.batch_alter_table("schedules") as batch_op:
        batch_op.add_column(
            sa.Column("current_time_minute", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "chk_schedule_current_time_non_negative",
            "current_time_minute >= 0",
        )

    with op.batch_alter_table("scheduled_operations") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PLANNED")
        )
        batch_op.create_check_constraint(
            "chk_sched_op_status",
            "status IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED')",
        )


def downgrade() -> None:
    """Revert operation lifecycle columns and schedule plant clock."""
    with op.batch_alter_table("scheduled_operations") as batch_op:
        batch_op.drop_constraint("chk_sched_op_status", type_="check")
        batch_op.drop_column("status")

    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_constraint("chk_schedule_current_time_non_negative", type_="check")
        batch_op.drop_column("current_time_minute")

    with op.batch_alter_table("operations") as batch_op:
        batch_op.drop_constraint("chk_op_lifecycle_consistency", type_="check")
        batch_op.drop_constraint("chk_op_remaining_duration_positive", type_="check")
        batch_op.drop_constraint("chk_op_actual_end_gt_start", type_="check")
        batch_op.drop_constraint("chk_op_actual_start_non_negative", type_="check")
        batch_op.drop_constraint("chk_op_status", type_="check")
        batch_op.drop_column("remaining_duration_minutes")
        batch_op.drop_column("actual_end_minute")
        batch_op.drop_column("actual_start_minute")
        batch_op.drop_column("status")
