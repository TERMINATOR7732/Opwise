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
}

export interface OperationResponse {
  id: string;
  order_id: string;
  sequence_index: number;
  machine_id: string;
  processing_minutes: number;
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
}

export interface FactoryConfigResponse {
  workspace_id: string;
  machines: MachineResponse[];
  downtimes: DowntimeResponse[];
  orders: OrderResponse[];
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

export interface ScheduledOperationResponse {
  operation_id: string;
  order_id: string;
  sequence_index: number;
  machine_id: string;
  start_minute: number;
  end_minute: number;
  duration: number;
  slack_minutes: number;
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
  created_at: string;
}
