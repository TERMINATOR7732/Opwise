/**
 * Optimization Results, KPIs, Telemetry & Verification Card
 * Governed by DATA_AND_API.md Section 3.3 and SPECIFICATION.md Section 4.
 */

import React, { useState } from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { OptimizeResponseData, ScheduledOperationResponse, StageTelemetryResponse } from '../../types/api';
import { GanttChart } from '../schedules/gantt/GanttChart';


export interface OptimizationResultCardProps {
  result: OptimizeResponseData;
  onViewSchedules?: () => void;
}

function StatusBanner({ status }: { status: string }): React.ReactElement {
  let variant: 'optimal' | 'warning' | 'critical' | 'neutral' = 'neutral';
  let title = `Solver Status: ${status}`;
  let desc = '';

  if (status === 'OPTIMAL') {
    variant = 'optimal';
    title = 'CP-SAT Proven Optimum Found';
    desc = 'The solver mathematically verified that no better schedule exists within the constraint boundaries.';
  } else if (status === 'FEASIBLE') {
    variant = 'warning';
    title = 'Feasible Schedule Found (Optimality Not Proven)';
    desc = 'A valid production schedule satisfying all operational constraints was found before the time budget expired.';
  } else if (status === 'INFEASIBLE') {
    variant = 'critical';
    title = 'Model Proven Infeasible';
    desc = 'The current combination of order due dates, processing durations, and downtime windows cannot be scheduled.';
  } else if (status === 'NO_WORK_STATE') {
    variant = 'warning';
    title = 'No Work to Schedule';
    desc = 'The factory workstations are configured but no production orders exist in the workspace.';
  }

  return (
    <div style={{ padding: '0.875rem 1rem', borderRadius: 'var(--radius-sm)', backgroundColor: `var(--color-${variant}-bg)`, border: `1px solid var(--color-${variant}-border)` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: desc ? '0.25rem' : 0 }}>
        <strong style={{ color: `var(--color-${variant})`, fontSize: '0.9375rem' }}>{title}</strong>
        <Badge variant={variant} className="font-mono">{status}</Badge>
      </div>
      {desc && <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', margin: 0 }}>{desc}</p>}
    </div>
  );
}

function KpiMetricsGrid({ result }: { result: OptimizeResponseData }): React.ReactElement {
  const m = result.metrics;
  const t = result.solver_telemetry;
  const gapStr = (m.optimality_gap === 0 || (m.optimality_gap === null && result.solver_status === 'OPTIMAL'))
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
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', display: 'block' }}>Wall-Clock Time</span>
        <strong className="font-mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>{t ? `${t.wall_clock_time_seconds.toFixed(2)}s` : '—'}</strong>
      </div>
    </div>
  );
}

function StageTelemetryRow({ label, telem }: { label: string; telem?: StageTelemetryResponse | null }): React.ReactElement | null {
  if (!telem || !telem.status) return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem', padding: '0.35rem 0' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}:</span>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <Badge variant={telem.status === 'OPTIMAL' ? 'optimal' : 'warning'} className="font-mono">{telem.status}</Badge>
        {telem.objective_value !== null && <span className="font-mono" style={{ color: 'var(--text-primary)' }}>Val: {telem.objective_value}</span>}
      </div>
    </div>
  );
}

function VerifierReportBlock({ result }: { result: OptimizeResponseData }): React.ReactElement {
  const isVerified = result.verification_status === 'VERIFIED';
  const vRep = result.verification_report;
  return (
    <div style={{ padding: '0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>Independent Clean-Room Verifier Audit</span>
        <Badge variant={isVerified ? 'optimal' : result.verification_status === 'SKIPPED' ? 'neutral' : 'critical'} className="font-mono">
          {result.verification_status}
        </Badge>
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        {vRep ? `Evaluated ${vRep.checks_passed} of ${vRep.checks_run} invariant checks successfully.` : `Verification state: ${result.verification_status}`}
      </div>
      {vRep && vRep.violations.length > 0 && (
        <ul style={{ marginTop: '0.35rem', paddingLeft: '1.25rem', color: 'var(--color-critical)', fontSize: '0.75rem' }}>
          {vRep.violations.map((v, i) => (<li key={i}>{v}</li>))}
        </ul>
      )}
    </div>
  );
}

function OperationsTable({ ops }: { ops: ScheduledOperationResponse[] }): React.ReactElement {
  if (ops.length === 0) {
    return <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>No scheduled operations for this solve run.</div>;
  }
  return (
    <div style={{ overflowX: 'auto', maxHeight: '280px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
            <th style={{ padding: '0.5rem 0.625rem' }}>Order</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Step</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Status</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Machine</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Window [Start, End)</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Duration</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Slack</th>
          </tr>
        </thead>
        <tbody>
          {ops.map((op, i) => (
            <tr key={op.operation_id || i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <td style={{ padding: '0.5rem 0.625rem', fontWeight: 600 }} className="font-mono">{op.order_id}</td>
              <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">#{op.sequence_index}</td>
              <td style={{ padding: '0.5rem 0.625rem' }}>
                {op.status ? (
                  <Badge
                    variant={op.status === 'COMPLETED' ? 'optimal' : op.status === 'IN_PROGRESS' ? 'warning' : 'neutral'}
                    className="font-mono"
                  >
                    {op.status}
                  </Badge>
                ) : '—'}
              </td>
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

export function OptimizationResultCard({ result, onViewSchedules }: OptimizationResultCardProps): React.ReactElement {
  const [showOps, setShowOps] = useState(false);

  return (
    <Card
      title={`Optimization Result: ${result.name}`}
      subtitle={`Schedule ID: ${result.schedule_id} | Objective: ${result.objective_type}`}
      actions={onViewSchedules ? <Button variant="secondary" size="sm" onClick={onViewSchedules}>View in Schedules →</Button> : undefined}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
        <StatusBanner status={result.solver_status} />
        <KpiMetricsGrid result={result} />
        {(result.stage1_telemetry || result.stage2_telemetry) && (
          <div style={{ padding: '0.625rem 0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <strong style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>Hierarchical Stage Telemetry</strong>
            <StageTelemetryRow label="Stage 1 (Primary)" telem={result.stage1_telemetry} />
            <StageTelemetryRow label="Stage 2 (Secondary)" telem={result.stage2_telemetry} />
          </div>
        )}
        <VerifierReportBlock result={result} />
        {result.scheduled_operations.length > 0 && (
          <GanttChart
            scheduleId={result.schedule_id}
            scheduleName={result.name}
            solverStatus={result.solver_status}
            verificationStatus={result.verification_status}
            makespanMinutes={result.metrics.makespan_minutes}
            operations={result.scheduled_operations}
            downtimes={result.downtimes}
            machines={result.machines}
            currentTimeMinute={result.current_time_minute}
          />
        )}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowOps(!showOps)} style={{ fontSize: '0.75rem', marginBottom: showOps ? '0.5rem' : 0 }}>
            {showOps ? '▲ Hide Operation Schedule Table' : `▼ Inspect Operation Allocations (${result.scheduled_operations.length} steps)`}
          </button>
          {showOps && <OperationsTable ops={result.scheduled_operations} />}
        </div>
      </div>
    </Card>

  );
}
