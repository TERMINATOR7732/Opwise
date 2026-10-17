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
} from '../demo/demoService';
import { DEMO_SCENARIO_LIST } from '../demo/fixtures';

describe('Standalone Demo Mode Service & Data Provider', () => {
  const store: Record<string, string> = {};

  beforeEach(() => {
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
});
