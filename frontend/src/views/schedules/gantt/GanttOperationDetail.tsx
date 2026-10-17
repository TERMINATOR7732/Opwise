/**
 * Operation inspection panel displaying details of a selected timeline block.
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.2.
 */

import React, { useEffect } from 'react';
import { ScheduledOperationResponse } from '../../../types/api';
import { Badge } from '../../../components/common/Badge';
import { Button } from '../../../components/common/Button';

export interface GanttOperationDetailProps {
  operation: ScheduledOperationResponse | null;
  machineName?: string;
  onClose: () => void;
}

export function GanttOperationDetail({
  operation,
  machineName,
  onClose,
}: GanttOperationDetailProps): React.ReactElement | null {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!operation) return null;

  return (
    <div
      style={{
        padding: '0.875rem 1rem',
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--color-primary-subtle, #3b82f6)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.625rem',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
      }}
      role="complementary"
      aria-label="Selected operation details"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>
            Operation Allocation Details
          </strong>
          <Badge variant="neutral" className="font-mono">
            {operation.order_id} · Step #{operation.sequence_index}
          </Badge>
        </div>
        <Button variant="secondary" size="sm" onClick={onClose} aria-label="Close operation inspection panel">
          Deselect (Esc)
        </Button>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '0.5rem',
          fontSize: '0.75rem',
        }}
      >
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Order ID</span>
          <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>{operation.order_id}</strong>
        </div>
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Operation ID</span>
          <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>{operation.operation_id}</strong>
        </div>
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Assigned Machine</span>
          <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>
            {machineName ? `${machineName} (${operation.machine_id})` : operation.machine_id}
          </strong>
        </div>
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Time Window [Start, End)</span>
          <strong className="font-mono" style={{ color: 'var(--color-primary)' }}>
            [{operation.start_minute}, {operation.end_minute}) min
          </strong>
        </div>
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Processing Duration</span>
          <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>{operation.duration} min</strong>
        </div>
        <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
          <span style={{ color: 'var(--text-secondary)', display: 'block' }}>Free Slack</span>
          <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>{operation.slack_minutes} min</strong>
        </div>
      </div>
    </div>
  );
}
