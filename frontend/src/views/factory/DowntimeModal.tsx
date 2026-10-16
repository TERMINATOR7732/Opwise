/**
 * Scheduled Maintenance Window Creation Dialog
 * Governed by DATA_AND_API.md Section 1.1 Table 3.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { DowntimeCreate, MachineResponse } from '../../types/api';

export interface DowntimeModalProps {
  isOpen: boolean;
  machines: MachineResponse[];
  initialMachineId?: string;
  onSave: (data: DowntimeCreate) => Promise<void>;
  onClose: () => void;
}

function validateDowntime(machineId: string, start: number, end: number): string | null {
  if (!machineId) return 'Please select a target machine.';
  if (isNaN(start) || start < 0) return 'Start minute must be a non-negative integer (>= 0).';
  if (isNaN(end) || end <= start) return 'End minute must be strictly greater than start minute.';
  return null;
}

function DowntimeFormFields({
  machineId, setMachineId, startMinute, setStartMinute, endMinute, setEndMinute, reason, setReason, machines,
}: {
  machineId: string; setMachineId: (v: string) => void; startMinute: string; setStartMinute: (v: string) => void;
  endMinute: string; setEndMinute: (v: string) => void; reason: string; setReason: (v: string) => void; machines: MachineResponse[];
}): React.ReactElement {
  return (
    <>
      <div className="form-group">
        <label htmlFor="downtime-machine" className="form-label">Target Machine Workstation *</label>
        <select id="downtime-machine" className="form-input font-mono" value={machineId} onChange={(e) => setMachineId(e.target.value)}>
          {machines.map((m) => (<option key={m.id} value={m.id}>{m.external_id} — {m.name}</option>))}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <div className="form-group">
          <label htmlFor="downtime-start" className="form-label">Start Minute [start, ...) *</label>
          <input id="downtime-start" type="number" min="0" required value={startMinute} onChange={(e) => setStartMinute(e.target.value)} className="form-input font-mono" />
        </div>
        <div className="form-group">
          <label htmlFor="downtime-end" className="form-label">End Minute [..., end) *</label>
          <input id="downtime-end" type="number" min="1" required value={endMinute} onChange={(e) => setEndMinute(e.target.value)} className="form-input font-mono" />
        </div>
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label htmlFor="downtime-reason" className="form-label">Maintenance Reason / Description (Optional)</label>
        <input id="downtime-reason" type="text" maxLength={128} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Spindle bearing overhaul" className="form-input" />
      </div>
    </>
  );
}

function DowntimeModalDialog({
  formError, isSubmitting, onClose, onSubmit, children,
}: {
  formError: string | null; isSubmitting: boolean; onClose: () => void; onSubmit: (e: React.FormEvent) => void; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div role="dialog" aria-labelledby="downtime-modal-title" aria-modal="true" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: '1rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '460px' }}>
        <div className="card-header">
          <h2 id="downtime-modal-title" className="card-title">Schedule Maintenance Downtime</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close dialog">✕</button>
        </div>
        <form onSubmit={onSubmit}>
          <div className="card-body">
            {formError && <p style={{ color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>{formError}</p>}
            {children}
          </div>
          <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>Schedule Downtime</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DowntimeModal({ isOpen, machines, initialMachineId, onSave, onClose }: DowntimeModalProps): React.ReactElement | null {
  const [machineId, setMachineId] = useState('');
  const [startMinute, setStartMinute] = useState('60');
  const [endMinute, setEndMinute] = useState('120');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setMachineId(initialMachineId || (machines.length > 0 ? machines[0].id : ''));
    setStartMinute('60');
    setEndMinute('120');
    setReason('');
    setFormError(null);
  }, [initialMachineId, machines, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const start = parseInt(startMinute, 10);
    const end = parseInt(endMinute, 10);
    const err = validateDowntime(machineId, start, end);
    if (err) { setFormError(err); return; }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await onSave({ machine_id: machineId, start_minute: start, end_minute: end, reason: reason.trim() || null });
      onClose();
    } catch (saveErr: unknown) {
      setFormError(saveErr instanceof Error ? saveErr.message : 'Failed to schedule maintenance');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DowntimeModalDialog formError={formError} isSubmitting={isSubmitting} onClose={onClose} onSubmit={handleSubmit}>
      <DowntimeFormFields machineId={machineId} setMachineId={setMachineId} startMinute={startMinute} setStartMinute={setStartMinute} endMinute={endMinute} setEndMinute={setEndMinute} reason={reason} setReason={setReason} machines={machines} />
    </DowntimeModalDialog>
  );
}
