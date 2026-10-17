/**
 * Unit & Component Tests for Reports, Analytics & Data Export (Milestone 11)
 * Governed by SPECIFICATION.md Section 8.1 View 5, Section 8.4 State 14, and DATA_AND_API.md Section 4.
 */

import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ReportSummaryCard } from '../views/reports/ReportSummaryCard';
import { BottleneckCard } from '../views/reports/BottleneckCard';
import { MachineUtilizationTable } from '../views/reports/MachineUtilizationTable';
import { OrderPerformanceTable } from '../views/reports/OrderPerformanceTable';
import { ExportActionButtons } from '../views/reports/ExportActionButtons';
import { ScheduleExplanationsCard } from '../views/reports/ScheduleExplanationsCard';
import { EmptyState } from '../components/common/EmptyState';
import { Button } from '../components/common/Button';
import { RouterProvider } from '../router/RouterContext';
import { WorkspaceProvider } from '../context/WorkspaceContext';
import { ReportsView } from '../views/ReportsView';
import {
  BottleneckReportItem,
  MachineUtilizationItem,
  OrderPerformanceItem,
  ScheduleExplanationItem,
  SummaryKPIs,
  VerificationAuditSummary,
} from '../types/reports';

const mockSummary: SummaryKPIs = {
  makespan_minutes: 120,
  total_weighted_tardiness: 45,
  late_order_count: 1,
  on_time_order_count: 3,
  total_order_count: 4,
  on_time_rate_pct: 75.0,
  solver_wall_clock_seconds: 1.25,
  solver_deterministic_time: 0.045,
};

const mockAudit: VerificationAuditSummary = {
  is_valid: true,
  checks_run: 8,
  checks_passed: 8,
  violations: [],
};

const mockBottleneck: BottleneckReportItem = {
  primary_bottleneck_machine_id: 'M1',
  primary_bottleneck_machine_name: 'CNC Milling Center 1',
  highest_workload_minutes: 95,
  highest_net_utilization_pct: 95.0,
  ranked_machines: ['M1', 'M2', 'M3'],
  disclaimer:
    'Note: High machine utilization indicates high capacity demand, but does not alone prove that this machine throttled overall throughput.',
};

const mockMachines: MachineUtilizationItem[] = [
  {
    machine_id: 'M1',
    machine_name: 'CNC Milling Center 1',
    workload_minutes: 95,
    downtime_minutes: 20,
    idle_minutes: 5,
    available_capacity_minutes: 100,
    net_utilization_pct: 95.0,
    gross_utilization_pct: 79.17,
    assigned_operation_count: 6,
    is_oversubscribed: false,
  },
  {
    machine_id: 'M2',
    machine_name: 'Lathe Turning Station',
    workload_minutes: 50,
    downtime_minutes: 0,
    idle_minutes: 70,
    available_capacity_minutes: 120,
    net_utilization_pct: 41.67,
    gross_utilization_pct: 41.67,
    assigned_operation_count: 4,
    is_oversubscribed: false,
  },
];

const mockOrders: OrderPerformanceItem[] = [
  {
    order_id: 'ORD-101',
    order_code: 'ORD-101',
    release_minute: 0,
    due_date_minute: 100,
    completion_minute: 90,
    tardiness_minutes: 0,
    tardiness_weight: 5,
    weighted_tardiness: 0,
    slack_minutes: 10,
    is_late: false,
    is_on_time: true,
    operation_count: 2,
    total_processing_minutes: 45,
  },
  {
    order_id: 'ORD-102',
    order_code: 'ORD-102',
    release_minute: 10,
    due_date_minute: 80,
    completion_minute: 110,
    tardiness_minutes: 30,
    tardiness_weight: 2,
    weighted_tardiness: 60,
    slack_minutes: 0,
    is_late: true,
    is_on_time: false,
    operation_count: 2,
    total_processing_minutes: 55,
  },
];

const mockExplanations: ScheduleExplanationItem[] = [
  {
    category: 'MAKESPAN',
    entity_type: 'Schedule',
    entity_id: 'SCHED-01',
    summary: 'Makespan determined by final operation completion',
    measured_value: '120m',
    threshold_or_target: null,
    mathematical_formula: 'Cmax = max(C_j,last) - 0',
    reason: 'Final operation completed at minute 120 relative to schedule origin.',
  },
];

describe('Milestone 11: Reports & Analytics View Components', () => {
  it('renders EmptyState with mandated State 14 copy when no schedule exists', () => {
    const markup = renderToStaticMarkup(
      <EmptyState
        title="No Schedule Generated"
        description="No schedule generated yet. Solve a scenario to generate analytics."
        action={<Button variant="primary">Go to Planning</Button>}
      />
    );

    expect(markup).toContain('No Schedule Generated');
    expect(markup).toContain('No schedule generated yet. Solve a scenario to generate analytics.');
    expect(markup).toContain('Go to Planning');
  });

  it('renders ReportSummaryCard with all KPIs and verification status', () => {
    const markup = renderToStaticMarkup(
      <ReportSummaryCard
        scheduleName="Production Plan #1"
        solverStatus="OPTIMAL"
        verificationStatus="VERIFIED"
        objectiveType="HIERARCHICAL"
        summary={mockSummary}
        audit={mockAudit}
      />
    );

    expect(markup).toContain('Production Plan #1');
    expect(markup).toContain('OPTIMAL');
    expect(markup).toContain('VERIFIED: 8/8 PASS');
    expect(markup).toContain('120m');
    expect(markup).toContain('45');
    expect(markup).toContain('75.0%');
    expect(markup).toContain('1.250s');
  });

  it('renders BottleneckCard with diagnosis, load ranking, and disclaimer', () => {
    const markup = renderToStaticMarkup(<BottleneckCard bottleneck={mockBottleneck} />);

    expect(markup).toContain('Primary Bottleneck Diagnosis');
    expect(markup).toContain('CNC Milling Center 1');
    expect(markup).toContain('95 min');
    expect(markup).toContain('95.00%');
    expect(markup).toContain('M1');
    expect(markup).toContain('M2');
    expect(markup).toContain('M3');
    expect(markup).toContain('Note: High machine utilization indicates high capacity demand');
  });

  it('renders MachineUtilizationTable with true Wm / (Cmax - Dm) calculations', () => {
    const markup = renderToStaticMarkup(<MachineUtilizationTable machines={mockMachines} />);

    expect(markup).toContain('Machine Capacity &amp; Utilization Audit');
    expect(markup).toContain('CNC Milling Center 1');
    expect(markup).toContain('Lathe Turning Station');
    expect(markup).toContain('95.0%');
    expect(markup).toContain('41.7%');
    expect(markup).toContain('20m');
    expect(markup).toContain('5m');
  });

  it('renders OrderPerformanceTable with tardiness, slack, and delivery status badges', () => {
    const markup = renderToStaticMarkup(<OrderPerformanceTable orders={mockOrders} />);

    expect(markup).toContain('Production Order Due Date &amp; Tardiness Audit');
    expect(markup).toContain('ORD-101');
    expect(markup).toContain('ORD-102');
    expect(markup).toContain('ON TIME');
    expect(markup).toContain('LATE');
    expect(markup).toContain('+30m');
    expect(markup).toContain('10m');
    expect(markup).toContain('w=5');
    expect(markup).toContain('w=2');
  });

  it('renders ScheduleExplanationsCard with mathematical formulas', () => {
    const markup = renderToStaticMarkup(<ScheduleExplanationsCard explanations={mockExplanations} />);

    expect(markup).toContain('Deterministic Mathematical Explanations');
    expect(markup).toContain('Makespan determined by final operation completion');
    expect(markup).toContain('Cmax = max(C_j,last) - 0');
    expect(markup).toContain('Final operation completed at minute 120 relative to schedule origin.');
  });

  it('renders ExportActionButtons with sanitized CSV and JSON export labels', () => {
    const markup = renderToStaticMarkup(
      <ExportActionButtons workspaceId="WS-101" scheduleId="SCHED-01" />
    );

    expect(markup).toContain('CSV');
    expect(markup).toContain('Export (Sanitized)');
    expect(markup).toContain('JSON');
    expect(markup).toContain('Export (Full Audit)');
  });

  it('renders ReportsView inside Router and Workspace providers', () => {
    const mockWs = [
      { id: 'ws-1', name: 'Production Factory', description: '', created_at: '', updated_at: '' },
    ];
    const markup = renderToStaticMarkup(
      <RouterProvider initialHash="#reports">
        <WorkspaceProvider initialWorkspaces={mockWs} initialActiveId="ws-1">
          <ReportsView />
        </WorkspaceProvider>
      </RouterProvider>
    );

    expect(markup).toContain('Reports &amp; Analytics');
    expect(markup).toContain('No Schedule Generated');
    expect(markup).toContain('No schedule generated yet. Solve a scenario to generate analytics.');
  });
});
