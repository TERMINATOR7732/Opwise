/**
 * Bottleneck analysis and workstation utilization context card.
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.4.
 */

import React from 'react';
import { Badge } from '../../../components/common/Badge';
import { MachineUtilization } from './ganttUtils';

export interface GanttBottleneckCardProps {
  utilizations: MachineUtilization[];
  bottleneck: MachineUtilization | null;
  makespanMinutes: number;
}

export function GanttBottleneckCard({
  utilizations,
  bottleneck,
  makespanMinutes,
}: GanttBottleneckCardProps): React.ReactElement {
  return (
    <div
      style={{
        padding: '0.75rem 1rem',
        backgroundColor: 'var(--bg-app)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.625rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong style={{ fontSize: '0.8125rem', color: 'var(--text-primary)' }}>
          Workstation Utilization & Bottleneck Context
        </strong>
        {bottleneck && bottleneck.busy_minutes > 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Critical Bottleneck:</span>
            <Badge variant="warning" className="font-mono">
              {bottleneck.machine_name} ({bottleneck.machine_id}) · {bottleneck.utilization_pct}%
            </Badge>
          </div>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No bottleneck detected</span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
        {utilizations.map((u) => {
          const isBottleneck = bottleneck?.machine_id === u.machine_id && u.busy_minutes > 0;
          return (
            <div
              key={u.machine_id}
              style={{
                display: 'grid',
                gridTemplateColumns: '150px 1fr 100px',
                alignItems: 'center',
                gap: '0.75rem',
                fontSize: '0.75rem',
              }}
            >
              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{u.machine_name}</span>{' '}
                <span className="font-mono" style={{ color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
                  ({u.machine_id})
                </span>
              </div>

              {/* Progress track */}
              <div
                style={{
                  height: '8px',
                  backgroundColor: 'var(--bg-card)',
                  borderRadius: '4px',
                  overflow: 'hidden',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(u.utilization_pct, 100)}%`,
                    backgroundColor: isBottleneck ? 'var(--color-warning)' : 'var(--color-primary)',
                    borderRadius: '3px',
                    transition: 'width 0.2s ease',
                  }}
                />
              </div>

              <div style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                <strong style={{ color: isBottleneck ? 'var(--color-warning)' : 'var(--text-primary)' }}>
                  {u.utilization_pct.toFixed(1)}%
                </strong>{' '}
                <span style={{ color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
                  ({u.busy_minutes}m/{makespanMinutes}m)
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
