/**
 * Opwise Disruption Scenario & Comparison Types
 * Governed by SPECIFICATION.md Section 6 and DATA_AND_API.md Section 1.1 & 3.2
 */

export interface DowntimeDisruptionItem {
  machine_id: string;
  start_minute: number;
  end_minute: number;
  reason?: string | null;
}

export interface OperationDisruptionItem {
  sequence_index: number;
  machine_id: string;
  processing_minutes: number;
}

export interface OrderDisruptionItem {
  order_code: string;
  release_time_minutes: number;
  due_date_minutes: number;
  tardiness_weight: number;
  operations: OperationDisruptionItem[];
}

export interface DisruptionDelta {
  added_downtimes: DowntimeDisruptionItem[];
  added_orders: OrderDisruptionItem[];
}

export interface ScenarioCreateRequest {
  name: string;
  baseline_schedule_id: string;
  disruption_type: 'MACHINE_DOWNTIME' | 'URGENT_ORDER' | 'COMBINED';
  disruption_delta: DisruptionDelta;
  description?: string | null;
}

export interface ScenarioReoptimizeRequest {
  primary_time_budget_seconds?: number;
  num_workers?: number;
  random_seed?: number;
}

export interface OperationDivergence {
  order_id: string;
  sequence_index: number;
  machine_id: string;
  baseline_start?: number | null;
  baseline_end?: number | null;
  compared_start: number;
  compared_end: number;
  delta_start_minutes?: number | null;
  status: 'UNMODIFIED' | 'DELAYED' | 'EXPEDITED' | 'NEW_RUSH_OPERATION' | 'REMOVED';
}

export interface ScenarioComparisonResponse {
  id: string;
  scenario_id?: string | null;
  baseline_schedule_id: string;
  compared_schedule_id: string;
  delta_makespan: number;
  delta_weighted_tardiness: number;
  delta_late_order_count: number;
  delta_on_time_rate: number;
  objective_diff_detected: boolean;
  order_set_diff_detected: boolean;
  status_diff_detected: boolean;
  time_limit_diff_detected: boolean;
  unlike_comparison_warning?: string | null;
  diverged_operations: OperationDivergence[];
  created_at: string;
}

export interface ScenarioResponse {
  id: string;
  workspace_id: string;
  baseline_schedule_id: string;
  reoptimized_schedule_id?: string | null;
  name: string;
  description?: string | null;
  disruption_type: 'MACHINE_DOWNTIME' | 'URGENT_ORDER' | 'COMBINED';
  disruption_delta: DisruptionDelta;
  created_at: string;
  comparison?: ScenarioComparisonResponse | null;
}

export interface ScenarioCompareRequest {
  baseline_schedule_id: string;
  compared_schedule_id: string;
  scenario_id?: string | null;
}
