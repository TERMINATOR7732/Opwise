import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';

export function PlanningView(): React.ReactElement {
  const { navigate } = useRouter();

  return (
    <div>
      <PageHeader
        title="Optimization Planning Engine"
        description="Configure CP-SAT solver parameters, select optimization objectives, and trigger deterministic scheduling runs."
        badge={<Badge variant="warning">Milestone 09 Implementation</Badge>}
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>
            ← Back to Overview
          </Button>
        }
      />

      <Card
        title="Solver Configuration & Optimization Triggers"
        subtitle="Scheduled for Milestone 09 (Factory Editor & Gantt Canvas)"
      >
        <div style={{ maxWidth: '640px', color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
          <p style={{ marginBottom: '1rem' }}>
            This capability will provide execution controls for:
          </p>
          <ul style={{ paddingLeft: '1.25rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Objective Selection:</strong> Choose between <code className="font-mono">PURE_MAKESPAN</code>, <code className="font-mono">PURE_WEIGHTED_TARDINESS</code>, or <code className="font-mono">HIERARCHICAL_LEXICOGRAPHIC</code> modes.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Execution Budget:</strong> Configurable wall-clock budget (5s–60s) with deterministic time bounds and search worker thread count.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Solver Telemetry:</strong> Live stopwatch, termination reasons, search progress logging, and gap reporting.
            </li>
          </ul>

          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
              Backend REST API endpoint <code className="font-mono">POST /api/v1/workspaces/:id/optimize</code> with full CP-SAT solver integration is verified and operational.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
