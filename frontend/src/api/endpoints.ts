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
  getDemoScenario,
  createDemoScenario,
  deleteDemoScenario,
  reoptimizeDemoScenario,
  getDemoExecutionStatus,
  advanceDemoClock,
  startDemoOperation,
  completeDemoOperation,
  adjustDemoRemainingDuration,
  saveDemoFactory,
  createDemoWorkspace,
  deleteDemoWorkspace,
  optimizeDemoSchedule,
} from '../demo/demoService';
import { exportDemoScheduleCsv, exportDemoScheduleJson } from '../demo/demoExport';
import { previewDemoImport, confirmDemoImport, downloadDemoTemplate } from '../demo/demoImport';

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
    isDemoMode() ? Promise.resolve(createDemoWorkspace(req)) : api.post<WorkspaceResponse>('/workspaces', req),

  /** Delete a workspace and cascade-delete its entities */
  deleteWorkspace: (id: string): Promise<void> => {
    if (isDemoMode()) {
      deleteDemoWorkspace(id);
      return Promise.resolve();
    }
    return api.delete<void>(`/workspaces/${id}`);
  },

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
      ? Promise.resolve(verifyDemoSchedule(workspaceId, scheduleId))
      : api.post<VerificationReportResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}/verify`),

  /** Execute synchronous CP-SAT optimization and independent verification */
  optimizeSchedule: (workspaceId: string, req: OptimizeRequest): Promise<OptimizeResponseData> =>
    isDemoMode()
      ? Promise.resolve(optimizeDemoSchedule(workspaceId, req))
      : api.post<OptimizeResponseData>(`/workspaces/${workspaceId}/optimize`, req),

  /** Fetch complete factory configuration for a workspace */
  getFactory: (workspaceId: string): Promise<FactoryConfigResponse> =>
    isDemoMode() ? Promise.resolve(getDemoFactory(workspaceId)) : api.get<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`),

  /** Atomically replace factory configuration for a workspace */
  replaceFactory: async (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryConfigResponse> =>
    isDemoMode()
      ? saveDemoFactory(workspaceId, payload)
      : api.put<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`, payload),

  /** Dry-run validation of factory inputs without saving */
  validateFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryValidationResponse> =>
    isDemoMode()
      ? Promise.resolve({ is_valid: true, classification: 'VALID_NON_EMPTY_FACTORY', issues: [] })
      : api.post<FactoryValidationResponse>(`/workspaces/${workspaceId}/factory/validate`, payload),

  /** List disruption scenarios for a workspace */
  listScenarios: (workspaceId: string): Promise<ScenarioResponse[]> =>
    isDemoMode() ? Promise.resolve(getDemoScenarios(workspaceId)) : api.get<ScenarioResponse[]>(`/workspaces/${workspaceId}/scenarios`),

  /** Get scenario details and reoptimization results */
  getScenario: async (workspaceId: string, scenarioId: string): Promise<ScenarioResponse> =>
    isDemoMode()
      ? getDemoScenario(workspaceId, scenarioId)
      : api.get<ScenarioResponse>(`/workspaces/${workspaceId}/scenarios/${scenarioId}`),

  /** Create an isolated disruption scenario */
  createScenario: async (workspaceId: string, req: ScenarioCreateRequest): Promise<ScenarioResponse> =>
    isDemoMode()
      ? createDemoScenario(workspaceId, req)
      : api.post<ScenarioResponse>(`/workspaces/${workspaceId}/scenarios`, req),

  /** Delete a scenario and its comparisons */
  deleteScenario: async (workspaceId: string, scenarioId: string): Promise<{ deleted: boolean; scenario_id: string }> =>
    isDemoMode()
      ? deleteDemoScenario(workspaceId, scenarioId)
      : api.delete<{ deleted: boolean; scenario_id: string }>(`/workspaces/${workspaceId}/scenarios/${scenarioId}`),

  /** Reoptimize factory schedule under disruption constraints */
  reoptimizeScenario: async (
    workspaceId: string,
    scenarioId: string,
    req?: ScenarioReoptimizeRequest
  ): Promise<ScenarioComparisonResponse> =>
    isDemoMode()
      ? reoptimizeDemoScenario(workspaceId, scenarioId, req)
      : api.post<ScenarioComparisonResponse>(`/workspaces/${workspaceId}/scenarios/${scenarioId}/reoptimize`, req),

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
    if (isDemoMode()) {
      return previewDemoImport(workspaceId, file);
    }
    const formData = new FormData();
    formData.append('file', file);
    return api.postForm<ImportPreviewResponse>(`/workspaces/${workspaceId}/import/preview`, formData);
  },

  /** Confirm and atomically commit staged import job into factory */
  confirmImport: async (workspaceId: string, jobId: string): Promise<ImportConfirmResponse> => {
    if (isDemoMode()) {
      return confirmDemoImport(workspaceId, jobId);
    }
    return api.post<ImportConfirmResponse>(`/workspaces/${workspaceId}/import/confirm`, { job_id: jobId });
  },

  /** Download starter template (format: 'csv' | 'xlsx') */
  downloadTemplate: (format: 'csv' | 'xlsx'): Promise<void> => {
    if (isDemoMode()) {
      try {
        downloadDemoTemplate(format);
        return Promise.resolve();
      } catch (err) {
        return Promise.reject(err);
      }
    }
    return downloadFile(`/templates/${format}`, `opwise_factory_template.${format === 'csv' ? 'zip' : 'xlsx'}`);
  },

  /** Advance plant clock and reconcile active operations */
  advanceClock: async (workspaceId: string, payload: ClockAdvancePayload): Promise<ExecutionStatusResponse> =>
    isDemoMode()
      ? advanceDemoClock(workspaceId, payload)
      : api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/clock/advance`, payload),

  /** Start a planned operation at the current plant clock */
  startOperation: async (
    workspaceId: string,
    operationId: string,
    payload: StartOperationPayload = {}
  ): Promise<ExecutionStatusResponse> =>
    isDemoMode()
      ? startDemoOperation(workspaceId, operationId, payload)
      : api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/start`, payload),

  /** Complete an in-progress operation at the current plant clock */
  completeOperation: async (
    workspaceId: string,
    operationId: string,
    payload: CompleteOperationPayload = {}
  ): Promise<ExecutionStatusResponse> =>
    isDemoMode()
      ? completeDemoOperation(workspaceId, operationId, payload)
      : api.post<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/complete`, payload),

  /** Adjust remaining duration for an in-progress operation */
  adjustRemainingDuration: async (
    workspaceId: string,
    operationId: string,
    payload: AdjustRemainingPayload
  ): Promise<ExecutionStatusResponse> =>
    isDemoMode()
      ? adjustDemoRemainingDuration(workspaceId, operationId, payload)
      : api.patch<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/operations/${operationId}/remaining`, payload),

  /** Get shop floor execution dispatching status */
  getExecutionStatus: async (workspaceId: string): Promise<ExecutionStatusResponse> =>
    isDemoMode()
      ? getDemoExecutionStatus(workspaceId)
      : api.get<ExecutionStatusResponse>(`/workspaces/${workspaceId}/execution/status`),
};
