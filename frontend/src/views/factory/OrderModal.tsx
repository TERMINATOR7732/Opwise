/**
 * Production Order and Routing Operations Dialog
 * Governed by DATA_AND_API.md Section 1.1 Table 4 & 5.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { MachineResponse, OperationCreate, OrderCreate, OrderResponse } from '../../types/api';

export interface OrderModalProps {
  isOpen: boolean;
  machines: MachineResponse[];
  initialOrder?: OrderResponse | null;
  onSave: (data: OrderCreate) => Promise<void>;
  onClose: () => void;
  existingCodes: string[];
}

function validateOrder(id: string, name: string, ops: OperationCreate[], existing: string[], isEdit: boolean): string | null {
  if (!id.trim() || !name.trim()) return 'Order Code and Name are required.';
  if (!isEdit && existing.includes(id.trim())) return `Order code '${id.trim()}' already exists.`;
  if (ops.length === 0) return 'Every production order must contain at least one operation step.';
  return null;
}

function BasicInputs({ extId, setExtId, name, setName, isEdit }: {
  extId: string; setExtId: (v: string) => void; name: string; setName: (v: string) => void; isEdit: boolean;
}): React.ReactElement {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
      <div className="form-group">
        <label htmlFor="order-ext-id" className="form-label">Order Code *</label>
        <input id="order-ext-id" type="text" required maxLength={64} value={extId} onChange={(e) => setExtId(e.target.value)} placeholder="e.g. ORD-101" className="form-input font-mono" disabled={isEdit} autoFocus />
      </div>
      <div className="form-group">
        <label htmlFor="order-name" className="form-label">Product / Job Name *</label>
        <input id="order-name" type="text" required maxLength={128} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Titanium Impeller" className="form-input" />
      </div>
    </div>
  );
}

function TimingInputs({ rel, setRel, due, setDue, weight, setWeight }: {
  rel: string; setRel: (v: string) => void; due: string; setDue: (v: string) => void; weight: string; setWeight: (v: string) => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
      <div className="form-group">
        <label htmlFor="order-release" className="form-label">Release Time [r_j)</label>
        <input id="order-release" type="number" min="0" required value={rel} onChange={(e) => setRel(e.target.value)} className="form-input font-mono" />
      </div>
      <div className="form-group">
        <label htmlFor="order-due" className="form-label">Due Date [d_j) *</label>
        <input id="order-due" type="number" min="0" required value={due} onChange={(e) => setDue(e.target.value)} className="form-input font-mono" />
      </div>
      <div className="form-group">
        <label htmlFor="order-weight" className="form-label">Tardiness Weight (w_j)</label>
        <input id="order-weight" type="number" min="0" required value={weight} onChange={(e) => setWeight(e.target.value)} className="form-input font-mono" />
      </div>
    </div>
  );
}

function StepRow({ step, idx, machines, onChangeMachine, onChangeDuration, onRemove, canRemove }: {
  step: OperationCreate; idx: number; machines: MachineResponse[]; onChangeMachine: (id: string) => void;
  onChangeDuration: (d: number) => void; onRemove: () => void; canRemove: boolean;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
      <span className="badge badge-neutral font-mono" style={{ minWidth: '28px', textAlign: 'center' }}>#{idx + 1}</span>
      <select className="form-input font-mono" style={{ flex: 2, padding: '0.35rem 0.5rem' }} value={step.machine_id} onChange={(e) => onChangeMachine(e.target.value)}>
        {machines.map((m) => (<option key={m.id} value={m.id}>{m.external_id} — {m.name}</option>))}
      </select>
      <input type="number" min="1" value={step.processing_minutes} onChange={(e) => onChangeDuration(parseInt(e.target.value, 10) || 1)} className="form-input font-mono" style={{ width: '80px', padding: '0.35rem 0.5rem' }} title="Processing Duration in minutes" />
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>min</span>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onRemove} disabled={!canRemove} aria-label={`Remove step ${idx + 1}`} style={{ padding: '0.25rem 0.5rem' }}>✕</button>
    </div>
  );
}

function OperationsEditor({ ops, setOps, machines }: {
  ops: OperationCreate[]; setOps: React.Dispatch<React.SetStateAction<OperationCreate[]>>; machines: MachineResponse[];
}): React.ReactElement {
  const addStep = () => {
    if (!machines.length) return;
    setOps((p) => [...p, { sequence_index: p.length + 1, machine_id: machines[0].id, processing_minutes: 30 }]);
  };
  return (
    <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span className="form-label" style={{ marginBottom: 0 }}>Linear Routing Operations Sequence *</span>
        <Button type="button" variant="secondary" size="sm" onClick={addStep} disabled={!machines.length}>+ Add Step</Button>
      </div>
      {ops.map((op, idx) => (
        <StepRow
          key={idx}
          step={op}
          idx={idx}
          machines={machines}
          onChangeMachine={(mId) => setOps((p) => p.map((item, i) => (i === idx ? { ...item, machine_id: mId } : item)))}
          onChangeDuration={(dur) => setOps((p) => p.map((item, i) => (i === idx ? { ...item, processing_minutes: dur } : item)))}
          onRemove={() => setOps((p) => p.filter((_, i) => i !== idx))}
          canRemove={ops.length > 1}
        />
      ))}
    </div>
  );
}

function OrderModalDialog({ isEdit, formError, isSubmitting, onClose, onSubmit, children }: {
  isEdit: boolean; formError: string | null; isSubmitting: boolean; onClose: () => void; onSubmit: (e: React.FormEvent) => void; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div role="dialog" aria-labelledby="order-modal-title" aria-modal="true" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: '1rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '580px', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        <div className="card-header">
          <h2 id="order-modal-title" className="card-title">{isEdit ? 'Edit Production Order' : 'Create Production Order'}</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close dialog">✕</button>
        </div>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div className="card-body" style={{ overflowY: 'auto' }}>
            {formError && <p style={{ color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>{formError}</p>}
            {children}
          </div>
          <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>{isEdit ? 'Save Changes' : 'Create Order'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function OrderModal({ isOpen, machines, initialOrder, onSave, onClose, existingCodes }: OrderModalProps): React.ReactElement | null {
  const [extId, setExtId] = useState(initialOrder ? initialOrder.external_id : '');
  const [name, setName] = useState(initialOrder ? initialOrder.name : '');
  const [rel, setRel] = useState(initialOrder ? String(initialOrder.release_minute) : '0');
  const [due, setDue] = useState(initialOrder ? String(initialOrder.due_minute) : '120');
  const [weight, setWeight] = useState(initialOrder ? String(initialOrder.tardiness_weight) : '1');
  const [ops, setOps] = useState<OperationCreate[]>(() => {
    if (initialOrder)
      return initialOrder.operations.map((o) => ({
        sequence_index: o.sequence_index,
        machine_id: o.machine_id,
        processing_minutes: o.processing_minutes,
        status: o.status,
        actual_start_minute: o.actual_start_minute,
        actual_end_minute: o.actual_end_minute,
        remaining_duration_minutes: o.remaining_duration_minutes,
      }));
    return machines.length > 0 ? [{ sequence_index: 1, machine_id: machines[0].id, processing_minutes: 30, status: 'PLANNED' }] : [];
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (initialOrder) {
      setExtId(initialOrder.external_id);
      setName(initialOrder.name);
      setRel(String(initialOrder.release_minute));
      setDue(String(initialOrder.due_minute));
      setWeight(String(initialOrder.tardiness_weight));
      setOps(
        initialOrder.operations.map((o) => ({
          sequence_index: o.sequence_index,
          machine_id: o.machine_id,
          processing_minutes: o.processing_minutes,
          status: o.status,
          actual_start_minute: o.actual_start_minute,
          actual_end_minute: o.actual_end_minute,
          remaining_duration_minutes: o.remaining_duration_minutes,
        }))
      );
    } else {
      setExtId('');
      setName('');
      setRel('0');
      setDue('120');
      setWeight('1');
      setOps(machines.length > 0 ? [{ sequence_index: 1, machine_id: machines[0].id, processing_minutes: 30, status: 'PLANNED' }] : []);
    }
    setFormError(null);
  }, [initialOrder, machines, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateOrder(extId, name, ops, existingCodes, Boolean(initialOrder));
    if (err) { setFormError(err); return; }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const sanitized = ops.map((op, i) => ({
        sequence_index: i + 1,
        machine_id: op.machine_id,
        processing_minutes: Math.max(1, op.processing_minutes),
        status: op.status,
        actual_start_minute: op.actual_start_minute,
        actual_end_minute: op.actual_end_minute,
        remaining_duration_minutes: op.remaining_duration_minutes,
      }));
      await onSave({ external_id: extId.trim(), name: name.trim(), release_minute: Math.max(0, parseInt(rel, 10) || 0), due_minute: Math.max(0, parseInt(due, 10) || 0), tardiness_weight: Math.max(0, parseInt(weight, 10) || 1), operations: sanitized });
      onClose();
    } catch (submitErr: unknown) {
      setFormError(submitErr instanceof Error ? submitErr.message : 'Failed to save order');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <OrderModalDialog isEdit={Boolean(initialOrder)} formError={formError} isSubmitting={isSubmitting} onClose={onClose} onSubmit={handleSubmit}>
      <BasicInputs extId={extId} setExtId={setExtId} name={name} setName={setName} isEdit={Boolean(initialOrder)} />
      <TimingInputs rel={rel} setRel={setRel} due={due} setDue={setDue} weight={weight} setWeight={setWeight} />
      <OperationsEditor ops={ops} setOps={setOps} machines={machines} />
    </OrderModalDialog>
  );
}
