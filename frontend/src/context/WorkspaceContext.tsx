/**
 * Global Workspace State Machine & Context
 * Governed by DATA_AND_API.md Section 1.1 Table 1 and ARCHITECTURE.md Section 3.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { apiEndpoints } from '../api/endpoints';
import { ApiClientError } from '../api/client';
import { WorkspaceResponse } from '../types/api';

const STORAGE_KEY = 'opwise_active_workspace_id';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

export interface WorkspaceContextValue {
  workspaces: WorkspaceResponse[];
  activeWorkspaceId: string | null;
  activeWorkspace: WorkspaceResponse | null;
  status: AsyncStatus;
  error: string | null;
  errorCode: string | null;
  refreshWorkspaces: () => Promise<void>;
  selectWorkspace: (id: string) => void;
  createWorkspace: (name: string, description?: string) => Promise<WorkspaceResponse>;
  deleteWorkspace: (id: string) => Promise<void>;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export interface WorkspaceProviderProps {
  children: React.ReactNode;
  initialWorkspaces?: WorkspaceResponse[];
  initialActiveId?: string | null;
}

function getInitialActiveId(initialActiveId?: string | null): string | null {
  if (initialActiveId !== undefined) return initialActiveId;
  if (typeof window !== 'undefined') {
    return localStorage.getItem(STORAGE_KEY);
  }
  return null;
}

function reconcileActiveId(prev: string | null, data: WorkspaceResponse[]): string | null {
  if (prev && data.some((w) => w.id === prev)) {
    return prev;
  }
  if (data.length > 0) {
    const firstId = data[0].id;
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, firstId);
    }
    return firstId;
  }
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
  }
  return null;
}

function handleContextError(
  err: unknown,
  defaultMsg: string,
  defaultCode: string,
  setError: (e: string | null) => void,
  setErrorCode: (c: string | null) => void
): never {
  if (err instanceof ApiClientError) {
    setError(err.message);
    setErrorCode(err.code);
    throw err;
  }
  const msg = err instanceof Error ? err.message : defaultMsg;
  setError(msg);
  setErrorCode(defaultCode);
  throw new Error(msg);
}

function useWorkspaceMutations(
  setWorkspaces: React.Dispatch<React.SetStateAction<WorkspaceResponse[]>>,
  activeWorkspaceId: string | null,
  setActiveWorkspaceId: React.Dispatch<React.SetStateAction<string | null>>,
  selectWorkspace: (id: string) => void,
  setStatus: (s: AsyncStatus) => void,
  setError: (e: string | null) => void,
  setErrorCode: (c: string | null) => void
) {
  const createWorkspace = useCallback(async (name: string, description: string = ''): Promise<WorkspaceResponse> => {
    setStatus('loading');
    setError(null);
    setErrorCode(null);
    try {
      const created = await apiEndpoints.createWorkspace({ name: name.trim(), description: description.trim() });
      setWorkspaces((prev) => [created, ...prev]);
      selectWorkspace(created.id);
      setStatus('success');
      return created;
    } catch (err: unknown) {
      setStatus('error');
      return handleContextError(err, 'Failed to create workspace', 'CREATE_FAILED', setError, setErrorCode);
    }
  }, [selectWorkspace, setStatus, setError, setErrorCode, setWorkspaces]);

  const deleteWorkspace = useCallback(async (id: string): Promise<void> => {
    setStatus('loading');
    setError(null);
    setErrorCode(null);
    try {
      await apiEndpoints.deleteWorkspace(id);
      setWorkspaces((prev) => prev.filter((w) => w.id !== id));
      if (activeWorkspaceId === id) {
        setActiveWorkspaceId(null);
        if (typeof window !== 'undefined') localStorage.removeItem(STORAGE_KEY);
      }
      setStatus('success');
    } catch (err: unknown) {
      setStatus('error');
      return handleContextError(err, 'Failed to delete workspace', 'DELETE_FAILED', setError, setErrorCode);
    }
  }, [activeWorkspaceId, setActiveWorkspaceId, setStatus, setError, setErrorCode, setWorkspaces]);

  return { createWorkspace, deleteWorkspace };
}

function useWorkspaceRefresh(
  setWorkspaces: React.Dispatch<React.SetStateAction<WorkspaceResponse[]>>,
  setStatus: (s: AsyncStatus) => void,
  setError: (e: string | null) => void,
  setErrorCode: (c: string | null) => void,
  setActiveWorkspaceId: React.Dispatch<React.SetStateAction<string | null>>
) {
  return useCallback(async () => {
    setStatus('loading');
    setError(null);
    setErrorCode(null);
    try {
      const data = await apiEndpoints.listWorkspaces();
      setWorkspaces(data);
      setStatus('success');
      setActiveWorkspaceId((prev) => reconcileActiveId(prev, data));
    } catch (err: unknown) {
      setStatus('error');
      if (err instanceof ApiClientError) {
        setError(err.message);
        setErrorCode(err.code);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch workspaces');
        setErrorCode('UNKNOWN_ERROR');
      }
    }
  }, [setActiveWorkspaceId, setError, setErrorCode, setStatus, setWorkspaces]);
}

function useWorkspaceState(initialWorkspaces?: WorkspaceResponse[], initialActiveId?: string | null) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>(initialWorkspaces || []);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(() => getInitialActiveId(initialActiveId));
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const selectWorkspace = useCallback((id: string) => {
    setActiveWorkspaceId(id);
    if (typeof window !== 'undefined') localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const refreshWorkspaces = useWorkspaceRefresh(setWorkspaces, setStatus, setError, setErrorCode, setActiveWorkspaceId);

  const { createWorkspace, deleteWorkspace } = useWorkspaceMutations(
    setWorkspaces,
    activeWorkspaceId,
    setActiveWorkspaceId,
    selectWorkspace,
    setStatus,
    setError,
    setErrorCode
  );

  return {
    workspaces,
    activeWorkspaceId,
    status,
    error,
    errorCode,
    refreshWorkspaces,
    selectWorkspace,
    createWorkspace,
    deleteWorkspace,
  };
}

export function WorkspaceProvider({
  children,
  initialWorkspaces,
  initialActiveId,
}: WorkspaceProviderProps): React.ReactElement {
  const state = useWorkspaceState(initialWorkspaces, initialActiveId);
  const { refreshWorkspaces } = state;

  useEffect(() => {
    if (initialWorkspaces === undefined) {
      refreshWorkspaces();
    }
  }, [initialWorkspaces, refreshWorkspaces]);

  const activeWorkspace = useMemo(
    () => state.workspaces.find((w) => w.id === state.activeWorkspaceId) || null,
    [state.workspaces, state.activeWorkspaceId]
  );

  const value = useMemo(
    () => ({
      ...state,
      activeWorkspace,
    }),
    [state, activeWorkspace]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
}
