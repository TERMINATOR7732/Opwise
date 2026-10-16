import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';

export function ScenariosView(): React.ReactElement {
  const { navigate } = useRouter();

  return (
    <div>
      <PageHeader
        title="Scenario Branching & Disruption Lab"
        description="Simulate manufacturing disruptions: machine breakdowns, urgent rush orders, and delivery delays without mutating baseline schedules."
        badge={<Badge variant="neutral">Milestone 10 Implementation</Badge>}
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>
            ← Back to Overview
          </Button>
        }
      />

      <Card
        title="Disruption Simulation & Scenario Comparator"
        subtitle="Scheduled for Milestone 10 (Scenario Branching & Disruption Lab)"
      >
        <div style={{ maxWidth: '640px', color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
          <p style={{ marginBottom: '1rem' }}>
            This capability will provide what-if experimentation tools:
          </p>
          <ul style={{ paddingLeft: '1.25rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Immutable Baseline Protection:</strong> Branch child scenarios from locked baseline solutions. Baseline timestamps are never mutated.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Disruption Injection:</strong> Model sudden machine breakdowns, expedite urgent orders, or adjust processing durations.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Side-by-Side Comparator:</strong> Dual Gantt chart visualization with delta badges (<code className="font-mono">+45m Makespan</code>, <code className="font-mono">+2 Late Orders</code>) and unlike-comparison warning banners.
            </li>
          </ul>

          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
              Database schemas for <code className="font-mono">scenarios</code> and <code className="font-mono">comparisons</code> tables are created and migrated via Alembic in Milestone 07.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
