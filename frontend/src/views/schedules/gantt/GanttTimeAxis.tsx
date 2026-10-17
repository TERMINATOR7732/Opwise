/**
 * Time axis ruler header with tick marks and formatted minute labels.
 * Governed by SPECIFICATION.md Section 4.
 */

import React from 'react';
import { formatTimeMinutes, timeToPixel } from './ganttUtils';

export interface GanttTimeAxisProps {
  ticks: number[];
  scale: number;
  timelineWidth: number;
  labelColumnWidth: number;
}

export function GanttTimeAxis({
  ticks,
  scale,
  timelineWidth,
  labelColumnWidth,
}: GanttTimeAxisProps): React.ReactElement {
  const headerHeight = 32;

  return (
    <div
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        backgroundColor: 'var(--bg-app)',
        position: 'sticky',
        top: 0,
        zIndex: 5,
      }}
    >
      {/* Fixed machine label header */}
      <div
        style={{
          width: `${labelColumnWidth}px`,
          minWidth: `${labelColumnWidth}px`,
          padding: '0.4rem 0.75rem',
          fontWeight: 600,
          fontSize: '0.75rem',
          color: 'var(--text-secondary)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          backgroundColor: 'var(--bg-app)',
        }}
      >
        Workstation Lane
      </div>

      {/* SVG Time Axis Ruler */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <svg
          width={timelineWidth}
          height={headerHeight}
          style={{ display: 'block' }}
          aria-label="Timeline time axis"
        >
          {ticks.map((tick) => {
            const x = timeToPixel(tick, scale);
            return (
              <g key={`tick-${tick}`} transform={`translate(${x}, 0)`}>
                {/* Tick mark tick line */}
                <line
                  x1={0}
                  y1={headerHeight - 8}
                  x2={0}
                  y2={headerHeight}
                  stroke="var(--border-strong)"
                  strokeWidth={1}
                />
                {/* Tick label */}
                <text
                  x={4}
                  y={headerHeight - 12}
                  fontSize={10}
                  fill="var(--text-secondary)"
                  fontFamily="monospace"
                  textAnchor="start"
                >
                  {formatTimeMinutes(tick)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
