/**
 * Factory Readiness & Pre-Solve Audit Summary Card
 * Governed by DATA_AND_API.md Section 3.2 and Section 3.3.
 */

import React from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { FactoryConfigResponse, FactoryValidationResponse } from '../../types/api';

export interface FactoryReadinessCardProps {
  factory: FactoryConfigResponse | null;
  validationResult: FactoryValidationResponse | null;
  isValidating: boolean;
  onValidate: () => Promise<void>;
  onNavigateToFactory: () => void;
}

function StatTile({ label, value }: { label: string; value: number | string }): React.ReactElement {
  return (
    <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>{label}</span>
      <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{value}</strong>
    </div>
  );
}

function ReadinessStatusBadge({
  machineCount, orderCount, val,
}: {
  machineCount: number; orderCount: number; val: FactoryValidationResponse | null;
}): React.ReactElement {
  if (machineCount === 0) return <Badge variant="critical">NO MACHINES</Badge>;
  if (orderCount === 0) return <Badge variant="warning">NO ORDERS</Badge>;
  if (!val) return <Badge variant="neutral">NOT AUDITED</Badge>;
  if (!val.is_valid) return <Badge variant="critical">INVALID INPUTS</Badge>;
  return <Badge variant="optimal">READY TO SOLVE</Badge>;
}

function IssuesAlert({ issues }: { issues: string[] }): React.ReactElement {
  return (
    <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--color-critical-bg)', border: '1px solid var(--color-critical-border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-critical)', display: 'inline-block' }} />
        <strong style={{ color: 'var(--color-critical)', fontSize: '0.8125rem' }}>Configuration Invariant Violations</strong>
      </div>
      <ul style={{ paddingLeft: '1.25rem', color: 'var(--text-primary)', fontSize: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        {issues.map((msg, i) => (<li key={i}>{msg}</li>))}
      </ul>
    </div>
  );
}

function ReadinessGuidance({
  machineCount, orderCount, onNavigate,
}: {
  machineCount: number; orderCount: number; onNavigate: () => void;
}): React.ReactElement | null {
  if (machineCount > 0 && orderCount > 0) return null;
  const reason = machineCount === 0 ? 'Machine workstations' : 'Production orders';
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
        {reason} are required before CP-SAT optimization can schedule workloads.
      </span>
      <Button variant="secondary" size="sm" onClick={onNavigate}>
        Configure Factory →
      </Button>
    </div>
  );
}

export function FactoryReadinessCard({
  factory, validationResult, isValidating, onValidate, onNavigateToFactory,
}: FactoryReadinessCardProps): React.ReactElement {
  const machines = factory?.machines.length || 0;
  const orders = factory?.orders.length || 0;
  const operations = factory?.orders.reduce((sum, o) => sum + o.operations.length, 0) || 0;
  const downtimes = factory?.downtimes.length || 0;

  return (
    <Card
      title="Shop Floor Readiness Audit"
      subtitle="Evaluates workstations, operations, and maintenance windows before solver dispatch."
      actions={<Button variant="secondary" size="sm" onClick={onValidate} isLoading={isValidating} disabled={!factory}>Run Pre-Solve Audit</Button>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.5rem' }}>
          <StatTile label="Machines" value={machines} />
          <StatTile label="Downtimes" value={downtimes} />
          <StatTile label="Orders" value={orders} />
          <StatTile label="Operations" value={operations} />
          <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Readiness</span>
            <div style={{ marginTop: '0.25rem' }}><ReadinessStatusBadge machineCount={machines} orderCount={orders} val={validationResult} /></div>
          </div>
        </div>
        {validationResult && !validationResult.is_valid && validationResult.issues.length > 0 && (
          <IssuesAlert issues={validationResult.issues} />
        )}
        <ReadinessGuidance machineCount={machines} orderCount={orders} onNavigate={onNavigateToFactory} />
      </div>
    </Card>
  );
}
