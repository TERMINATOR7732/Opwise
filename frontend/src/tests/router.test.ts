import { describe, it, expect } from 'vitest';
import { parseRouteFromHash } from '../router/RouterContext';
import { APP_ROUTES } from '../router/types';

describe('Router & Route Definitions', () => {
  it('parses empty, slash, and overview hashes into overview route', () => {
    expect(parseRouteFromHash('')).toBe('overview');
    expect(parseRouteFromHash('#')).toBe('overview');
    expect(parseRouteFromHash('#/')).toBe('overview');
    expect(parseRouteFromHash('#overview')).toBe('overview');
    expect(parseRouteFromHash('#/overview')).toBe('overview');
    expect(parseRouteFromHash('#OVERVIEW')).toBe('overview');
  });

  it('parses valid secondary routes correctly', () => {
    expect(parseRouteFromHash('#factory')).toBe('factory');
    expect(parseRouteFromHash('#/factory')).toBe('factory');
    expect(parseRouteFromHash('#planning')).toBe('planning');
    expect(parseRouteFromHash('#schedules')).toBe('schedules');
    expect(parseRouteFromHash('#schedule')).toBe('schedules');
    expect(parseRouteFromHash('#scenarios')).toBe('scenarios');
    expect(parseRouteFromHash('#scenario')).toBe('scenarios');
    expect(parseRouteFromHash('#reports')).toBe('reports');
    expect(parseRouteFromHash('#report')).toBe('reports');
  });

  it('routes unknown hashes to not-found', () => {
    expect(parseRouteFromHash('#unknown-path')).toBe('not-found');
    expect(parseRouteFromHash('#/admin/secret')).toBe('not-found');
    expect(parseRouteFromHash('#404')).toBe('not-found');
  });

  it('maintains strict route metadata integrity', () => {
    expect(APP_ROUTES.overview.isAvailable).toBe(true);
    expect(APP_ROUTES.overview.hash).toBe('#overview');

    expect(APP_ROUTES.factory.isAvailable).toBe(false);
    expect(APP_ROUTES.factory.milestone).toBe('Milestone 09');
    expect(APP_ROUTES.factory.badge).toBe('M09');

    expect(APP_ROUTES.planning.isAvailable).toBe(false);
    expect(APP_ROUTES.planning.milestone).toBe('Milestone 09');

    expect(APP_ROUTES.schedules.isAvailable).toBe(false);
    expect(APP_ROUTES.schedules.milestone).toBe('Milestone 09');

    expect(APP_ROUTES.scenarios.isAvailable).toBe(false);
    expect(APP_ROUTES.scenarios.milestone).toBe('Milestone 10');
    expect(APP_ROUTES.scenarios.badge).toBe('M10');

    expect(APP_ROUTES.reports.isAvailable).toBe(false);
    expect(APP_ROUTES.reports.milestone).toBe('Milestone 11');
    expect(APP_ROUTES.reports.badge).toBe('M11');
  });
});
