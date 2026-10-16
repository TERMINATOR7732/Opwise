"""Initial Opwise schema migration.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-16 12:00:00.000000

Governed by DATA_AND_API.md Section 1.1 and ARCHITECTURE.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_workspace_and_machine_tables() -> None:
    """Create workspaces, machines, and machine_downtimes tables."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_workspaces_name"),
    )
    op.create_table(
        "machines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_machines_workspace_external_id"),
    )
    op.create_index("ix_machines_workspace_id", "machines", ["workspace_id"])
    op.create_table(
        "machine_downtimes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint("start_minute >= 0", name="chk_downtime_start_non_negative"),
        sa.CheckConstraint("end_minute > start_minute", name="chk_downtime_end_gt_start"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_machine_downtimes_machine_start", "machine_downtimes", ["machine_id", "start_minute"])


def _create_order_and_operation_tables() -> None:
    """Create production_orders and operations tables."""
    op.create_table(
        "production_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("release_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_minute", sa.Integer(), nullable=False),
        sa.Column("tardiness_weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("release_minute >= 0", name="chk_order_release_non_negative"),
        sa.CheckConstraint("due_minute >= 0", name="chk_order_due_non_negative"),
        sa.CheckConstraint("tardiness_weight >= 0", name="chk_order_weight_non_negative"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_orders_workspace_external_id"),
    )
    op.create_index("ix_orders_workspace_id", "production_orders", ["workspace_id"])
    op.create_table(
        "operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=False),
        sa.Column("processing_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("sequence_index >= 1", name="chk_op_sequence_positive"),
        sa.CheckConstraint("processing_minutes >= 1", name="chk_op_processing_positive"),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["production_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "sequence_index", name="uq_operations_order_sequence"),
    )
    op.create_index("ix_operations_order_id", "operations", ["order_id"])
    op.create_index("ix_operations_machine_id", "operations", ["machine_id"])


def _create_schedule_tables() -> None:
    """Create schedules and scheduled_operations tables."""
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("objective_type", sa.String(length=32), nullable=False),
        sa.Column("solver_status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("objective_value", sa.Integer(), nullable=True),
        sa.Column("best_objective_bound", sa.Integer(), nullable=True),
        sa.Column("optimality_gap", sa.Float(), nullable=True),
        sa.Column("stage1_status", sa.String(length=32), nullable=True),
        sa.Column("stage1_objective_value", sa.Integer(), nullable=True),
        sa.Column("stage1_best_bound", sa.Integer(), nullable=True),
        sa.Column("stage1_wall_clock_seconds", sa.Float(), nullable=True),
        sa.Column("stage2_status", sa.String(length=32), nullable=True),
        sa.Column("stage2_objective_value", sa.Integer(), nullable=True),
        sa.Column("stage2_best_bound", sa.Integer(), nullable=True),
        sa.Column("stage2_wall_clock_seconds", sa.Float(), nullable=True),
        sa.Column("makespan_minutes", sa.Integer(), nullable=False),
        sa.Column("weighted_tardiness", sa.Integer(), nullable=False),
        sa.Column("late_order_count", sa.Integer(), nullable=False),
        sa.Column("on_time_rate", sa.Float(), nullable=False),
        sa.Column("solver_wall_clock_seconds", sa.Float(), nullable=False),
        sa.Column("solver_deterministic_time", sa.Float(), nullable=True),
        sa.Column("input_snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedules_workspace_created", "schedules", ["workspace_id", "created_at"])
    op.create_table(
        "scheduled_operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("processing_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("slack_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("start_minute >= 0", name="chk_sched_op_start_non_negative"),
        sa.CheckConstraint("end_minute > start_minute", name="chk_sched_op_end_gt_start"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_ops_machine_start", "scheduled_operations", ["schedule_id", "machine_id", "start_minute"])
    op.create_index("ix_scheduled_ops_order", "scheduled_operations", ["schedule_id", "order_id"])


def _create_scenario_and_import_tables() -> None:
    """Create scenarios, scenario_comparisons, and import_jobs tables."""
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("baseline_schedule_id", sa.String(length=36), nullable=False),
        sa.Column("reoptimized_schedule_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("disruption_type", sa.String(length=32), nullable=False),
        sa.Column("disruption_delta_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["baseline_schedule_id"], ["schedules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reoptimized_schedule_id"], ["schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenarios_workspace", "scenarios", ["workspace_id"])
    op.create_index("ix_scenarios_baseline", "scenarios", ["baseline_schedule_id"])
    op.create_table(
        "scenario_comparisons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("baseline_schedule_id", sa.String(length=36), nullable=False),
        sa.Column("compared_schedule_id", sa.String(length=36), nullable=False),
        sa.Column("delta_makespan", sa.Integer(), nullable=False),
        sa.Column("delta_weighted_tardiness", sa.Integer(), nullable=False),
        sa.Column("delta_late_order_count", sa.Integer(), nullable=False),
        sa.Column("objective_diff_detected", sa.Boolean(), nullable=False),
        sa.Column("order_set_diff_detected", sa.Boolean(), nullable=False),
        sa.Column("status_diff_detected", sa.Boolean(), nullable=False),
        sa.Column("time_limit_diff_detected", sa.Boolean(), nullable=False),
        sa.Column("unlike_comparison_warning", sa.Text(), nullable=True),
        sa.Column("critical_path_divergence_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["baseline_schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compared_schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("staged_data_json", sa.Text(), nullable=False),
        sa.Column("error_report_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def upgrade() -> None:
    """Apply schema migrations."""
    _create_workspace_and_machine_tables()
    _create_order_and_operation_tables()
    _create_schedule_tables()
    _create_scenario_and_import_tables()


def downgrade() -> None:
    """Revert schema migrations."""
    op.drop_table("import_jobs")
    op.drop_table("scenario_comparisons")
    op.drop_table("scenarios")
    op.drop_table("scheduled_operations")
    op.drop_table("schedules")
    op.drop_table("operations")
    op.drop_table("production_orders")
    op.drop_table("machine_downtimes")
    op.drop_table("machines")
    op.drop_table("workspaces")
