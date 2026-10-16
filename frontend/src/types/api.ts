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
