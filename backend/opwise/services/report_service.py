"""Service for compiling deterministic production schedule reports and analytics.

Governed by SPECIFICATION.md Section 5.1, Section 8.1, and DATA_AND_API.md Section 3.2.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from opwise.api.schemas.report import (
    BottleneckReportItem,
    MachineUtilizationItem,
    OrderPerformanceItem,
    ScheduleExplanationItem,
    ScheduleReportResponse,
    SummaryKPIs,
    VerificationAuditSummary,
)
from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.domain.exceptions import ResourceNotFoundError
from opwise.domain.metrics import calculate_metrics_from_operations
from opwise.domain.metrics_types import BOTTLENECK_DISCLAIMER, ProductionScheduleMetrics
from opwise.persistence.models import ScheduleModel
from opwise.persistence.repository import ScheduleRepository, WorkspaceRepository
from opwise.services.snapshot import reconstruct_factory_from_snapshot
from opwise.verifier.independent_verifier import ScheduleVerifier, VerificationReport


def _build_audit_summary(verification_result: VerificationReport) -> VerificationAuditSummary:
    """Build structured summary of verification audit rules and results."""
    return VerificationAuditSummary(
        is_valid=verification_result.is_valid,
        checks_run=len(verification_result.passed_rules) + len(verification_result.failed_rules),
        checks_passed=len(verification_result.passed_rules),
        violations=[v.message for v in verification_result.violations],
    )


def _build_utilization_items(
    metrics: ProductionScheduleMetrics, machine_name_map: dict[str, str]
) -> list[MachineUtilizationItem]:
    """Map raw machine metrics to API utilization response items."""
    return [
        MachineUtilizationItem(
            machine_id=m_id,
            machine_name=machine_name_map.get(m_id, m_id),
            workload_minutes=m_metrics.workload_minutes,
            downtime_minutes=m_metrics.downtime_minutes,
            idle_minutes=m_metrics.idle_minutes,
            available_capacity_minutes=m_metrics.available_capacity_minutes,
            net_utilization_pct=m_metrics.net_utilization_pct,
            gross_utilization_pct=m_metrics.gross_utilization_pct,
            assigned_operation_count=m_metrics.assigned_operation_count,
            is_oversubscribed=m_metrics.is_oversubscribed,
        )
        for m_id, m_metrics in metrics.machine_metrics.items()
    ]


def _build_performance_items(
    metrics: ProductionScheduleMetrics, factory: Factory
) -> list[OrderPerformanceItem]:
    """Map raw order metrics to API order performance response items."""
    order_map = {o.id: o for o in factory.orders}
    return [
        OrderPerformanceItem(
            order_id=o_id,
            order_code=o_metrics.order_code,
            release_minute=order_map[o_id].release_time_minutes if o_id in order_map else 0,
            due_date_minute=o_metrics.due_date_minute,
            completion_minute=o_metrics.completion_minute,
            tardiness_minutes=o_metrics.tardiness_minutes,
            tardiness_weight=o_metrics.tardiness_weight,
            weighted_tardiness=o_metrics.weighted_tardiness,
            slack_minutes=o_metrics.slack_minutes,
            is_late=o_metrics.is_late,
            is_on_time=o_metrics.is_on_time,
            operation_count=o_metrics.operation_count,
            total_processing_minutes=o_metrics.total_processing_minutes,
        )
        for o_id, o_metrics in metrics.order_metrics.items()
    ]


def _build_bottleneck_item(
    metrics: ProductionScheduleMetrics, machine_name_map: dict[str, str]
) -> BottleneckReportItem:
    """Build bottleneck analysis report item with standard disclaimer."""
    bottleneck_m_id = metrics.bottleneck.primary_bottleneck_machine_id
    return BottleneckReportItem(
        primary_bottleneck_machine_id=bottleneck_m_id,
        primary_bottleneck_machine_name=machine_name_map.get(bottleneck_m_id, bottleneck_m_id)
        if bottleneck_m_id
        else None,
        highest_workload_minutes=metrics.bottleneck.highest_workload_minutes,
        highest_net_utilization_pct=metrics.bottleneck.highest_net_utilization_pct,
        ranked_machines=metrics.bottleneck.ranked_machines,
        disclaimer=BOTTLENECK_DISCLAIMER,
    )


def _build_explanation_items(metrics: ProductionScheduleMetrics) -> list[ScheduleExplanationItem]:
    """Map analytical schedule explanations to API response items."""
    return [
        ScheduleExplanationItem(
            category=e.category,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            summary=e.summary,
            measured_value=str(e.measured_value),
            threshold_or_target=str(e.threshold_or_target) if e.threshold_or_target is not None else None,
            mathematical_formula=e.mathematical_formula,
            reason=e.reason,
        )
        for e in metrics.explanations
    ]


def _build_summary_kpis(model: ScheduleModel, metrics: ProductionScheduleMetrics) -> SummaryKPIs:
    """Aggregate top-level summary KPIs combining solver model and recomputed metrics."""
    return SummaryKPIs(
        makespan_minutes=model.makespan_minutes,
        total_weighted_tardiness=model.weighted_tardiness,
        late_order_count=model.late_order_count,
        on_time_order_count=metrics.on_time_order_count,
        total_order_count=metrics.total_order_count,
        on_time_rate_pct=model.on_time_rate,
        solver_wall_clock_seconds=model.solver_wall_clock_seconds,
        solver_deterministic_time=model.solver_deterministic_time,
    )


class ReportService:
    """Builds verified schedule reports and multi-dimensional analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.schedule_repo = ScheduleRepository(session)
        self.verifier = ScheduleVerifier()

    def _map_objective_mode(self, mode_str: str) -> ObjectiveMode:
        mapping = {
            "PURE_MAKESPAN": ObjectiveMode.PURE_MAKESPAN,
            "PURE_WEIGHTED_TARDINESS": ObjectiveMode.PURE_WEIGHTED_TARDINESS,
            "HIERARCHICAL": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
            "HIERARCHICAL_LEXICOGRAPHIC": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
        }
        return mapping.get(mode_str.upper(), ObjectiveMode.PURE_MAKESPAN)

    def _map_schedule_status(self, status_str: str) -> ScheduleStatus:
        mapping = {
            "OPTIMAL": ScheduleStatus.OPTIMAL,
            "FEASIBLE": ScheduleStatus.FEASIBLE,
            "INFEASIBLE": ScheduleStatus.INFEASIBLE,
            "NO_WORK_STATE": ScheduleStatus.NO_WORK_STATE,
            "TIMEOUT": ScheduleStatus.FEASIBLE,
        }
        return mapping.get(status_str.upper(), ScheduleStatus.FEASIBLE)

    def _convert_operations(self, schedule_model: ScheduleModel) -> list[ScheduledOperation]:
        return [
            ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=op.start_minute,
                end_minute=op.end_minute,
                processing_duration_minutes=op.processing_duration_minutes,
                slack_minutes=op.slack_minutes,
            )
            for op in schedule_model.scheduled_operations
        ]

    def _build_schedule_domain(
        self,
        model: ScheduleModel,
        workspace_id: str,
        domain_ops: list[ScheduledOperation],
        metrics: ProductionScheduleMetrics,
    ) -> Schedule:
        return Schedule(
            id=model.id,
            workspace_id=workspace_id,
            status=self._map_schedule_status(model.solver_status),
            objective_mode=self._map_objective_mode(model.objective_type),
            kpis=ScheduleKPIs(
                makespan_minutes=metrics.makespan_minutes,
                total_weighted_tardiness=metrics.total_weighted_tardiness,
                late_order_count=metrics.late_order_count,
                on_time_rate=metrics.on_time_rate_pct,
            ),
            scheduled_operations=domain_ops,
            verified=False,
        )

    async def generate_schedule_report(
        self, workspace_id: str, schedule_id: str
    ) -> ScheduleReportResponse:
        """Construct a comprehensive analytical report for a persisted schedule."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        model = await self.schedule_repo.get_by_id(workspace_id, schedule_id)
        if model is None:
            raise ResourceNotFoundError("Schedule", schedule_id)

        factory = reconstruct_factory_from_snapshot(workspace_id, model.input_snapshot_json)
        if factory is None:
            factory = Factory(workspace_id=workspace_id, machines=[], downtimes=[], orders=[])

        domain_ops = self._convert_operations(model)
        metrics = calculate_metrics_from_operations(factory, domain_ops, schedule_id=model.id)
        schedule_domain = self._build_schedule_domain(model, workspace_id, domain_ops, metrics)
        verification_result = self.verifier.verify(factory, schedule_domain)
        machine_name_map = {m.id: m.name for m in factory.machines}

        return ScheduleReportResponse(
            workspace_id=workspace_id,
            schedule_id=schedule_id,
            schedule_name=model.name,
            objective_type=model.objective_type,
            solver_status=model.solver_status,
            verification_status=model.verification_status,
            created_at=model.created_at,
            summary=_build_summary_kpis(model, metrics),
            machine_utilization=_build_utilization_items(metrics, machine_name_map),
            order_performance=_build_performance_items(metrics, factory),
            bottleneck=_build_bottleneck_item(metrics, machine_name_map),
            explanations=_build_explanation_items(metrics),
            verification_audit=_build_audit_summary(verification_result),
        )
