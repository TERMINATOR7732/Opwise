import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';

export function SchedulesView(): React.ReactElement {
  const { navigate } = useRouter();

  return (
    <div>
      <PageHeader
        title="Production Schedules & Gantt Canvas"
        description="Interactive machine swimlanes, critical path tracking, independent verification audit reports, and production KPIs."
        badge={<Badge variant="warning">Milestone 09 Implementation</Badge>}
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>
            ← Back to Overview
          </Button>
        }
      />

      <Card
        title="Zero-Panel-Diving Schedule Canvas"
        subtitle="Scheduled for Milestone 09 (Factory Editor & Gantt Canvas)"
      >
        <div style={{ maxWidth: '640px', color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
          <p style={{ marginBottom: '1rem' }}>
            This capability will render the primary scheduling view:
          </p>
          <ul style={{ paddingLeft: '1.25rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>11 Direct Viewport Indicators:</strong> Solver status badge, active objective, makespan relative to t=0, total weighted tardiness, late order count, and net machine utilization.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Machine Swimlane Gantt:</strong> High-density SVG canvas showing scheduled operation intervals, slack minutes, and hatched planned downtime overlays.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Clean-Room Verifier Audit:</strong> Real-time 8-invariant validation badge with detailed audit breakdown of precedence, capacity, and downtime non-collision.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Bottleneck Callout:</strong> Mathematical bottleneck machine identification with workload and critical path segment logs.
            </li>
          </ul>

          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
              Backend schedule retrieval (<code className="font-mono">GET /schedules/:id</code>) and verification (<code className="font-mono">POST /schedules/:id/verify</code>) are verified in Milestone 07.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
