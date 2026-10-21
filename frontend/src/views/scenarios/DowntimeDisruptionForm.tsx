/**
 * Injected downtime windows sub-form for scenario creation.
 * Governed by SPECIFICATION.md Section 6.1.
 */

import React from 'react';
import { Button } from '../../components/common/Button';
import { MachineResponse } from '../../types/api';
import { DowntimeDisruptionItem } from '../../types/scenarios';

interface DowntimeDisruptionFormProps {
  machines: MachineResponse[];
  downtimes: DowntimeDisruptionItem[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: keyof DowntimeDisruptionItem, value: string | number) => void;
}

export function DowntimeDisruptionForm({
  machines,
  downtimes,
  onAdd,
  onRemove,
  onUpdate,
}: DowntimeDisruptionFormProps): React.ReactElement {
  return (
    <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '1rem', backgroundColor: 'var(--bg-app)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          Injected Machine Downtimes ({downtimes.length})
        </span>
        <Button type="button" variant="secondary" size="sm" onClick={onAdd}>
          + Add Window
        </Button>
      </div>
      {downtimes.map((dt, idx) => (
        <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr 2fr auto', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <select
            value={dt.machine_id}
            onChange={(e) => onUpdate(idx, 'machine_id', e.target.value)}
            style={{ padding: '0.375rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: '0.75rem' }}
          >
            {machines.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name || m.external_id}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            value={dt.start_minute}
            onChange={(e) => onUpdate(idx, 'start_minute', parseInt(e.target.value) || 0)}
            placeholder="Start (min)"
            style={{ padding: '0.375rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: '0.75rem' }}
          />
          <input
            type="number"
            min={1}
            value={dt.end_minute}
            onChange={(e) => onUpdate(idx, 'end_minute', parseInt(e.target.value) || 1)}
            placeholder="End (min)"
            style={{ padding: '0.375rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: '0.75rem' }}
          />
          <input
            type="text"
            value={dt.reason || ''}
            onChange={(e) => onUpdate(idx, 'reason', e.target.value)}
            placeholder="Reason"
            style={{ padding: '0.375rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: '0.75rem' }}
          />
          {downtimes.length > 1 && (
            <button
              type="button"
              onClick={() => onRemove(idx)}
              style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
