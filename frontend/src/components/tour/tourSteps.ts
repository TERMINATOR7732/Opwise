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
      'Opwise solves complex factory scheduling problems. In discrete manufacturing, multiple custom orders compete for shared machines with sequence rules and delivery deadlines. Opwise uses Google OR-Tools CP-SAT constraint programming to compute optimal, conflict-free production schedules in seconds.',
    route: 'overview',
    targetSelector: '[data-tour="overview-welcome"]',
    placement: 'bottom',
  },
  {
    id: 'factory',
    stepNumber: 2,
    title: 'Factory Resources & Routings',
    description:
      'Configure your physical shop floor: define machine workstations, scheduled maintenance downtime, and production orders with operation sequences, processing times, and customer delivery dates.',
    route: 'factory',
    targetSelector: '[data-tour="factory-tabs"]',
    placement: 'bottom',
  },
  {
    id: 'planning',
    stepNumber: 3,
    title: 'CP-SAT Discrete Optimization',
    description:
      'Turn factory capacity and constraints into exact mathematical models. Choose an optimization goal—such as minimizing total completion time (Makespan) or avoiding customer delays (Weighted Tardiness)—and solve with exact constraint programming.',
    route: 'planning',
    targetSelector: '[data-tour="planning-controls"]',
    placement: 'bottom',
  },
  {
    id: 'schedules',
    stepNumber: 4,
    title: 'Interactive Gantt Schedule',
    description:
      'Inspect the generated timeline canvas: view operation allocations across machine swimlanes, verify sequence ordering, ensure downtime windows are avoided, and identify production bottlenecks.',
    route: 'schedules',
    targetSelector: '[data-tour="gantt-chart"]',
    placement: 'bottom',
  },
  {
    id: 'execution',
    stepNumber: 5,
    title: 'Shop-Floor Execution Simulation',
    description:
      'Simulate live operations against the plan. Advance the plant clock, start jobs as machines become available, adjust remaining durations, and automatically reconcile schedule deviations.',
    route: 'factory',
    targetSelector: '[data-tour="plant-clock"]',
    placement: 'bottom',
  },
  {
    id: 'scenarios',
    stepNumber: 6,
    title: 'Disruption Lab & Recovery Scenarios',
    description:
      'Test how your schedule handles real-world surprises—like unexpected machine breakdowns or high-priority rush orders. Compare baseline schedules against recovery plans side by side.',
    route: 'scenarios',
    targetSelector: '[data-tour="scenarios-view"]',
    placement: 'bottom',
  },
  {
    id: 'reports',
    stepNumber: 7,
    title: 'Verification & Performance Analytics',
    description:
      'Every schedule is audited against 8 mathematical invariants to guarantee zero machine overlap or deadline violations. Review utilization rates, order delays, and export clean reports.',
    route: 'reports',
    targetSelector: '[data-tour="reports-summary"]',
    placement: 'bottom',
  },
  {
    id: 'finish',
    stepNumber: 8,
    title: "You're Ready to Plan",
    description:
      "You have seen the full discrete manufacturing workflow! Explore the pre-loaded demo workspace or configure your own factory floor. You can restart this tour anytime using the Guided Tour button in the header.",
    route: 'overview',
    targetSelector: '[data-tour="overview-welcome"]',
    placement: 'center',
  },
];
