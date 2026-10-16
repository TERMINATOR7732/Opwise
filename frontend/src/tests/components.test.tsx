import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { PageHeader } from '../components/layout/PageHeader';
import { AppNav } from '../components/layout/AppNav';
import { RouterProvider } from '../router/RouterContext';
import { WorkspaceProvider } from '../context/WorkspaceContext';
import { OverviewView } from '../views/OverviewView';
import { NotFoundView } from '../views/NotFoundView';
import { FactoryView } from '../views/FactoryView';
import { PlanningView } from '../views/PlanningView';
import { SchedulesView } from '../views/SchedulesView';
import { ScenariosView } from '../views/ScenariosView';
import { App } from '../App';

describe('UI Primitives and Layout Components', () => {
  it('renders Badge with correct semantic class variant', () => {
    const markup = renderToStaticMarkup(<Badge variant="optimal">VERIFIED</Badge>);
    expect(markup).toContain('badge badge-optimal');
    expect(markup).toContain('VERIFIED');
  });

  it('renders Button with accessibility attributes and variant', () => {
    const normalBtn = renderToStaticMarkup(<Button variant="primary">Submit</Button>);
    expect(normalBtn).toContain('btn btn-primary');
    expect(normalBtn).toContain('Submit');

    const loadingBtn = renderToStaticMarkup(<Button variant="secondary" isLoading>Save</Button>);
    expect(loadingBtn).toContain('aria-busy="true"');
    expect(loadingBtn).toContain('disabled');
    expect(loadingBtn).toContain('Loading...');
  });

  it('renders Card with header, title, and body', () => {
    const markup = renderToStaticMarkup(
      <Card title="Machine 1" subtitle="Milling">
        <p>Operational</p>
      </Card>
    );
    expect(markup).toContain('card');
    expect(markup).toContain('Machine 1');
    expect(markup).toContain('Milling');
    expect(markup).toContain('Operational');
  });

  it('renders EmptyState with accessible action and copy', () => {
    const markup = renderToStaticMarkup(
      <EmptyState
        title="No Orders"
        description="Add jobs to schedule."
        action={<Button variant="primary">Create</Button>}
      />
    );
    expect(markup).toContain('No Orders');
    expect(markup).toContain('Add jobs to schedule.');
    expect(markup).toContain('Create');
  });

  it('renders LoadingState with role="status" and polite announcement', () => {
    const markup = renderToStaticMarkup(<LoadingState message="Fetching data..." />);
    expect(markup).toContain('role="status"');
    expect(markup).toContain('aria-live="polite"');
    expect(markup).toContain('Fetching data...');
  });

  it('renders ErrorBanner with role="alert" and structured validation issues', () => {
    const markup = renderToStaticMarkup(
      <ErrorBanner
        code="EMPTY_WORKSPACE"
        message="Cannot solve empty workspace"
        details={[{ field: 'machines', issue: 'At least 1 machine required' }]}
      />
    );
    expect(markup).toContain('role="alert"');
    expect(markup).toContain('[EMPTY_WORKSPACE]');
    expect(markup).toContain('Cannot solve empty workspace');
    expect(markup).toContain('machines');
    expect(markup).toContain('At least 1 machine required');
  });

  it('renders PageHeader with semantic header and title', () => {
    const markup = renderToStaticMarkup(
      <PageHeader
        title="Schedule Results"
        description="Interactive Gantt canvas"
        badge={<Badge variant="optimal">PROVEN</Badge>}
      />
    );
    expect(markup).toContain('<header');
    expect(markup).toContain('Schedule Results');
    expect(markup).toContain('Interactive Gantt canvas');
    expect(markup).toContain('PROVEN');
  });

  it('renders AppNav with aria-current="page" on active route and honest coming soon badges', () => {
    const markup = renderToStaticMarkup(
      <RouterProvider initialHash="#overview">
        <AppNav />
      </RouterProvider>
    );
    expect(markup).toContain('aria-label="Primary Navigation"');
    expect(markup).toContain('aria-current="page"');
    expect(markup).toContain('Overview');
    expect(markup).toContain('M09');
    expect(markup).toContain('M10');
  });

  it('renders NotFoundView for unknown routes', () => {
    const markup = renderToStaticMarkup(
      <RouterProvider initialHash="#invalid-route-xyz">
        <NotFoundView />
      </RouterProvider>
    );
    expect(markup).toContain('404 — Route Not Found');
    expect(markup).toContain('invalid-route-xyz');
  });

  it('renders views and Milestone 09/10 placeholders with honest disclosures', () => {
    const factoryMarkup = renderToStaticMarkup(
      <RouterProvider initialHash="#factory">
        <WorkspaceProvider>
          <FactoryView />
        </WorkspaceProvider>
      </RouterProvider>
    );
    expect(factoryMarkup).toContain('No Workspace Selected');

    const planningMarkup = renderToStaticMarkup(
      <RouterProvider initialHash="#planning">
        <PlanningView />
      </RouterProvider>
    );
    expect(planningMarkup).toContain('Optimization Planning Engine');
    expect(planningMarkup).toContain('Milestone 09 Implementation');

    const schedulesMarkup = renderToStaticMarkup(
      <RouterProvider initialHash="#schedules">
        <SchedulesView />
      </RouterProvider>
    );
    expect(schedulesMarkup).toContain('Production Schedules &amp; Gantt Canvas');
    expect(schedulesMarkup).toContain('Milestone 09 Implementation');

    const scenariosMarkup = renderToStaticMarkup(
      <RouterProvider initialHash="#scenarios">
        <ScenariosView />
      </RouterProvider>
    );
    expect(scenariosMarkup).toContain('Scenario Branching &amp; Disruption Lab');
    expect(scenariosMarkup).toContain('Milestone 10 Implementation');
  });

  it('renders full App shell and workflow overview without crashes', () => {
    // Mock global fetch for health check
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: { status: 'healthy', database: 'ok', version: '0.1.0' },
        metadata: { timestamp: '2026-10-16T12:00:00Z', requestId: 'req-1' },
      }),
    });

    // Test App default mount with EmptyState
    const appMarkup = renderToStaticMarkup(<App />);
    expect(appMarkup).toContain('OPWISE');
    expect(appMarkup).toContain('No Workspaces Configured');
    expect(appMarkup).toContain('Production Planning Overview');

    // Test OverviewView with active populated workspace
    const populatedMarkup = renderToStaticMarkup(
      <RouterProvider initialHash="#overview">
        <WorkspaceProvider
          initialWorkspaces={[
            {
              id: 'ws-1',
              name: 'Precision CNC Cell',
              description: 'Sample active shop',
              created_at: '2026-10-16T12:00:00Z',
              updated_at: '2026-10-16T12:00:00Z',
            },
          ]}
          initialActiveId="ws-1"
        >
          <OverviewView />
        </WorkspaceProvider>
      </RouterProvider>
    );
    expect(populatedMarkup).toContain('Precision CNC Cell');
    expect(populatedMarkup).toContain('Sample active shop');
    expect(populatedMarkup).toContain('Production Planning Workflow');
  });
});
