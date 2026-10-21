/**
 * Opwise Guided Product Tour Steps Definition
 * Governed by SPECIFICATION.md and UI Refinement Requirements Section 4.3.
 */

import { AppRoute } from '../../router/types';

export interface TourStep {
  id: string;
  stepNumber: number;
  title: string;
  description: string;
  route: AppRoute;
  targetSelector: string;
  placement?: 'bottom' | 'top' | 'left' | 'right' | 'center';
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome',
    stepNumber: 1,
    title: 'Welcome to Opwise',
    description:
      'Opwise is a local-first production planning and operations intelligence workbench for discrete manufacturing. Configure resources, optimize production schedules with Google OR-Tools CP-SAT, and evaluate disruption recovery in real time.',
    route: 'overview',
    targetSelector: '[data-tour="overview-welcome"]',
    placement: 'bottom',
  },
  {
    id: 'factory',
    stepNumber: 2,
    title: 'Factory Configuration & Routings',
    description:
      'Model physical manufacturing capacity: machine workstations, planned maintenance downtime intervals, and multi-step production orders with deterministic processing durations, precedence constraints, and release/due dates.',
    route: 'factory',
    targetSelector: '[data-tour="factory-tabs"]',
    placement: 'bottom',
  },
  {
    id: 'planning',
    stepNumber: 3,
    title: 'CP-SAT Discrete Optimization',
    description:
      'Translate shop-floor resources and job sequences into exact constraint programming models. Select optimization objectives (Makespan, Total Weighted Tardiness, or Lexicographic multi-objective) and configure solver time limits.',
    route: 'planning',
    targetSelector: '[data-tour="planning-controls"]',
    placement: 'bottom',
  },
  {
    id: 'schedules',
    stepNumber: 4,
    title: 'Schedule Timeline & Interactive Gantt',
    description:
      'Inspect the generated schedule canvas: operation allocations across machine swimlanes, sequence precedence, downtime collision avoidance, makespan, tardiness penalties, and automated bottleneck diagnostics.',
    route: 'schedules',
    targetSelector: '[data-tour="gantt-chart"]',
    placement: 'bottom',
  },
  {
    id: 'execution',
    stepNumber: 5,
    title: 'Shop-Floor Execution Simulation',
    description:
      'Simulate actual shop-floor execution using the discrete Plant Clock (t₀). Start operations when machines are available, advance operational time, adjust remaining work, and reconcile overdue operations with Policy B safety gates.',
    route: 'factory',
    targetSelector: '[data-tour="plant-clock"]',
    placement: 'bottom',
  },
  {
    id: 'scenarios',
    stepNumber: 6,
    title: 'Disruption Lab & Recovery Scenarios',
    description:
      'Simulate unexpected manufacturing disruptions—such as machine breakdowns or urgent rush orders. Re-optimize the schedule and compare dual-Gantt diffs side by side against the baseline to evaluate recovery feasibility.',
    route: 'scenarios',
    targetSelector: '[data-tour="scenarios-view"]',
    placement: 'bottom',
  },
  {
    id: 'reports',
    stepNumber: 7,
    title: 'Analytical Reports & Clean-Room Verification',
    description:
      'Audit production plans against 8 independent clean-room mathematical invariants (zero overlapping operations, downtime exclusion, precedence satisfaction). Review machine utilization, order delays, and delivery slack.',
    route: 'reports',
    targetSelector: '[data-tour="reports-summary"]',
    placement: 'bottom',
  },
  {
    id: 'finish',
    stepNumber: 8,
    title: "You're Ready to Plan",
    description:
      "You have explored the end-to-end Opwise planning lifecycle! You can now explore the pre-solved demo scenarios or configure your own factory. You can restart this tour at any time from the 'Guided Tour' button in the header.",
    route: 'overview',
    targetSelector: '[data-tour="overview-welcome"]',
    placement: 'center',
  },
];
