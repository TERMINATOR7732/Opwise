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
  ScheduleSummaryResponse,
  WorkspaceResponse,
} from '../types/api';

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

  /** Fetch complete factory configuration for a workspace */
  getFactory: (workspaceId: string): Promise<FactoryConfigResponse> =>
    api.get<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`),

  /** Atomically replace factory configuration for a workspace */
  replaceFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryConfigResponse> =>
    api.put<FactoryConfigResponse>(`/workspaces/${workspaceId}/factory`, payload),

  /** Dry-run validation of factory inputs without saving */
  validateFactory: (workspaceId: string, payload: FactoryConfigPayload): Promise<FactoryValidationResponse> =>
    api.post<FactoryValidationResponse>(`/workspaces/${workspaceId}/factory/validate`, payload),
};
