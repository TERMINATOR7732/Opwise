/**
 * Standalone Client-Side Demo Service & Fallback Provider
 * Governed by SPECIFICATION.md Section 1.1 (Tier 2), Section 8.4 State 13, and Section 10.
 */

import {
  FactoryConfigResponse,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
  VerificationReportResponse,
  WorkspaceResponse,
} from '../types/api';
import { ScheduleReportResponse } from '../types/reports';
import { ScenarioResponse } from '../types/scenarios';
import { DEMO_FIXTURES, DEMO_SCENARIO_LIST, DemoFixture } from './fixtures';
import { verifyScheduleClient } from './clientVerifier';
import { buildDemoReport } from './demoReportBuilder';

const DEMO_MODE_STORAGE_KEY = 'opwise_demo_mode';
const ACTIVE_DEMO_STORAGE_KEY = 'opwise_active_demo_id';

let runtimeDemoModeOverride: boolean | null = null;

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
  return DEMO_SCENARIO_LIST.map((fixture) => ({
    id: fixture.factory.workspace_id,
    name: `[Demo] ${fixture.name}`,
    description: fixture.description,
    created_at: fixture.schedule.created_at,
    updated_at: fixture.schedule.created_at,
  }));
}

export function findDemoFixtureByWorkspace(workspaceId: string): DemoFixture {
  const match = DEMO_SCENARIO_LIST.find((f) => f.factory.workspace_id === workspaceId);
  return match || DEMO_FIXTURES[getActiveDemoId()] || DEMO_FIXTURES['demo-1'];
}

export function getDemoFactory(workspaceId: string): FactoryConfigResponse {
  return findDemoFixtureByWorkspace(workspaceId).factory;
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
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  if (fixture.schedule.id === scheduleId) return fixture.schedule;
  return fixture.schedule;
}

export function verifyDemoSchedule(workspaceId: string): VerificationReportResponse {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const result = verifyScheduleClient(fixture.factory, fixture.schedule);
  return {
    is_valid: result.is_valid,
    checks_run: result.checks_run,
    checks_passed: result.checks_passed,
    violations: result.violations,
  };
}

export function getDemoScheduleReport(workspaceId: string): ScheduleReportResponse {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  const verification = verifyScheduleClient(fixture.factory, fixture.schedule);
  return buildDemoReport(fixture.factory, fixture.schedule, verification);
}

export function getDemoScenarios(workspaceId: string): ScenarioResponse[] {
  const fixture = findDemoFixtureByWorkspace(workspaceId);
  if (fixture.id === 'demo-4') {
    return [
      {
        id: 'scen-demo-4',
        workspace_id: workspaceId,
        baseline_schedule_id: fixture.schedule.id,
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
        created_at: fixture.schedule.created_at,
      },
    ];
  }
  if (fixture.id === 'demo-5') {
    return [
      {
        id: 'scen-demo-5',
        workspace_id: workspaceId,
        baseline_schedule_id: fixture.schedule.id,
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
        created_at: fixture.schedule.created_at,
      },
    ];
  }
  return [];
}
