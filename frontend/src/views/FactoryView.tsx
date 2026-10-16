import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';

export function FactoryView(): React.ReactElement {
  const { navigate } = useRouter();

  return (
    <div>
      <PageHeader
        title="Factory Management"
        description="Configure manufacturing shop floor assets: machines, planned maintenance downtime, and production order routings."
        badge={<Badge variant="warning">Milestone 09 Implementation</Badge>}
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>
            ← Back to Overview
          </Button>
        }
      />

      <Card
        title="Shop Floor Editor & Capacity Grid"
        subtitle="Scheduled for Milestone 09 (Factory Editor & Gantt Canvas)"
      >
        <div style={{ maxWidth: '640px', color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
          <p style={{ marginBottom: '1rem' }}>
            This capability will provide an interactive data grid for:
          </p>
          <ul style={{ paddingLeft: '1.25rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Machine Workstations:</strong> Add and configure machine capacity, unique tags, and operational descriptions.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Planned Maintenance Windows:</strong> Canonical downtime normalization with zero-length filtering and automatic adjacent interval merging.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Production Orders & Routings:</strong> Define release times, due dates, tardiness weights, and linear operation sequences.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Referential Integrity Auditing:</strong> Immediate client-side validation of machine IDs and non-empty operation sequences before solve submission.
            </li>
          </ul>

          <div style={{ padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
              Backend REST API endpoint <code className="font-mono">PUT /api/v1/workspaces/:id/factory</code> and data models are fully implemented and verified in Milestone 07.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
