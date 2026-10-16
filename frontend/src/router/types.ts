/**
 * Navigation and Routing Types
 * Governed by SPECIFICATION.md Section 8.1
 */

export type AppRoute = 'overview' | 'factory' | 'planning' | 'schedules' | 'scenarios' | 'not-found';

export interface RouteMeta {
  id: AppRoute;
  label: string;
  hash: string;
  description: string;
  isAvailable: boolean;
  milestone?: string;
  badge?: string;
}

export const APP_ROUTES: Record<Exclude<AppRoute, 'not-found'>, RouteMeta> = {
  overview: {
    id: 'overview',
    label: 'Overview',
    hash: '#overview',
    description: 'System state, workspace selector, and planning workflow overview',
    isAvailable: true,
  },
  factory: {
    id: 'factory',
    label: 'Factory',
    hash: '#factory',
    description: 'Shop floor setup: Machines, downtimes, and production orders',
    isAvailable: false,
    milestone: 'Milestone 09',
    badge: 'M09',
  },
  planning: {
    id: 'planning',
    label: 'Planning',
    hash: '#planning',
    description: 'CP-SAT optimization solver engine and parameter controls',
    isAvailable: false,
    milestone: 'Milestone 09',
    badge: 'M09',
  },
  schedules: {
    id: 'schedules',
    label: 'Schedules',
    hash: '#schedules',
    description: 'Interactive Gantt canvas, metrics, and clean-room verification',
    isAvailable: false,
    milestone: 'Milestone 09',
    badge: 'M09',
  },
  scenarios: {
    id: 'scenarios',
    label: 'Scenarios',
    hash: '#scenarios',
    description: 'Branching disruption lab and scenario comparison engine',
    isAvailable: false,
    milestone: 'Milestone 10',
    badge: 'M10',
  },
};
