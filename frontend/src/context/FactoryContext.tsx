/**
 * Factory Management State & Mutation Hook
 * Governed by DATA_AND_API.md Section 3.2 and ARCHITECTURE.md Section 3.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { apiEndpoints } from '../api/endpoints';
import { ApiClientError } from '../api/client';
import {
  DowntimeCreate,
  FactoryConfigPayload,
  FactoryConfigResponse,
  FactoryValidationResponse,
  MachineCreate,
  OrderCreate,
} from '../types/api';
import { useWorkspace } from './WorkspaceContext';

export interface FactoryContextValue {
  factory: FactoryConfigResponse | null;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string | null;
  errorCode: string | null;
  validationResult: FactoryValidationResponse | null;
  isValidating: boolean;
  loadFactory: () => Promise<void>;
  validateCurrentFactory: () => Promise<FactoryValidationResponse | null>;
  addMachine: (m: MachineCreate) => Promise<void>;
  updateMachine: (id: string, m: MachineCreate) => Promise<void>;
  deleteMachine: (id: string) => Promise<void>;
  addDowntime: (dt: DowntimeCreate) => Promise<void>;
  deleteDowntime: (id: string) => Promise<void>;
  addOrder: (o: OrderCreate) => Promise<void>;
  updateOrder: (id: string, o: OrderCreate) => Promise<void>;
  deleteOrder: (id: string) => Promise<void>;
}

const FactoryContext = createContext<FactoryContextValue | null>(null);

function formatError(err: unknown, defaultMsg: string): { message: string; code: string } {
  if (err instanceof ApiClientError) return { message: err.message, code: err.code };
  return { message: err instanceof Error ? err.message : defaultMsg, code: 'UNKNOWN_ERROR' };
}

function buildMachinesPayload(
  current: FactoryConfigResponse,
  addOrUpdate?: { id?: string; data: MachineCreate },
  deleteId?: string
): MachineCreate[] {
  let list = current.machines.map((m) => ({ id: m.id, external_id: m.external_id, name: m.name }));
  if (deleteId) {
    list = list.filter((m) => m.id !== deleteId && m.external_id !== deleteId);
  } else if (addOrUpdate) {
    list = addOrUpdate.id
      ? list.map((m) => (m.id === addOrUpdate.id ? { ...m, ...addOrUpdate.data } : m))
      : [...list, { id: '', ...addOrUpdate.data }];
  }
  return list.map((m) => ({ external_id: m.external_id, name: m.name }));
}

function buildDowntimesPayload(
  current: FactoryConfigResponse,
  add?: DowntimeCreate,
  deleteId?: string,
  deletedMachineId?: string
): DowntimeCreate[] {
  let list = current.downtimes.map((dt) => ({ ...dt }));
  if (deleteId) list = list.filter((dt) => dt.id !== deleteId);
  if (deletedMachineId) list = list.filter((dt) => dt.machine_id !== deletedMachineId);
  if (add) {
    list.push({
      id: '',
      machine_id: add.machine_id,
      start_minute: add.start_minute,
      end_minute: add.end_minute,
      reason: add.reason ?? null,
    });
  }
  return list.map((dt) => ({
    machine_id: dt.machine_id,
    start_minute: dt.start_minute,
    end_minute: dt.end_minute,
    reason: dt.reason,
  }));
}

function buildOrdersPayload(
  current: FactoryConfigResponse,
  addOrUpdate?: { id?: string; data: OrderCreate },
  deleteId?: string
): OrderCreate[] {
  let list = current.orders.map((o) => ({
    id: o.id,
    external_id: o.external_id,
    name: o.name,
    release_minute: o.release_minute,
    due_minute: o.due_minute,
    tardiness_weight: o.tardiness_weight,
    operations: o.operations.map((op) => ({
      sequence_index: op.sequence_index,
      machine_id: op.machine_id,
      processing_minutes: op.processing_minutes,
    })),
  }));
  if (deleteId) {
    list = list.filter((o) => o.id !== deleteId && o.external_id !== deleteId);
  } else if (addOrUpdate) {
    list = addOrUpdate.id
      ? list.map((o) => (o.id === addOrUpdate.id ? { id: o.id, ...addOrUpdate.data } : o))
      : [...list, { id: '', ...addOrUpdate.data }];
  }
  return list.map((o) => ({
    external_id: o.external_id,
    name: o.name,
    release_minute: o.release_minute,
    due_minute: o.due_minute,
    tardiness_weight: o.tardiness_weight,
    operations: o.operations,
  }));
}

function useFactoryState(workspaceId: string | null) {
  const [factory, setFactory] = useState<FactoryConfigResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const loadFactory = useCallback(async () => {
    if (!workspaceId) { setFactory(null); setStatus('idle'); return; }
    setStatus('loading'); setError(null); setErrorCode(null);
    try {
      setFactory(await apiEndpoints.getFactory(workspaceId));
      setStatus('success');
    } catch (err) {
      const e = formatError(err, 'Failed to fetch factory configuration');
      setStatus('error'); setError(e.message); setErrorCode(e.code);
    }
  }, [workspaceId]);

  useEffect(() => { loadFactory(); }, [loadFactory]);

  const saveConfig = useCallback(async (payload: FactoryConfigPayload): Promise<void> => {
    if (!workspaceId) throw new Error('No active workspace selected');
    setStatus('loading'); setError(null); setErrorCode(null);
    try {
      setFactory(await apiEndpoints.replaceFactory(workspaceId, payload));
      setStatus('success');
    } catch (err) {
      const e = formatError(err, 'Failed to update factory');
      setStatus('error'); setError(e.message); setErrorCode(e.code);
      throw err;
    }
  }, [workspaceId]);

  return { factory, status, error, errorCode, loadFactory, saveConfig };
}

function useFactoryMutations(
  factory: FactoryConfigResponse | null,
  saveConfig: (payload: FactoryConfigPayload) => Promise<void>
) {
  const addMachine = useCallback(async (m: MachineCreate) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory, { data: m }), downtimes: buildDowntimesPayload(factory), orders: buildOrdersPayload(factory) });
  }, [factory, saveConfig]);

  const updateMachine = useCallback(async (id: string, m: MachineCreate) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory, { id, data: m }), downtimes: buildDowntimesPayload(factory), orders: buildOrdersPayload(factory) });
  }, [factory, saveConfig]);

  const deleteMachine = useCallback(async (id: string) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory, undefined, id), downtimes: buildDowntimesPayload(factory, undefined, undefined, id), orders: buildOrdersPayload(factory) });
  }, [factory, saveConfig]);

  const addDowntime = useCallback(async (dt: DowntimeCreate) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory), downtimes: buildDowntimesPayload(factory, dt), orders: buildOrdersPayload(factory) });
  }, [factory, saveConfig]);

  const deleteDowntime = useCallback(async (id: string) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory), downtimes: buildDowntimesPayload(factory, undefined, id), orders: buildOrdersPayload(factory) });
  }, [factory, saveConfig]);

  const addOrder = useCallback(async (o: OrderCreate) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory), downtimes: buildDowntimesPayload(factory), orders: buildOrdersPayload(factory, { data: o }) });
  }, [factory, saveConfig]);

  const updateOrder = useCallback(async (id: string, o: OrderCreate) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory), downtimes: buildDowntimesPayload(factory), orders: buildOrdersPayload(factory, { id, data: o }) });
  }, [factory, saveConfig]);

  const deleteOrder = useCallback(async (id: string) => {
    if (!factory) return;
    await saveConfig({ machines: buildMachinesPayload(factory), downtimes: buildDowntimesPayload(factory), orders: buildOrdersPayload(factory, undefined, id) });
  }, [factory, saveConfig]);

  return { addMachine, updateMachine, deleteMachine, addDowntime, deleteDowntime, addOrder, updateOrder, deleteOrder };
}

export function FactoryProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const { activeWorkspaceId } = useWorkspace();
  const state = useFactoryState(activeWorkspaceId);
  const mutations = useFactoryMutations(state.factory, state.saveConfig);
  const [validationResult, setValidationResult] = useState<FactoryValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const validateCurrentFactory = useCallback(async (): Promise<FactoryValidationResponse | null> => {
    if (!activeWorkspaceId || !state.factory) return null;
    setIsValidating(true);
    try {
      const payload: FactoryConfigPayload = {
        machines: buildMachinesPayload(state.factory),
        downtimes: buildDowntimesPayload(state.factory),
        orders: buildOrdersPayload(state.factory),
      };
      const res = await apiEndpoints.validateFactory(activeWorkspaceId, payload);
      setValidationResult(res);
      return res;
    } catch {
      return null;
    } finally {
      setIsValidating(false);
    }
  }, [activeWorkspaceId, state.factory]);

  const value = useMemo(() => ({
    factory: state.factory,
    status: state.status,
    error: state.error,
    errorCode: state.errorCode,
    validationResult,
    isValidating,
    loadFactory: state.loadFactory,
    validateCurrentFactory,
    ...mutations,
  }), [state, mutations, validationResult, isValidating, validateCurrentFactory]);

  return <FactoryContext.Provider value={value}>{children}</FactoryContext.Provider>;
}

export function useFactory(): FactoryContextValue {
  const context = useContext(FactoryContext);
  if (!context) throw new Error('useFactory must be used within a FactoryProvider');
  return context;
}
