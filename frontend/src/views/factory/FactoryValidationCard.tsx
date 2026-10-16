/**
 * Structural Dry-Run Validation Card
 * Governed by DATA_AND_API.md Section 3.2 (POST /factory/validate)
 */

import React from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { FactoryValidationResponse } from '../../types/api';

export interface FactoryValidationCardProps {
  validationResult: FactoryValidationResponse | null;
  isValidating: boolean;
  onValidate: () => Promise<void>;
  machineCount: number;
  orderCount: number;
}

function getBadgeVariant(classification: string, isValid: boolean): 'critical' | 'warning' | 'optimal' {
  if (!isValid) return 'critical';
  if (classification === 'NO_WORK_STATE') return 'warning';
  return 'optimal';
}

function ValidationSummaryTiles({ machineCount, orderCount, res }: {
  machineCount: number; orderCount: number; res: FactoryValidationResponse | null;
}): React.ReactElement {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
      <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Configured Stations</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{machineCount}</strong>
      </div>
      <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Configured Orders</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{orderCount}</strong>
      </div>
      <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Validation Classification</span>
        <div style={{ marginTop: '0.25rem' }}>
          {res ? <Badge variant={getBadgeVariant(res.classification, res.is_valid)}>{res.classification}</Badge> : <Badge variant="neutral">NOT AUDITED</Badge>}
        </div>
      </div>
    </div>
  );
}

function ValidationIssueAlert({ res }: { res: FactoryValidationResponse }): React.ReactElement {
  const isOk = res.is_valid;
  return (
    <div style={{ padding: '1rem', borderRadius: 'var(--radius-md)', backgroundColor: isOk ? 'var(--color-optimal-bg)' : 'var(--color-critical-bg)', border: `1px solid ${isOk ? 'var(--color-optimal-border)' : 'var(--color-critical-border)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: res.issues.length > 0 ? '0.5rem' : 0 }}>
        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: isOk ? 'var(--color-optimal)' : 'var(--color-critical)', display: 'inline-block' }} />
        <strong style={{ color: isOk ? 'var(--color-optimal)' : 'var(--color-critical)' }}>
          {isOk ? 'Factory Ready for CP-SAT Solver Execution' : 'Factory Configuration Has Invariant Violations'}
        </strong>
      </div>
      {res.issues.length > 0 && (
        <ul style={{ paddingLeft: '1.25rem', color: 'var(--text-primary)', fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {res.issues.map((issue, idx) => (<li key={idx}>{issue}</li>))}
        </ul>
      )}
    </div>
  );
}

export function FactoryValidationCard({
  validationResult, isValidating, onValidate, machineCount, orderCount,
}: FactoryValidationCardProps): React.ReactElement {
  return (
    <Card
      title="CP-SAT Pre-Optimization Validation Audit"
      subtitle="Runs non-persisting dry-run structural validation across all machines, downtimes, and order operations."
      actions={<Button variant="secondary" size="sm" onClick={onValidate} isLoading={isValidating}>{validationResult ? 'Re-run Validation' : 'Run Validation Audit'}</Button>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.875rem' }}>
        <ValidationSummaryTiles machineCount={machineCount} orderCount={orderCount} res={validationResult} />
        {validationResult && <ValidationIssueAlert res={validationResult} />}
      </div>
    </Card>
  );
}
