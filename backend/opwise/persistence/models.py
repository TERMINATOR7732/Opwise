"""SQLAlchemy 2.0 ORM mappings for Opwise persistence.

Governed by DATA_AND_API.md Section 1.1 and ARCHITECTURE.md.
Explicit schema definitions with foreign keys, checks, unique constraints, and indexes.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opwise.persistence.database import Base


def _generate_uuid() -> str:
    """Generate a UUID4 string."""
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class WorkspaceModel(Base):
    """Root tenant boundary for multi-scenario planning."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("current_time_minute >= 0", name="chk_workspace_current_time_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_time_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    machines: Mapped[list["MachineModel"]] = relationship(
        "MachineModel",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="MachineModel.external_id",
    )
    orders: Mapped[list["ProductionOrderModel"]] = relationship(
        "ProductionOrderModel",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ProductionOrderModel.external_id",
    )
    schedules: Mapped[list["ScheduleModel"]] = relationship(
        "ScheduleModel",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="ScheduleModel.created_at.desc()",
    )


class MachineModel(Base):
    """Physical production resource."""

    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_id", name="uq_machines_workspace_external_id"),
        Index("ix_machines_workspace_id", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel", back_populates="machines")
    downtimes: Mapped[list["MachineDowntimeModel"]] = relationship(
        "MachineDowntimeModel",
        back_populates="machine",
        cascade="all, delete-orphan",
        order_by="MachineDowntimeModel.start_minute",
    )


class MachineDowntimeModel(Base):
    """Planned maintenance or outage window for a machine."""

    __tablename__ = "machine_downtimes"
    __table_args__ = (
        CheckConstraint("start_minute >= 0", name="chk_downtime_start_non_negative"),
        CheckConstraint("end_minute > start_minute", name="chk_downtime_end_gt_start"),
        Index("ix_machine_downtimes_machine_start", "machine_id", "start_minute"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    machine_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False
    )
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    machine: Mapped[MachineModel] = relationship("MachineModel", back_populates="downtimes")


class ProductionOrderModel(Base):
    """Customer or replenishment order requiring operations."""

    __tablename__ = "production_orders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_id", name="uq_orders_workspace_external_id"),
        CheckConstraint("release_minute >= 0", name="chk_order_release_non_negative"),
        CheckConstraint("due_minute >= 0", name="chk_order_due_non_negative"),
        CheckConstraint("tardiness_weight >= 0", name="chk_order_weight_non_negative"),
        Index("ix_orders_workspace_id", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    release_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    tardiness_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel", back_populates="orders")
    operations: Mapped[list["OperationModel"]] = relationship(
        "OperationModel",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OperationModel.sequence_index",
    )


class OperationModel(Base):
    """Atomic task belonging to an order, processed on a machine."""

    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint("order_id", "sequence_index", name="uq_operations_order_sequence"),
        CheckConstraint("sequence_index >= 1", name="chk_op_sequence_positive"),
        CheckConstraint("processing_minutes >= 1", name="chk_op_processing_positive"),
        CheckConstraint("status IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED')", name="chk_op_status"),
        CheckConstraint(
            "actual_start_minute IS NULL OR actual_start_minute >= 0",
            name="chk_op_actual_start_non_negative",
        ),
        CheckConstraint(
            "actual_end_minute IS NULL OR actual_start_minute IS NULL OR actual_end_minute > actual_start_minute",
            name="chk_op_actual_end_gt_start",
        ),
        CheckConstraint(
            "remaining_duration_minutes IS NULL OR remaining_duration_minutes >= 1",
            name="chk_op_remaining_duration_positive",
        ),
        CheckConstraint(
            "(status = 'PLANNED' AND actual_start_minute IS NULL AND actual_end_minute IS NULL AND remaining_duration_minutes IS NULL) OR "
            "(status = 'IN_PROGRESS' AND actual_start_minute IS NOT NULL AND actual_end_minute IS NULL AND remaining_duration_minutes IS NOT NULL) OR "
            "(status = 'COMPLETED' AND actual_start_minute IS NOT NULL AND actual_end_minute IS NOT NULL AND remaining_duration_minutes IS NULL)",
            name="chk_op_lifecycle_consistency",
        ),
        Index("ix_operations_order_id", "order_id"),
        Index("ix_operations_machine_id", "machine_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    machine_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("machines.id", ondelete="RESTRICT"), nullable=False
    )
    processing_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    actual_start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    order: Mapped[ProductionOrderModel] = relationship("ProductionOrderModel", back_populates="operations")
    machine: Mapped[MachineModel] = relationship("MachineModel")


class ScheduleModel(Base):
    """Immutable optimization solution snapshot."""

    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("current_time_minute >= 0", name="chk_schedule_current_time_non_negative"),
        Index("ix_schedules_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    objective_type: Mapped[str] = mapped_column(String(32), nullable=False)
    solver_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    objective_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_objective_bound: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimality_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    stage1_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage1_objective_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage1_best_bound: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage1_wall_clock_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    stage2_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage2_objective_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage2_best_bound: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage2_wall_clock_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    makespan_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    weighted_tardiness: Mapped[int] = mapped_column(Integer, nullable=False)
    late_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False)
    solver_wall_clock_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    solver_deterministic_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    current_time_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    workspace: Mapped[WorkspaceModel] = relationship("WorkspaceModel", back_populates="schedules")
    scheduled_operations: Mapped[list["ScheduledOperationModel"]] = relationship(
        "ScheduledOperationModel",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduledOperationModel.start_minute",
    )


class ScheduledOperationModel(Base):
    """Allocated timestamp placement of an operation in a schedule."""

    __tablename__ = "scheduled_operations"
    __table_args__ = (
        CheckConstraint("start_minute >= 0", name="chk_sched_op_start_non_negative"),
        CheckConstraint("end_minute > start_minute", name="chk_sched_op_end_gt_start"),
        CheckConstraint("status IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED')", name="chk_sched_op_status"),
        Index("ix_scheduled_ops_machine_start", "schedule_id", "machine_id", "start_minute"),
        Index("ix_scheduled_ops_order", "schedule_id", "order_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    slack_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")

    schedule: Mapped[ScheduleModel] = relationship("ScheduleModel", back_populates="scheduled_operations")


class ScenarioModel(Base):
    """Branch from a baseline schedule for offline disruption simulation."""

    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_workspace", "workspace_id"),
        Index("ix_scenarios_baseline", "baseline_schedule_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    baseline_schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="RESTRICT"), nullable=False
    )
    reoptimized_schedule_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    disruption_type: Mapped[str] = mapped_column(String(32), nullable=False)
    disruption_delta_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class ScenarioComparisonModel(Base):
    """Computed difference between baseline schedule and reoptimized scenario."""

    __tablename__ = "scenario_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    baseline_schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    compared_schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    delta_makespan: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_weighted_tardiness: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_late_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    objective_diff_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_set_diff_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_diff_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_limit_diff_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlike_comparison_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    critical_path_divergence_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class ImportJobModel(Base):
    """Batch CSV/Excel import tracking entity."""

    __tablename__ = "import_jobs"
    __table_args__ = (Index("ix_import_jobs_workspace_id", "workspace_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    staged_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    error_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
