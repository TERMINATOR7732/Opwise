/**
 * Tests for Optimization Planning Engine & Schedule Inspector (Milestone 09B)
 * Governed by DATA_AND_API.md Section 3.3 and SPECIFICATION.md Section 4.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { apiEndpoints } from '../api/endpoints';
import {
  FactoryConfigResponse,
  OptimizeResponseData,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
  VerificationReportResponse,
} from '../types/api';
import { FactoryReadinessCard } from '../views/planning/FactoryReadinessCard';
import { OptimizationParametersForm } from '../views/planning/OptimizationParametersForm';
import { OptimizationResultCard } from '../views/planning/OptimizationResultCard';
import { RecentSchedulesCard } from '../views/planning/RecentSchedulesCard';
import { ScheduleDetailCard } from '../views/schedules/ScheduleDetailCard';

const mockFactory: FactoryConfigResponse = {
  workspace_id: 'ws-1',
  current_time_minute: 0,
  machines: [
    { id: 'm-1', external_id: 'M1', name: '5-Axis CNC Mill', created_at: '2026-10-17T10:00:00Z' },
    { id: 'm-2', external_id: 'M2', name: 'Manual Lathe', created_at: '2026-10-17T10:00:00Z' },
  ],
  downtimes: [
    { id: 'dt-1', machine_id: 'm-1', start_minute: 60, end_minute: 90, reason: 'Tool Inspection' },
  ],
  orders: [
    {
      id: 'ord-1',
      external_id: 'ORD-101',
      name: 'Turbine Disk',
      release_minute: 0,
      due_minute: 180,
      tardiness_weight: 3,
      operations: [
        { id: 'op-1', order_id: 'ord-1', sequence_index: 1, machine_id: 'm-1', processing_minutes: 45 },
        { id: 'op-2', order_id: 'ord-1', sequence_index: 2, machine_id: 'm-2', processing_minutes: 30 },
      ],
    },
  ],
};

const mockOptimizeResponse: OptimizeResponseData = {
  schedule_id: 'sched-101',
  name: 'Test Optimization Run',
  objective_type: 'PURE_MAKESPAN',
  solver_status: 'OPTIMAL',
  verification_status: 'VERIFIED',
  stage1_telemetry: null,
  stage2_telemetry: null,
  metrics: {
    makespan_minutes: 105,
    weighted_tardiness: 0,
    late_order_count: 0,
    on_time_rate: 100.0,
    objective_value: 105,
    best_objective_bound: 105,
    optimality_gap: 0.0,
  },
  solver_telemetry: {
    wall_clock_time_seconds: 0.84,
    deterministic_time: 0.042,
    user_cpu_time_seconds: 0.81,
    termination_reason: 'SOLVER_STATUS_OPTIMAL',
  },
  verification_report: {
    is_valid: true,
    checks_run: 8,
    checks_passed: 8,
    violations: [],
  },
  scheduled_operations: [
    { operation_id: 'op-1', order_id: 'ORD-101', sequence_index: 1, machine_id: 'M1', start_minute: 0, end_minute: 45, duration: 45, slack_minutes: 0 },
    { operation_id: 'op-2', order_id: 'ORD-101', sequence_index: 2, machine_id: 'M2', start_minute: 45, end_minute: 75, duration: 30, slack_minutes: 105 },
  ],
};

const mockScheduleDetail: ScheduleDetailResponse = {
  id: 'sched-101',
  workspace_id: 'ws-1',
  name: 'Batch Schedule #1',
  objective_type: 'HIERARCHICAL',
  solver_status: 'OPTIMAL',
  verification_status: 'VERIFIED',
  stage1_telemetry: { status: 'OPTIMAL', objective_value: 0, wall_clock_seconds: 0.35 },
  stage2_telemetry: { status: 'OPTIMAL', objective_value: 105, wall_clock_seconds: 0.12 },
  metrics: {
    makespan_minutes: 105,
    weighted_tardiness: 0,
    late_order_count: 0,
    on_time_rate: 100.0,
    optimality_gap: 0.0,
  },
  solver_telemetry: {
    wall_clock_time_seconds: 0.47,
    deterministic_time: 0.021,
    termination_reason: 'SOLVER_STATUS_OPTIMAL',
  },
  scheduled_operations: [
    { operation_id: 'op-1', order_id: 'ORD-101', sequence_index: 1, machine_id: 'M1', start_minute: 0, end_minute: 45, duration: 45, slack_minutes: 0 },
  ],
  created_at: '2026-10-17T11:00:00Z',
};

describe('Optimization API Endpoints', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('optimizeSchedule posts parameters and returns solve response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockOptimizeResponse, metadata: {} }),
    });

    const res = await apiEndpoints.optimizeSchedule('ws-1', {
      name: 'Shift Run',
      objective_type: 'PURE_MAKESPAN',
    });
    expect(res.schedule_id).toBe('sched-101');
    expect(res.solver_status).toBe('OPTIMAL');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/optimize',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('getSchedule retrieves full detail and telemetry', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: mockScheduleDetail, metadata: {} }),
    });

    const res = await apiEndpoints.getSchedule('ws-1', 'sched-101');
    expect(res.id).toBe('sched-101');
    expect(res.objective_type).toBe('HIERARCHICAL');
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/schedules/sched-101', expect.any(Object));
  });

  it('verifySchedule triggers on-demand clean-room verification', async () => {
    const report: VerificationReportResponse = { is_valid: true, checks_run: 8, checks_passed: 8, violations: [] };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: report, metadata: {} }),
    });

    const res = await apiEndpoints.verifySchedule('ws-1', 'sched-101');
    expect(res.is_valid).toBe(true);
    expect(res.checks_passed).toBe(8);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/schedules/sched-101/verify',
      expect.objectContaining({ method: 'POST' })
    );
  });
});

describe('Planning Components UI Markup', () => {
  it('renders FactoryReadinessCard with accurate counts and readiness badge', () => {
    const markup = renderToStaticMarkup(
      <FactoryReadinessCard
        factory={mockFactory}
        validationResult={{ is_valid: true, classification: 'OPTIMAL_OR_FEASIBLE', issues: [] }}
        isValidating={false}
        onValidate={async () => {}}
        onNavigateToFactory={() => {}}
      />
    );
    expect(markup).toContain('Shop Floor Readiness Audit');
    expect(markup).toContain('Machines');
    expect(markup).toContain('READY TO SOLVE');
  });

  it('renders FactoryReadinessCard with configuration violations alert', () => {
    const markup = renderToStaticMarkup(
      <FactoryReadinessCard
        factory={mockFactory}
        validationResult={{ is_valid: false, classification: 'PROVEN_INFEASIBLE', issues: ['Overlapping maintenance interval'] }}
        isValidating={false}
        onValidate={async () => {}}
        onNavigateToFactory={() => {}}
      />
    );
    expect(markup).toContain('INVALID INPUTS');
    expect(markup).toContain('Configuration Invariant Violations');
    expect(markup).toContain('Overlapping maintenance interval');
  });

  it('renders OptimizationParametersForm with objective modes and tuning controls', () => {
    const markup = renderToStaticMarkup(
      <OptimizationParametersForm onOptimize={async () => {}} isSolving={false} isDisabled={false} />
    );
    expect(markup).toContain('CP-SAT Solver Parameters &amp; Controls');
    expect(markup).toContain('Pure Makespan (C_max)');
    expect(markup).toContain('Pure Weighted Tardiness');
    expect(markup).toContain('Hierarchical Lexicographic');
    expect(markup).toContain('Run CP-SAT Optimization');
  });

  it('renders OptimizationResultCard with optimal status, metrics, and verifier report', () => {
    const markup = renderToStaticMarkup(
      <OptimizationResultCard result={mockOptimizeResponse} />
    );
    expect(markup).toContain('CP-SAT Proven Optimum Found');
    expect(markup).toContain('105m');
    expect(markup).toContain('0.0% (Exact)');
    expect(markup).toContain('Independent Clean-Room Verifier Audit');
    expect(markup).toContain('VERIFIED');
    expect(markup).toContain('Evaluated 8 of 8 invariant checks successfully');
  });

  it('renders OptimizationResultCard with feasible non-optimal status disclosure', () => {
    const feasibleResponse: OptimizeResponseData = {
      ...mockOptimizeResponse,
      solver_status: 'FEASIBLE',
      metrics: { ...mockOptimizeResponse.metrics, optimality_gap: 0.12 },
    };
    const markup = renderToStaticMarkup(<OptimizationResultCard result={feasibleResponse} />);
    expect(markup).toContain('Feasible Schedule Found (Optimality Not Proven)');
    expect(markup).toContain('12.0%');
  });

  it('renders OptimizationResultCard with DEMO_SIMULATION and does not fabricate 0.0% exact gap when optimality_gap is null', () => {
    const demoSimResponse: OptimizeResponseData = {
      ...mockOptimizeResponse,
      solver_status: 'DEMO_SIMULATION',
      metrics: {
        ...mockOptimizeResponse.metrics,
        optimality_gap: null,
        objective_value: null,
        best_objective_bound: null,
      },
    };
    const markup = renderToStaticMarkup(<OptimizationResultCard result={demoSimResponse} />);
    expect(markup).toContain('Demo Simulation (Client-Side Heuristic)');
    expect(markup).toContain('—');
    expect(markup).not.toContain('0.0% (Exact)');
    expect(markup).not.toContain('CP-SAT Proven Optimum Found');
  });

  it('does not fabricate 0.0% exact gap even if solver_status is OPTIMAL when optimality_gap is null', () => {
    const nullGapResponse: OptimizeResponseData = {
      ...mockOptimizeResponse,
      solver_status: 'OPTIMAL',
      metrics: {
        ...mockOptimizeResponse.metrics,
        optimality_gap: null,
      },
    };
    const markup = renderToStaticMarkup(<OptimizationResultCard result={nullGapResponse} />);
    expect(markup).toContain('—');
    expect(markup).not.toContain('0.0% (Exact)');
  });

  it('renders OptimizationResultCard with infeasible model disclosure', () => {
    const infeasibleResponse: OptimizeResponseData = {
      ...mockOptimizeResponse,
      solver_status: 'INFEASIBLE',
      verification_status: 'SKIPPED',
      scheduled_operations: [],
    };
    const markup = renderToStaticMarkup(<OptimizationResultCard result={infeasibleResponse} />);
    expect(markup).toContain('Model Proven Infeasible');
    expect(markup).toContain('SKIPPED');
  });

  it('renders RecentSchedulesCard with historical schedules list', () => {
    const summaries: ScheduleSummaryResponse[] = [
      {
        id: 'sched-1',
        workspace_id: 'ws-1',
        name: 'Morning Shift',
        objective_type: 'PURE_MAKESPAN',
        solver_status: 'OPTIMAL',
        verification_status: 'VERIFIED',
        makespan_minutes: 105,
        weighted_tardiness: 0,
        late_order_count: 0,
        on_time_rate: 100.0,
        created_at: '2026-10-17T09:00:00Z',
      },
    ];
    const markup = renderToStaticMarkup(
      <RecentSchedulesCard schedules={summaries} isLoading={false} onRefresh={async () => {}} onSelectSchedule={() => {}} />
    );
    expect(markup).toContain('Persisted Schedules History (1)');
    expect(markup).toContain('Morning Shift');
    expect(markup).toContain('OPTIMAL');
    expect(markup).toContain('VERIFIED');
  });

  it('renders ScheduleDetailCard with on-demand verifier button and operation details', () => {
    const markup = renderToStaticMarkup(
      <ScheduleDetailCard schedule={mockScheduleDetail} workspaceId="ws-1" onClose={() => {}} />
    );
    expect(markup).toContain('Schedule Details: Batch Schedule #1');
    expect(markup).toContain('Independent Clean-Room Verification');
    expect(markup).toContain('Re-verify Invariants');
    expect(markup).toContain('Allocated Operation Sequence (1 steps)');
    expect(markup).toContain('ORD-101');
    expect(markup).toContain('M1');
  });
});
