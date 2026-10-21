import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  isDemoMode,
  setDemoMode,
  getDemoWorkspaces,
  getDemoFactory,
  getDemoSchedules,
  getDemoScheduleDetail,
  verifyDemoSchedule,
  getDemoScheduleReport,
  getActiveDemoId,
  setActiveDemoId,
  resetDemoFactoryState,
  getDemoExecutionStatus,
  advanceDemoClock,
  startDemoOperation,
  completeDemoOperation,
  adjustDemoRemainingDuration,
} from '../demo/demoService';
import { apiEndpoints } from '../api/endpoints';
import { ApiClientError } from '../api/client';
import { DEMO_SCENARIO_LIST } from '../demo/fixtures';

describe('Standalone Demo Mode Service & Data Provider', () => {
  const store: Record<string, string> = {};

  beforeEach(() => {
    resetDemoFactoryState();
    Object.keys(store).forEach((k) => delete store[k]);
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
      clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
    });
    vi.stubGlobal('window', {
      localStorage: globalThis.localStorage,
      dispatchEvent: vi.fn(),
      location: { hash: '' },
    });
    setDemoMode(true);
  });

  afterEach(() => {
    resetDemoFactoryState();
    setDemoMode(false);
    vi.unstubAllGlobals();
  });

  it('detects and toggles demo mode via localStorage and runtime state', () => {
    expect(isDemoMode()).toBe(true);
    setDemoMode(false);
    expect(isDemoMode()).toBe(false);
    setDemoMode(true);
    expect(isDemoMode()).toBe(true);
  });

  it('manages active demo scenario ID selection', () => {
    expect(getActiveDemoId()).toBe('demo-1');
    setActiveDemoId('demo-3');
    expect(getActiveDemoId()).toBe('demo-3');
  });

  it('returns exactly 6 demo workspaces conforming to API contracts', () => {
    const workspaces = getDemoWorkspaces();
    expect(workspaces).toHaveLength(6);
    expect(workspaces.map((w) => w.id)).toEqual([
      'ws-demo-1',
      'ws-demo-2',
      'ws-demo-3',
      'ws-demo-4',
      'ws-demo-5',
      'ws-demo-6',
    ]);
    for (const ws of workspaces) {
      expect(ws.name).toContain('[Demo]');
      expect(ws.description).toBeTruthy();
    }
  });

  it('provides matching factory configs for all 6 demo workspaces', () => {
    for (const fixture of DEMO_SCENARIO_LIST) {
      const factory = getDemoFactory(fixture.factory.workspace_id);
      expect(factory.workspace_id).toBe(fixture.factory.workspace_id);
      expect(factory.machines.length).toBe(fixture.factory.machines.length);
      expect(factory.orders.length).toBe(fixture.factory.orders.length);
    }
  });

  it('provides schedules with valid KPIs and solver telemetry', () => {
    for (const fixture of DEMO_SCENARIO_LIST) {
      const summaries = getDemoSchedules(fixture.factory.workspace_id);
      expect(summaries).toHaveLength(1);
      const summary = summaries[0];
      expect(summary.makespan_minutes).toBe(fixture.schedule.metrics.makespan_minutes);

      const detail = getDemoScheduleDetail(fixture.factory.workspace_id, summary.id);
      expect(detail.id).toBe(fixture.schedule.id);
      expect(detail.scheduled_operations.length).toBe(fixture.schedule.scheduled_operations.length);
      expect(detail.solver_telemetry).toBeDefined();
    }
  });

  it('audits demo schedules via client-side verifier', () => {
    // Demos 1-5 must be verified valid
    for (let i = 1; i <= 5; i++) {
      const rep = verifyDemoSchedule(`ws-demo-${i}`);
      expect(rep.is_valid).toBe(true);
      expect(rep.checks_passed).toBe(8);
      expect(rep.violations).toHaveLength(0);
    }

    // Demo 6 must be flagged invalid
    const rep6 = verifyDemoSchedule('ws-demo-6');
    expect(rep6.is_valid).toBe(false);
    expect(rep6.violations.length).toBeGreaterThan(0);
  });

  it('builds comprehensive analytical reports matching ScheduleReportResponse', () => {
    const report = getDemoScheduleReport('ws-demo-1');
    expect(report.workspace_id).toBe('ws-demo-1');
    expect(report.summary.makespan_minutes).toBeGreaterThan(0);
    expect(report.summary.total_order_count).toBe(6);
    expect(report.machine_utilization).toHaveLength(4);
    expect(report.order_performance).toHaveLength(6);
    expect(report.bottleneck.primary_bottleneck_machine_id).toBeTruthy();
    expect(report.verification_audit.is_valid).toBe(true);
  });

  describe('Shop-Floor Execution Controls in Demo Mode', () => {
    it('initializes execution status with all initial released operations ready to start and machines idle', () => {
      const status = getDemoExecutionStatus('ws-demo-1');
      expect(status.workspace_id).toBe('ws-demo-1');
      expect(status.current_time_minute).toBe(0);
      expect(status.active_operations).toHaveLength(0);
      // All 6 orders have sequence_index: 1 released at t=0
      expect(status.ready_to_start_operations.length).toBeGreaterThan(0);
      for (const m of status.occupied_machines) {
        expect(m.status).toBe('IDLE');
        expect(m.active_operation_id).toBeNull();
      }
    });

    it('starts a planned operation and transitions machine to BUSY', () => {
      const status = startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      expect(status.current_time_minute).toBe(0);
      expect(status.active_operations).toHaveLength(1);
      const active = status.active_operations[0];
      expect(active.operation_id).toBe('ORD-01-OP1');
      expect(active.actual_start_minute).toBe(0);
      expect(active.remaining_duration_minutes).toBe(15);
      expect(active.is_overdue).toBe(false);

      const m1 = status.occupied_machines.find((m) => m.machine_id === 'M1');
      expect(m1?.status).toBe('BUSY');
      expect(m1?.active_operation_id).toBe('ORD-01-OP1');

      // Factory reflection
      const factory = getDemoFactory('ws-demo-1');
      const op = factory.orders[0].operations[0];
      expect(op.status).toBe('IN_PROGRESS');
      expect(op.actual_start_minute).toBe(0);
      expect(op.remaining_duration_minutes).toBe(15);
    });

    it('enforces execution lifecycle constraints on start', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');

      // Cannot start an already IN_PROGRESS operation
      expect(() => startDemoOperation('ws-demo-1', 'ORD-01-OP1')).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_LIFECYCLE_STATE');
      }

      // Cannot start predecessor step 2 while step 1 is in progress
      expect(() => startDemoOperation('ws-demo-1', 'ORD-01-OP2')).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-1', 'ORD-01-OP2');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_SEQUENCE');
      }

      // Cannot start on an occupied machine (ORD-05-OP1 also requires M1)
      expect(() => startDemoOperation('ws-demo-1', 'ORD-05-OP1')).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-1', 'ORD-05-OP1');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('MACHINE_OCCUPIED');
      }

      // Nonexistent operation
      expect(() => startDemoOperation('ws-demo-1', 'NONEXISTENT-OP')).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-1', 'NONEXISTENT-OP');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('RESOURCE_NOT_FOUND');
      }

      // Stale optimistic fencing token
      expect(() =>
        startDemoOperation('ws-demo-1', 'ORD-03-OP1', { expected_current_time_minute: 999 })
      ).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-1', 'ORD-03-OP1', { expected_current_time_minute: 999 });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('STALE_EXECUTION_STATE');
        expect((err as ApiClientError).status).toBe(409);
      }
    });

    it('linearly decrements active operation remaining duration on clock advance', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      const status = advanceDemoClock('ws-demo-1', { advance_by_minutes: 10 });

      expect(status.current_time_minute).toBe(10);
      expect(status.active_operations).toHaveLength(1);
      const active = status.active_operations[0];
      expect(active.elapsed_minutes).toBe(10);
      expect(active.remaining_duration_minutes).toBe(5);

      const factory = getDemoFactory('ws-demo-1');
      expect(factory.current_time_minute).toBe(10);
      expect(factory.orders[0].operations[0].remaining_duration_minutes).toBe(5);
    });

    it('allows adjusting remaining duration of an in-progress operation', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      advanceDemoClock('ws-demo-1', { advance_by_minutes: 10 });

      const status = adjustDemoRemainingDuration('ws-demo-1', 'ORD-01-OP1', {
        remaining_duration_minutes: 8,
      });
      expect(status.active_operations[0].remaining_duration_minutes).toBe(8);

      // Remaining duration < 1 must be rejected
      expect(() =>
        adjustDemoRemainingDuration('ws-demo-1', 'ORD-01-OP1', {
          remaining_duration_minutes: 0,
        })
      ).toThrowError(ApiClientError);
      try {
        adjustDemoRemainingDuration('ws-demo-1', 'ORD-01-OP1', {
          remaining_duration_minutes: 0,
        });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_DURATION');
      }
    });

    it('enforces Policy B overdue reconciliation requirement when advancing past remaining work', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1'); // 15 minutes processing
      // Advancing by 20 without reconciling must throw OVERDUE_RECONCILIATION_REQUIRED
      expect(() =>
        advanceDemoClock('ws-demo-1', { advance_by_minutes: 20 })
      ).toThrowError(ApiClientError);
      try {
        advanceDemoClock('ws-demo-1', { advance_by_minutes: 20 });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('OVERDUE_RECONCILIATION_REQUIRED');
      }

      // Reconciling via override allows clock advance
      const status = advanceDemoClock('ws-demo-1', {
        advance_by_minutes: 20,
        remaining_duration_overrides: { 'ORD-01-OP1': 5 },
      });
      expect(status.current_time_minute).toBe(20);
      expect(status.active_operations[0].remaining_duration_minutes).toBe(5);
    });

    it('completes operation via clock advance with completed_operation_ids and enables successor', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      const status = advanceDemoClock('ws-demo-1', {
        target_time_minute: 15,
        completed_operation_ids: ['ORD-01-OP1'],
      });

      expect(status.current_time_minute).toBe(15);
      expect(status.active_operations).toHaveLength(0);

      const m1 = status.occupied_machines.find((m) => m.machine_id === 'M1');
      expect(m1?.status).toBe('IDLE');

      // Successor ORD-01-OP2 should now be ready to start
      const op2Ready = status.ready_to_start_operations.find((r) => r.operation_id === 'ORD-01-OP2');
      expect(op2Ready).toBeDefined();

      const factory = getDemoFactory('ws-demo-1');
      const op1 = factory.orders[0].operations[0];
      expect(op1.status).toBe('COMPLETED');
      expect(op1.actual_end_minute).toBe(15);
      expect(op1.remaining_duration_minutes).toBeNull();
    });

    it('supports direct completeDemoOperation endpoint after clock advance', () => {
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');

      // Completing at start minute must fail (duration must be strictly positive)
      expect(() => completeDemoOperation('ws-demo-1', 'ORD-01-OP1')).toThrowError(ApiClientError);
      try {
        completeDemoOperation('ws-demo-1', 'ORD-01-OP1');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_LIFECYCLE_STATE');
      }

      // Advance clock then complete
      advanceDemoClock('ws-demo-1', { advance_by_minutes: 10 });
      const status = completeDemoOperation('ws-demo-1', 'ORD-01-OP1');
      expect(status.current_time_minute).toBe(10);
      expect(status.active_operations).toHaveLength(0);

      const factory = getDemoFactory('ws-demo-1');
      const op1 = factory.orders[0].operations[0];
      expect(op1.status).toBe('COMPLETED');
      expect(op1.actual_end_minute).toBe(10);
    });

    it('validates advance clock input parameters and reject backward progress', () => {
      advanceDemoClock('ws-demo-1', { advance_by_minutes: 20 });

      // Backward advance
      expect(() => advanceDemoClock('ws-demo-1', { target_time_minute: 10 })).toThrowError(ApiClientError);
      try {
        advanceDemoClock('ws-demo-1', { target_time_minute: 10 });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_CLOCK');
      }

      // Missing both advance_by_minutes and target_time_minute
      expect(() => advanceDemoClock('ws-demo-1', {})).toThrowError(ApiClientError);
      try {
        advanceDemoClock('ws-demo-1', {});
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_CLOCK');
      }

      // Stale optimistic token
      expect(() =>
        advanceDemoClock('ws-demo-1', { advance_by_minutes: 5, expected_current_time_minute: 0 })
      ).toThrowError(ApiClientError);
      try {
        advanceDemoClock('ws-demo-1', { advance_by_minutes: 5, expected_current_time_minute: 0 });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('STALE_EXECUTION_STATE');
      }

      // Conflicting completed and override on the same operation
      startDemoOperation('ws-demo-1', 'ORD-01-OP1');
      expect(() =>
        advanceDemoClock('ws-demo-1', {
          advance_by_minutes: 5,
          completed_operation_ids: ['ORD-01-OP1'],
          remaining_duration_overrides: { 'ORD-01-OP1': 3 },
        })
      ).toThrowError(ApiClientError);
      try {
        advanceDemoClock('ws-demo-1', {
          advance_by_minutes: 5,
          completed_operation_ids: ['ORD-01-OP1'],
          remaining_duration_overrides: { 'ORD-01-OP1': 3 },
        });
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('INVALID_LIFECYCLE_STATE');
      }
    });

    it('detects downtime collision during operation start and clock advance', () => {
      // In ws-demo-5, M1 is down in [30, 90)
      const initStatus = getDemoExecutionStatus('ws-demo-5');
      expect(initStatus.occupied_machines.find((m) => m.machine_id === 'M1')?.status).toBe('IDLE');

      // Advance clock into the downtime window (t = 35)
      advanceDemoClock('ws-demo-5', { target_time_minute: 35 });
      const statusAt35 = getDemoExecutionStatus('ws-demo-5');
      expect(statusAt35.occupied_machines.find((m) => m.machine_id === 'M1')?.status).toBe('DOWNTIME');

      // Starting an operation on M1 at t=35 must be rejected due to active downtime
      expect(() => startDemoOperation('ws-demo-5', 'ORD-01-OP1')).toThrowError(ApiClientError);
      try {
        startDemoOperation('ws-demo-5', 'ORD-01-OP1');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        expect((err as ApiClientError).code).toBe('HISTORICAL_DOWNTIME_CONFLICT');
      }
    });

    it('supports saving/replacing factory configuration in demo mode', async () => {
      const orig = getDemoFactory('ws-demo-1');
      expect(orig.machines).toHaveLength(4);

      const updated = await apiEndpoints.replaceFactory('ws-demo-1', {
        current_time_minute: 45,
        machines: [
          { external_id: 'NEW-M1', name: 'Custom CNC' },
        ],
        downtimes: [],
        orders: [
          {
            external_id: 'NEW-ORD1',
            name: 'Custom Order',
            release_minute: 0,
            due_minute: 100,
            tardiness_weight: 1,
            operations: [
              { sequence_index: 1, machine_id: 'NEW-M1', processing_minutes: 20 },
            ],
          },
        ],
      });

      expect(updated.current_time_minute).toBe(45);
      expect(updated.machines).toHaveLength(1);
      expect(updated.machines[0].name).toBe('Custom CNC');

      const reloaded = await apiEndpoints.getFactory('ws-demo-1');
      expect(reloaded.current_time_minute).toBe(45);
      expect(reloaded.orders[0].external_id).toBe('NEW-ORD1');
    });

    it('executes full execution workflow via typed apiEndpoints in demo mode without HTTP calls', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');

      const initStatus = await apiEndpoints.getExecutionStatus('ws-demo-1');
      expect(initStatus.current_time_minute).toBe(0);

      const startedStatus = await apiEndpoints.startOperation('ws-demo-1', 'ORD-01-OP1');
      expect(startedStatus.active_operations).toHaveLength(1);

      const advancedStatus = await apiEndpoints.advanceClock('ws-demo-1', { advance_by_minutes: 5 });
      expect(advancedStatus.current_time_minute).toBe(5);
      expect(advancedStatus.active_operations[0].remaining_duration_minutes).toBe(10);

      const adjustedStatus = await apiEndpoints.adjustRemainingDuration('ws-demo-1', 'ORD-01-OP1', {
        remaining_duration_minutes: 12,
      });
      expect(adjustedStatus.active_operations[0].remaining_duration_minutes).toBe(12);

      await apiEndpoints.advanceClock('ws-demo-1', { advance_by_minutes: 3 });
      const completedStatus = await apiEndpoints.completeOperation('ws-demo-1', 'ORD-01-OP1');
      expect(completedStatus.current_time_minute).toBe(8);
      expect(completedStatus.active_operations).toHaveLength(0);

      // Verify zero network calls were made
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });

    it('manages demo disruption scenarios and reoptimization without network calls', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');

      // 1. List scenarios
      const scenarios = await apiEndpoints.listScenarios('ws-demo-1');
      expect(scenarios.length).toBeGreaterThanOrEqual(1);

      // 2. Create scenario
      const created = await apiEndpoints.createScenario('ws-demo-1', {
        baseline_schedule_id: scenarios[0].baseline_schedule_id,
        disruption_type: 'MACHINE_DOWNTIME',
        name: 'Unplanned CNC Outage',
        description: 'Simulating tool break',
        disruption_delta: {
          added_downtimes: [{ machine_id: 'M1', start_minute: 10, end_minute: 40, reason: 'Tool break' }],
          added_orders: [],
        },
      });
      expect(created.id).toContain('scen-demo-');
      expect(created.name).toBe('Unplanned CNC Outage');

      // 3. Get single scenario
      const fetched = await apiEndpoints.getScenario('ws-demo-1', created.id);
      expect(fetched.name).toBe('Unplanned CNC Outage');

      // 4. Reoptimize scenario
      const comp = await apiEndpoints.reoptimizeScenario('ws-demo-1', created.id);
      expect(comp.scenario_id).toBe(created.id);
      expect(comp.compared_schedule_id).toContain('sched-rec-');

      // 5. Updated scenario has reoptimized_schedule_id
      const updated = await apiEndpoints.getScenario('ws-demo-1', created.id);
      expect(updated.reoptimized_schedule_id).toBe(comp.compared_schedule_id);

      // 6. Delete scenario
      const delRes = await apiEndpoints.deleteScenario('ws-demo-1', created.id);
      expect(delRes.deleted).toBe(true);

      // Verify deletion
      await expect(apiEndpoints.getScenario('ws-demo-1', created.id)).rejects.toThrow(ApiClientError);

      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });

    it('truthfully handles CP-SAT pre-solved scenarios vs. client-side heuristic simulation', async () => {
      // 1. Pre-solved rush order disruption uses genuine CP-SAT optimal fixture
      const scenarios = await apiEndpoints.listScenarios('ws-demo-1');
      const rushScen = scenarios.find((s) => s.disruption_type === 'URGENT_ORDER');
      expect(rushScen).toBeDefined();

      const rushComp = await apiEndpoints.reoptimizeScenario('ws-demo-1', rushScen!.id);
      expect(rushComp.unlike_comparison_warning).toBeNull();
      expect(rushComp.status_diff_detected).toBe(false);

      const rushRecSched = await apiEndpoints.getSchedule('ws-demo-1', rushComp.compared_schedule_id);
      expect(rushRecSched.solver_status).toBe('OPTIMAL');
      expect(rushRecSched.verification_status).toBe('VERIFIED');
      expect(rushRecSched.name).toContain('CP-SAT Reoptimized');

      // 2. Custom disruption scenario clearly discloses client-side demo simulation
      const customScen = await apiEndpoints.createScenario('ws-demo-1', {
        name: 'Custom Ad-Hoc Outage',
        disruption_type: 'MACHINE_DOWNTIME',
        baseline_schedule_id: rushScen!.baseline_schedule_id,
        disruption_delta: {
          added_downtimes: [{ machine_id: 'M2', start_minute: 10, end_minute: 40, reason: 'Custom test outage' }],
          added_orders: [],
        },
      });

      const simComp = await apiEndpoints.reoptimizeScenario('ws-demo-1', customScen.id);
      expect(simComp.unlike_comparison_warning).toContain('Demo Simulation Notice');
      expect(simComp.status_diff_detected).toBe(true);

      const simRecSched = await apiEndpoints.getSchedule('ws-demo-1', simComp.compared_schedule_id);
      expect(simRecSched.solver_status).toBe('DEMO_SIMULATION'); // Explicit demo simulation status, never misleading FEASIBLE or OPTIMAL
      expect(simRecSched.name).toContain('[Demo Simulation]');
      expect(simRecSched.solver_telemetry?.termination_reason).toContain('Client-side demo simulation');
      expect(simRecSched.metrics.makespan_minutes).toBeGreaterThan(0);
      expect(simRecSched.metrics.objective_value).toBeNull();
      expect(simRecSched.metrics.optimality_gap).toBeNull();
    });

    it('preserves precise objective claims distinguishing weighted tardiness optimality from makespan in urgent-order recovery', async () => {
      // Urgent order recovery fixture (sched-demo-4) minimizes weighted tardiness, achieving Z* = 0
      const sched = await apiEndpoints.getSchedule('ws-demo-4', 'sched-demo-4');
      expect(sched.objective_type).toBe('PURE_WEIGHTED_TARDINESS');
      expect(sched.solver_status).toBe('OPTIMAL');
      expect(sched.verification_status).toBe('VERIFIED');
      expect(sched.metrics.weighted_tardiness).toBe(0);
      expect(sched.metrics.objective_value).toBe(0);
      expect(sched.metrics.late_order_count).toBe(0);
      expect(sched.metrics.on_time_rate).toBe(100.0);
      // Makespan is 140 minutes in this valid CP-SAT schedule (though a 135-minute makespan schedule is also tardiness-optimal)
      expect(sched.metrics.makespan_minutes).toBe(140);
      // The solver telemetry explicitly proves optimality under weighted tardiness, NOT makespan
      expect(sched.solver_telemetry?.termination_reason).toContain('weighted tardiness minimization');
      expect(sched.solver_telemetry?.termination_reason).not.toContain('makespan minimization');

      // Contrast with downtime fixture (sched-demo-5) which is strictly makespan-optimal
      const dtSched = await apiEndpoints.getSchedule('ws-demo-5', 'sched-demo-5');
      expect(dtSched.objective_type).toBe('PURE_MAKESPAN');
      expect(dtSched.solver_status).toBe('OPTIMAL');
      expect(dtSched.metrics.makespan_minutes).toBe(155);
      expect(dtSched.metrics.objective_value).toBe(155);
      expect(dtSched.solver_telemetry?.termination_reason).toContain('makespan minimization');
    });

    it('honestly validates demo imports end to end and rejects unsupported binary files', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');

      vi.stubGlobal('URL', {
        createObjectURL: vi.fn(() => 'blob:mock-url'),
        revokeObjectURL: vi.fn(),
      });

      // 1. Template download: CSV downloads file; XLSX throws informative limitation
      await apiEndpoints.downloadTemplate('csv');
      await expect(apiEndpoints.downloadTemplate('xlsx')).rejects.toThrow(ApiClientError);

      // 2. Binary .xlsx rejection with explicit limitation notice
      const xlsxFile = new File(['fake-binary-content'], 'factory_upload.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const xlsxPreview = await apiEndpoints.previewImport('ws-demo-1', xlsxFile);
      expect(xlsxPreview.is_valid).toBe(false);
      expect(xlsxPreview.status).toBe('FAILED');
      expect(xlsxPreview.errors?.[0]?.issue).toContain('Static Demo Limitation: Binary Excel (.xlsx)');

      // 3. Binary .zip rejection with explicit limitation notice
      const zipFile = new File(['fake-zip-content'], 'bundle.zip', { type: 'application/zip' });
      const zipPreview = await apiEndpoints.previewImport('ws-demo-1', zipFile);
      expect(zipPreview.is_valid).toBe(false);
      expect(zipPreview.errors?.[0]?.issue).toContain('Static Demo Limitation');

      // 4. Empty CSV rejection
      const emptyFile = new File(['# Only comments\n\n'], 'empty.csv', { type: 'text/csv' });
      const emptyPreview = await apiEndpoints.previewImport('ws-demo-1', emptyFile);
      expect(emptyPreview.is_valid).toBe(false);
      expect(emptyPreview.errors?.[0]?.issue).toContain('File is empty');

      // 5. Valid CSV parsing, preview, and confirmation into factory state
      const validCsv = [
        '# Section: Machines',
        'M-NEW-1,New Milling Station',
        'M-NEW-2,New Lathe Station',
        '# Section: Orders',
        'ORD-NEW-1,New Order A,0,100,2',
        '# Section: Operations',
        'ORD-NEW-1,1,M-NEW-1,20',
        'ORD-NEW-1,2,M-NEW-2,30',
      ].join('\n');

      const csvFile = new File([validCsv], 'factory_valid.csv', { type: 'text/csv' });
      const csvPreview = await apiEndpoints.previewImport('ws-demo-1', csvFile);
      expect(csvPreview.is_valid).toBe(true);
      expect(csvPreview.status).toBe('VALIDATED');
      expect(csvPreview.summary?.machine_count).toBe(2);
      expect(csvPreview.summary?.order_count).toBe(1);
      expect(csvPreview.summary?.operation_count).toBe(2);
      expect(csvPreview.job_id).toBeTruthy();

      // 6. Confirm import commits directly to demoFactoryState
      const confirmResult = await apiEndpoints.confirmImport('ws-demo-1', csvPreview.job_id || '');
      expect(confirmResult.status).toBe('COMMITTED');

      const updatedFactory = await apiEndpoints.getFactory('ws-demo-1');
      expect(updatedFactory.machines.some((m) => m.external_id === 'M-NEW-1')).toBe(true);
      expect(updatedFactory.orders.some((o) => o.external_id === 'ORD-NEW-1')).toBe(true);

      // 7. Repeated confirmation with same stale job ID throws 404
      await expect(apiEndpoints.confirmImport('ws-demo-1', csvPreview.job_id || '')).rejects.toThrow(ApiClientError);

      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });

    it('rejects malformed CSVs with missing columns, invalid integers, duplicates, and referential errors without mutating factory state', async () => {
      const originalFactory = await apiEndpoints.getFactory('ws-demo-1');
      const origMachineCount = originalFactory.machines.length;

      // 1. Duplicate machine ID
      const dupMachineCsv = [
        '# Section: Machines',
        'M1,Machine One',
        'M1,Duplicate Machine One',
        '# Section: Orders',
        'O1,Order 1,0,100,1',
        '# Section: Operations',
        'O1,1,M1,10',
      ].join('\n');
      const dupPreview = await apiEndpoints.previewImport('ws-demo-1', new File([dupMachineCsv], 'dup.csv', { type: 'text/csv' }));
      expect(dupPreview.is_valid).toBe(false);
      expect(dupPreview.errors?.some((e) => e.issue.includes("Duplicate machine ID 'M1'"))).toBe(true);

      // 2. Non-positive durations and invalid integers
      const badDurationCsv = [
        '# Section: Machines',
        'M1,Machine One',
        '# Section: Orders',
        'O1,Order 1,0,100,1',
        '# Section: Operations',
        'O1,1,M1,-5',
      ].join('\n');
      const badDurPreview = await apiEndpoints.previewImport('ws-demo-1', new File([badDurationCsv], 'bad_dur.csv', { type: 'text/csv' }));
      expect(badDurPreview.is_valid).toBe(false);
      expect(badDurPreview.errors?.some((e) => e.issue.includes('Processing minutes must be integer >= 1'))).toBe(true);

      // 3. Unknown machine reference in operations
      const unknownMachineCsv = [
        '# Section: Machines',
        'M1,Machine One',
        '# Section: Orders',
        'O1,Order 1,0,100,1',
        '# Section: Operations',
        'O1,1,M-NONEXISTENT,15',
      ].join('\n');
      const unkPreview = await apiEndpoints.previewImport('ws-demo-1', new File([unknownMachineCsv], 'unk.csv', { type: 'text/csv' }));
      expect(unkPreview.is_valid).toBe(false);
      expect(unkPreview.errors?.some((e) => e.issue.includes("unknown machine 'M-NONEXISTENT'"))).toBe(true);

      // 4. Verify factory was NOT mutated on validation failures
      const factoryAfterFailures = await apiEndpoints.getFactory('ws-demo-1');
      expect(factoryAfterFailures.machines.length).toBe(origMachineCount);
    });

    it('correctly parses CSV with embedded commas and quotes in entity names', async () => {
      const quotedCsv = [
        '# Section: Machines',
        'M-CNC,"CNC Milling, High-Precision Station"',
        '# Section: Orders',
        'ORD-A,"Bracket, Subassembly A",0,150,3',
        '# Section: Operations',
        'ORD-A,1,M-CNC,25',
      ].join('\n');

      const preview = await apiEndpoints.previewImport('ws-demo-1', new File([quotedCsv], 'quoted.csv', { type: 'text/csv' }));
      expect(preview.is_valid).toBe(true);
      expect(preview.staged_data?.machines[0]?.name).toBe('CNC Milling, High-Precision Station');
      expect(preview.staged_data?.orders[0]?.name).toBe('Bracket, Subassembly A');

      // Confirm and verify exact names applied
      expect(preview.job_id).toBeTruthy();
      await apiEndpoints.confirmImport('ws-demo-1', preview.job_id!);
      const factory = await apiEndpoints.getFactory('ws-demo-1');
      const machine = factory.machines.find((m) => m.external_id === 'M-CNC');
      const order = factory.orders.find((o) => o.external_id === 'ORD-A');
      expect(machine?.name).toBe('CNC Milling, High-Precision Station');
      expect(order?.name).toBe('Bracket, Subassembly A');
    });

    it('maintains strict state isolation and lifecycle across multiple workspaces', async () => {
      // 1. Verify two distinct workspaces start with their respective fixtures
      const f1 = await apiEndpoints.getFactory('ws-demo-1');
      const f2 = await apiEndpoints.getFactory('ws-demo-2');
      expect(f1.workspace_id).toBe('ws-demo-1');
      expect(f2.workspace_id).toBe('ws-demo-2');

      // 2. Advance clock in ws-demo-1
      await apiEndpoints.advanceClock('ws-demo-1', { target_time_minute: 25 });
      const f1After = await apiEndpoints.getFactory('ws-demo-1');
      const f2After = await apiEndpoints.getFactory('ws-demo-2');
      expect(f1After.current_time_minute).toBe(25);
      expect(f2After.current_time_minute).toBe(0); // ws-demo-2 is completely untouched

      // 3. Create scenario in ws-demo-1
      const scen1 = await apiEndpoints.createScenario('ws-demo-1', {
        name: 'Isolated Outage ws-1',
        disruption_type: 'MACHINE_DOWNTIME',
        baseline_schedule_id: (await apiEndpoints.listSchedules('ws-demo-1'))[0].id,
        disruption_delta: { added_downtimes: [], added_orders: [] },
      });
      const scens1 = await apiEndpoints.listScenarios('ws-demo-1');
      const scens2 = await apiEndpoints.listScenarios('ws-demo-2');
      expect(scens1.some((s) => s.id === scen1.id)).toBe(true);
      expect(scens2.some((s) => s.id === scen1.id)).toBe(false); // No scenario leak

      // 4. Reset factory state for ws-demo-1 resets only ws-demo-1
      resetDemoFactoryState('ws-demo-1');
      const f1Reset = await apiEndpoints.getFactory('ws-demo-1');
      expect(f1Reset.current_time_minute).toBe(0);
    });

    it('manages custom workspace creation, isolation, and reset in demo mode', async () => {
      const initialWorkspaces = await apiEndpoints.listWorkspaces();
      expect(initialWorkspaces.length).toBe(6);

      // Create custom workspace
      const created = await apiEndpoints.createWorkspace({
        name: 'Custom Test Plant',
        description: 'Temporary workspace for testing',
      });
      expect(created.name).toBe('Custom Test Plant');

      const updatedList = await apiEndpoints.listWorkspaces();
      expect(updatedList.length).toBe(7);
      expect(updatedList.some((w) => w.id === created.id)).toBe(true);

      // Delete custom workspace
      await apiEndpoints.deleteWorkspace(created.id);
      const afterDelete = await apiEndpoints.listWorkspaces();
      expect(afterDelete.length).toBe(6);
      expect(afterDelete.some((w) => w.id === created.id)).toBe(false);
    });
  });
});
