/**
 * Standalone Client-Side Demo Service & Fallback Provider
 * Governed by SPECIFICATION.md Section 1.1 (Tier 2), Section 8.4 State 13, Section 10,
 * and MILESTONE_15D_SCOPE_PROPOSAL.md.
 */

import {
  ActiveOperationSummary,
  AdjustRemainingPayload,
  ClockAdvancePayload,
  CompleteOperationPayload,
  CreateWorkspaceRequest,
  ExecutionStatusResponse,
  FactoryConfigPayload,
  FactoryConfigResponse,
  OccupiedMachineSummary,
  OperationResponse,
  OrderResponse,
  ReadyOperationSummary,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
  ScheduledOperationResponse,
  StartOperationPayload,
  VerificationReportResponse,
  WorkspaceResponse,
} from '../types/api';
import { ScheduleReportResponse } from '../types/reports';
import {
  OperationDivergence,
  ScenarioComparisonResponse,
  ScenarioCreateRequest,
  ScenarioReoptimizeRequest,
  ScenarioResponse,
} from '../types/scenarios';
import { ApiClientError } from '../api/client';
import { DEMO_FIXTURES, DEMO_SCENARIO_LIST, DemoFixture } from './fixtures';
import { verifyScheduleClient } from './clientVerifier';
import { buildDemoReport } from './demoReportBuilder';
import { clearDemoStagedImports } from './demoImport';

const DEMO_MODE_STORAGE_KEY = 'opwise_demo_mode';
const ACTIVE_DEMO_STORAGE_KEY = 'opwise_active_demo_id';

let runtimeDemoModeOverride: boolean | null = null;

// In-memory mutable stores for demo mode sessions
const demoFactoryState: Record<string, FactoryConfigResponse> = {};
const demoScenariosState: Record<string, ScenarioResponse[]> = {};
const demoRecoverySchedules: Record<string, ScheduleDetailResponse> = {};
const demoCustomWorkspaces: WorkspaceResponse[] = [];

function findOperationAndOrder(
  factory: FactoryConfigResponse,
  operationId: string
): { order: OrderResponse; op: OperationResponse } {
  for (const order of factory.orders) {
    for (const op of order.operations) {
      if (op.id === operationId) {
        return { order, op };
      }
    }
  }
  throw new ApiClientError('RESOURCE_NOT_FOUND', `Operation '${operationId}' not found.`, 404);
}

export function isDemoMode(): boolean {
  if (runtimeDemoModeOverride !== null) {
    return runtimeDemoModeOverride;
  }
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.MODE === 'demo') {
    return true;
  }
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(DEMO_MODE_STORAGE_KEY);
    if (stored === 'true') return true;
    if (window.location.hash.includes('demo=true')) return true;
  }
  return false;
}

export function setDemoMode(enabled: boolean): void {
  runtimeDemoModeOverride = enabled;
  if (typeof window !== 'undefined') {
    localStorage.setItem(DEMO_MODE_STORAGE_KEY, enabled ? 'true' : 'false');
    window.dispatchEvent(new CustomEvent('opwise:demo-mode-changed', { detail: { enabled } }));
  }
}

export function getActiveDemoId(): string {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(ACTIVE_DEMO_STORAGE_KEY);
    if (stored && DEMO_FIXTURES[stored]) return stored;
  }
  return 'demo-1';
}

export function setActiveDemoId(id: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(ACTIVE_DEMO_STORAGE_KEY, id);
    window.dispatchEvent(new CustomEvent('opwise:demo-scenario-changed', { detail: { id } }));
  }
}

export function getDemoWorkspaces(): WorkspaceResponse[] {
  const standard = DEMO_SCENARIO_LIST.map((fixture) => ({
    id: fixture.factory.workspace_id,
    name: `[Demo] ${fixture.name}`,
    description: fixture.description,
    created_at: fixture.schedule.created_at,
    updated_at: fixture.schedule.created_at,
  }));
  return [...standard, ...JSON.parse(JSON.stringify(demoCustomWorkspaces))];
}

export function createDemoWorkspace(req: CreateWorkspaceRequest): WorkspaceResponse {
  const now = new Date().toISOString();
  const newWs: WorkspaceResponse = {
    id: `ws-custom-${Date.now()}`,
    name: req.name,
    description: req.description || '',
    created_at: now,
    updated_at: now,
  };
  demoCustomWorkspaces.push(newWs);
  return JSON.parse(JSON.stringify(newWs));
}

export function deleteDemoWorkspace(id: string): void {
  const idx = demoCustomWorkspaces.findIndex((w) => w.id === id);
  if (idx !== -1) {
    demoCustomWorkspaces.splice(idx, 1);
  }
  resetDemoFactoryState(id);
}

export function findDemoFixtureByWorkspace(workspaceId: string): DemoFixture {
  const match = DEMO_SCENARIO_LIST.find((f) => f.factory.workspace_id === workspaceId);
  return match || DEMO_FIXTURES[getActiveDemoId()] || DEMO_FIXTURES['demo-1'];
}

function initDemoFactoryState(workspaceId: string): FactoryConfigResponse {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const cloned: FactoryConfigResponse = JSON.parse(JSON.stringify(fixture.factory));
  if (typeof cloned.current_time_minute !== 'number') {
    cloned.current_time_minute = 0;
  }
  for (const order of cloned.orders) {
    for (const op of order.operations) {
      if (!op.status) {
        op.status = 'PLANNED';
      }
      if (op.actual_start_minute === undefined) op.actual_start_minute = null;
      if (op.actual_end_minute === undefined) op.actual_end_minute = null;
      if (op.remaining_duration_minutes === undefined) op.remaining_duration_minutes = null;
    }
  }
  return cloned;
}

export function getMutableDemoFactory(workspaceId: string): FactoryConfigResponse {
  if (!demoFactoryState[workspaceId]) {
    demoFactoryState[workspaceId] = initDemoFactoryState(workspaceId);
  }
  return demoFactoryState[workspaceId];
}

export function resetDemoFactoryState(workspaceId?: string): void {
  if (workspaceId) {
    delete demoFactoryState[workspaceId];
    delete demoScenariosState[workspaceId];
  } else {
    for (const key of Object.keys(demoFactoryState)) {
      delete demoFactoryState[key];
    }
    for (const key of Object.keys(demoScenariosState)) {
      delete demoScenariosState[key];
    }
    for (const key of Object.keys(demoRecoverySchedules)) {
      delete demoRecoverySchedules[key];
    }
    demoCustomWorkspaces.length = 0;
    clearDemoStagedImports();
  }
}

export function getDemoFactory(workspaceId: string): FactoryConfigResponse {
  return JSON.parse(JSON.stringify(getMutableDemoFactory(workspaceId)));
}

export function saveDemoFactory(workspaceId: string, payload: FactoryConfigPayload): FactoryConfigResponse {
  const factory = getMutableDemoFactory(workspaceId);
  if (typeof payload.current_time_minute === 'number') {
    factory.current_time_minute = payload.current_time_minute;
  }

  factory.machines = payload.machines.map((m, idx) => ({
    id: m.external_id || `M${idx + 1}`,
    external_id: m.external_id,
    name: m.name,
    created_at: new Date().toISOString(),
  }));

  factory.downtimes = payload.downtimes.map((dt, idx) => ({
    id: `dt-${idx + 1}`,
    machine_id: dt.machine_id,
    start_minute: dt.start_minute,
    end_minute: dt.end_minute,
    reason: dt.reason ?? null,
  }));

  factory.orders = payload.orders.map((o, orderIdx) => ({
    id: o.external_id || `ORD-${orderIdx + 1}`,
    external_id: o.external_id,
    name: o.name,
    release_minute: o.release_minute,
    due_minute: o.due_minute,
    tardiness_weight: o.tardiness_weight,
    operations: o.operations.map((op, opIdx) => ({
      id: `${o.external_id || `ORD-${orderIdx + 1}`}-OP${op.sequence_index || opIdx + 1}`,
      order_id: o.external_id || `ORD-${orderIdx + 1}`,
      sequence_index: op.sequence_index,
      machine_id: op.machine_id,
      processing_minutes: op.processing_minutes,
      status: op.status || 'PLANNED',
      actual_start_minute: op.actual_start_minute ?? null,
      actual_end_minute: op.actual_end_minute ?? null,
      remaining_duration_minutes: op.remaining_duration_minutes ?? null,
    })),
  }));

  return JSON.parse(JSON.stringify(factory));
}

export function getDemoExecutionStatus(workspaceId: string): ExecutionStatusResponse {
  const factory = getMutableDemoFactory(workspaceId);
  const currentTime = factory.current_time_minute;
  const machineMap = new Map(factory.machines.map((m) => [m.id, m]));

  const allOps: { order: OrderResponse; op: OperationResponse }[] = [];
  for (const order of factory.orders) {
    for (const op of order.operations) {
      allOps.push({ order, op });
    }
  }

  // 1. Active (IN_PROGRESS) operations
  const activeSummaries: ActiveOperationSummary[] = [];
  for (const { order, op } of allOps) {
    if (op.status === 'IN_PROGRESS') {
      const start = op.actual_start_minute ?? currentTime;
      const rem = op.remaining_duration_minutes ?? op.processing_minutes;
      const elapsed = Math.max(0, currentTime - start);
      const projectedEnd = currentTime + rem;
      const isOverdue = elapsed >= op.processing_minutes;
      const mach = machineMap.get(op.machine_id);
      const machineName = mach ? mach.name : op.machine_id;

      activeSummaries.push({
        operation_id: op.id,
        order_id: order.id,
        order_code: order.external_id,
        sequence_index: op.sequence_index,
        machine_id: op.machine_id,
        machine_name: machineName,
        actual_start_minute: start,
        elapsed_minutes: elapsed,
        remaining_duration_minutes: rem,
        projected_end_minute: projectedEnd,
        is_overdue: isOverdue,
      });
    }
  }

  // Occupied machines and busy orders
  const occupiedMachineIds = new Set(
    allOps.filter(({ op }) => op.status === 'IN_PROGRESS').map(({ op }) => op.machine_id)
  );
  const busyOrderIds = new Set(
    allOps.filter(({ op }) => op.status === 'IN_PROGRESS').map(({ order }) => order.id)
  );

  // Machine downtime at currentTime: [start_minute, end_minute)
  const downtimeMachineIds = new Set<string>();
  for (const dt of factory.downtimes) {
    if (dt.start_minute <= currentTime && currentTime < dt.end_minute) {
      downtimeMachineIds.add(dt.machine_id);
    }
  }

  // 2. Ready-to-start (PLANNED) operations
  const readySummaries: ReadyOperationSummary[] = [];
  for (const { order, op } of allOps) {
    if (op.status === 'PLANNED') {
      // Order must be released
      if (order.release_minute > currentTime) continue;
      // Order cannot already have an operation in progress
      if (busyOrderIds.has(order.id)) continue;
      // Predecessor sequence constraint
      if (op.sequence_index > 1) {
        const pred = order.operations.find((p) => p.sequence_index === op.sequence_index - 1);
        if (!pred) continue;
        if (pred.status !== 'COMPLETED') continue;
        if (
          pred.actual_end_minute === null ||
          pred.actual_end_minute === undefined ||
          pred.actual_end_minute > currentTime
        ) {
          continue;
        }
      }
      // Machine must be free
      if (occupiedMachineIds.has(op.machine_id)) continue;
      // Machine must not be in active downtime
      if (downtimeMachineIds.has(op.machine_id)) continue;

      const mach = machineMap.get(op.machine_id);
      const machineName = mach ? mach.name : op.machine_id;
      readySummaries.push({
        operation_id: op.id,
        order_id: order.id,
        order_code: order.external_id,
        sequence_index: op.sequence_index,
        machine_id: op.machine_id,
        machine_name: machineName,
        processing_minutes: op.processing_minutes,
      });
    }
  }

  // 3. Machine status summaries
  const machineSummaries: OccupiedMachineSummary[] = [];
  for (const m of factory.machines) {
    const activeOpOnM = allOps.find(
      ({ op }) => op.machine_id === m.id && op.status === 'IN_PROGRESS'
    )?.op;

    let status: 'BUSY' | 'DOWNTIME' | 'IDLE';
    let activeId: string | null = null;
    if (activeOpOnM) {
      status = 'BUSY';
      activeId = activeOpOnM.id;
    } else if (downtimeMachineIds.has(m.id)) {
      status = 'DOWNTIME';
    } else {
      status = 'IDLE';
    }

    machineSummaries.push({
      machine_id: m.id,
      machine_name: m.name,
      status,
      active_operation_id: activeId,
    });
  }

  return {
    workspace_id: workspaceId,
    current_time_minute: currentTime,
    active_operations: activeSummaries,
    ready_to_start_operations: readySummaries,
    occupied_machines: machineSummaries,
  };
}

export function advanceDemoClock(
  workspaceId: string,
  payload: ClockAdvancePayload
): ExecutionStatusResponse {
  const factory = getMutableDemoFactory(workspaceId);
  const t0 = factory.current_time_minute;

  let t1: number;
  if (payload.advance_by_minutes !== undefined && payload.advance_by_minutes !== null) {
    t1 = t0 + payload.advance_by_minutes;
  } else if (payload.target_time_minute !== undefined && payload.target_time_minute !== null) {
    t1 = payload.target_time_minute;
  } else {
    throw new ApiClientError(
      'INVALID_CLOCK',
      "Must provide either 'advance_by_minutes' or 'target_time_minute'.",
      400
    );
  }

  if (t1 < 0) {
    throw new ApiClientError(
      'INVALID_CLOCK',
      `Plant clock destination cannot be negative: ${t1}.`,
      400
    );
  }

  if (
    payload.expected_current_time_minute !== undefined &&
    payload.expected_current_time_minute !== null &&
    payload.expected_current_time_minute !== t0
  ) {
    throw new ApiClientError(
      'STALE_EXECUTION_STATE',
      `Stale execution state: expected clock ${payload.expected_current_time_minute}, but current clock is ${t0}.`,
      409
    );
  }

  if (t1 < t0) {
    throw new ApiClientError(
      'INVALID_CLOCK',
      `Cannot move plant clock backward from ${t0} to ${t1}.`,
      400
    );
  }

  const completedIds = payload.completed_operation_ids || [];
  const overrides = payload.remaining_duration_overrides || {};

  // Idempotent no-op check
  if (t1 === t0 && completedIds.length === 0 && Object.keys(overrides).length === 0) {
    return getDemoExecutionStatus(workspaceId);
  }

  const allOpsMap = new Map<string, OperationResponse>();
  for (const order of factory.orders) {
    for (const op of order.operations) {
      allOpsMap.set(op.id, op);
    }
  }

  for (const opId of completedIds) {
    const op = allOpsMap.get(opId);
    if (!op) {
      throw new ApiClientError('RESOURCE_NOT_FOUND', `Operation '${opId}' not found.`, 404);
    }
    if (op.status !== 'IN_PROGRESS') {
      throw new ApiClientError(
        'INVALID_LIFECYCLE_STATE',
        `Operation '${opId}' is not IN_PROGRESS (status: ${op.status}).`,
        400
      );
    }
  }

  for (const [opId, newRem] of Object.entries(overrides)) {
    const op = allOpsMap.get(opId);
    if (!op) {
      throw new ApiClientError('RESOURCE_NOT_FOUND', `Operation '${opId}' not found.`, 404);
    }
    if (op.status !== 'IN_PROGRESS') {
      throw new ApiClientError(
        'INVALID_LIFECYCLE_STATE',
        `Operation '${opId}' is not IN_PROGRESS (status: ${op.status}).`,
        400
      );
    }
    if (newRem < 1) {
      throw new ApiClientError(
        'INVALID_DURATION',
        `Remaining duration override for operation '${opId}' must be >= 1.`,
        400
      );
    }
  }

  const conflict = completedIds.filter((id) => Object.prototype.hasOwnProperty.call(overrides, id));
  if (conflict.length > 0) {
    throw new ApiClientError(
      'INVALID_LIFECYCLE_STATE',
      `Operation(s) ${conflict.join(', ')} cannot be both completed and overridden in the same request.`,
      400
    );
  }

  const delta = t1 - t0;
  const activeOps = Array.from(allOpsMap.values()).filter((op) => op.status === 'IN_PROGRESS');

  for (const op of activeOps) {
    if (completedIds.includes(op.id)) {
      if (t1 <= (op.actual_start_minute ?? 0)) {
        throw new ApiClientError(
          'INVALID_LIFECYCLE_STATE',
          `Completed operation '${op.id}' actual_end (${t1}) must be strictly greater than start (${op.actual_start_minute}).`,
          400
        );
      }
    } else if (Object.prototype.hasOwnProperty.call(overrides, op.id)) {
      // Overridden explicitly
    } else {
      const currentRem = op.remaining_duration_minutes ?? op.processing_minutes;
      if (delta < currentRem) {
        // Linear decrement
      } else {
        const projectedFinish = t0 + currentRem;
        throw new ApiClientError(
          'OVERDUE_RECONCILIATION_REQUIRED',
          `Operation '${op.id}' reached projected finish at ${projectedFinish}m. Explicit reconciliation required.`,
          400
        );
      }
    }
  }

  // Audit downtime collisions on elapsed intervals [actual_start, t1)
  for (const op of activeOps) {
    const startMin = op.actual_start_minute ?? t0;
    const dts = factory.downtimes.filter((d) => d.machine_id === op.machine_id);
    for (const dt of dts) {
      if (Math.max(startMin, dt.start_minute) < Math.min(t1, dt.end_minute)) {
        throw new ApiClientError(
          'HISTORICAL_DOWNTIME_CONFLICT',
          `Operation '${op.id}' execution interval [${startMin}, ${t1}) collides with downtime [${dt.start_minute}, ${dt.end_minute}) on machine '${op.machine_id}'.`,
          400
        );
      }
    }
  }

  // Apply mutations
  for (const op of activeOps) {
    if (completedIds.includes(op.id)) {
      op.status = 'COMPLETED';
      op.actual_end_minute = t1;
      op.remaining_duration_minutes = null;
    } else if (Object.prototype.hasOwnProperty.call(overrides, op.id)) {
      op.remaining_duration_minutes = overrides[op.id];
    } else {
      op.remaining_duration_minutes = (op.remaining_duration_minutes ?? op.processing_minutes) - delta;
    }
  }

  factory.current_time_minute = t1;
  return getDemoExecutionStatus(workspaceId);
}

export function startDemoOperation(
  workspaceId: string,
  operationId: string,
  payload: StartOperationPayload = {}
): ExecutionStatusResponse {
  const factory = getMutableDemoFactory(workspaceId);
  const t0 = factory.current_time_minute;

  if (
    payload.expected_current_time_minute !== undefined &&
    payload.expected_current_time_minute !== null &&
    payload.expected_current_time_minute !== t0
  ) {
    throw new ApiClientError(
      'STALE_EXECUTION_STATE',
      `Stale execution state: expected clock ${payload.expected_current_time_minute}, but current clock is ${t0}.`,
      409
    );
  }

  const { order: targetOrder, op: targetOp } = findOperationAndOrder(factory, operationId);

  // 1. Status PLANNED
  if (targetOp.status !== 'PLANNED') {
    throw new ApiClientError(
      'INVALID_LIFECYCLE_STATE',
      `Operation '${operationId}' cannot start because status is ${targetOp.status}.`,
      400
    );
  }

  // 2. Order release time
  if (targetOrder.release_minute > t0) {
    throw new ApiClientError(
      'INVALID_SEQUENCE',
      `Operation '${operationId}' cannot start before order release minute ${targetOrder.release_minute} (current clock: ${t0}).`,
      400
    );
  }

  // 3. Order concurrency: at most 1 op in progress per order
  if (targetOrder.operations.some((p) => p.status === 'IN_PROGRESS')) {
    throw new ApiClientError(
      'INVALID_SEQUENCE',
      `Order '${targetOrder.id}' already has an operation in progress.`,
      400
    );
  }

  // 4. Predecessor sequence
  if (targetOp.sequence_index > 1) {
    const pred = targetOrder.operations.find(
      (p) => p.sequence_index === targetOp!.sequence_index - 1
    );
    if (!pred) {
      throw new ApiClientError(
        'INVALID_SEQUENCE',
        `Predecessor step ${targetOp.sequence_index - 1} missing in order '${targetOrder.id}'.`,
        400
      );
    }
    if (pred.status !== 'COMPLETED') {
      throw new ApiClientError(
        'INVALID_SEQUENCE',
        `Predecessor operation '${pred.id}' (step ${pred.sequence_index}) is ${pred.status}, not COMPLETED.`,
        400
      );
    }
    if (
      pred.actual_end_minute !== null &&
      pred.actual_end_minute !== undefined &&
      pred.actual_end_minute > t0
    ) {
      throw new ApiClientError(
        'INVALID_SEQUENCE',
        `Predecessor operation '${pred.id}' ends in the future (${pred.actual_end_minute} > ${t0}).`,
        400
      );
    }
  }

  // 5. Machine exclusivity: assigned machine must be free
  for (const otherOrder of factory.orders) {
    for (const otherOp of otherOrder.operations) {
      if (otherOp.machine_id === targetOp.machine_id && otherOp.status === 'IN_PROGRESS') {
        throw new ApiClientError(
          'MACHINE_OCCUPIED',
          `Machine '${targetOp.machine_id}' is occupied by in-progress operation '${otherOp.id}'.`,
          400
        );
      }
    }
  }

  // 6. Machine active downtime
  const dts = factory.downtimes.filter((d) => d.machine_id === targetOp!.machine_id);
  for (const dt of dts) {
    if (dt.start_minute <= t0 && t0 < dt.end_minute) {
      throw new ApiClientError(
        'HISTORICAL_DOWNTIME_CONFLICT',
        `Machine '${targetOp.machine_id}' is in maintenance downtime [${dt.start_minute}, ${dt.end_minute}) at clock ${t0}m.`,
        400
      );
    }
  }

  const remDur =
    payload.estimated_remaining_duration_minutes !== undefined &&
    payload.estimated_remaining_duration_minutes !== null
      ? payload.estimated_remaining_duration_minutes
      : targetOp.processing_minutes;

  if (remDur < 1) {
    throw new ApiClientError(
      'INVALID_DURATION',
      `Remaining duration must be >= 1 (got ${remDur}).`,
      400
    );
  }

  targetOp.status = 'IN_PROGRESS';
  targetOp.actual_start_minute = t0;
  targetOp.actual_end_minute = null;
  targetOp.remaining_duration_minutes = remDur;

  return getDemoExecutionStatus(workspaceId);
}

export function completeDemoOperation(
  workspaceId: string,
  operationId: string,
  payload: CompleteOperationPayload = {}
): ExecutionStatusResponse {
  const factory = getMutableDemoFactory(workspaceId);
  const t0 = factory.current_time_minute;

  if (
    payload.expected_current_time_minute !== undefined &&
    payload.expected_current_time_minute !== null &&
    payload.expected_current_time_minute !== t0
  ) {
    throw new ApiClientError(
      'STALE_EXECUTION_STATE',
      `Stale execution state: expected clock ${payload.expected_current_time_minute}, but current clock is ${t0}.`,
      409
    );
  }

  const { op: targetOp } = findOperationAndOrder(factory, operationId);

  if (targetOp.status !== 'IN_PROGRESS') {
    throw new ApiClientError(
      'INVALID_LIFECYCLE_STATE',
      `Operation '${operationId}' cannot complete because status is ${targetOp.status}.`,
      400
    );
  }

  const start = targetOp.actual_start_minute ?? 0;
  if (t0 <= start) {
    throw new ApiClientError(
      'INVALID_LIFECYCLE_STATE',
      `Operation '${operationId}' cannot complete at start minute (${t0}m). Advance plant clock first.`,
      400
    );
  }

  // Downtime collision audit on [start, t0)
  const dts = factory.downtimes.filter((d) => d.machine_id === targetOp!.machine_id);
  for (const dt of dts) {
    if (Math.max(start, dt.start_minute) < Math.min(t0, dt.end_minute)) {
      throw new ApiClientError(
        'HISTORICAL_DOWNTIME_CONFLICT',
        `Completed operation interval [${start}, ${t0}) collides with downtime [${dt.start_minute}, ${dt.end_minute}) on machine '${targetOp.machine_id}'.`,
        400
      );
    }
  }

  targetOp.status = 'COMPLETED';
  targetOp.actual_end_minute = t0;
  targetOp.remaining_duration_minutes = null;

  return getDemoExecutionStatus(workspaceId);
}

export function adjustDemoRemainingDuration(
  workspaceId: string,
  operationId: string,
  payload: AdjustRemainingPayload
): ExecutionStatusResponse {
  const factory = getMutableDemoFactory(workspaceId);
  const t0 = factory.current_time_minute;

  if (
    payload.expected_current_time_minute !== undefined &&
    payload.expected_current_time_minute !== null &&
    payload.expected_current_time_minute !== t0
  ) {
    throw new ApiClientError(
      'STALE_EXECUTION_STATE',
      `Stale execution state: expected clock ${payload.expected_current_time_minute}, but current clock is ${t0}.`,
      409
    );
  }

  const { op: targetOp } = findOperationAndOrder(factory, operationId);

  if (targetOp.status !== 'IN_PROGRESS') {
    throw new ApiClientError(
      'INVALID_LIFECYCLE_STATE',
      `Operation '${operationId}' is not IN_PROGRESS (status: ${targetOp.status}).`,
      400
    );
  }

  if (payload.remaining_duration_minutes < 1) {
    throw new ApiClientError(
      'INVALID_DURATION',
      `Remaining duration must be >= 1 (got ${payload.remaining_duration_minutes}).`,
      400
    );
  }

  targetOp.remaining_duration_minutes = payload.remaining_duration_minutes;

  return getDemoExecutionStatus(workspaceId);
}

export function getDemoSchedules(workspaceId: string): ScheduleSummaryResponse[] {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const s = fixture.schedule;
  return [
    {
      id: s.id,
      workspace_id: s.workspace_id,
      name: s.name,
      objective_type: s.objective_type,
      solver_status: s.solver_status,
      verification_status: s.verification_status,
      makespan_minutes: s.metrics.makespan_minutes,
      weighted_tardiness: s.metrics.weighted_tardiness,
      late_order_count: s.metrics.late_order_count,
      on_time_rate: s.metrics.on_time_rate,
      created_at: s.created_at,
    },
  ];
}

export function getDemoScheduleDetail(workspaceId: string, scheduleId: string): ScheduleDetailResponse {
  if (demoRecoverySchedules[scheduleId]) {
    return JSON.parse(JSON.stringify(demoRecoverySchedules[scheduleId]));
  }
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  return JSON.parse(JSON.stringify(fixture.schedule));
}

export function verifyDemoSchedule(workspaceId: string): VerificationReportResponse {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const factory = getDemoFactory(workspaceId);
  const result = verifyScheduleClient(factory, fixture.schedule);
  return {
    is_valid: result.is_valid,
    checks_run: result.checks_run,
    checks_passed: result.checks_passed,
    violations: result.violations,
  };
}

export function getDemoScheduleReport(workspaceId: string): ScheduleReportResponse {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const factory = getDemoFactory(workspaceId);
  const verification = verifyScheduleClient(factory, fixture.schedule);
  return buildDemoReport(factory, fixture.schedule, verification);
}

function initDemoScenariosForWorkspace(workspaceId: string): ScenarioResponse[] {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const baseSched = fixture.schedule;

  if (fixture.id === 'demo-4') {
    return [
      {
        id: 'scen-demo-4',
        workspace_id: workspaceId,
        baseline_schedule_id: DEMO_FIXTURES['demo-1']?.schedule.id || baseSched.id,
        disruption_type: 'URGENT_ORDER',
        name: 'Urgent Rush-Order Injection',
        description: 'Order ORD-RUSH (w=50, r=0, d=60) placed immediately, displacing lower priority jobs.',
        disruption_delta: {
          added_downtimes: [],
          added_orders: [
            {
              order_code: 'ORD-RUSH',
              release_time_minutes: 0,
              due_date_minutes: 60,
              tardiness_weight: 50,
              operations: [
                { sequence_index: 1, machine_id: 'M1', processing_minutes: 15 },
                { sequence_index: 2, machine_id: 'M2', processing_minutes: 15 },
                { sequence_index: 3, machine_id: 'M3', processing_minutes: 15 },
              ],
            },
          ],
        },
        created_at: baseSched.created_at,
      },
    ];
  }
  if (fixture.id === 'demo-5') {
    return [
      {
        id: 'scen-demo-5',
        workspace_id: workspaceId,
        baseline_schedule_id: DEMO_FIXTURES['demo-1']?.schedule.id || baseSched.id,
        disruption_type: 'MACHINE_DOWNTIME',
        name: 'Unplanned Maintenance Window',
        description: 'Machine M1 undergoes 60m maintenance during [30, 90).',
        disruption_delta: {
          added_downtimes: [
            {
              machine_id: 'M1',
              start_minute: 30,
              end_minute: 90,
              reason: 'Scheduled spindle rebuild',
            },
          ],
          added_orders: [],
        },
        created_at: baseSched.created_at,
      },
    ];
  }

  // Baseline workspace (demo-1 or custom workspace)
  return [
    {
      id: `scen-demo-${workspaceId}-rush`,
      workspace_id: workspaceId,
      baseline_schedule_id: baseSched.id,
      disruption_type: 'URGENT_ORDER',
      name: 'Urgent Rush-Order Injection',
      description: 'Emergency order ORD-RUSH (w=50, r=0, d=60). CP-SAT re-optimizes the entire schedule to guarantee zero tardiness.',
      disruption_delta: {
        added_downtimes: [],
        added_orders: [
          {
            order_code: 'ORD-RUSH',
            release_time_minutes: 0,
            due_date_minutes: 60,
            tardiness_weight: 50,
            operations: [
              { sequence_index: 1, machine_id: 'M1', processing_minutes: 15 },
              { sequence_index: 2, machine_id: 'M2', processing_minutes: 15 },
              { sequence_index: 3, machine_id: 'M3', processing_minutes: 15 },
            ],
          },
        ],
      },
      created_at: baseSched.created_at,
    },
    {
      id: `scen-demo-${workspaceId}-downtime`,
      workspace_id: workspaceId,
      baseline_schedule_id: baseSched.id,
      disruption_type: 'MACHINE_DOWNTIME',
      name: 'Unplanned Machine Downtime Outage',
      description: 'CNC Milling Station M1 undergoes emergency 60m maintenance during [30, 90). Recomputed to avoid outage interval.',
      disruption_delta: {
        added_downtimes: [
          {
            machine_id: 'M1',
            start_minute: 30,
            end_minute: 90,
            reason: 'Scheduled spindle rebuild and calibration',
          },
        ],
        added_orders: [],
      },
      created_at: baseSched.created_at,
    },
  ];
}

function getMutableDemoScenarios(workspaceId: string): ScenarioResponse[] {
  if (!demoScenariosState[workspaceId]) {
    demoScenariosState[workspaceId] = initDemoScenariosForWorkspace(workspaceId);
  }
  return demoScenariosState[workspaceId];
}

export function getDemoScenarios(workspaceId: string): ScenarioResponse[] {
  return JSON.parse(JSON.stringify(getMutableDemoScenarios(workspaceId)));
}

export function getDemoScenario(workspaceId: string, scenarioId: string): ScenarioResponse {
  const list = getMutableDemoScenarios(workspaceId);
  const found = list.find((s) => s.id === scenarioId);
  if (!found) {
    throw new ApiClientError('RESOURCE_NOT_FOUND', `Scenario '${scenarioId}' not found in demo workspace.`, 404);
  }
  return JSON.parse(JSON.stringify(found));
}

export function createDemoScenario(workspaceId: string, req: ScenarioCreateRequest): ScenarioResponse {
  const list = getMutableDemoScenarios(workspaceId);
  const newScen: ScenarioResponse = {
    id: `scen-demo-${Date.now()}`,
    workspace_id: workspaceId,
    baseline_schedule_id: req.baseline_schedule_id,
    disruption_type: req.disruption_type,
    name: req.name,
    description: req.description || '',
    disruption_delta: req.disruption_delta,
    created_at: new Date().toISOString(),
  };
  list.unshift(newScen);
  return JSON.parse(JSON.stringify(newScen));
}

export function deleteDemoScenario(workspaceId: string, scenarioId: string): { deleted: boolean; scenario_id: string } {
  const list = getMutableDemoScenarios(workspaceId);
  const idx = list.findIndex((s) => s.id === scenarioId);
  if (idx !== -1) {
    list.splice(idx, 1);
  }
  return { deleted: true, scenario_id: scenarioId };
}

export function reoptimizeDemoScenario(
  workspaceId: string,
  scenarioId: string,
  _req?: ScenarioReoptimizeRequest
): ScenarioComparisonResponse {
  const list = getMutableDemoScenarios(workspaceId);
  const scenario = list.find((s) => s.id === scenarioId);
  if (!scenario) {
    throw new ApiClientError('RESOURCE_NOT_FOUND', `Scenario '${scenarioId}' not found.`, 404);
  }

  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const baseSched = fixture.schedule;
  const recoverySchedId = `sched-rec-${scenario.id}`;

  let recSched = demoRecoverySchedules[recoverySchedId];
  let isHeuristicSimulation = false;

  // Strict fixture matching: Only pre-solved fixture scenarios on their matching base workspaces
  const isRushDisruption =
    (scenario.id === 'scen-demo-4' || scenario.id === `scen-demo-${workspaceId}-rush`) &&
    (workspaceId === 'ws-demo-1' || workspaceId === 'ws-demo-4' || workspaceId === 'demo-1' || workspaceId === 'demo-4');

  const isDowntimeDisruption =
    (scenario.id === 'scen-demo-5' || scenario.id === `scen-demo-${workspaceId}-downtime`) &&
    (workspaceId === 'ws-demo-1' || workspaceId === 'ws-demo-5' || workspaceId === 'demo-1' || workspaceId === 'demo-5');

  if (!recSched) {
    if (isRushDisruption && DEMO_FIXTURES['demo-4']) {
      // Genuine CP-SAT pre-solved optimal schedule for rush-order disruption
      recSched = JSON.parse(JSON.stringify(DEMO_FIXTURES['demo-4'].schedule));
      recSched.id = recoverySchedId;
      recSched.workspace_id = workspaceId;
      recSched.name = `CP-SAT Reoptimized — ${scenario.name}`;
      demoRecoverySchedules[recoverySchedId] = recSched;
    } else if (isDowntimeDisruption && DEMO_FIXTURES['demo-5']) {
      // Genuine CP-SAT pre-solved optimal schedule for downtime disruption
      recSched = JSON.parse(JSON.stringify(DEMO_FIXTURES['demo-5'].schedule));
      recSched.id = recoverySchedId;
      recSched.workspace_id = workspaceId;
      recSched.name = `CP-SAT Reoptimized — ${scenario.name}`;
      demoRecoverySchedules[recoverySchedId] = recSched;
    } else {
      // Custom / Ad-hoc disruption: Heuristic demo simulation
      isHeuristicSimulation = true;
      recSched = JSON.parse(JSON.stringify(baseSched));
      recSched.id = recoverySchedId;
      recSched.workspace_id = workspaceId;
      recSched.name = `[Demo Simulation] Recovery — ${scenario.name}`;
      recSched.solver_status = 'DEMO_SIMULATION';
      recSched.solver_telemetry = {
        wall_clock_time_seconds: 0.002,
        deterministic_time: 0.002,
        user_cpu_time_seconds: 0.002,
        termination_reason:
          'Client-side demo simulation: Operations adjusted by heuristic time-shift without CP-SAT backend solver.',
      };

      const delayMinutes = scenario.disruption_type === 'URGENT_ORDER' ? 15 : 30;
      recSched.scheduled_operations = recSched.scheduled_operations.map((op: ScheduledOperationResponse, i: number) => ({
        ...op,
        start_minute: op.start_minute + (i > 1 ? delayMinutes : 0),
        end_minute: op.end_minute + (i > 1 ? delayMinutes : 0),
      }));

      // Construct simulated factory configuration and run clean-room verifier
      const simFactory: FactoryConfigResponse = JSON.parse(JSON.stringify(getMutableDemoFactory(workspaceId)));
      if (scenario.disruption_delta?.added_downtimes) {
        for (const dt of scenario.disruption_delta.added_downtimes) {
          simFactory.downtimes.push({
            id: `dt-sim-${Date.now()}`,
            machine_id: dt.machine_id,
            start_minute: dt.start_minute,
            end_minute: dt.end_minute,
            reason: dt.reason || 'Simulated outage',
          });
        }
      }

      const verResult = verifyScheduleClient(simFactory, recSched);
      recSched.verification_status = verResult.is_valid ? 'VERIFIED' : 'FAILED';
      recSched.metrics = {
        ...recSched.metrics,
        makespan_minutes: verResult.recomputed_metrics.makespan_minutes,
        weighted_tardiness: verResult.recomputed_metrics.total_weighted_tardiness,
        late_order_count: verResult.recomputed_metrics.late_order_count,
        on_time_rate: verResult.recomputed_metrics.on_time_rate,
        objective_value: null,
        best_objective_bound: null,
        optimality_gap: null,
      };
      demoRecoverySchedules[recoverySchedId] = recSched;
    }
  } else {
    isHeuristicSimulation = recSched.solver_status === 'DEMO_SIMULATION' || recSched.name.startsWith('[Demo Simulation]');
  }

  scenario.reoptimized_schedule_id = recoverySchedId;

  // Accurate diverged operations calculation against baseline schedule
  const baseOpMap = new Map<string, ScheduledOperationResponse>();
  for (const bOp of baseSched.scheduled_operations) {
    baseOpMap.set(bOp.operation_id, bOp);
  }

  const diverged: OperationDivergence[] = [];
  for (const rOp of recSched.scheduled_operations) {
    const bOp = baseOpMap.get(rOp.operation_id);
    if (!bOp) {
      diverged.push({
        order_id: rOp.order_id,
        sequence_index: rOp.sequence_index,
        machine_id: rOp.machine_id,
        baseline_start: null,
        baseline_end: null,
        compared_start: rOp.start_minute,
        compared_end: rOp.end_minute,
        delta_start_minutes: rOp.start_minute,
        status: 'NEW_RUSH_OPERATION',
      });
    } else if (
      rOp.start_minute !== bOp.start_minute ||
      rOp.end_minute !== bOp.end_minute ||
      rOp.machine_id !== bOp.machine_id
    ) {
      const delta = rOp.start_minute - bOp.start_minute;
      diverged.push({
        order_id: rOp.order_id,
        sequence_index: rOp.sequence_index,
        machine_id: rOp.machine_id,
        baseline_start: bOp.start_minute,
        baseline_end: bOp.end_minute,
        compared_start: rOp.start_minute,
        compared_end: rOp.end_minute,
        delta_start_minutes: delta,
        status: delta > 0 ? 'DELAYED' : 'EXPEDITED',
      });
    }
  }

  const comparison: ScenarioComparisonResponse = {
    id: `comp-${scenario.id}`,
    scenario_id: scenario.id,
    baseline_schedule_id: scenario.baseline_schedule_id,
    compared_schedule_id: recoverySchedId,
    delta_makespan: recSched.metrics.makespan_minutes - baseSched.metrics.makespan_minutes,
    delta_weighted_tardiness: recSched.metrics.weighted_tardiness - baseSched.metrics.weighted_tardiness,
    delta_late_order_count: recSched.metrics.late_order_count - baseSched.metrics.late_order_count,
    delta_on_time_rate: recSched.metrics.on_time_rate - baseSched.metrics.on_time_rate,
    objective_diff_detected: false,
    order_set_diff_detected: scenario.disruption_type === 'URGENT_ORDER',
    status_diff_detected: isHeuristicSimulation,
    time_limit_diff_detected: false,
    unlike_comparison_warning: isHeuristicSimulation
      ? recSched.verification_status === 'FAILED'
        ? 'Demo Simulation Notice: Client-side heuristic simulation produced a schedule with constraint violations (e.g. downtime collision or overlap). For proven mathematically valid and optimal recovery plans, connect the Python backend or select a pre-solved demo scenario.'
        : 'Demo Simulation Notice: This recovery schedule was generated by client-side heuristic simulation without the CP-SAT backend solver. For proven mathematically optimal recovery plans, connect the Python backend or select a pre-solved demo scenario.'
      : null,
    diverged_operations: diverged,
    created_at: new Date().toISOString(),
  };

  scenario.comparison = comparison;
  return comparison;
}
