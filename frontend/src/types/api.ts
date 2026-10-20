/**
 * Opwise API Types & Response Envelope Contracts
 * Governed by DATA_AND_API.md Section 3.1 & 3.2
 */

export interface RequestMetadata {
  timestamp: string;
  requestId: string;
}

export interface SuccessEnvelope<T> {
  success: true;
  data: T;
  metadata: RequestMetadata;
}

export interface ValidationErrorDetail {
  field: string;
  issue: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: ValidationErrorDetail[] | Record<string, unknown> | null;
}

export interface ErrorEnvelope {
  success: false;
  error: ApiError;
  metadata: RequestMetadata;
}

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkspaceRequest {
  name: string;
  description?: string;
}

export interface ScheduleSummaryResponse {
  id: string;
  workspace_id: string;
  name: string;
  objective_type: string;
  solver_status: string;
  verification_status: string;
  makespan_minutes: number;
  weighted_tardiness: number;
  late_order_count: number;
  on_time_rate: number;
  current_time_minute?: number;
  created_at: string;
}

export interface MachineCreate {
  external_id: string;
  name: string;
}

export interface MachineResponse {
  id: string;
  external_id: string;
  name: string;
  created_at: string;
}

export interface DowntimeCreate {
  machine_id: string;
  start_minute: number;
  end_minute: number;
  reason?: string | null;
}

export interface DowntimeResponse {
  id: string;
  machine_id: string;
  start_minute: number;
  end_minute: number;
  reason: string | null;
}

export interface OperationCreate {
  sequence_index: number;
  machine_id: string;
  processing_minutes: number;
  status?: string;
  actual_start_minute?: number | null;
  actual_end_minute?: number | null;
  remaining_duration_minutes?: number | null;
}

export interface OperationResponse {
  id: string;
  order_id: string;
  sequence_index: number;
  machine_id: string;
  processing_minutes: number;
  status?: string;
  actual_start_minute?: number | null;
  actual_end_minute?: number | null;
  remaining_duration_minutes?: number | null;
}

export interface OrderCreate {
  external_id: string;
  name: string;
  release_minute: number;
  due_minute: number;
  tardiness_weight: number;
  operations: OperationCreate[];
}

export interface OrderResponse {
  id: string;
  external_id: string;
  name: string;
  release_minute: number;
  due_minute: number;
  tardiness_weight: number;
  operations: OperationResponse[];
}

export interface FactoryConfigPayload {
  machines: MachineCreate[];
  downtimes: DowntimeCreate[];
  orders: OrderCreate[];
  current_time_minute?: number;
}

export interface FactoryConfigResponse {
  workspace_id: string;
  machines: MachineResponse[];
  downtimes: DowntimeResponse[];
  orders: OrderResponse[];
  current_time_minute: number;
}

export interface FactoryValidationResponse {
  is_valid: boolean;
  classification: string;
  issues: string[];
}

export interface OptimizeParameters {
  primary_objective?: string;
  secondary_objective?: string | null;
  primary_time_budget_seconds?: number;
  secondary_time_budget_seconds?: number;
  num_workers?: number;
  random_seed?: number;
}

export interface OptimizeRequest {
  name: string;
  objective_type: string;
  parameters?: OptimizeParameters;
}

export type OperationStatus = 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED';

export interface ScheduledOperationResponse {
  operation_id: string;
  order_id: string;
  sequence_index: number;
  machine_id: string;
  start_minute: number;
  end_minute: number;
  duration: number;
  slack_minutes: number;
  status?: OperationStatus;
}

export interface ScheduleMetricsResponse {
  makespan_minutes: number;
  weighted_tardiness: number;
  late_order_count: number;
  on_time_rate: number;
  objective_value?: number | null;
  best_objective_bound?: number | null;
  optimality_gap?: number | null;
}

export interface ScheduleTelemetryResponse {
  wall_clock_time_seconds: number;
  deterministic_time?: number | null;
  user_cpu_time_seconds?: number | null;
  termination_reason: string;
}

export interface StageTelemetryResponse {
  status?: string | null;
  objective_value?: number | null;
  best_bound?: number | null;
  wall_clock_seconds?: number | null;
}

export interface VerificationReportResponse {
  is_valid: boolean;
  checks_run: number;
  checks_passed: number;
  violations: string[];
}

export interface ScheduleMachineResponse {
  id: string;
  name: string;
}

export interface OptimizeResponseData {
  schedule_id: string;
  name: string;
  objective_type: string;
  solver_status: string;
  verification_status: string;
  stage1_telemetry?: StageTelemetryResponse | null;
  stage2_telemetry?: StageTelemetryResponse | null;
  metrics: ScheduleMetricsResponse;
  solver_telemetry?: ScheduleTelemetryResponse | null;
  verification_report?: VerificationReportResponse | null;
  scheduled_operations: ScheduledOperationResponse[];
  downtimes?: DowntimeResponse[];
  machines?: ScheduleMachineResponse[];
  current_time_minute?: number;
}

export interface ScheduleDetailResponse {
  id: string;
  workspace_id: string;
  name: string;
  objective_type: string;
  solver_status: string;
  verification_status: string;
  stage1_telemetry?: StageTelemetryResponse | null;
  stage2_telemetry?: StageTelemetryResponse | null;
  metrics: ScheduleMetricsResponse;
  solver_telemetry?: ScheduleTelemetryResponse | null;
  scheduled_operations: ScheduledOperationResponse[];
  downtimes?: DowntimeResponse[];
  machines?: ScheduleMachineResponse[];
  created_at: string;
  current_time_minute?: number;
}

export interface ImportRowError {
  sheet: string;
  row: number;
  column: string;
  value: string;
  issue: string;
}

export interface ImportSummary {
  machine_count: number;
  order_count: number;
  operation_count: number;
  downtime_count: number;
}

export interface ImportStagedData {
  machines: MachineCreate[];
  orders: OrderCreate[];
  downtimes: DowntimeCreate[];
}

export interface ImportPreviewResponse {
  job_id: string | null;
  filename: string;
  status: string;
  is_valid: boolean;
  summary?: ImportSummary | null;
  warnings?: string[];
  staged_data?: ImportStagedData | null;
  errors?: ImportRowError[];
}

export interface ImportConfirmResponse {
  job_id: string;
  status: string;
  message: string;
  factory: FactoryConfigResponse;
}

export interface ClockAdvancePayload {
  advance_by_minutes?: number | null;
  target_time_minute?: number | null;
  expected_current_time_minute?: number | null;
  completed_operation_ids?: string[];
  remaining_duration_overrides?: Record<string, number>;
}

export interface StartOperationPayload {
  estimated_remaining_duration_minutes?: number | null;
  expected_current_time_minute?: number | null;
}

export interface CompleteOperationPayload {
  expected_current_time_minute?: number | null;
}

export interface AdjustRemainingPayload {
  remaining_duration_minutes: number;
  expected_current_time_minute?: number | null;
}

export interface ActiveOperationSummary {
  operation_id: string;
  order_id: string;
  order_code: string;
  sequence_index: number;
  machine_id: string;
  machine_name: string;
  actual_start_minute: number;
  elapsed_minutes: number;
  remaining_duration_minutes: number;
  projected_end_minute: number;
  is_overdue: boolean;
}

export interface ReadyOperationSummary {
  operation_id: string;
  order_id: string;
  order_code: string;
  sequence_index: number;
  machine_id: string;
  machine_name: string;
  processing_minutes: number;
}

export interface OccupiedMachineSummary {
  machine_id: string;
  machine_name: string;
  status: 'BUSY' | 'IDLE' | 'DOWNTIME' | string;
  active_operation_id?: string | null;
}

export interface ExecutionStatusResponse {
  workspace_id: string;
  current_time_minute: number;
  active_operations: ActiveOperationSummary[];
  ready_to_start_operations: ReadyOperationSummary[];
  occupied_machines: OccupiedMachineSummary[];
}
