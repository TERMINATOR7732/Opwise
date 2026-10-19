/**
 * Interactive SVG Gantt Schedule Visualization Canvas
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.4.
 */

import React, { useState, useRef, useMemo } from 'react';
import { Badge } from '../../../components/common/Badge';
import { DowntimeResponse, ScheduledOperationResponse } from '../../../types/api';
import {
  calculateMachineUtilization,
  calculateTimeTicks,
  MachineDescriptor,
  timeToPixel,
} from './ganttUtils';
import { GanttControls } from './GanttControls';
import { GanttTimeAxis } from './GanttTimeAxis';
import { GanttSwimlane } from './GanttSwimlane';
import { GanttOperationDetail } from './GanttOperationDetail';
import { GanttBottleneckCard } from './GanttBottleneckCard';

export interface GanttChartProps {
  scheduleId: string;
  scheduleName: string;
  solverStatus: string;
  verificationStatus: string;
  makespanMinutes: number;
  operations: ScheduledOperationResponse[];
  downtimes?: DowntimeResponse[];
  machines?: MachineDescriptor[];
  currentTimeMinute?: number;
}

const DEFAULT_SCALE = 2.0; // 2 pixels per minute
const MIN_SCALE = 0.4;
const MAX_SCALE = 8.0;
const LABEL_WIDTH = 170;

export function GanttChart({
  scheduleName,
  solverStatus,
  verificationStatus,
  makespanMinutes,
  operations,
  downtimes = [],
  machines = [],
  currentTimeMinute,
}: GanttChartProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState<number>(DEFAULT_SCALE);
  const [selectedOp, setSelectedOp] = useState<ScheduledOperationResponse | null>(null);

  // Derive complete machine list from snapshot or scheduled operations
  const activeMachines = useMemo<MachineDescriptor[]>(() => {
    if (machines.length > 0) return machines;
    const seen = new Set<string>();
    const list: MachineDescriptor[] = [];
    for (const op of operations) {
      if (!seen.has(op.machine_id)) {
        seen.add(op.machine_id);
        list.push({ id: op.machine_id, name: `Workstation ${op.machine_id}` });
      }
    }
    return list.sort((a, b) => a.id.localeCompare(b.id));
  }, [machines, operations]);

  // Calculate timeline bounds and ticks
  const maxMinute = useMemo(() => {
    let max = makespanMinutes;
    if (currentTimeMinute !== undefined) max = Math.max(max, currentTimeMinute);
    for (const op of operations) max = Math.max(max, op.end_minute);
    for (const dt of downtimes) max = Math.max(max, dt.end_minute);
    return Math.max(max, 60);
  }, [makespanMinutes, currentTimeMinute, operations, downtimes]);

  const ticks = useMemo(() => calculateTimeTicks(maxMinute, scale), [maxMinute, scale]);
  const timelineWidth = Math.max(timeToPixel(maxMinute, scale) + 80, 600);

  // Machine utilization & bottleneck analysis
  const { utilizations, bottleneck } = useMemo(
    () => calculateMachineUtilization(activeMachines, operations, makespanMinutes),
    [activeMachines, operations, makespanMinutes]
  );

  const handleZoomIn = () => setScale((s) => Math.min(Number((s * 1.35).toFixed(2)), MAX_SCALE));
  const handleZoomOut = () => setScale((s) => Math.max(Number((s / 1.35).toFixed(2)), MIN_SCALE));
  const handleResetZoom = () => setScale(DEFAULT_SCALE);
  const handleFitSchedule = () => {
    if (!containerRef.current) return;
    const availWidth = containerRef.current.clientWidth - LABEL_WIDTH - 40;
    if (availWidth > 100 && maxMinute > 0) {
      const fit = Math.min(Math.max(availWidth / maxMinute, MIN_SCALE), MAX_SCALE);
      setScale(Number(fit.toFixed(2)));
    }
  };

  const isOptimal = solverStatus === 'OPTIMAL';
  const isVerified = verificationStatus === 'VERIFIED';
  const solverBadgeVariant = isOptimal ? 'optimal' : solverStatus === 'FEASIBLE' ? 'warning' : 'critical';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}
    >
      {/* SVG Pattern Definition */}
      <svg width={0} height={0} style={{ position: 'absolute' }}>
        <defs>
          <pattern
            id="downtime-stripe-pattern"
            width={10}
            height={10}
            patternTransform="rotate(45 0 0)"
            patternUnits="userSpaceOnUse"
          >
            <rect width={5} height={10} fill="#78350f" opacity={0.65} />
            <rect x={5} width={5} height={10} fill="#f59e0b" opacity={0.9} />
          </pattern>
        </defs>
      </svg>

      {/* Header bar with solver and verification status */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.75rem 1rem',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-app)',
        }}
      >
        <div>
          <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>
            Production Schedule Timeline: {scheduleName}
          </strong>
          <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {activeMachines.length} Workstations · {operations.length} Operations · Makespan: {makespanMinutes}m
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {currentTimeMinute !== undefined && currentTimeMinute > 0 && (
            <Badge variant="warning" className="font-mono">
              PLANT CLOCK: {currentTimeMinute}m
            </Badge>
          )}
          <Badge variant={solverBadgeVariant} className="font-mono">
            {isOptimal ? 'CP-SAT OPTIMAL' : solverStatus}
          </Badge>
          <Badge variant={isVerified ? 'optimal' : 'critical'} className="font-mono">
            {verificationStatus}
          </Badge>
        </div>
      </div>

      {/* Navigation Controls */}
      <GanttControls
        scale={scale}
        minScale={MIN_SCALE}
        maxScale={MAX_SCALE}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetZoom={handleResetZoom}
        onFitSchedule={handleFitSchedule}
      />

      {/* Selected Operation Detail Drawer */}
      {selectedOp && (
        <div style={{ padding: '0 1rem' }}>
          <GanttOperationDetail
            operation={selectedOp}
            machineName={activeMachines.find((m) => m.id === selectedOp.machine_id)?.name}
            onClose={() => setSelectedOp(null)}
          />
        </div>
      )}

      {/* Main Gantt Canvas Container */}
      <div
        ref={containerRef}
        style={{
          overflowX: 'auto',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-card)',
        }}
        tabIndex={0}
        aria-label="Interactive Gantt schedule timeline"
      >
        <div style={{ minWidth: `${LABEL_WIDTH + timelineWidth}px` }}>
          <GanttTimeAxis
            ticks={ticks}
            scale={scale}
            timelineWidth={timelineWidth}
            labelColumnWidth={LABEL_WIDTH}
            currentTimeMinute={currentTimeMinute}
          />

          {activeMachines.length === 0 || (operations.length === 0 && downtimes.length === 0) ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              {solverStatus === 'INFEASIBLE'
                ? 'Model Proven Infeasible — No valid timeline allocations exist for these constraints.'
                : solverStatus === 'NO_WORK_STATE'
                ? 'No Work to Schedule — Configure production orders in the workspace to generate timeline allocations.'
                : 'No operations or maintenance intervals recorded for this schedule.'}
            </div>
          ) : (
            activeMachines.map((m, index) => {
              const machineOps = operations.filter((op) => op.machine_id === m.id);
              const machineDts = downtimes.filter((dt) => dt.machine_id === m.id);
              return (
                <GanttSwimlane
                  key={m.id}
                  machineId={m.id}
                  machineName={m.name}
                  operations={machineOps}
                  downtimes={machineDts}
                  ticks={ticks}
                  scale={scale}
                  timelineWidth={timelineWidth}
                  labelColumnWidth={LABEL_WIDTH}
                  currentTimeMinute={currentTimeMinute}
                  selectedOperationId={selectedOp?.operation_id || null}
                  onSelectOperation={(op) => setSelectedOp(op)}
                  isEvenRow={index % 2 === 0}
                />
              );
            })
          )}
        </div>
      </div>

      {/* Bottleneck and utilization context */}
      {activeMachines.length > 0 && makespanMinutes > 0 && (
        <div style={{ padding: '0 1rem 0.75rem 1rem' }}>
          <GanttBottleneckCard
            utilizations={utilizations}
            bottleneck={bottleneck}
            makespanMinutes={makespanMinutes}
          />
        </div>
      )}
    </div>
  );
}
