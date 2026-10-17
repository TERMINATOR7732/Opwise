/**
 * Typed API Endpoints for Opwise v1 Services
 * Governed by DATA_AND_API.md Section 3.2
 */

import { api } from './client';
import {
  CreateWorkspaceRequest,
  FactoryConfigPayload,
  FactoryConfigResponse,
  FactoryValidationResponse,
  HealthResponse,
  OptimizeRequest,
  OptimizeResponseData,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
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


export const apiEndpoints = {
  /** Check server and database health status */
  getHealth: (): Promise<HealthResponse> => api.get<HealthResponse>('/health'),

  /** List all workspaces */
  listWorkspaces: (): Promise<WorkspaceResponse[]> => api.get<WorkspaceResponse[]>('/workspaces'),

  /** Get single workspace details */
  getWorkspace: (id: string): Promise<WorkspaceResponse> => api.get<WorkspaceResponse>(`/workspaces/${id}`),

  /** Create a new workspace */
  createWorkspace: (req: CreateWorkspaceRequest): Promise<WorkspaceResponse> =>
    api.post<WorkspaceResponse>('/workspaces', req),

  /** Delete a workspace and cascade-delete its entities */
  deleteWorkspace: (id: string): Promise<void> => api.delete<void>(`/workspaces/${id}`),

  /** List schedules belonging to a workspace */
  listSchedules: (workspaceId: string): Promise<ScheduleSummaryResponse[]> =>
    api.get<ScheduleSummaryResponse[]>(`/workspaces/${workspaceId}/schedules`),

  /** Get detailed schedule data including operations and solver telemetry */
  getSchedule: (workspaceId: string, scheduleId: string): Promise<ScheduleDetailResponse> =>
    api.get<ScheduleDetailResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}`),

  /** Run on-demand independent clean-room verification for a schedule */
  verifySchedule: (workspaceId: string, scheduleId: string): Promise<VerificationReportResponse> =>
    api.post<VerificationReportResponse>(`/workspaces/${workspaceId}/schedules/${scheduleId}/verify`),

  /** Execute synchronous CP-SAT optimization and independent verification */
  optimizeSchedule: (workspaceId: string, req: OptimizeRequest): Promise<OptimizeResponseData> =>
    api.post<OptimizeResponseData>(`/workspaces/${workspaceId}/optimize`, req),

  /** Fetch complete factory configuration for a workspace */
  getFactory: (workspaceId: string): Promise<FactoryConfigResponse> =>
    api.get<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`),

  /** Atomically replace factory configuration for a workspace */
  replaceFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryConfigResponse> =>
    api.put<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`, payload),

  /** Dry-run validation of factory inputs without saving */
  validateFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryValidationResponse> =>
    api.post<FactoryValidationResponse>(`/workspaces/${workspaceId}/factory/validate`, payload),

  /** List disruption scenarios for a workspace */
  listScenarios: (workspaceId: string): Promise<ScenarioResponse[]> =>
    api.get<ScenarioResponse[]>(`/workspaces/${workspaceId}/scenarios`),

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
    req?: ScenarioReoptimizeRequest
  ): Promise<ScenarioComparisonResponse> =>
    api.post<ScenarioComparisonResponse>(`/workspaces/${workspaceId}/scenarios/${scenarioId}/reoptimize`, req),

  /** Compare baseline schedule with scenario recovery schedule */
  compareSchedules: (workspaceId: string, req: ScenarioCompareRequest): Promise<ScenarioComparisonResponse> =>
    api.post<ScenarioComparisonResponse>(`/workspaces/${workspaceId}/scenarios/compare`, req),
};
