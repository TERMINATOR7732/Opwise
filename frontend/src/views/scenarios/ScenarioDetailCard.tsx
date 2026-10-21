/**
 * Card displaying scenario configuration, disruption delta parameters, and reoptimization triggers.
 * Governed by SPECIFICATION.md Section 6 and PROJECT_RULES.md.
 */

import React from 'react';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ScenarioResponse } from '../../types/scenarios';
import { isDemoMode } from '../../demo/demoService';

interface ScenarioDetailCardProps {
  scenario: ScenarioResponse;
  baselineName?: string;
  isReoptimizing: boolean;
  onReoptimize: () => void;
  onDelete: () => void;
  onSelectRecoverySchedule?: (scheduleId: string) => void;
}

export function ScenarioDetailCard({
  scenario,
  baselineName,
  isReoptimizing,
  onReoptimize,
  onDelete,
  onSelectRecoverySchedule,
}: ScenarioDetailCardProps): React.ReactElement {
  const { disruption_delta, disruption_type } = scenario;
  const hasRecovery = Boolean(scenario.reoptimized_schedule_id);

  return (
    <Card
      title={scenario.name}
      subtitle={scenario.description || 'Isolated disruption simulation branch'}
      actions={
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <Button
            variant="primary"
            size="sm"
            onClick={onReoptimize}
            disabled={isReoptimizing}
          >
            {isReoptimizing ? 'Reoptimizing CP-SAT...' : hasRecovery ? 'Re-run Reoptimization' : '⚡ Reoptimize Scenario'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={onDelete}
            disabled={isReoptimizing}
            style={{ color: '#ef4444' }}
          >
            Delete
          </Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Scenario metadata banner */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
            padding: '0.875rem 1rem',
            backgroundColor: 'var(--bg-app)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Disruption Type
            </span>
            <div style={{ marginTop: '0.25rem' }}>
              <Badge variant="warning">{disruption_type.replace('_', ' ')}</Badge>
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Baseline Schedule
            </span>
            <div style={{ marginTop: '0.25rem', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-primary)' }}>
              {baselineName || scenario.baseline_schedule_id.slice(0, 8)} (Locked)
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Recovery Plan Status
            </span>
            <div style={{ marginTop: '0.25rem' }}>
              {hasRecovery ? (
                scenario.comparison?.unlike_comparison_warning ? (
                  <Badge variant="warning">DEMO SIMULATION</Badge>
                ) : (
                  <Badge variant="optimal">
                    {isDemoMode() ? 'PRECOMPUTED CP-SAT (READY)' : 'REOPTIMIZED (READY)'}
                  </Badge>
                )
              ) : (
                <Badge variant="neutral">NOT SOLVED YET</Badge>
              )}
            </div>
          </div>
        </div>

        {/* Disruption details section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {disruption_delta.added_downtimes && disruption_delta.added_downtimes.length > 0 && (
            <div>
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Injected Machine Downtime Windows ({disruption_delta.added_downtimes.length})
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                {disruption_delta.added_downtimes.map((dt, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '0.5rem 0.75rem',
                      backgroundColor: 'var(--bg-app)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '0.8125rem',
                    }}
                  >
                    <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      Machine: <code className="font-mono">{dt.machine_id}</code>
                    </span>
                    <span style={{ color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                      t = [{dt.start_minute}m → {dt.end_minute}m] ({dt.end_minute - dt.start_minute}m duration)
                    </span>
                    {dt.reason && (
                      <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.75rem' }}>
                        {dt.reason}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {disruption_delta.added_orders && disruption_delta.added_orders.length > 0 && (
            <div>
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Injected Rush Orders ({disruption_delta.added_orders.length})
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {disruption_delta.added_orders.map((ord, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '0.625rem 0.75rem',
                      backgroundColor: 'var(--bg-app)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '0.8125rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
                      <span style={{ fontWeight: 600, color: '#f59e0b' }}>
                        Order: {ord.order_code}
                      </span>
                      <span style={{ color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
                        Release: {ord.release_time_minutes}m | Due: {ord.due_date_minutes}m | Weight: {ord.tardiness_weight}x
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {ord.operations.map((op, oIdx) => (
                        <div
                          key={oIdx}
                          style={{
                            padding: '0.25rem 0.5rem',
                            backgroundColor: 'var(--bg-card)',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-default)',
                            fontSize: '0.75rem',
                            fontFamily: 'JetBrains Mono, monospace',
                          }}
                        >
                          Step {op.sequence_index}: {op.machine_id} ({op.processing_minutes}m)
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Reoptimized schedule link if available */}
        {hasRecovery && onSelectRecoverySchedule && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onSelectRecoverySchedule(scenario.reoptimized_schedule_id!)}
            >
              Inspect Recovery Schedule in Schedule View →
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
