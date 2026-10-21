/**
 * Operation inspection panel displaying details of a selected timeline block.
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.2.
 */

import React, { useEffect, useState } from 'react';
import { ScheduledOperationResponse } from '../../../types/api';
import { Badge } from '../../../components/common/Badge';
import { Button } from '../../../components/common/Button';
import { useOptionalFactory } from '../../../context/FactoryContext';

export interface GanttOperationDetailProps {
  operation: ScheduledOperationResponse | null;
  machineName?: string;
  onClose: () => void;
  onStart?: (opId: string) => Promise<void>;
  onComplete?: (opId: string) => Promise<void>;
}

export function GanttOperationDetail({
  operation,
  machineName,
  onClose,
  onStart,
  onComplete,
}: GanttOperationDetailProps): React.ReactElement | null {
  const factoryCtx = useOptionalFactory();
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

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

  const handleStart = async () => {
    setIsActionLoading(true);
    setActionError(null);
    try {
      if (onStart) {
        await onStart(operation.operation_id);
      } else if (factoryCtx) {
        await factoryCtx.startOperation(operation.operation_id);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to start operation');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleComplete = async () => {
    setIsActionLoading(true);
    setActionError(null);
    try {
      if (onComplete) {
        await onComplete(operation.operation_id);
      } else if (factoryCtx) {
        await factoryCtx.completeOperation(operation.operation_id);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to complete operation');
    } finally {
      setIsActionLoading(false);
    }
  };

  const canStart = operation.status === 'PLANNED';
  const canComplete = operation.status === 'IN_PROGRESS';

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
          <strong style={{ fontSize: 'var(--font-size-body)', color: 'var(--text-primary)' }}>
            Operation Allocation Details
          </strong>
          <Badge variant="neutral" className="font-mono">
            {operation.order_id} · Step #{operation.sequence_index}
          </Badge>
          {operation.status && (
            <Badge
              variant={
                operation.status === 'COMPLETED'
                  ? 'optimal'
                  : operation.status === 'IN_PROGRESS'
                  ? 'warning'
                  : 'neutral'
              }
              className="font-mono"
            >
              {operation.status}
            </Badge>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {canStart && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleStart}
              isLoading={isActionLoading}
              aria-label="Start scheduled operation"
            >
              Start Operation
            </Button>
          )}
          {canComplete && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleComplete}
              isLoading={isActionLoading}
              aria-label="Complete scheduled operation"
            >
              Complete Operation
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={onClose} aria-label="Close operation inspection panel">
            Deselect (Esc)
          </Button>
        </div>
      </div>

      {actionError && (
        <div
          style={{
            padding: '0.4rem 0.6rem',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid var(--color-critical)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--color-critical)',
            fontSize: '0.75rem',
          }}
        >
          {actionError}
        </div>
      )}

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
