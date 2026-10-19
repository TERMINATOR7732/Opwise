/**
 * Modal dialog for branching a disruption scenario from an immutable baseline schedule.
 * Governed by SPECIFICATION.md Section 6 and DATA_AND_API.md Section 1.1 & 3.2.
 */

import React, { useState } from 'react';
import { Button } from '../../components/common/Button';
import { ScheduleSummaryResponse, MachineResponse } from '../../types/api';
import {
  DisruptionDelta,
  DowntimeDisruptionItem,
  OrderDisruptionItem,
  ScenarioCreateRequest,
} from '../../types/scenarios';
import { DowntimeDisruptionForm } from './DowntimeDisruptionForm';
import { RushOrderDisruptionForm } from './RushOrderDisruptionForm';

interface CreateScenarioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (req: ScenarioCreateRequest) => Promise<void>;
  schedules: ScheduleSummaryResponse[];
  machines: MachineResponse[];
}

export function CreateScenarioModal({
  isOpen,
  onClose,
  onSubmit,
  schedules,
  machines,
}: CreateScenarioModalProps): React.ReactElement | null {
  const initialClock = schedules[0]?.current_time_minute ?? 0;
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [baselineScheduleId, setBaselineScheduleId] = useState(schedules[0]?.id || '');
  const [disruptionType, setDisruptionType] = useState<'MACHINE_DOWNTIME' | 'URGENT_ORDER' | 'COMBINED'>('MACHINE_DOWNTIME');
  const [downtimes, setDowntimes] = useState<DowntimeDisruptionItem[]>([
    { machine_id: machines[0]?.id || '', start_minute: initialClock, end_minute: initialClock + 30, reason: 'Unplanned breakdown' },
  ]);
  const [rushOrders, setRushOrders] = useState<OrderDisruptionItem[]>([
    {
      order_code: 'RUSH-101',
      release_time_minutes: initialClock,
      due_date_minutes: initialClock + 60,
      tardiness_weight: 5,
      operations: [{ sequence_index: 1, machine_id: machines[0]?.id || '', processing_minutes: 20 }],
    },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSchedule = schedules.find((s) => s.id === baselineScheduleId) || schedules[0];
  const baselineClock = selectedSchedule?.current_time_minute ?? 0;

  if (!isOpen) return null;

  const handleAddDowntime = () => {
    setDowntimes((prev) => [
      ...prev,
      { machine_id: machines[0]?.id || '', start_minute: baselineClock, end_minute: baselineClock + 30, reason: 'Maintenance outage' },
    ]);
  };

  const handleRemoveDowntime = (index: number) => {
    setDowntimes((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpdateDowntime = (index: number, field: keyof DowntimeDisruptionItem, value: any) => {
    setDowntimes((prev) => prev.map((item, i) => (i === index ? { ...item, [field]: value } : item)));
  };

  const handleAddRushOrder = () => {
    setRushOrders((prev) => [
      ...prev,
      {
        order_code: `RUSH-${prev.length + 101}`,
        release_time_minutes: baselineClock,
        due_date_minutes: baselineClock + 90,
        tardiness_weight: 5,
        operations: [{ sequence_index: 1, machine_id: machines[0]?.id || '', processing_minutes: 25 }],
      },
    ]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError('Scenario name is required.');
      return;
    }
    if (!baselineScheduleId) {
      setError('A baseline schedule must be selected.');
      return;
    }

    const delta: DisruptionDelta = {
      added_downtimes: disruptionType === 'URGENT_ORDER' ? [] : downtimes,
      added_orders: disruptionType === 'MACHINE_DOWNTIME' ? [] : rushOrders,
    };

    try {
      setSubmitting(true);
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        baseline_schedule_id: baselineScheduleId,
        disruption_type: disruptionType,
        disruption_delta: delta,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to create scenario.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: '1rem',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-lg)',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
        }}
      >
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
          <h2 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Branch Disruption Scenario
          </h2>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Simulate downtime outages and rush orders against an immutable baseline solution.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {error && (
            <div style={{ padding: '0.75rem', backgroundColor: '#451a1a', border: '1px solid #dc2626', borderRadius: 'var(--radius-md)', color: '#fca5a5', fontSize: '0.8125rem' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Scenario Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. M1 Breakdown Recovery Simulation"
              required
              style={{
                width: '100%',
                padding: '0.5rem 0.75rem',
                backgroundColor: 'var(--bg-app)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '0.875rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Description (Optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Emergency lathe outage during shift 1"
              style={{
                width: '100%',
                padding: '0.5rem 0.75rem',
                backgroundColor: 'var(--bg-app)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '0.875rem',
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Baseline Schedule *
              </label>
              <select
                value={baselineScheduleId}
                onChange={(e) => setBaselineScheduleId(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  backgroundColor: 'var(--bg-app)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem',
                }}
              >
                {schedules.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.solver_status}, Cmax: {s.makespan_minutes}m{s.current_time_minute ? `, Clock: ${s.current_time_minute}m` : ''})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Disruption Type
              </label>
              <select
                value={disruptionType}
                onChange={(e) => setDisruptionType(e.target.value as any)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  backgroundColor: 'var(--bg-app)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem',
                }}
              >
                <option value="MACHINE_DOWNTIME">Machine Downtime Outage</option>
                <option value="URGENT_ORDER">Urgent Rush Order</option>
                <option value="COMBINED">Combined (Outage + Rush Order)</option>
              </select>
            </div>
          </div>

          {(disruptionType === 'MACHINE_DOWNTIME' || disruptionType === 'COMBINED') && (
            <DowntimeDisruptionForm
              machines={machines}
              downtimes={downtimes}
              onAdd={handleAddDowntime}
              onRemove={handleRemoveDowntime}
              onUpdate={handleUpdateDowntime}
            />
          )}

          {(disruptionType === 'URGENT_ORDER' || disruptionType === 'COMBINED') && (
            <RushOrderDisruptionForm
              machines={machines}
              rushOrders={rushOrders}
              onAdd={handleAddRushOrder}
              onRemove={(idx) => setRushOrders((prev) => prev.filter((_, i) => i !== idx))}
              onUpdate={(idx, updated) => setRushOrders((prev) => prev.map((item, i) => (i === idx ? updated : item)))}
            />
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
            <Button type="button" variant="secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Branching...' : 'Create Scenario'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
