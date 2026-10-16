/**
 * Machine Creation and Edit Dialog
 * Governed by DATA_AND_API.md Section 1.1 Table 2.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/common/Button';
import { MachineCreate, MachineResponse } from '../../types/api';

export interface MachineModalProps {
  isOpen: boolean;
  initialMachine?: MachineResponse | null;
  onSave: (data: MachineCreate) => Promise<void>;
  onClose: () => void;
  existingCodes: string[];
}

function validateMachine(id: string, name: string, existing: string[], isEdit: boolean): string | null {
  if (!id) return 'Machine code is required (e.g. M1, CNC-01).';
  if (!name) return 'Machine name is required.';
  if (!isEdit && existing.includes(id)) return `Machine code '${id}' already exists in this workspace.`;
  return null;
}

function MachineFormFields({
  extId, setExtId, name, setName, isEdit,
}: {
  extId: string; setExtId: (v: string) => void; name: string; setName: (v: string) => void; isEdit: boolean;
}): React.ReactElement {
  return (
    <>
      <div className="form-group">
        <label htmlFor="machine-ext-id" className="form-label">Machine Code (Unique Identifier) *</label>
        <input id="machine-ext-id" type="text" required maxLength={64} value={extId} onChange={(e) => setExtId(e.target.value)} placeholder="e.g. M1, CNC-01" className="form-input font-mono" disabled={isEdit} autoFocus />
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'block' }}>Used in routing operations and schedule allocations.</span>
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label htmlFor="machine-name" className="form-label">Machine Name / Station Description *</label>
        <input id="machine-name" type="text" required maxLength={128} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 5-Axis Milling Center" className="form-input" />
      </div>
    </>
  );
}

function MachineModalDialog({
  isEdit, formError, isSubmitting, onClose, onSubmit, children,
}: {
  isEdit: boolean; formError: string | null; isSubmitting: boolean; onClose: () => void; onSubmit: (e: React.FormEvent) => void; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div role="dialog" aria-labelledby="machine-modal-title" aria-modal="true" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: '1rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '440px' }}>
        <div className="card-header">
          <h2 id="machine-modal-title" className="card-title">{isEdit ? 'Edit Machine Workstation' : 'Add Machine Workstation'}</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close dialog">✕</button>
        </div>
        <form onSubmit={onSubmit}>
          <div className="card-body">
            {formError && <p style={{ color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>{formError}</p>}
            {children}
          </div>
          <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>{isEdit ? 'Save Changes' : 'Add Machine'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function MachineModal({ isOpen, initialMachine, onSave, onClose, existingCodes }: MachineModalProps): React.ReactElement | null {
  const [extId, setExtId] = useState(initialMachine ? initialMachine.external_id : '');
  const [name, setName] = useState(initialMachine ? initialMachine.name : '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setExtId(initialMachine ? initialMachine.external_id : '');
    setName(initialMachine ? initialMachine.name : '');
    setFormError(null);
  }, [initialMachine, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateMachine(extId.trim(), name.trim(), existingCodes, Boolean(initialMachine));
    if (err) { setFormError(err); return; }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await onSave({ external_id: extId.trim(), name: name.trim() });
      onClose();
    } catch (saveErr: unknown) {
      setFormError(saveErr instanceof Error ? saveErr.message : 'Failed to save machine');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <MachineModalDialog isEdit={Boolean(initialMachine)} formError={formError} isSubmitting={isSubmitting} onClose={onClose} onSubmit={handleSubmit}>
      <MachineFormFields extId={extId} setExtId={setExtId} name={name} setName={setName} isEdit={Boolean(initialMachine)} />
    </MachineModalDialog>
  );
}
