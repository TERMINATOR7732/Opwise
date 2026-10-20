/**
 * Typed API Endpoints for Opwise v1 Services
 * Governed by DATA_AND_API.md Section 3.2 and SPECIFICATION.md Section 1.1 (Tier 2 Demo Mode).
 */

import { api, downloadFile } from './client';
import {
  AdjustRemainingPayload,
  ClockAdvancePayload,
  CompleteOperationPayload,
  CreateWorkspaceRequest,
  ExecutionStatusResponse,
  FactoryConfigPayload,
  FactoryConfigResponse,
  FactoryValidationResponse,
  HealthResponse,
  ImportConfirmResponse,
  ImportPreviewResponse,
  OptimizeRequest,
  OptimizeResponseData,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
  StartOperationPayload,
  VerificationReportResponse,
  WorkspaceResponse,
} from '../types/api';
import {
  ScenarioCompareRequest,
  ScenarioComparisonResponse,
  ScenarioCreateRequest,
  ScenarioReoptimizeRequest,
  ScenarioResponse,
} from '../types/scenarios';
import { ScheduleReportResponse } from '../types/reports';
import {
  isDemoMode,
  getDemoWorkspaces,
  getDemoFactory,
  getDemoSchedules,
  getDemoScheduleDetail,
  verifyDemoSchedule,
  getDemoScheduleReport,
  getDemoScenarios,
} from '../demo/demoService';
import { exportDemoScheduleCsv, exportDemoScheduleJson } from '../demo/demoExport';

function createMockOptimizedResponse(workspaceId: string, req: OptimizeRequest): OptimizeResponseData {
  const detail = getDemoScheduleDetail(workspaceId, '');
  const ver = verifyDemoSchedule(workspaceId);
  return {
    schedule_id: detail.id,
    name: `${req.name} (${detail.name})`,
    objective_type: req.objective_type || detail.objective_type,
    solver_status: detail.solver_status,
    verification_status: detail.verification_status,
    metrics: detail.metrics,
    solver_telemetry: detail.solver_telemetry,
    verification_report: ver,
    scheduled_operations: detail.scheduled_operations,
    downtimes: detail.downtimes,
    machines: detail.machines,
  };
}

function createMockComparisonResponse(workspaceId: string, baselineId: string): ScenarioComparisonResponse {
  const detail = getDemoScheduleDetail(workspaceId, baselineId);
  return {
    id: 'comp-demo-mock',
    scenario_id: 'scen-demo-compare',
    baseline_schedule_id: baselineId || detail.id,
    compared_schedule_id: detail.id,
    delta_makespan: 0,
    delta_weighted_tardiness: 0,
    delta_late_order_count: 0,
    delta_on_time_rate: 0,
    objective_diff_detected: false,
    order_set_diff_detected: false,
    status_diff_detected: false,
    time_limit_diff_detected: false,
    unlike_comparison_warning: null,
    diverged_operations: [],
    created_at: detail.created_at,
  };
}

export const apiEndpoints = {
  /** Check server and database health status */
  getHealth: (): Promise<HealthResponse> =>
    isDemoMode()
      ? Promise.resolve({
          status: 'healthy',
          database: 'Standalone Demo Mode (Client-Side)',
          version: '0.1.0-demo',
        })
      : api.get<HealthResponse>('/health'),

  /** List all workspaces */
  listWorkspaces: (): Promise<WorkspaceResponse[]> =>
    isDemoMode() ? Promise.resolve(getDemoWorkspaces()) : api.get<WorkspaceResponse[]>('/workspaces'),

  /** Get single workspace details */
  getWorkspace: (id: string): Promise<WorkspaceResponse> =>
    isDemoMode()
      ? Promise.resolve(getDemoWorkspaces().find((w) => w.id === id) || getDemoWorkspaces()[0])
      : api.get<WorkspaceResponse>(`/workspaces/${id}`),

  /** Create a new workspace */
  createWorkspace: (req: CreateWorkspaceRequest): Promise<WorkspaceResponse> =>
    isDemoMode()
      ? Promise.resolve({
          id: `ws-custom-${Date.now()}`,
          name: req.name,
          description: req.description || '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
      : api.post<WorkspaceResponse>('/workspaces', req),

  /** Delete a workspace and cascade-delete its entities */
  deleteWorkspace: (id: string): Promise<void> =>
    isDemoMode() ? Promise.resolve() : api.delete<void>(`/workspaces/${id}`),

  /** List schedules belonging to a workspace */
  listSchedules: (workspaceId: string): Promise<ScheduleSummaryResponse[]> =>
    isDemoMode() ? Promise.resolve(getDemoSchedules(workspaceId)) : api.get<ScheduleSummaryResponse[]>(`/workspaces/${workspaceId}/schedules`),

  /** Get detailed schedule data including operations and solver telemetry */
  getSchedule: (workspaceId: string, scheduleId: string): Promise<ScheduleDetailResponse> =>
    isDemoMode()
      ? Promise.resolve(getDemoScheduleDetail(workspaceId, scheduleId))
      : api.get<ScheduleDetailResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}`),

  /** Run on-demand independent clean-room verification for a schedule */
  verifySchedule: (workspaceId: string, scheduleId: string): Promise<VerificationReportResponse> =>
    isDemoMode()
      ? Promise.resolve(verifyDemoSchedule(workspaceId))
      : api.post<VerificationReportResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}/verify`),

  /** Execute synchronous CP-SAT optimization and independent verification */
  optimizeSchedule: (workspaceId: string, req: OptimizeRequest): Promise<OptimizeResponseData> =>
    isDemoMode()
      ? Promise.resolve(createMockOptimizedResponse(workspaceId, req))
      : api.post<OptimizeResponseData>(`/workspaces/${workspaceId}/optimize`, req),

  /** Fetch complete factory configuration for a workspace */
  getFactory: (workspaceId: string): Promise<FactoryConfigResponse> =>
    isDemoMode() ? Promise.resolve(getDemoFactory(workspaceId)) : api.get<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`),

  /** Atomically replace factory configuration for a workspace */
  replaceFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryConfigResponse> =>
    api.put<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`, payload),

  /** Dry-run validation of factory inputs without saving */
  validateFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryValidationResponse> =>
    isDemoMode()
      ? Promise.resolve({ is_valid: true, classification: 'VALID_NON_EMPTY_FACTORY', issues: [] })
      : api.post<FactoryValidationResponse>(`/workspaces/${workspaceId}/factory/validate`, payload),

  /** List disruption scenarios for a workspace */
  listScenarios: (workspaceId: string): Promise<ScenarioResponse[]> =>
    isDemoMode() ? Promise.resolve(getDemoScenarios(workspaceId)) : api.get<ScenarioResponse[]>(`/workspaces/${workspaceId}/scenarios`),

  /** Get scenario details and reoptimization results */
  getScenario: (workspaceId: string, scenarioId: string): Promise<ScenarioResponse> =>
    api.get<ScenarioResponse>(`/workspaces/${workspaceId}/scenarios/${scenarioId}`),

  /** Create an isolated disruption scenario */
  createScenario: (workspaceId: string, req: ScenarioCreateRequest): Promise<ScenarioResponse> =>
    api.post<ScenarioResponse>(`/workspaces/${workspaceId}/scenarios`, req),

  /** Delete a scenario and its comparisons */
  deleteScenario: (workspaceId: string, scenarioId: string): Promise<{ deleted: boolean; scenario_id: string }> =>
    api.delete<{ deleted: boolean; scenario_id: string }>(`/workspaces/${workspaceId}/scenarios/${scenarioId}`),

  /** Reoptimize factory schedule under disruption constraints */
  reoptimizeScenario: (
    workspaceId: string,
    scenarioId: string,
    _req?: ScenarioReoptimizeRequest
  ): Promise<ScenarioComparisonResponse> =>
    isDemoMode()
      ? Promise.resolve(createMockComparisonResponse(workspaceId, ''))
      : api.post<ScenarioComparisonResponse>(`/workspaces/${workspaceId}/scenarios/${scenarioId}/reoptimize`, _req),

  /** Compare baseline schedule with scenario recovery schedule */
  compareSchedules: (workspaceId: string, req: ScenarioCompareRequest): Promise<ScenarioComparisonResponse> =>
    isDemoMode()
      ? Promise.resolve(createMockComparisonResponse(workspaceId, req.baseline_schedule_id))
      : api.post<ScenarioComparisonResponse>(`/workspaces/${workspaceId}/scenarios/compare`, req),

  /** Get comprehensive schedule report and metrics breakdown */
  getScheduleReport: (workspaceId: string, scheduleId: string): Promise<ScheduleReportResponse> =>
    isDemoMode()
      ? Promise.resolve(getDemoScheduleReport(workspaceId))
      : api.get<ScheduleReportResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}/report`),

  /** Trigger one-click download of schedule CSV or JSON report */
  downloadScheduleExport: (workspaceId: string, scheduleId: string, format: 'csv' | 'json'): Promise<void> => {
    if (isDemoMode()) {
      const detail = getDemoScheduleDetail(workspaceId, scheduleId);
      if (format === 'csv') {
        exportDemoScheduleCsv(detail);
      } else {
        const rep = getDemoScheduleReport(workspaceId);
        exportDemoScheduleJson(rep);
      }
      return Promise.resolve();
    }
    return downloadFile(
      `/workspaces/${workspaceId}/schedules/${scheduleId}/export?format=${format}`,
      `schedule_${scheduleId}_report.${format}`
    );
  },

  /** Trigger one-click download of scenario CSV or JSON export */
  downloadScenarioExport: (workspaceId: string, scenarioId: string, format: 'csv' | 'json'): Promise<void> => {
    if (isDemoMode()) {
      const detail = getDemoScheduleDetail(workspaceId, '');
      if (format === 'csv') {
        exportDemoScheduleCsv(detail);
      } else {
        const rep = getDemoScheduleReport(workspaceId);
        exportDemoScheduleJson(rep);
      }
      return Promise.resolve();
    }
    return downloadFile(
      `/workspaces/${workspaceId}/scenarios/${scenarioId}/export?format=${format}`,
      `scenario_${scenarioId}_export.${format}`
    );
  },

  /** Upload CSV/Excel file for preview and validation */
  previewImport: (workspaceId: string, file: File): Promise<ImportPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    return api.postForm<ImportPreviewResponse>(`/workspaces/${workspaceId}/import/preview`, formData);
  },

  /** Confirm and atomically commit staged import job into factory */
  confirmImport: (workspaceId: string, jobId: string): Promise<ImportConfirmResponse> =>
    api.post<ImportConfirmResponse>(`/workspaces/${workspaceId}/import/confirm`, { job_id: jobId }),

  /** Download starter template (format: 'csv' | 'xlsx') */
  downloadTemplate: (format: 'csv' | 'xlsx'): Promise<void> =>
    downloadFile(`/templates/${format}`, `opwise_factory_template.${format === 'csv' ? 'zip' : 'xlsx'}`),

  /** Advance plant clock and reconcile active operations */
  advanceClock: (workspaceId: string, payload: ClockAdvancePayload): Promise<ExecutionStatusResponse> =>
    api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/clock/advance`, payload),

  /** Start a planned operation at the current plant clock */
  startOperation: (
    workspaceId: string,
    operationId: string,
    payload: StartOperationPayload = {}
  ): Promise<ExecutionStatusResponse> =>
    api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/start`, payload),

  /** Complete an in-progress operation at the current plant clock */
  completeOperation: (
    workspaceId: string,
    operationId: string,
    payload: CompleteOperationPayload = {}
  ): Promise<ExecutionStatusResponse> =>
    api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/complete`, payload),

  /** Adjust remaining duration for an in-progress operation */
  adjustRemainingDuration: (
    workspaceId: string,
    operationId: string,
    payload: AdjustRemainingPayload
  ): Promise<ExecutionStatusResponse> =>
    api.patch<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/remaining`, payload),

  /** Get shop floor execution dispatching status */
  getExecutionStatus: (workspaceId: string): Promise<ExecutionStatusResponse> =>
    api.get<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/status`),
};
