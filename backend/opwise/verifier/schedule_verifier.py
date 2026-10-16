"""Clean-room independent schedule verifier orchestrator for Opwise.

Governed by SOLVER_MODEL.md Section 6, PROJECT_RULES.md Section 6.3,
and TEST_AND_RELEASE_PLAN.md Milestone 03.
Decoupled completely from OR-Tools and persistence.
"""

from opwise.domain.entities import (
    Factory,
    Schedule,
    ScheduleStatus,
)
from opwise.verifier.invariant_auditor import (
    audit_cardinality,
    audit_downtime_respect,
    audit_duration_and_machine,
    audit_horizon_bounds,
    audit_machine_exclusivity,
    audit_precedence,
    audit_release_times,
)
from opwise.verifier.metric_recalculator import (
    check_candidate_kpi_concordance,
    check_stage1_preservation,
    metrics_concordant,
    recompute_schedule_metrics,
)
from opwise.verifier.verification_types import (
    InvariantRule,
    InvariantViolation,
    RecomputedMetrics,
    VerificationReport,
    VerificationStatus,
)


class ScheduleVerifier:
    """Independent auditor validating candidate production schedules against 8 invariants."""

    def verify(
        self,
        factory: Factory,
        schedule: Schedule,
        stage1_bound: int | None = None,
    ) -> VerificationReport:
        """Inspect a candidate schedule against factory inputs without modifying either object."""
        # Case: Infeasible, Timeout, or Model Invalid with 0 scheduled operations
        if not schedule.scheduled_operations and schedule.status in {
            ScheduleStatus.INFEASIBLE,
            ScheduleStatus.TIMEOUT,
            ScheduleStatus.MODEL_INVALID,
        }:
            return VerificationReport(
                status=VerificationStatus.SKIPPED,
                is_valid=False,
                passed_rules=[],
                failed_rules=[],
                violations=[],
                recomputed_metrics=None,
                candidate_metrics_match=False,
            )

        # Case: No-Work State: 0 factory orders and 0 scheduled operations
        if not factory.orders and not schedule.scheduled_operations:
            return self._verify_no_work_state(factory, schedule)

        violations: list[InvariantViolation] = []
        violations.extend(audit_cardinality(factory, schedule.scheduled_operations))
        violations.extend(audit_duration_and_machine(factory, schedule.scheduled_operations))
        violations.extend(audit_release_times(factory, schedule.scheduled_operations))
        violations.extend(audit_precedence(factory, schedule.scheduled_operations))
        violations.extend(audit_machine_exclusivity(schedule.scheduled_operations))
        violations.extend(audit_downtime_respect(factory, schedule.scheduled_operations))
        violations.extend(audit_horizon_bounds(factory, schedule.scheduled_operations))

        recomputed = self.recompute_metrics(factory, schedule)
        metric_violations = check_candidate_kpi_concordance(schedule, recomputed)
        stage1_violations = check_stage1_preservation(schedule, recomputed, stage1_bound)
        violations.extend(metric_violations)
        violations.extend(stage1_violations)

        failed_rules = sorted({v.rule for v in violations}, key=lambda r: r.value)
        passed_rules = [
            rule for rule in InvariantRule
            if rule not in failed_rules and (rule != InvariantRule.INV_8_STAGE1_PRESERVATION or stage1_bound is not None)
        ]
        is_valid = len(violations) == 0

        return VerificationReport(
            status=VerificationStatus.VERIFIED if is_valid else VerificationStatus.VERIFICATION_FAILED,
            is_valid=is_valid,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            violations=violations,
            recomputed_metrics=recomputed,
            candidate_metrics_match=not any(v.rule == InvariantRule.INV_8_METRIC_CONCORDANCE for v in metric_violations),
        )

    def recompute_metrics(self, factory: Factory, schedule: Schedule) -> RecomputedMetrics:
        """Expose analytical metric recalculation publicly on the verifier instance."""
        return recompute_schedule_metrics(factory, schedule.scheduled_operations)

    def _verify_no_work_state(self, factory: Factory, schedule: Schedule) -> VerificationReport:
        """Handle formal Case 2: Factory with machines but 0 production orders."""
        recomputed = self.recompute_metrics(factory, schedule)
        metrics_match = metrics_concordant(schedule.kpis, recomputed)
        all_rules = list(InvariantRule)
        if metrics_match:
            return VerificationReport(
                status=VerificationStatus.VERIFIED,
                is_valid=True,
                passed_rules=all_rules,
                failed_rules=[],
                violations=[],
                recomputed_metrics=recomputed,
                candidate_metrics_match=True,
            )

        return VerificationReport(
            status=VerificationStatus.VERIFICATION_FAILED,
            is_valid=False,
            passed_rules=[r for r in all_rules if r != InvariantRule.INV_8_METRIC_CONCORDANCE],
            failed_rules=[InvariantRule.INV_8_METRIC_CONCORDANCE],
            violations=[
                InvariantViolation(
                    rule=InvariantRule.INV_8_METRIC_CONCORDANCE,
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    message="Candidate KPIs do not match recomputed metrics for no-work state",
                )
            ],
            recomputed_metrics=recomputed,
            candidate_metrics_match=False,
        )
