/**
 * Card displaying mathematical comparison deltas, unlike warnings, and operation divergences.
 * Governed by SPECIFICATION.md Section 6.3 and DATA_AND_API.md Section 1.1 (Table 9).
 */

import React, { useState } from 'react';
import { Badge } from '../../components/common/Badge';
import { Card } from '../../components/common/Card';
import { OperationDivergence, ScenarioComparisonResponse } from '../../types/scenarios';

interface ScenarioComparisonCardProps {
  comparison: ScenarioComparisonResponse;
}

export function ScenarioComparisonCard({ comparison }: ScenarioComparisonCardProps): React.ReactElement {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const filteredDivergences = comparison.diverged_operations.filter((op) => {
    if (statusFilter === 'ALL') return true;
    return op.status === statusFilter;
  });

  const getStatusBadge = (status: OperationDivergence['status']) => {
    switch (status) {
      case 'DELAYED':
        return <Badge variant="warning">DELAYED</Badge>;
      case 'EXPEDITED':
        return <Badge variant="optimal">EXPEDITED</Badge>;
      case 'NEW_RUSH_OPERATION':
        return <Badge variant="neutral">RUSH OP</Badge>;
      case 'REMOVED':
        return <Badge variant="critical">REMOVED</Badge>;
      default:
        return <Badge variant="neutral">UNMODIFIED</Badge>;
    }
  };

  const formatDelta = (val: number, unit = '') => {
    const prefix = val > 0 ? '+' : '';
    return `${prefix}${val}${unit}`;
  };

  return (
    <Card
      title="Recovery Schedule Comparison & Impact Analysis"
      subtitle="Exact mathematical divergences relative to locked baseline solution"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Metric Deltas Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
          }}
        >
          <div style={{ padding: '0.875rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Makespan Delta (ΔCmax)</span>
            <div
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                fontFamily: 'JetBrains Mono, monospace',
                marginTop: '0.25rem',
                color: comparison.delta_makespan > 0 ? '#f59e0b' : '#10b981',
              }}
            >
              {formatDelta(comparison.delta_makespan, 'm')}
            </div>
          </div>

          <div style={{ padding: '0.875rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Weighted Tardiness (ΔWT)</span>
            <div
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                fontFamily: 'JetBrains Mono, monospace',
                marginTop: '0.25rem',
                color: comparison.delta_weighted_tardiness > 0 ? '#ef4444' : '#10b981',
              }}
            >
              {formatDelta(comparison.delta_weighted_tardiness, ' pts')}
            </div>
          </div>

          <div style={{ padding: '0.875rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Late Orders Delta (ΔNlate)</span>
            <div
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                fontFamily: 'JetBrains Mono, monospace',
                marginTop: '0.25rem',
                color: comparison.delta_late_order_count > 0 ? '#ef4444' : '#10b981',
              }}
            >
              {formatDelta(comparison.delta_late_order_count)}
            </div>
          </div>

          <div style={{ padding: '0.875rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>On-Time Rate Delta</span>
            <div
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                fontFamily: 'JetBrains Mono, monospace',
                marginTop: '0.25rem',
                color: comparison.delta_on_time_rate < 0 ? '#ef4444' : '#10b981',
              }}
            >
              {formatDelta(comparison.delta_on_time_rate, '%')}
            </div>
          </div>
        </div>

        {/* Unlike comparison warning banner */}
        {comparison.unlike_comparison_warning && (
          <div
            style={{
              padding: '1rem',
              backgroundColor: '#451a03',
              border: '1px solid #d97706',
              borderRadius: 'var(--radius-md)',
              color: '#fef3c7',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
              <span style={{ fontSize: '1rem' }}>⚠️</span>
              <strong style={{ fontSize: '0.875rem', color: '#fde68a' }}>Unlike-Results Disclosure:</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', lineHeight: 1.5, color: '#fef3c7' }}>
              {comparison.unlike_comparison_warning}
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
              {comparison.order_set_diff_detected && (
                <Badge variant="warning">STRUCTURAL ORDER SET CHANGE</Badge>
              )}
              {comparison.objective_diff_detected && (
                <Badge variant="warning">OBJECTIVE MODE DIVERGENCE</Badge>
              )}
              {comparison.status_diff_detected && (
                <Badge variant="warning">SOLVER STATUS DIVERGENCE</Badge>
              )}
            </div>
          </div>
        )}

        {/* Operation Divergence Table */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Operation Placement Divergences ({filteredDivergences.length})
            </h4>
            <div style={{ display: 'flex', gap: '0.375rem' }}>
              {['ALL', 'DELAYED', 'EXPEDITED', 'NEW_RUSH_OPERATION', 'UNMODIFIED'].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.6875rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid',
                    cursor: 'pointer',
                    backgroundColor: statusFilter === st ? 'var(--accent-primary)' : 'var(--bg-app)',
                    borderColor: statusFilter === st ? 'var(--accent-primary)' : 'var(--border-default)',
                    color: statusFilter === st ? '#ffffff' : 'var(--text-secondary)',
                  }}
                >
                  {st.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <div style={{ overflowX: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Order</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Step</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Machine</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Baseline Window</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Scenario Window</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Start Delta</th>
                  <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredDivergences.map((div, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      backgroundColor: idx % 2 === 0 ? 'var(--bg-card)' : 'var(--bg-app)',
                    }}
                  >
                    <td style={{ padding: '0.5rem 0.75rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {div.order_id}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'JetBrains Mono, monospace' }}>
                      #{div.sequence_index}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'JetBrains Mono, monospace' }}>
                      {div.machine_id}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>
                      {div.baseline_start !== null ? `[${div.baseline_start}m → ${div.baseline_end}m]` : '—'}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-primary)' }}>
                      [{div.compared_start}m → {div.compared_end}m]
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
                      {typeof div.delta_start_minutes === 'number' ? (
                        <span style={{ color: div.delta_start_minutes > 0 ? '#f59e0b' : div.delta_start_minutes < 0 ? '#10b981' : 'var(--text-muted)' }}>
                          {formatDelta(div.delta_start_minutes, 'm')}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem' }}>{getStatusBadge(div.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Card>
  );
}
