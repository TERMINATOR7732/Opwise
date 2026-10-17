/**
 * Reports and Data Export Frontend Types
 * Governed by SPECIFICATION.md Section 5.1, Section 8.1, and DATA_AND_API.md Section 4
 */

export interface SummaryKPIs {
  makespan_minutes: number;
  total_weighted_tardiness: number;
  late_order_count: number;
  on_time_order_count: number;
  total_order_count: number;
  on_time_rate_pct: number;
  solver_wall_clock_seconds: number;
  solver_deterministic_time: number | null;
}

export interface MachineUtilizationItem {
  machine_id: string;
  machine_name: string;
  workload_minutes: number;
  downtime_minutes: number;
  idle_minutes: number;
  available_capacity_minutes: number;
  net_utilization_pct: number;
  gross_utilization_pct: number;
  assigned_operation_count: number;
  is_oversubscribed: boolean;
}

export interface OrderPerformanceItem {
  order_id: string;
  order_code: string;
  release_minute: number;
  due_date_minute: number;
  completion_minute: number;
  tardiness_minutes: number;
  tardiness_weight: number;
  weighted_tardiness: number;
  slack_minutes: number;
  is_late: boolean;
  is_on_time: boolean;
  operation_count: number;
  total_processing_minutes: number;
}

export interface BottleneckReportItem {
  primary_bottleneck_machine_id: string | null;
  primary_bottleneck_machine_name: string | null;
  highest_workload_minutes: number;
  highest_net_utilization_pct: number;
  ranked_machines: string[];
  disclaimer: string;
}

export interface ScheduleExplanationItem {
  category: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  measured_value: string;
  threshold_or_target: string | null;
  mathematical_formula: string;
  reason: string;
}

export interface VerificationAuditSummary {
  is_valid: boolean;
  checks_run: number;
  checks_passed: number;
  violations: string[];
}

export interface ScheduleReportResponse {
  workspace_id: string;
  schedule_id: string;
  schedule_name: string;
  objective_type: string;
  solver_status: string;
  verification_status: string;
  created_at: string;
  summary: SummaryKPIs;
  machine_utilization: MachineUtilizationItem[];
  order_performance: OrderPerformanceItem[];
  bottleneck: BottleneckReportItem;
  explanations: ScheduleExplanationItem[];
  verification_audit: VerificationAuditSummary;
}
