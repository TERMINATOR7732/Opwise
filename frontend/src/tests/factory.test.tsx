/**
 * Tests for Factory and Production Order Management (Milestone 09A)
 * Governed by DATA_AND_API.md Section 3.2 and ARCHITECTURE.md Section 3.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { apiEndpoints } from '../api/endpoints';
import { MachineResponse, DowntimeResponse, OrderResponse, FactoryValidationResponse } from '../types/api';
import { MachinesTab } from '../views/factory/MachinesTab';
import { OrdersTab } from '../views/factory/OrdersTab';
import { MachineModal } from '../views/factory/MachineModal';
import { DowntimeModal } from '../views/factory/DowntimeModal';
import { OrderModal } from '../views/factory/OrderModal';
import { DeleteConfirmModal } from '../views/factory/DeleteConfirmModal';
import { FactoryValidationCard } from '../views/factory/FactoryValidationCard';

const mockMachines: MachineResponse[] = [
  { id: 'm-1', external_id: 'M1', name: '5-Axis CNC Mill', created_at: '2026-10-16T12:00:00Z' },
  { id: 'm-2', external_id: 'M2', name: 'Manual Lathe', created_at: '2026-10-16T12:00:00Z' },
];

const mockDowntimes: DowntimeResponse[] = [
  { id: 'dt-1', machine_id: 'm-1', start_minute: 60, end_minute: 120, reason: 'Calibration' },
];

const mockOrders: OrderResponse[] = [
  {
    id: 'ord-1',
    external_id: 'ORD-101',
    name: 'Precision Rotor Shaft',
    release_minute: 0,
    due_minute: 180,
    tardiness_weight: 2,
    operations: [
      { id: 'op-1', order_id: 'ord-1', sequence_index: 1, machine_id: 'm-1', processing_minutes: 45 },
      { id: 'op-2', order_id: 'ord-1', sequence_index: 2, machine_id: 'm-2', processing_minutes: 30 },
    ],
  },
];

describe('Factory API Endpoints', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getFactory fetches workspace factory configuration', async () => {
    const mockData = { machines: mockMachines, downtimes: mockDowntimes, orders: mockOrders };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockData, metadata: { timestamp: '2026-10-16T12:00:00Z' } }),
    });

    const res = await apiEndpoints.getFactory('ws-1');
    expect(res.machines).toHaveLength(2);
    expect(res.orders).toHaveLength(1);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/factory', expect.any(Object));
  });

  it('replaceFactory sends atomic PUT payload', async () => {
    const payload = {
      machines: [{ external_id: 'M1', name: '5-Axis CNC Mill' }],
      downtimes: [{ machine_id: 'M1', start_minute: 60, end_minute: 120, reason: 'Calibration' }],
      orders: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: { ...payload, orders: [] }, metadata: {} }),
    });

    const res = await apiEndpoints.replaceFactory('ws-1', payload);
    expect(res.machines).toHaveLength(1);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/factory',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('validateFactory calls dry-run POST /factory/validate', async () => {
    const validationData: FactoryValidationResponse = {
      is_valid: true,
      classification: 'OPTIMAL_OR_FEASIBLE',
      issues: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: validationData, metadata: {} }),
    });

    const res = await apiEndpoints.validateFactory('ws-1', { machines: [], downtimes: [], orders: [] });
    expect(res.is_valid).toBe(true);
    expect(res.classification).toBe('OPTIMAL_OR_FEASIBLE');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/factory/validate',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('Factory UI Component Markup', () => {
  it('renders MachinesTab with workstations grid and maintenance windows table', () => {
    const markup = renderToStaticMarkup(
      <MachinesTab
        machines={mockMachines}
        downtimes={mockDowntimes}
        orders={mockOrders}
        onAddMachine={async () => {}}
        onUpdateMachine={async () => {}}
        onDeleteMachine={async () => {}}
        onAddDowntime={async () => {}}
        onDeleteDowntime={async () => {}}
      />
    );
    expect(markup).toContain('Machine Workstations (2)');
    expect(markup).toContain('5-Axis CNC Mill');
    expect(markup).toContain('Manual Lathe');
    expect(markup).toContain('Planned Maintenance Windows');
    expect(markup).toContain('Calibration');
    expect(markup).toContain('[60, 120)');
  });

  it('renders MachinesTab empty state when no machines are configured', () => {
    const markup = renderToStaticMarkup(
      <MachinesTab
        machines={[]}
        downtimes={[]}
        orders={[]}
        onAddMachine={async () => {}}
        onUpdateMachine={async () => {}}
        onDeleteMachine={async () => {}}
        onAddDowntime={async () => {}}
        onDeleteDowntime={async () => {}}
      />
    );
    expect(markup).toContain('No Machines Configured');
    expect(markup).toContain('+ Add First Machine');
  });

  it('renders OrdersTab with order sequence, release, due, and duration', () => {
    const markup = renderToStaticMarkup(
      <OrdersTab
        orders={mockOrders}
        machines={mockMachines}
        onAddOrder={async () => {}}
        onUpdateOrder={async () => {}}
        onDeleteOrder={async () => {}}
      />
    );
    expect(markup).toContain('Production Orders &amp; Sequences (1)');
    expect(markup).toContain('ORD-101');
    expect(markup).toContain('Precision Rotor Shaft');
    expect(markup).toContain('180m');
    expect(markup).toContain('75m');
  });

  it('renders OrdersTab machine prerequisite card when no machines exist', () => {
    const markup = renderToStaticMarkup(
      <OrdersTab
        orders={[]}
        machines={[]}
        onAddOrder={async () => {}}
        onUpdateOrder={async () => {}}
        onDeleteOrder={async () => {}}
      />
    );
    expect(markup).toContain('Prerequisite: Machine Workstations Required');
  });

  it('renders MachineModal in creation and edit modes', () => {
    const createMarkup = renderToStaticMarkup(
      <MachineModal isOpen={true} onSave={async () => {}} onClose={() => {}} existingCodes={[]} />
    );
    expect(createMarkup).toContain('Add Machine Workstation');
    expect(createMarkup).toContain('Machine Code (Unique Identifier) *');

    const editMarkup = renderToStaticMarkup(
      <MachineModal isOpen={true} initialMachine={mockMachines[0]} onSave={async () => {}} onClose={() => {}} existingCodes={[]} />
    );
    expect(editMarkup).toContain('Edit Machine Workstation');
    expect(editMarkup).toContain('value="M1"');
  });

  it('renders DowntimeModal with machine selector and minute inputs', () => {
    const markup = renderToStaticMarkup(
      <DowntimeModal isOpen={true} machines={mockMachines} onSave={async () => {}} onClose={() => {}} />
    );
    expect(markup).toContain('Schedule Maintenance Downtime');
    expect(markup).toContain('Target Machine Workstation *');
    expect(markup).toContain('M1 — 5-Axis CNC Mill');
    expect(markup).toContain('Start Minute [start, ...) *');
  });

  it('renders OrderModal with multi-step routing builder', () => {
    const markup = renderToStaticMarkup(
      <OrderModal isOpen={true} machines={mockMachines} onSave={async () => {}} onClose={() => {}} existingCodes={[]} />
    );
    expect(markup).toContain('Create Production Order');
    expect(markup).toContain('Linear Routing Operations Sequence *');
    expect(markup).toContain('+ Add Step');
  });

  it('renders FactoryValidationCard with valid and invalid audit results', () => {
    const validMarkup = renderToStaticMarkup(
      <FactoryValidationCard
        validationResult={{ is_valid: true, classification: 'OPTIMAL_OR_FEASIBLE', issues: [] }}
        isValidating={false}
        onValidate={async () => {}}
        machineCount={2}
        orderCount={1}
      />
    );
    expect(validMarkup).toContain('Factory Ready for CP-SAT Solver Execution');
    expect(validMarkup).toContain('OPTIMAL_OR_FEASIBLE');

    const invalidMarkup = renderToStaticMarkup(
      <FactoryValidationCard
        validationResult={{ is_valid: false, classification: 'PROVEN_INFEASIBLE', issues: ['Overlapping downtime [10, 50) and [20, 60)'] }}
        isValidating={false}
        onValidate={async () => {}}
        machineCount={1}
        orderCount={1}
      />
    );
    expect(invalidMarkup).toContain('Factory Configuration Has Invariant Violations');
    expect(invalidMarkup).toContain('Overlapping downtime');
  });

  it('renders DeleteConfirmModal with accessible attributes and item name', () => {
    const markup = renderToStaticMarkup(
      <DeleteConfirmModal
        isOpen={true}
        title="Delete Machine"
        message="Are you sure you want to remove this workstation?"
        itemName="M1 (5-Axis CNC Mill)"
        onConfirm={async () => {}}
        onCancel={() => {}}
      />
    );
    expect(markup).toContain('Delete Machine');
    expect(markup).toContain('M1 (5-Axis CNC Mill)');
    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
  });
});
