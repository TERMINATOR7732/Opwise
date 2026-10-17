/**
 * Detailed Schedule Inspector & On-Demand Verification Card
 * Governed by DATA_AND_API.md Section 3.2 and Section 3.3.
 */

import React, { useState } from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { apiEndpoints } from '../../api/endpoints';
import { ScheduleDetailResponse, VerificationReportResponse } from '../../types/api';

export interface ScheduleDetailCardProps {
  schedule: ScheduleDetailResponse;
  workspaceId: string;
  onClose: () => void;
}

function ScheduleMetricsTiles({ s }: { s: ScheduleDetailResponse }): React.ReactElement {
  const m = s.metrics;
  const t = s.solver_telemetry;
  const gapStr = (m.optimality_gap === 0 || (m.optimality_gap === null && s.solver_status === 'OPTIMAL'))
    ? '0.0% (Exact)'
    : m.optimality_gap !== null && m.optimality_gap !== undefined
    ? `${(m.optimality_gap * 100).toFixed(1)}%`
    : '—';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.5rem' }}>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Makespan (C_max)</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{m.makespan_minutes}m</strong>
      </div>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Weighted Tardiness</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: m.weighted_tardiness > 0 ? 'var(--color-warning)' : 'var(--text-primary)' }}>{m.weighted_tardiness}</strong>
      </div>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>On-Time Delivery</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: m.on_time_rate === 100 ? 'var(--color-optimal)' : 'var(--color-warning)' }}>{m.on_time_rate.toFixed(1)}%</strong>
      </div>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Late Orders</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: m.late_order_count > 0 ? 'var(--color-critical)' : 'var(--text-primary)' }}>{m.late_order_count}</strong>
      </div>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Optimality Gap</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{gapStr}</strong>
      </div>
      <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Solve Duration</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{t ? `${t.wall_clock_time_seconds.toFixed(2)}s` : '—'}</strong>
      </div>
    </div>
  );
}

function OnDemandVerifier({
  workspaceId, scheduleId, initialStatus,
}: {
  workspaceId: string; scheduleId: string; initialStatus: string;
}): React.ReactElement {
  const [report, setReport] = useState<VerificationReportResponse | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    setIsVerifying(true);
    setError(null);
    try {
      setReport(await apiEndpoints.verifySchedule(workspaceId, scheduleId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setIsVerifying(false);
    }
  };

  const isVerified = report ? report.is_valid : initialStatus === 'VERIFIED';
  return (
    <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
        <div>
          <strong style={{ fontSize: '0.8125rem', color: 'var(--text-primary)' }}>Independent Clean-Room Verification</strong>
          <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {report ? `${report.checks_passed} of ${report.checks_run} invariant checks passed.` : `Current verification status: ${initialStatus}`}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <Badge variant={isVerified ? 'optimal' : 'critical'} className="font-mono">{isVerified ? 'VERIFIED' : 'FAILED'}</Badge>
          <Button variant="secondary" size="sm" onClick={handleVerify} isLoading={isVerifying}>Re-verify Invariants</Button>
        </div>
      </div>
      {error && <p style={{ color: 'var(--color-critical)', fontSize: '0.75rem', margin: '0.25rem 0' }}>{error}</p>}
      {report && report.violations.length > 0 && (
        <ul style={{ marginTop: '0.35rem', paddingLeft: '1.25rem', color: 'var(--color-critical)', fontSize: '0.75rem' }}>
          {report.violations.map((v, i) => (<li key={i}>{v}</li>))}
        </ul>
      )}
    </div>
  );
}

function ScheduleOpsTable({ s }: { s: ScheduleDetailResponse }): React.ReactElement {
  if (s.scheduled_operations.length === 0) {
    return <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>No operations scheduled.</div>;
  }
  return (
    <div style={{ overflowX: 'auto', maxHeight: '280px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
            <th style={{ padding: '0.5rem 0.625rem' }}>Order</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Step</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Machine</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Window [Start, End)</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Duration</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Slack</th>
          </tr>
        </thead>
        <tbody>
          {s.scheduled_operations.map((op, i) => (
            <tr key={op.operation_id || i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <td style={{ padding: '0.5rem 0.625rem', fontWeight: 600 }} className="font-mono">{op.order_id}</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">#{op.sequence_index}</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">{op.machine_id}</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">[{op.start_minute}, {op.end_minute})</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">{op.duration}m</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">{op.slack_minutes}m</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ScheduleDetailCard({ schedule, workspaceId, onClose }: ScheduleDetailCardProps): React.ReactElement {
  return (
    <Card
      title={`Schedule Details: ${schedule.name}`}
      subtitle={`ID: ${schedule.id} | Mode: ${schedule.objective_type} | Generated: ${new Date(schedule.created_at).toLocaleString()}`}
      actions={<Button variant="secondary" size="sm" onClick={onClose}>Close Details</Button>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
        <ScheduleMetricsTiles s={schedule} />
        <OnDemandVerifier workspaceId={workspaceId} scheduleId={schedule.id} initialStatus={schedule.verification_status} />
        <div>
          <strong style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', display: 'block', marginBottom: '0.35rem' }}>
            Allocated Operation Sequence ({schedule.scheduled_operations.length} steps)
          </strong>
          <ScheduleOpsTable s={schedule} />
        </div>
      </div>
    </Card>
  );
}
