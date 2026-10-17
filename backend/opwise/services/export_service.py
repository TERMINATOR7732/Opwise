"""Data export formatting service with CSV formula injection mitigation and JSON serialization.

Governed by DATA_AND_API.md Section 4.4 and SPECIFICATION.md Section 8.1.
"""

import csv
import io
import json
from collections.abc import Sequence
from typing import Any

from opwise.api.schemas.report import ScheduleReportResponse
from opwise.api.schemas.scenario import ScenarioComparisonResponse, ScenarioResponse
from opwise.persistence.models import ScheduleModel


def sanitize_csv_cell(value: Any) -> Any:
    """Escape CSV formula injection triggers ('=', '+', '-', '@', '\\t', '\\r')."""
    if value is None:
        return ""
    if isinstance(value, str):
        if not value:
            return value
        stripped_spaces = value.lstrip(" ")
        if not stripped_spaces:
            return value
        first = stripped_spaces[0]
        if first in ("=", "@", "\t", "\r"):
            return "'" + value
        if first in ("+", "-"):
            num_cand = stripped_spaces.strip()
            num_body = num_cand[1:]
            if num_body and num_body.replace(".", "", 1).isdigit():
                return value
            return "'" + value
        return value
    return value


def _write_section_rows(
    writer: Any, header: str, columns: Sequence[Any], rows: Sequence[Any]
) -> None:
    """Helper to write a titled CSV section with headers and sanitized cells."""
    writer.writerow([header])
    writer.writerow([sanitize_csv_cell(c) for c in columns])
    for row in rows:
        writer.writerow([sanitize_csv_cell(v) for v in row])
    writer.writerow([])


def _build_summary_rows(report: ScheduleReportResponse) -> list[list[Any]]:
    """Build key-value summary rows for schedule report."""
    return [
        ["Schedule ID", report.schedule_id],
        ["Schedule Name", report.schedule_name],
        ["Objective Type", report.objective_type],
        ["Solver Status", report.solver_status],
        ["Verification Status", report.verification_status],
        ["Created At", report.created_at.isoformat()],
        ["Makespan (minutes)", report.summary.makespan_minutes],
        ["Weighted Tardiness", report.summary.total_weighted_tardiness],
        ["Late Orders", report.summary.late_order_count],
        ["On-Time Orders", report.summary.on_time_order_count],
        ["Total Orders", report.summary.total_order_count],
        ["On-Time Delivery Rate (%)", f"{report.summary.on_time_rate_pct:.2f}%"],
        ["Solver Wall Clock (seconds)", f"{report.summary.solver_wall_clock_seconds:.4f}"],
        ["Solver Deterministic Time", str(report.summary.solver_deterministic_time or "N/A")],
    ]


def _build_machine_rows(report: ScheduleReportResponse) -> tuple[list[str], list[list[Any]]]:
    """Build headers and rows for machine utilization metrics."""
    headers = [
        "Machine ID",
        "Name",
        "Workload (min)",
        "Downtime (min)",
        "Idle (min)",
        "Net Util (%)",
        "Gross Util (%)",
        "Operations",
    ]
    rows = [
        [
            m.machine_id,
            m.machine_name,
            m.workload_minutes,
            m.downtime_minutes,
            m.idle_minutes,
            f"{m.net_utilization_pct:.2f}%",
            f"{m.gross_utilization_pct:.2f}%",
            m.assigned_operation_count,
        ]
        for m in report.machine_utilization
    ]
    return headers, rows


def _build_order_rows(report: ScheduleReportResponse) -> tuple[list[str], list[list[Any]]]:
    """Build headers and rows for order performance metrics."""
    headers = [
        "Order ID",
        "Order Code",
        "Release (min)",
        "Due Date (min)",
        "Completion (min)",
        "Tardiness (min)",
        "Weight",
        "Weighted Tardiness",
        "Slack (min)",
        "Status",
        "Operations",
        "Total Proc Time (min)",
    ]
    rows = [
        [
            o.order_id,
            o.order_code,
            o.release_minute,
            o.due_date_minute,
            o.completion_minute,
            o.tardiness_minutes,
            o.tardiness_weight,
            o.weighted_tardiness,
            o.slack_minutes,
            "LATE" if o.is_late else "ON_TIME",
            o.operation_count,
            o.total_processing_minutes,
        ]
        for o in report.order_performance
    ]
    return headers, rows


def _build_operation_rows(
    schedule_model: ScheduleModel,
) -> tuple[list[str], list[list[Any]]]:
    """Build headers and rows for scheduled operations."""
    headers = [
        "Operation ID",
        "Order ID",
        "Machine ID",
        "Sequence",
        "Start (min)",
        "End (min)",
        "Duration (min)",
        "Slack (min)",
    ]
    rows = [
        [
            op.operation_id,
            op.order_id,
            op.machine_id,
            op.sequence_number,
            op.start_minute,
            op.end_minute,
            op.processing_duration_minutes,
            op.slack_minutes,
        ]
        for op in schedule_model.scheduled_operations
    ]
    return headers, rows


def _build_bottleneck_rows(report: ScheduleReportResponse) -> list[list[Any]]:
    """Build rows for bottleneck diagnostic analysis."""
    bn = report.bottleneck
    return [
        ["Primary Bottleneck Machine", bn.primary_bottleneck_machine_id or "NONE"],
        ["Primary Bottleneck Name", bn.primary_bottleneck_machine_name or "N/A"],
        ["Highest Workload (minutes)", bn.highest_workload_minutes],
        ["Highest Net Utilization (%)", f"{bn.highest_net_utilization_pct:.2f}%"],
        ["Machine Load Ranking", " > ".join(bn.ranked_machines) if bn.ranked_machines else "N/A"],
        ["Disclaimer", bn.disclaimer],
    ]


def _build_audit_rows(report: ScheduleReportResponse) -> list[list[Any]]:
    """Build rows for independent verification audit results."""
    audit = report.verification_audit
    return [
        ["Verification Status", "VALID" if audit.is_valid else "INVALID"],
        ["Checks Run", audit.checks_run],
        ["Checks Passed", audit.checks_passed],
        ["Violations", "; ".join(audit.violations) if audit.violations else "None"],
    ]


class ExportService:
    """Generates sanitized, structurally sound CSV and JSON exports."""

    @staticmethod
    def generate_schedule_csv(report: ScheduleReportResponse, schedule_model: ScheduleModel) -> str:
        """Render complete schedule performance and operations into sanitized multi-section CSV."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        _write_section_rows(
            writer, "# 1. SCHEDULE SUMMARY", ["Metric", "Value"], _build_summary_rows(report)
        )

        mach_headers, mach_rows = _build_machine_rows(report)
        _write_section_rows(writer, "# 2. MACHINE UTILIZATION", mach_headers, mach_rows)

        order_headers, order_rows = _build_order_rows(report)
        _write_section_rows(writer, "# 3. ORDER PERFORMANCE", order_headers, order_rows)

        op_headers, op_rows = _build_operation_rows(schedule_model)
        _write_section_rows(writer, "# 4. SCHEDULED OPERATIONS", op_headers, op_rows)

        _write_section_rows(
            writer, "# 5. BOTTLENECK ANALYSIS", ["Diagnostic", "Detail"], _build_bottleneck_rows(report)
        )

        _write_section_rows(
            writer, "# 6. INDEPENDENT VERIFICATION AUDIT", ["Check", "Result"], _build_audit_rows(report)
        )

        return output.getvalue()

    @staticmethod
    def generate_schedule_json(report: ScheduleReportResponse, schedule_model: ScheduleModel) -> str:
        """Render complete schedule report and operations into formatted JSON with Unicode safety."""
        report_dict = report.model_dump(mode="json")
        report_dict["scheduled_operations"] = [
            {
                "operation_id": op.operation_id,
                "order_id": op.order_id,
                "machine_id": op.machine_id,
                "sequence_number": op.sequence_number,
                "start_minute": op.start_minute,
                "end_minute": op.end_minute,
                "duration_minutes": op.processing_duration_minutes,
                "slack_minutes": op.slack_minutes,
            }
            for op in schedule_model.scheduled_operations
        ]
        return json.dumps(report_dict, indent=2, ensure_ascii=False)

    @staticmethod
    def generate_scenario_csv(
        scenario: ScenarioResponse, comparison: ScenarioComparisonResponse | None
    ) -> str:
        """Render scenario configuration and disruption comparison delta into sanitized CSV."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        delta = scenario.disruption_delta
        scen_rows = [
            ["Scenario ID", scenario.id],
            ["Scenario Name", scenario.name],
            ["Disruption Type", scenario.disruption_type],
            ["Description", scenario.description or ""],
            ["Baseline Schedule ID", scenario.baseline_schedule_id],
            ["Reoptimized Schedule ID", scenario.reoptimized_schedule_id or "Not Reoptimized"],
            ["Created At", scenario.created_at.isoformat()],
            ["Added Downtimes Count", len(delta.added_downtimes)],
            ["Added Orders Count", len(delta.added_orders)],
        ]
        _write_section_rows(writer, "# 1. SCENARIO CONFIGURATION", ["Parameter", "Value"], scen_rows)

        if comparison is not None:
            comp_rows = [
                ["Delta Makespan (min)", comparison.delta_makespan],
                ["Delta Weighted Tardiness", comparison.delta_weighted_tardiness],
                ["Delta Late Orders", comparison.delta_late_order_count],
                ["Objective Difference Detected", comparison.objective_diff_detected],
                ["Order Set Difference Detected", comparison.order_set_diff_detected],
                ["Solver Status Difference Detected", comparison.status_diff_detected],
                ["Time Limit Difference Detected", comparison.time_limit_diff_detected],
                ["Unlike Comparison Warning", comparison.unlike_comparison_warning or "None"],
            ]
            _write_section_rows(writer, "# 2. COMPARISON METRICS DELTA", ["Metric", "Value"], comp_rows)

            div_headers = [
                "Order ID",
                "Sequence",
                "Machine ID",
                "Baseline Start",
                "Baseline End",
                "Compared Start",
                "Compared End",
                "Delta Start (min)",
                "Status",
            ]
            div_rows = [
                [
                    d.order_id,
                    d.sequence_index,
                    d.machine_id,
                    d.baseline_start if d.baseline_start is not None else "N/A",
                    d.baseline_end if d.baseline_end is not None else "N/A",
                    d.compared_start,
                    d.compared_end,
                    d.delta_start_minutes if d.delta_start_minutes is not None else "N/A",
                    d.status,
                ]
                for d in comparison.diverged_operations
            ]
            _write_section_rows(writer, "# 3. OPERATION DIVERGENCES", div_headers, div_rows)

        return output.getvalue()

    @staticmethod
    def generate_scenario_json(
        scenario: ScenarioResponse, comparison: ScenarioComparisonResponse | None
    ) -> str:
        """Render scenario details and comparison into formatted JSON."""
        data = {
            "scenario": scenario.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json") if comparison else None,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
