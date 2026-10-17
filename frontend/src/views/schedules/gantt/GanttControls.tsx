/**
 * Gantt navigation toolbar: Zoom In, Zoom Out, Reset, and Fit-to-Schedule.
 * Governed by DATA_AND_API.md Section 3.4.
 */

import React from 'react';
import { Button } from '../../../components/common/Button';

export interface GanttControlsProps {
  scale: number;
  minScale: number;
  maxScale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  onFitSchedule: () => void;
}

export function GanttControls({
  scale,
  minScale,
  maxScale,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  onFitSchedule,
}: GanttControlsProps): React.ReactElement {
  const zoomPct = Math.round((scale / 2.0) * 100);

  return (
    <div
      role="toolbar"
      aria-label="Gantt chart timeline navigation controls"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.5rem 0.75rem',
        backgroundColor: 'var(--bg-app)',
        borderBottom: '1px solid var(--border-subtle)',
        fontSize: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
        <span style={{ color: 'var(--text-secondary)', marginRight: '0.25rem', fontWeight: 500 }}>
          Timeline Zoom:
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={onZoomOut}
          disabled={scale <= minScale}
          aria-label="Zoom out timeline"
        >
          − Zoom Out
        </Button>
        <span
          className="font-mono"
          style={{
            padding: '0.25rem 0.5rem',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            minWidth: '70px',
            textAlign: 'center',
            color: 'var(--text-primary)',
          }}
          aria-live="polite"
        >
          {zoomPct}% ({scale.toFixed(1)}x)
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={onZoomIn}
          disabled={scale >= maxScale}
          aria-label="Zoom in timeline"
        >
          + Zoom In
        </Button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Button
          variant="secondary"
          size="sm"
          onClick={onResetZoom}
          aria-label="Reset zoom to default scale"
        >
          Reset (100%)
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={onFitSchedule}
          aria-label="Fit entire schedule to screen width"
        >
          Fit to Screen
        </Button>
      </div>
    </div>
  );
}
