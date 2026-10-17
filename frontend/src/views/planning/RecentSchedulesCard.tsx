/**
 * Recent Workspace Schedules History Card
 * Governed by DATA_AND_API.md Section 3.2 (GET /workspaces/{id}/schedules)
 */

import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { ScheduleSummaryResponse } from '../../types/api';

export interface RecentSchedulesCardProps {
  schedules: ScheduleSummaryResponse[];
  isLoading: boolean;
  onRefresh: () => Promise<void>;
  onSelectSchedule: (scheduleId: string) => void;
}

function StatusPill({ status }: { status: string }): React.ReactElement {
  const variant = status === 'OPTIMAL' ? 'optimal' : status === 'FEASIBLE' ? 'warning' : status === 'NO_WORK_STATE' ? 'warning' : 'critical';
  return <Badge variant={variant} className="font-mono">{status}</Badge>;
}

function ScheduleHistoryRow({
  s, onSelect,
}: {
  s: ScheduleSummaryResponse; onSelect: () => void;
}): React.ReactElement {
  const dateStr = new Date(s.created_at).toLocaleString();
  return (
    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <td style={{ padding: '0.5rem 0.625rem', fontWeight: 600 }}>{s.name}</td>
      <td style={{ padding: '0.5rem 0.625rem' }}><StatusPill status={s.solver_status} /></td>
      <td style={{ padding: '0.5rem 0.625rem' }}><Badge variant={s.verification_status === 'VERIFIED' ? 'optimal' : 'neutral'} className="font-mono">{s.verification_status}</Badge></td>
      <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">{s.makespan_minutes}m</td>
      <td style={{ padding: '0.5rem 0.625rem' }} className="font-mono">{s.weighted_tardiness}</td>
      <td style={{ padding: '0.5rem 0.625rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>{dateStr}</td>
      <td style={{ padding: '0.5rem 0.625rem', textAlign: 'right' }}>
        <Button variant="secondary" size="sm" onClick={onSelect}>Inspect →</Button>
      </td>
    </tr>
  );
}

function SchedulesTable({
  schedules, onSelect,
}: {
  schedules: ScheduleSummaryResponse[]; onSelect: (id: string) => void;
}): React.ReactElement {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
            <th style={{ padding: '0.5rem 0.625rem' }}>Run Name</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Solver Status</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Verifier</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Makespan</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Tardiness</th>
            <th style={{ padding: '0.5rem 0.625rem' }}>Created At</th>
            <th style={{ padding: '0.5rem 0.625rem', textAlign: 'right' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => (
            <ScheduleHistoryRow key={s.id} s={s} onSelect={() => onSelect(s.id)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecentSchedulesCard({
  schedules, isLoading, onRefresh, onSelectSchedule,
}: RecentSchedulesCardProps): React.ReactElement {
  return (
    <Card
      title={`Persisted Schedules History (${schedules.length})`}
      subtitle="Historical optimization snapshots persisted in SQLite database for this workspace."
      actions={<Button variant="secondary" size="sm" onClick={onRefresh} isLoading={isLoading}>Refresh History</Button>}
    >
      {schedules.length === 0 ? (
        <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          No schedules generated yet in this workspace. Run CP-SAT optimization above to generate a persistent production plan.
        </div>
      ) : (
        <SchedulesTable schedules={schedules} onSelect={onSelectSchedule} />
      )}
    </Card>
  );
}
