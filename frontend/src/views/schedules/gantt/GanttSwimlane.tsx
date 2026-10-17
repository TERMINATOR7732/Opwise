/**
 * Machine swimlane rendering machine metadata, downtime intervals, and operation blocks.
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.4.
 */

import React from 'react';
import { DowntimeResponse, ScheduledOperationResponse } from '../../../types/api';
import { getOrderColor, timeToPixel } from './ganttUtils';

export interface GanttSwimlaneProps {
  machineId: string;
  machineName: string;
  operations: ScheduledOperationResponse[];
  downtimes: DowntimeResponse[];
  ticks: number[];
  scale: number;
  timelineWidth: number;
  labelColumnWidth: number;
  selectedOperationId: string | null;
  onSelectOperation: (op: ScheduledOperationResponse) => void;
  isEvenRow: boolean;
}

export function GanttSwimlane({
  machineId,
  machineName,
  operations,
  downtimes,
  ticks,
  scale,
  timelineWidth,
  labelColumnWidth,
  selectedOperationId,
  onSelectOperation,
  isEvenRow,
}: GanttSwimlaneProps): React.ReactElement {
  const laneHeight = 56;
  const opHeight = 36;
  const opY = (laneHeight - opHeight) / 2;

  const totalBusy = operations.reduce((sum, op) => sum + Math.max(op.duration, 0), 0);

  return (
    <div
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        backgroundColor: isEvenRow ? 'transparent' : 'var(--bg-app)',
        minHeight: `${laneHeight}px`,
      }}
    >
      {/* Machine label column */}
      <div
        style={{
          width: `${labelColumnWidth}px`,
          minWidth: `${labelColumnWidth}px`,
          padding: '0.5rem 0.75rem',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          backgroundColor: isEvenRow ? 'transparent' : 'var(--bg-app)',
        }}
      >
        <span
          style={{
            fontWeight: 600,
            fontSize: '0.8125rem',
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={machineName}
        >
          {machineName}
        </span>
        <div style={{ display: 'flex', gap: '0.375rem', alignItems: 'center', marginTop: '0.125rem' }}>
          <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--color-primary)' }}>
            {machineId}
          </span>
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
            · {operations.length} ops ({totalBusy}m)
          </span>
        </div>
      </div>

      {/* Swimlane SVG canvas */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <svg
          width={timelineWidth}
          height={laneHeight}
          style={{ display: 'block' }}
          role="region"
          aria-label={`Swimlane for ${machineName}`}
        >
          {/* Vertical grid lines */}
          {ticks.map((tick) => {
            const x = timeToPixel(tick, scale);
            return (
              <line
                key={`grid-${tick}`}
                x1={x}
                y1={0}
                x2={x}
                y2={laneHeight}
                stroke="var(--border-subtle)"
                strokeWidth={1}
                strokeDasharray="2 4"
              />
            );
          })}

          {/* Downtime intervals */}
          {downtimes.map((dt) => {
            const dtX = timeToPixel(dt.start_minute, scale);
            const dtWidth = Math.max(timeToPixel(dt.end_minute - dt.start_minute, scale), 4);
            const dtTitle = `Maintenance Downtime: [${dt.start_minute}, ${dt.end_minute})m (${dt.end_minute - dt.start_minute}m)${dt.reason ? ` — ${dt.reason}` : ''}`;
            return (
              <g key={`dt-${dt.id || dt.start_minute}`} transform={`translate(${dtX}, 4)`}>
                <title>{dtTitle}</title>
                <rect
                  width={dtWidth}
                  height={laneHeight - 8}
                  rx={3}
                  fill="url(#downtime-stripe-pattern)"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  opacity={0.85}
                />
                {dtWidth >= 32 && (
                  <text
                    x={dtWidth / 2}
                    y={(laneHeight - 8) / 2 + 3}
                    textAnchor="middle"
                    fill="#fef3c7"
                    fontSize={dtWidth >= 55 ? 10 : 9}
                    fontWeight={600}
                    style={{ pointerEvents: 'none' }}
                  >
                    {dtWidth >= 55 ? 'MAINTENANCE' : 'MAINT'}
                  </text>
                )}

              </g>
            );
          })}

          {/* Operation blocks */}
          {operations.map((op) => {
            const opX = timeToPixel(op.start_minute, scale);
            const opWidth = Math.max(timeToPixel(op.duration, scale), 6);
            const isSelected = op.operation_id === selectedOperationId;
            const colors = getOrderColor(op.order_id);
            const opTitle = `Order: ${op.order_id}\nOperation: ${op.operation_id}\nSequence Step: #${op.sequence_index}\nMachine: ${op.machine_id}\nWindow: [${op.start_minute}, ${op.end_minute})m\nDuration: ${op.duration}m\nSlack: ${op.slack_minutes}m`;

            return (
              <g
                key={`op-${op.operation_id || `${op.order_id}-${op.sequence_index}`}`}
                transform={`translate(${opX}, ${opY})`}
                onClick={() => onSelectOperation(op)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectOperation(op);
                  }
                }}
                tabIndex={0}
                role="button"
                aria-label={`Select operation for ${op.order_id} on ${machineName}`}
                aria-pressed={isSelected}
                style={{ cursor: 'pointer', outline: 'none' }}
              >
                <title>{opTitle}</title>
                <rect
                  width={opWidth}
                  height={opHeight}
                  rx={4}
                  fill={colors.bg}
                  stroke={isSelected ? '#38bdf8' : colors.border}
                  strokeWidth={isSelected ? 3 : 1.5}
                  filter={isSelected ? 'drop-shadow(0 0 4px rgba(56, 189, 248, 0.6))' : undefined}
                />
                {/* Labels if space permits */}
                {opWidth >= 44 ? (
                  <text
                    x={6}
                    y={opHeight / 2 + 4}
                    fill={colors.text}
                    fontSize={opWidth >= 60 ? 11 : 9.5}
                    fontWeight={600}
                    fontFamily="monospace"
                    style={{ pointerEvents: 'none' }}
                  >
                    {op.order_id} #{op.sequence_index}
                  </text>
                ) : opWidth >= 24 ? (
                  <text
                    x={opWidth / 2}
                    y={opHeight / 2 + 4}
                    fill={colors.text}
                    fontSize={10}
                    fontWeight={600}
                    fontFamily="monospace"
                    textAnchor="middle"
                    style={{ pointerEvents: 'none' }}
                  >
                    #{op.sequence_index}
                  </text>
                ) : null}

              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
