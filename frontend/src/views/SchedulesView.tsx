/**
 * Production Schedules History & Detail Inspector View
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.2.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useRouter } from '../router/RouterContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { apiEndpoints } from '../api/endpoints';
import { ScheduleDetailResponse, ScheduleSummaryResponse } from '../types/api';
import { ScheduleDetailCard } from './schedules/ScheduleDetailCard';

function ScheduleListRow({
  s, isSelected, onSelect,
}: {
  s: ScheduleSummaryResponse; isSelected: boolean; onSelect: () => void;
}): React.ReactElement {
  const dateStr = new Date(s.created_at).toLocaleString();
  const stVariant = s.solver_status === 'OPTIMAL' ? 'optimal' : s.solver_status === 'FEASIBLE' ? 'warning' : 'critical';
  return (
    <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: isSelected ? 'var(--color-primary-subtle, rgba(59, 130, 246, 0.05))' : 'transparent' }}>
      <td style={{ padding: '0.625rem 0.75rem', fontWeight: 600 }}>{s.name}</td>
      <td style={{ padding: '0.625rem 0.75rem' }}><Badge variant={stVariant} className="font-mono">{s.solver_status}</Badge></td>
      <td style={{ padding: '0.625rem 0.75rem' }}><Badge variant={s.verification_status === 'VERIFIED' ? 'optimal' : 'neutral'} className="font-mono">{s.verification_status}</Badge></td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{s.makespan_minutes}m</td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{s.weighted_tardiness}</td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{s.late_order_count}</td>
      <td style={{ padding: '0.625rem 0.75rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>{dateStr}</td>
      <td style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>
        <Button variant={isSelected ? 'primary' : 'secondary'} size="sm" onClick={onSelect}>
          {isSelected ? 'Viewing' : 'Inspect'}
        </Button>
      </td>
    </tr>
  );
}

function SchedulesListTable({
  schedules, selectedId, onSelect,
}: {
  schedules: ScheduleSummaryResponse[]; selectedId: string | null; onSelect: (id: string) => void;
}): React.ReactElement {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
            <th style={{ padding: '0.625rem 0.75rem' }}>Schedule Name</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Solver Status</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Verifier</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Makespan</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Tardiness</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Late</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Generated At</th>
            <th style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => (
            <ScheduleListRow key={s.id} s={s} isSelected={s.id === selectedId} onSelect={() => onSelect(s.id)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SchedulesView(): React.ReactElement {
  const { activeWorkspace } = useWorkspace();
  const { navigate } = useRouter();
  const [schedules, setSchedules] = useState<ScheduleSummaryResponse[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<ScheduleDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSchedules = useCallback(async () => {
    if (!activeWorkspace) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiEndpoints.listSchedules(activeWorkspace.id);
      setSchedules(data);
      if (data.length > 0 && !selectedDetail) {
        const detail = await apiEndpoints.getSchedule(activeWorkspace.id, data[0].id);
        setSelectedDetail(detail);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch schedules');
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace, selectedDetail]);

  useEffect(() => { loadSchedules(); }, [loadSchedules]);

  const handleSelectSchedule = async (id: string) => {
    if (!activeWorkspace) return;
    try {
      setSelectedDetail(await apiEndpoints.getSchedule(activeWorkspace.id, id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load schedule detail');
    }
  };

  if (!activeWorkspace) {
    return <EmptyState title="No Workspace Selected" description="Select or create a workspace to inspect generated schedules." action={<Button variant="primary" onClick={() => navigate('overview')}>Go to Overview</Button>} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <PageHeader
        title="Production Schedules & Historical Telemetry"
        description={`Workspace: ${activeWorkspace.name} — Persisted schedule snapshots, deterministic metrics, and clean-room verification.`}
        badge={<Badge variant="optimal">Milestone 09B Active</Badge>}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" size="sm" onClick={loadSchedules} disabled={isLoading}>Refresh Schedules</Button>
            <Button variant="primary" size="sm" onClick={() => navigate('planning')}>+ New Optimization Solve</Button>
          </div>
        }
      />
      {error && <ErrorBanner message={error} onRetry={loadSchedules} />}
      {isLoading && schedules.length === 0 ? (
        <LoadingState message="Loading persisted schedules from SQLite..." />
      ) : schedules.length === 0 ? (
        <EmptyState title="No Schedules Generated Yet" description="No optimization schedules have been recorded for this workspace. Run the CP-SAT optimizer to create your first schedule." action={<Button variant="primary" onClick={() => navigate('planning')}>Open Planning Engine →</Button>} />
      ) : (
        <>
          {selectedDetail && <ScheduleDetailCard schedule={selectedDetail} workspaceId={activeWorkspace.id} onClose={() => setSelectedDetail(null)} />}
          <Card title={`All Persisted Schedules (${schedules.length})`} subtitle="Sorted by persistence timestamp. Click Inspect on any record to view telemetry and operation allocations.">
            <SchedulesListTable schedules={schedules} selectedId={selectedDetail?.id || null} onSelect={handleSelectSchedule} />
          </Card>
        </>
      )}
    </div>
  );
}
