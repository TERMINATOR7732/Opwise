/**
 * Injected rush orders sub-form for scenario creation.
 * Governed by SPECIFICATION.md Section 6.1.
 */

import React from 'react';
import { Button } from '../../components/common/Button';
import { MachineResponse } from '../../types/api';
import { OrderDisruptionItem } from '../../types/scenarios';

interface RushOrderDisruptionFormProps {
  machines: MachineResponse[];
  rushOrders: OrderDisruptionItem[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, updated: OrderDisruptionItem) => void;
}

export function RushOrderDisruptionForm({
  machines,
  rushOrders,
  onAdd,
  onRemove,
  onUpdate,
}: RushOrderDisruptionFormProps): React.ReactElement {
  return (
    <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '1rem', backgroundColor: 'var(--bg-app)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          Injected Rush Orders ({rushOrders.length})
        </span>
        <Button type="button" variant="secondary" size="sm" onClick={onAdd}>
          + Add Rush Order
        </Button>
      </div>
      {rushOrders.map((ord, idx) => (
        <div key={idx} style={{ padding: '0.75rem', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-card)', marginBottom: '0.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Order Code</label>
              <input
                type="text"
                value={ord.order_code}
                onChange={(e) => onUpdate(idx, { ...ord, order_code: e.target.value })}
                style={{ width: '100%', padding: '0.25rem', fontSize: '0.75rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Release (min)</label>
              <input
                type="number"
                min={0}
                value={ord.release_time_minutes}
                onChange={(e) => onUpdate(idx, { ...ord, release_time_minutes: parseInt(e.target.value) || 0 })}
                style={{ width: '100%', padding: '0.25rem', fontSize: '0.75rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Due Date (min)</label>
              <input
                type="number"
                min={1}
                value={ord.due_date_minutes}
                onChange={(e) => onUpdate(idx, { ...ord, due_date_minutes: parseInt(e.target.value) || 1 })}
                style={{ width: '100%', padding: '0.25rem', fontSize: '0.75rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Weight</label>
              <input
                type="number"
                min={1}
                value={ord.tardiness_weight}
                onChange={(e) => onUpdate(idx, { ...ord, tardiness_weight: parseInt(e.target.value) || 1 })}
                style={{ width: '100%', padding: '0.25rem', fontSize: '0.75rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)' }}
              />
            </div>
            {rushOrders.length > 1 && (
              <button
                type="button"
                onClick={() => onRemove(idx)}
                style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem', marginTop: '0.75rem' }}
              >
                ×
              </button>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.5rem', alignItems: 'center' }}>
            <select
              value={ord.operations[0]?.machine_id || ''}
              onChange={(e) => {
                const mId = e.target.value;
                onUpdate(idx, {
                  ...ord,
                  operations: [{ ...ord.operations[0], machine_id: mId }],
                });
              }}
              style={{ padding: '0.25rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '0.75rem', borderRadius: 'var(--radius-sm)' }}
            >
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  Step 1 on {m.name || m.external_id}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              value={ord.operations[0]?.processing_minutes || 20}
              onChange={(e) => {
                const dur = parseInt(e.target.value) || 1;
                onUpdate(idx, {
                  ...ord,
                  operations: [{ ...ord.operations[0], processing_minutes: dur }],
                });
              }}
              placeholder="Duration (min)"
              style={{ padding: '0.25rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', fontSize: '0.75rem', borderRadius: 'var(--radius-sm)' }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
