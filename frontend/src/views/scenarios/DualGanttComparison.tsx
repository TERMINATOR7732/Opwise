/**
 * Side-by-side or stacked dual Gantt schedule comparator canvas.
 * Governed by SPECIFICATION.md Section 6.3, Section 8.1, and PROJECT_RULES.md.
 */

import React, { useState } from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { ScheduleDetailResponse } from '../../types/api';
import { GanttChart } from '../schedules/gantt/GanttChart';

interface DualGanttComparisonProps {
  baselineSchedule: ScheduleDetailResponse;
  recoverySchedule?: ScheduleDetailResponse | null;
}

export function DualGanttComparison({
  baselineSchedule,
  recoverySchedule,
}: DualGanttComparisonProps): React.ReactElement {
  const [viewMode, setViewMode] = useState<'STACKED' | 'BASELINE' | 'RECOVERY'>('STACKED');

  return (
    <Card
      title="Interactive Dual Schedule Comparator"
      subtitle="Visual timeline divergence inspection between baseline solution and recovery schedule"
      actions={
        recoverySchedule ? (
          <div style={{ display: 'flex', gap: '0.375rem' }}>
            <button
              type="button"
              onClick={() => setViewMode('STACKED')}
              style={{
                padding: '0.375rem 0.625rem',
                fontSize: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid',
                cursor: 'pointer',
                backgroundColor: viewMode === 'STACKED' ? 'var(--accent-primary)' : 'var(--bg-app)',
                borderColor: viewMode === 'STACKED' ? 'var(--accent-primary)' : 'var(--border-default)',
                color: viewMode === 'STACKED' ? '#ffffff' : 'var(--text-secondary)',
              }}
            >
              Stacked Dual View
            </button>
            <button
              type="button"
              onClick={() => setViewMode('BASELINE')}
              style={{
                padding: '0.375rem 0.625rem',
                fontSize: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid',
                cursor: 'pointer',
                backgroundColor: viewMode === 'BASELINE' ? 'var(--accent-primary)' : 'var(--bg-app)',
                borderColor: viewMode === 'BASELINE' ? 'var(--accent-primary)' : 'var(--border-default)',
                color: viewMode === 'BASELINE' ? '#ffffff' : 'var(--text-secondary)',
              }}
            >
              Baseline Only
            </button>
            <button
              type="button"
              onClick={() => setViewMode('RECOVERY')}
              style={{
                padding: '0.375rem 0.625rem',
                fontSize: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid',
                cursor: 'pointer',
                backgroundColor: viewMode === 'RECOVERY' ? 'var(--accent-primary)' : 'var(--bg-app)',
                borderColor: viewMode === 'RECOVERY' ? 'var(--accent-primary)' : 'var(--border-default)',
                color: viewMode === 'RECOVERY' ? '#ffffff' : 'var(--text-secondary)',
              }}
            >
              Recovery Only
            </button>
          </div>
        ) : undefined
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Baseline Gantt */}
        {(viewMode === 'STACKED' || viewMode === 'BASELINE') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Baseline Schedule: {baselineSchedule.name}
              </span>
              <Badge variant="neutral">IMMUTABLE BASELINE</Badge>
              {baselineSchedule.current_time_minute !== undefined && baselineSchedule.current_time_minute > 0 && (
                <Badge variant="warning">CLOCK t₀ = {baselineSchedule.current_time_minute}m</Badge>
              )}
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                Cmax: {baselineSchedule.metrics.makespan_minutes}m · Obj ({baselineSchedule.objective_type === 'PURE_WEIGHTED_TARDINESS' ? 'Tardiness' : 'Makespan'}): {baselineSchedule.objective_type === 'PURE_WEIGHTED_TARDINESS' ? baselineSchedule.metrics.weighted_tardiness : `${baselineSchedule.metrics.makespan_minutes}m`}
              </span>
            </div>
            <GanttChart
              scheduleId={baselineSchedule.id}
              scheduleName={baselineSchedule.name}
              solverStatus={baselineSchedule.solver_status}
              verificationStatus={baselineSchedule.verification_status}
              makespanMinutes={baselineSchedule.metrics.makespan_minutes}
              operations={baselineSchedule.scheduled_operations}
              downtimes={baselineSchedule.downtimes}
              machines={baselineSchedule.machines}
              currentTimeMinute={baselineSchedule.current_time_minute}
            />
          </div>
        )}

        {/* Divider if stacked */}
        {viewMode === 'STACKED' && recoverySchedule && (
          <div style={{ height: '1px', backgroundColor: 'var(--border-subtle)' }} />
        )}

        {/* Recovery Gantt */}
        {(viewMode === 'STACKED' || viewMode === 'RECOVERY') && recoverySchedule && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Recovery Schedule: {recoverySchedule.name}
              </span>
              {recoverySchedule.solver_status === 'OPTIMAL' ? (
                <Badge variant="optimal">CP-SAT REOPTIMIZED</Badge>
              ) : (
                <Badge variant="warning">DEMO SIMULATION</Badge>
              )}
              {recoverySchedule.current_time_minute !== undefined && recoverySchedule.current_time_minute > 0 && (
                <Badge variant="warning">CLOCK t₀ = {recoverySchedule.current_time_minute}m</Badge>
              )}
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                Cmax: {recoverySchedule.metrics.makespan_minutes}m · Obj ({recoverySchedule.objective_type === 'PURE_WEIGHTED_TARDINESS' ? 'Tardiness' : 'Makespan'}): {recoverySchedule.objective_type === 'PURE_WEIGHTED_TARDINESS' ? recoverySchedule.metrics.weighted_tardiness : `${recoverySchedule.metrics.makespan_minutes}m`}
              </span>
            </div>
            {recoverySchedule.solver_status === 'DEMO_SIMULATION' && (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  backgroundColor: '#451a03',
                  border: '1px solid #d97706',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.8125rem',
                  color: '#fef3c7',
                  lineHeight: 1.4,
                }}
              >
                ⚠️ <strong>Client Demo Simulation:</strong> This recovery schedule was generated by an in-browser heuristic time-shift for demonstration purposes. No backend CP-SAT solver was executed.
              </div>
            )}
            <GanttChart
              scheduleId={recoverySchedule.id}
              scheduleName={recoverySchedule.name}
              solverStatus={recoverySchedule.solver_status}
              verificationStatus={recoverySchedule.verification_status}
              makespanMinutes={recoverySchedule.metrics.makespan_minutes}
              operations={recoverySchedule.scheduled_operations}
              downtimes={recoverySchedule.downtimes}
              machines={recoverySchedule.machines}
              currentTimeMinute={recoverySchedule.current_time_minute}
            />
          </div>
        )}

        {/* Placeholder if recovery schedule not yet solved */}
        {!recoverySchedule && (
          <div
            style={{
              padding: '2rem',
              backgroundColor: 'var(--bg-app)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-default)',
              textAlign: 'center',
              color: 'var(--text-secondary)',
              fontSize: '0.875rem',
            }}
          >
            Click <strong style={{ color: 'var(--text-primary)' }}>"⚡ Reoptimize Scenario"</strong> above to compute the recovery plan and view the comparison Gantt timeline.
          </div>
        )}
      </div>
    </Card>
  );
}
