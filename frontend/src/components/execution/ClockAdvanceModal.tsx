/**
 * Plant Clock Advance & Overdue Operations Reconciliation Modal
 * Governed by MILESTONE_15D_SCOPE_PROPOSAL.md Section 7.1, 7.2, and Section 9.
 */

import React, { useState, useMemo } from 'react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ClockAdvancePayload } from '../../types/api';

export interface InProgressOpInfo {
  id: string;
  orderExternalId: string;
  orderName: string;
  sequenceIndex: number;
  machineId: string;
  actualStartMinute: number;
  remainingDurationMinutes: number;
}

export interface ClockAdvanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentClock: number;
  inProgressOps: InProgressOpInfo[];
  onAdvance: (payload: ClockAdvancePayload) => Promise<void>;
}

export function ClockAdvanceModal({
  isOpen,
  onClose,
  currentClock,
  inProgressOps,
  onAdvance,
}: ClockAdvanceModalProps): React.ReactElement | null {
  const [mode, setMode] = useState<'increment' | 'target'>('increment');
  const [advanceBy, setAdvanceBy] = useState<number>(15);
  const [targetMinute, setTargetMinute] = useState<number>(currentClock + 15);
  const [completedOpIds, setCompletedOpIds] = useState<Record<string, boolean>>({});
  const [remainingOverrides, setRemainingOverrides] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const destTime = useMemo(() => {
    if (mode === 'increment') {
      return currentClock + Math.max(0, advanceBy || 0);
    }
    return Math.max(currentClock, targetMinute || currentClock);
  }, [mode, currentClock, advanceBy, targetMinute]);

  const elapsed = destTime - currentClock;

  // Identify overdue operations requiring reconciliation
  const overdueOps = useMemo(() => {
    if (elapsed <= 0) return [];
    return inProgressOps.filter((op) => elapsed >= op.remainingDurationMinutes);
  }, [inProgressOps, elapsed]);

  // Validation: Every overdue op must either be marked completed OR have an override >= 1
  const unreconciledOps = useMemo(() => {
    return overdueOps.filter((op) => {
      const isMarkedCompleted = completedOpIds[op.id] === true;
      const overrideVal = parseInt(remainingOverrides[op.id] || '', 10);
      const hasValidOverride = !isNaN(overrideVal) && overrideVal >= 1;
      return !isMarkedCompleted && !hasValidOverride;
    });
  }, [overdueOps, completedOpIds, remainingOverrides]);

  if (!isOpen) return null;

  const handlePreset = (delta: number) => {
    setMode('increment');
    setAdvanceBy(delta);
    setTargetMinute(currentClock + delta);
    setFormError(null);
  };

  const handleToggleCompleted = (opId: string, val: boolean) => {
    setCompletedOpIds((prev) => ({ ...prev, [opId]: val }));
    if (val) {
      setRemainingOverrides((prev) => {
        const next = { ...prev };
        delete next[opId];
        return next;
      });
    }
  };

  const handleOverrideChange = (opId: string, val: string) => {
    setRemainingOverrides((prev) => ({ ...prev, [opId]: val }));
    if (val) {
      setCompletedOpIds((prev) => ({ ...prev, [opId]: false }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (destTime < currentClock) {
      setFormError('Cannot advance clock backward into the past.');
      return;
    }
    if (unreconciledOps.length > 0) {
      setFormError(
        `Reconciliation required: ${unreconciledOps.length} operation(s) reached or exceeded their estimated finish. Mark them completed or specify remaining duration.`
      );
      return;
    }

    setIsSubmitting(true);
    setFormError(null);
    try {
      const finalCompleted = Object.entries(completedOpIds)
        .filter(([_, checked]) => checked)
        .map(([id]) => id);

      const finalOverrides: Record<string, number> = {};
      Object.entries(remainingOverrides).forEach(([id, strVal]) => {
        const num = parseInt(strVal, 10);
        if (!completedOpIds[id] && !isNaN(num) && num >= 1) {
          finalOverrides[id] = num;
        }
      });

      const payload: ClockAdvancePayload = {
        advance_by_minutes: mode === 'increment' ? advanceBy : undefined,
        target_time_minute: mode === 'target' ? destTime : undefined,
        expected_current_time_minute: currentClock,
        completed_operation_ids: finalCompleted.length > 0 ? finalCompleted : undefined,
        remaining_duration_overrides: Object.keys(finalOverrides).length > 0 ? finalOverrides : undefined,
      };

      await onAdvance(payload);
      onClose();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to advance plant clock');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-labelledby="clock-advance-title"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: '1rem',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '560px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
        }}
      >
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>⏱️</span>
            <div>
              <h2 id="clock-advance-title" className="card-title" style={{ margin: 0 }}>
                Advance Plant Clock
              </h2>
              <span style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)' }}>
                Current Plant Clock: <strong className="font-mono">t₀ = {currentClock}m</strong>
              </span>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            aria-label="Close clock advance dialog"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div className="card-body" style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {formError && (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  backgroundColor: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid var(--color-critical, #ef4444)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--color-critical, #ef4444)',
                  fontSize: 'var(--font-size-body)',
                }}
              >
                {formError}
              </div>
            )}

            {/* Quick Presets */}
            <div>
              <label className="form-label" style={{ marginBottom: '0.35rem' }}>
                Quick Presets
              </label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button
                  type="button"
                  variant={mode === 'increment' && advanceBy === 15 ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => handlePreset(15)}
                >
                  +15 min
                </Button>
                <Button
                  type="button"
                  variant={mode === 'increment' && advanceBy === 30 ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => handlePreset(30)}
                >
                  +30 min
                </Button>
                <Button
                  type="button"
                  variant={mode === 'increment' && advanceBy === 60 ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => handlePreset(60)}
                >
                  +60 min (1 hr)
                </Button>
              </div>
            </div>

            {/* Destination Mode Inputs */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div
                style={{
                  padding: '0.75rem',
                  backgroundColor: mode === 'increment' ? 'var(--bg-app)' : 'transparent',
                  border: `1px solid ${mode === 'increment' ? 'var(--color-primary)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
                onClick={() => setMode('increment')}
              >
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: 'var(--font-size-body)', fontWeight: 600 }}>
                  <input
                    type="radio"
                    name="advance-mode"
                    checked={mode === 'increment'}
                    onChange={() => setMode('increment')}
                  />
                  Advance by Duration
                </label>
                <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <input
                    type="number"
                    min="0"
                    className="form-input font-mono"
                    value={advanceBy}
                    onChange={(e) => {
                      setMode('increment');
                      setAdvanceBy(Math.max(0, parseInt(e.target.value, 10) || 0));
                    }}
                    style={{ width: '90px', padding: '0.35rem 0.5rem', fontSize: 'var(--font-size-body)' }}
                  />
                  <span style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)' }}>minutes</span>
                </div>
              </div>

              <div
                style={{
                  padding: '0.75rem',
                  backgroundColor: mode === 'target' ? 'var(--bg-app)' : 'transparent',
                  border: `1px solid ${mode === 'target' ? 'var(--color-primary)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
                onClick={() => setMode('target')}
              >
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: 'var(--font-size-body)', fontWeight: 600 }}>
                  <input
                    type="radio"
                    name="advance-mode"
                    checked={mode === 'target'}
                    onChange={() => setMode('target')}
                  />
                  Set Target Minute
                </label>
                <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <input
                    type="number"
                    min={currentClock}
                    className="form-input font-mono"
                    value={targetMinute}
                    onChange={(e) => {
                      setMode('target');
                      setTargetMinute(Math.max(currentClock, parseInt(e.target.value, 10) || currentClock));
                    }}
                    style={{ width: '90px', padding: '0.35rem 0.5rem', fontSize: 'var(--font-size-body)' }}
                  />
                  <span style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)' }}>min</span>
                </div>
              </div>
            </div>

            {/* Destination Summary Banner */}
            <div
              style={{
                padding: '0.625rem 0.875rem',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: 'var(--font-size-body)',
              }}
            >
              <span>
                Simulated Step: <strong className="font-mono">+{elapsed}m</strong>
              </span>
              <span>
                New Clock Target: <Badge variant="warning" className="font-mono">t = {destTime}m</Badge>
              </span>
            </div>

            {/* Overdue Operations Reconciliation Section */}
            {overdueOps.length > 0 && (
              <div
                style={{
                  border: '1px solid var(--color-warning, #f59e0b)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.875rem',
                  backgroundColor: 'rgba(245, 158, 11, 0.06)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <Badge variant="warning">RECONCILIATION REQUIRED</Badge>
                  <span style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-secondary)' }}>
                    {overdueOps.length} operation(s) reached estimated finish.
                  </span>
                </div>
                <p style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)', margin: '0 0 0.75rem 0' }}>
                  Per Policy B, overdue operations must either be marked completed at the destination clock or have supervisor-estimated remaining minutes specified.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                  {overdueOps.map((op) => {
                    const isDone = completedOpIds[op.id] === true;
                    const override = remainingOverrides[op.id] || '';
                    const estFinish = currentClock + op.remainingDurationMinutes;

                    return (
                      <div
                        key={op.id}
                        style={{
                          padding: '0.625rem 0.75rem',
                          backgroundColor: 'var(--bg-card)',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border-subtle)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.35rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: 'var(--font-size-body)' }}>
                            {op.orderExternalId} (#{op.sequenceIndex}) — {op.orderName}
                          </span>
                          <span className="font-mono" style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)' }}>
                            Machine: {op.machineId} · Est. End: {estFinish}m
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.25rem', fontSize: 'var(--font-size-body)' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={isDone}
                              onChange={(e) => handleToggleCompleted(op.id, e.target.checked)}
                            />
                            <strong>Mark Completed at t = {destTime}m</strong>
                          </label>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>or Remaining Work:</span>
                            <input
                              type="number"
                              min="1"
                              placeholder="e.g. 15"
                              disabled={isDone}
                              value={override}
                              onChange={(e) => handleOverrideChange(op.id, e.target.value)}
                              className="form-input font-mono"
                              style={{ width: '70px', padding: '0.2rem 0.4rem', fontSize: 'var(--font-size-body)' }}
                            />
                            <span style={{ color: 'var(--text-muted)' }}>min</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div
            style={{
              padding: '0.875rem 1.25rem',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.5rem',
            }}
          >
            <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              disabled={isSubmitting || unreconciledOps.length > 0}
            >
              Advance to t₀ = {destTime}m
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
