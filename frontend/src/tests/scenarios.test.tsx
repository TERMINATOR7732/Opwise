/**
 * Unit & Component Tests for Scenario Lab, Disruption Simulation & Comparator
 * Governed by TEST_AND_RELEASE_PLAN.md and SPECIFICATION.md Section 6.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ScenarioDetailCard } from '../views/scenarios/ScenarioDetailCard';
import { ScenarioComparisonCard } from '../views/scenarios/ScenarioComparisonCard';
import { DualGanttComparison } from '../views/scenarios/DualGanttComparison';
import { CreateScenarioModal } from '../views/scenarios/CreateScenarioModal';
import { ScenarioResponse, ScenarioComparisonResponse } from '../types/scenarios';
import { ScheduleDetailResponse } from '../types/api';

describe('Scenario Lab & Disruption Components', () => {
  const mockScenario: ScenarioResponse = {
    id: 'scen-101',
    workspace_id: 'ws-1',
    baseline_schedule_id: 'sched-base-1',
    reoptimized_schedule_id: 'sched-rec-1',
    name: 'M1 Outage Simulation',
    description: 'Testing 30m lathe outage',
    disruption_type: 'COMBINED',
    disruption_delta: {
      added_downtimes: [
        { machine_id: 'M1', start_minute: 10, end_minute: 40, reason: 'Bearing failure' },
      ],
      added_orders: [
        {
          order_code: 'RUSH-999',
          release_time_minutes: 0,
          due_date_minutes: 80,
          tardiness_weight: 10,
          operations: [{ sequence_index: 1, machine_id: 'M1', processing_minutes: 20 }],
        },
      ],
    },
    created_at: '2026-10-17T12:00:00Z',
  };

  const mockComparison: ScenarioComparisonResponse = {
    id: 'comp-101',
    scenario_id: 'scen-101',
    baseline_schedule_id: 'sched-base-1',
    compared_schedule_id: 'sched-rec-1',
    delta_makespan: 30,
    delta_weighted_tardiness: 50,
    delta_late_order_count: 1,
    delta_on_time_rate: -20.0,
    objective_diff_detected: false,
    order_set_diff_detected: true,
    status_diff_detected: false,
    time_limit_diff_detected: false,
    unlike_comparison_warning:
      'Baseline and Scenario differ in objective mode, order set, solver status, or time limit. Metric deltas reflect the compound effect of structural changes and must not be interpreted as pure delay on baseline orders.',
    diverged_operations: [
      {
        order_id: 'ORD-1',
        sequence_index: 1,
        machine_id: 'M1',
        baseline_start: 0,
        baseline_end: 25,
        compared_start: 40,
        compared_end: 65,
        delta_start_minutes: 40,
        status: 'DELAYED',
      },
      {
        order_id: 'RUSH-999',
        sequence_index: 1,
        machine_id: 'M1',
        baseline_start: null,
        baseline_end: null,
        compared_start: 0,
        compared_end: 20,
        delta_start_minutes: null,
        status: 'NEW_RUSH_OPERATION',
      },
    ],
    created_at: '2026-10-17T12:05:00Z',
  };

  const mockBaselineSchedule: ScheduleDetailResponse = {
    id: 'sched-base-1',
    workspace_id: 'ws-1',
    name: 'Baseline Plan',
    objective_type: 'PURE_MAKESPAN',
    solver_status: 'OPTIMAL',
    verification_status: 'VERIFIED',
    metrics: {
      makespan_minutes: 100,
      weighted_tardiness: 0,
      late_order_count: 0,
      on_time_rate: 100.0,
    },
    scheduled_operations: [
      {
        operation_id: 'op-1',
        order_id: 'ORD-1',
        sequence_index: 1,
        machine_id: 'M1',
        start_minute: 0,
        end_minute: 25,
        duration: 25,
        slack_minutes: 0,
      },
    ],
    machines: [{ id: 'M1', name: 'CNC Mill' }],
    downtimes: [],
    created_at: '2026-10-17T11:00:00Z',
  };

  const mockRecoverySchedule: ScheduleDetailResponse = {
    id: 'sched-rec-1',
    workspace_id: 'ws-1',
    name: 'Recovery Plan',
    objective_type: 'PURE_MAKESPAN',
    solver_status: 'OPTIMAL',
    verification_status: 'VERIFIED',
    metrics: {
      makespan_minutes: 130,
      weighted_tardiness: 50,
      late_order_count: 1,
      on_time_rate: 80.0,
    },
    scheduled_operations: [
      {
        operation_id: 'op-1',
        order_id: 'ORD-1',
        sequence_index: 1,
        machine_id: 'M1',
        start_minute: 40,
        end_minute: 65,
        duration: 25,
        slack_minutes: 0,
      },
      {
        operation_id: 'op-rush-1',
        order_id: 'RUSH-999',
        sequence_index: 1,
        machine_id: 'M1',
        start_minute: 0,
        end_minute: 20,
        duration: 20,
        slack_minutes: 0,
      },
    ],
    machines: [{ id: 'M1', name: 'CNC Mill' }],
    downtimes: [{ id: 'dt-1', machine_id: 'M1', start_minute: 10, end_minute: 40, reason: 'Outage' }],
    created_at: '2026-10-17T12:05:00Z',
  };

  it('renders ScenarioDetailCard with disruption breakdowns and reoptimize trigger', () => {
    const markup = renderToStaticMarkup(
      <ScenarioDetailCard
        scenario={mockScenario}
        baselineName="Baseline Plan"
        isReoptimizing={false}
        onReoptimize={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(markup).toContain('M1 Outage Simulation');
    expect(markup).toContain('Bearing failure');
    expect(markup).toContain('RUSH-999');
    expect(markup).toContain('COMBINED');
    expect(markup).toContain('REOPTIMIZED (READY)');
  });

  it('renders ScenarioComparisonCard with deltas, unlike disclosure warning, and divergence rows', () => {
    const markup = renderToStaticMarkup(<ScenarioComparisonCard comparison={mockComparison} />);
    expect(markup).toContain('+30m');
    expect(markup).toContain('+50 pts');
    expect(markup).toContain('+1');
    expect(markup).toContain('-20%');
    expect(markup).toContain('Unlike-Results Disclosure');
    expect(markup).toContain('STRUCTURAL ORDER SET CHANGE');
    expect(markup).toContain('DELAYED');
    expect(markup).toContain('RUSH OP');
  });

  it('renders DualGanttComparison in stacked mode without crashing', () => {
    const markup = renderToStaticMarkup(
      <DualGanttComparison
        baselineSchedule={mockBaselineSchedule}
        recoverySchedule={mockRecoverySchedule}
      />
    );
    expect(markup).toContain('Interactive Dual Schedule Comparator');
    expect(markup).toContain('Baseline Schedule: Baseline Plan');
    expect(markup).toContain('Recovery Schedule: Recovery Plan');
    expect(markup).toContain('Stacked Dual View');
  });

  it('renders CreateScenarioModal form elements when open', () => {
    const markup = renderToStaticMarkup(
      <CreateScenarioModal
        isOpen={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        schedules={[{ id: 's1', workspace_id: 'ws1', name: 'S1', objective_type: 'PURE_MAKESPAN', solver_status: 'OPTIMAL', verification_status: 'VERIFIED', makespan_minutes: 100, weighted_tardiness: 0, late_order_count: 0, on_time_rate: 100, created_at: '' }]}
        machines={[{ id: 'M1', external_id: 'M1', name: 'M1', created_at: '' }]}
      />
    );
    expect(markup).toContain('Branch Disruption Scenario');
    expect(markup).toContain('Scenario Name *');
    expect(markup).toContain('Disruption Type');
    expect(markup).toContain('Injected Machine Downtimes');
  });
});
