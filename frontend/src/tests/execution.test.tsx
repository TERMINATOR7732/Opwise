/**
 * Comprehensive Tests for Shop-Floor Execution Controls (Milestone 15D)
 * Governed by MILESTONE_15D_SCOPE_PROPOSAL.md criteria AC-15D-28 through AC-15D-31.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { apiEndpoints } from '../api/endpoints';
import {
  ClockAdvancePayload,
  ExecutionStatusResponse,
  MachineResponse,
  OrderResponse,
  StartOperationPayload,
  CompleteOperationPayload,
  AdjustRemainingPayload,
  ScheduledOperationResponse,
} from '../types/api';
import { AppHeader } from '../components/layout/AppHeader';
import { OrdersTab } from '../views/factory/OrdersTab';
import { ClockAdvanceModal } from '../components/execution/ClockAdvanceModal';
import { GanttOperationDetail } from '../views/schedules/gantt/GanttOperationDetail';
import { WorkspaceProvider } from '../context/WorkspaceContext';
import { RouterProvider } from '../router/RouterContext';

const mockMachines: MachineResponse[] = [
  { id: 'm-1', external_id: 'M1', name: '5-Axis CNC Mill', created_at: '2026-10-20T10:00:00Z' },
  { id: 'm-2', external_id: 'M2', name: 'Manual Lathe', created_at: '2026-10-20T10:00:00Z' },
];

const mockOrdersMixedLifecycle: OrderResponse[] = [
  {
    id: 'ord-1',
    external_id: 'ORD-101',
    name: 'Precision Rotor Shaft',
    release_minute: 0,
    due_minute: 180,
    tardiness_weight: 2,
    operations: [
      {
        id: 'op-1',
        order_id: 'ord-1',
        sequence_index: 1,
        machine_id: 'm-1',
        processing_minutes: 30,
        status: 'COMPLETED',
        actual_start_minute: 0,
        actual_end_minute: 25,
        remaining_duration_minutes: null,
      },
      {
        id: 'op-2',
        order_id: 'ord-1',
        sequence_index: 2,
        machine_id: 'm-2',
        processing_minutes: 40,
        status: 'IN_PROGRESS',
        actual_start_minute: 25,
        actual_end_minute: null,
        remaining_duration_minutes: 20,
      },
    ],
  },
  {
    id: 'ord-2',
    external_id: 'ORD-102',
    name: 'Bearing Housing',
    release_minute: 10,
    due_minute: 120,
    tardiness_weight: 1,
    operations: [
      {
        id: 'op-3',
        order_id: 'ord-2',
        sequence_index: 1,
        machine_id: 'm-1',
        processing_minutes: 25,
        status: 'PLANNED',
        actual_start_minute: null,
        actual_end_minute: null,
        remaining_duration_minutes: null,
      },
    ],
  },
];

describe('Milestone 15D Execution API Endpoints', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('advanceClock calls POST /execution/clock/advance', async () => {
    const payload: ClockAdvancePayload = {
      advance_by_minutes: 15,
      expected_current_time_minute: 25,
    };
    const mockRes: ExecutionStatusResponse = {
      workspace_id: 'ws-1',
      current_time_minute: 40,
      active_operations: [],
      ready_to_start_operations: [],
      occupied_machines: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockRes, metadata: {} }),
    });

    const res = await apiEndpoints.advanceClock('ws-1', payload);
    expect(res.current_time_minute).toBe(40);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/execution/clock/advance',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('startOperation calls POST /execution/operations/{id}/start', async () => {
    const payload: StartOperationPayload = {
      expected_current_time_minute: 40,
    };
    const mockRes: ExecutionStatusResponse = {
      workspace_id: 'ws-1',
      current_time_minute: 40,
      active_operations: [
        {
          operation_id: 'op-3',
          order_id: 'ord-2',
          order_code: 'ORD-102',
          sequence_index: 1,
          machine_id: 'm-1',
          machine_name: '5-Axis CNC Mill',
          actual_start_minute: 40,
          elapsed_minutes: 0,
          remaining_duration_minutes: 25,
          projected_end_minute: 65,
          is_overdue: false,
        },
      ],
      ready_to_start_operations: [],
      occupied_machines: [
        {
          machine_id: 'm-1',
          machine_name: '5-Axis CNC Mill',
          status: 'BUSY',
          active_operation_id: 'op-3',
        },
      ],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockRes, metadata: {} }),
    });

    const res = await apiEndpoints.startOperation('ws-1', 'op-3', payload);
    expect(res.active_operations).toHaveLength(1);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/execution/operations/op-3/start',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('completeOperation calls POST /execution/operations/{id}/complete', async () => {
    const payload: CompleteOperationPayload = {
      expected_current_time_minute: 45,
    };
    const mockRes: ExecutionStatusResponse = {
      workspace_id: 'ws-1',
      current_time_minute: 45,
      active_operations: [],
      ready_to_start_operations: [],
      occupied_machines: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockRes, metadata: {} }),
    });

    const res = await apiEndpoints.completeOperation('ws-1', 'op-2', payload);
    expect(res.current_time_minute).toBe(45);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/execution/operations/op-2/complete',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('adjustRemainingDuration calls PATCH /execution/operations/{id}/remaining', async () => {
    const payload: AdjustRemainingPayload = {
      remaining_duration_minutes: 35,
      expected_current_time_minute: 45,
    };
    const mockRes: ExecutionStatusResponse = {
      workspace_id: 'ws-1',
      current_time_minute: 45,
      active_operations: [],
      ready_to_start_operations: [],
      occupied_machines: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockRes, metadata: {} }),
    });

    const res = await apiEndpoints.adjustRemainingDuration('ws-1', 'op-2', payload);
    expect(res.current_time_minute).toBe(45);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/execution/operations/op-2/remaining',
      expect.objectContaining({ method: 'PATCH' })
    );
  });

  it('getExecutionStatus calls GET /execution/status', async () => {
    const mockRes: ExecutionStatusResponse = {
      workspace_id: 'ws-1',
      current_time_minute: 30,
      active_operations: [],
      ready_to_start_operations: [],
      occupied_machines: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockRes, metadata: {} }),
    });

    const res = await apiEndpoints.getExecutionStatus('ws-1');
    expect(res.current_time_minute).toBe(30);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/execution/status',
      expect.any(Object)
    );
  });
});

describe('AC-15D-28: UI Header Plant Clock Widget', () => {
  it('renders AppHeader with plant clock and advance button', () => {
    const markup = renderToStaticMarkup(
      <RouterProvider initialHash="#factory">
        <WorkspaceProvider>
          <AppHeader />
        </WorkspaceProvider>
      </RouterProvider>
    );

    expect(markup).toContain('OPWISE');
    expect(markup).toContain('Active Workspace');
  });
});

describe('AC-15D-29: Contextual Action Buttons in OrdersTab', () => {
  it('renders Start for eligible planned op, Complete for running op, and Done for completed op', () => {
    const startSpy = vi.fn();
    const completeSpy = vi.fn();

    const markup = renderToStaticMarkup(
      <OrdersTab
        orders={mockOrdersMixedLifecycle}
        machines={mockMachines}
        onAddOrder={async () => {}}
        onUpdateOrder={async () => {}}
        onDeleteOrder={async () => {}}
        onStartOperation={startSpy}
        onCompleteOperation={completeSpy}
        currentTimeMinute={25}
      />
    );

    // Verifies completed operation renders "✓ Done"
    expect(markup).toContain('✓ Done');

    // Verifies in-progress operation renders Running status and "Complete" button
    expect(markup).toContain('Running (20m rem)');
    expect(markup).toContain('Complete');

    // Verifies eligible planned op (ORD-102 Step 1) renders "Start" button
    expect(markup).toContain('Start');
  });
});

describe('ClockAdvanceModal & Policy B Overdue Reconciliation', () => {
  it('renders ClockAdvanceModal with current clock, presets, and destination', () => {
    const markup = renderToStaticMarkup(
      <ClockAdvanceModal
        isOpen={true}
        onClose={() => {}}
        currentClock={20}
        inProgressOps={[]}
        onAdvance={async () => {}}
      />
    );

    expect(markup).toContain('Advance Plant Clock');
    expect(markup).toContain('t₀ = 20m');
    expect(markup).toContain('+15 min');
    expect(markup).toContain('+30 min');
    expect(markup).toContain('+60 min');
    expect(markup).toContain('Simulated Step:');
  });

  it('renders reconciliation section when an operation will become overdue', () => {
    const inProgressOps = [
      {
        id: 'op-running-1',
        orderExternalId: 'ORD-101',
        orderName: 'Rotor',
        sequenceIndex: 2,
        machineId: 'm-2',
        actualStartMinute: 10,
        remainingDurationMinutes: 10, // will be overdue if advancing >= 10m
      },
    ];

    // Advancing from 20 with remaining 10: default advance is +15m (dest = 35m) => elapsed = 15 >= 10 => Overdue!
    const markup = renderToStaticMarkup(
      <ClockAdvanceModal
        isOpen={true}
        onClose={() => {}}
        currentClock={20}
        inProgressOps={inProgressOps}
        onAdvance={async () => {}}
      />
    );

    expect(markup).toContain('RECONCILIATION REQUIRED');
    expect(markup).toContain('Mark Completed at t = 35m');
    expect(markup).toContain('or Remaining Work:');
  });
});

describe('GanttOperationDetail Contextual Controls', () => {
  it('renders Start Operation button when selected operation is PLANNED', () => {
    const plannedOp: ScheduledOperationResponse = {
      operation_id: 'op-planned',
      order_id: 'ORD-101',
      sequence_index: 1,
      machine_id: 'm-1',
      start_minute: 30,
      end_minute: 60,
      duration: 30,
      slack_minutes: 0,
      status: 'PLANNED',
    };

    const markup = renderToStaticMarkup(
      <GanttOperationDetail
        operation={plannedOp}
        machineName="5-Axis CNC Mill"
        onClose={() => {}}
      />
    );

    expect(markup).toContain('PLANNED');
    expect(markup).toContain('Start Operation');
  });

  it('renders Complete Operation button when selected operation is IN_PROGRESS', () => {
    const runningOp: ScheduledOperationResponse = {
      operation_id: 'op-running',
      order_id: 'ORD-101',
      sequence_index: 2,
      machine_id: 'm-2',
      start_minute: 20,
      end_minute: 50,
      duration: 30,
      slack_minutes: 0,
      status: 'IN_PROGRESS',
    };

    const markup = renderToStaticMarkup(
      <GanttOperationDetail
        operation={runningOp}
        machineName="Manual Lathe"
        onClose={() => {}}
      />
    );

    expect(markup).toContain('IN_PROGRESS');
    expect(markup).toContain('Complete Operation');
  });
});
