/**
 * Comprehensive tests for Interactive Gantt Schedule Visualization (Milestone 09C)
 * Governed by SPECIFICATION.md Section 4, DATA_AND_API.md Section 3.4, and TEST_AND_RELEASE_PLAN.md.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  calculateMachineUtilization,
  calculateTimeTicks,
  formatTimeMinutes,
  getOrderColor,
  getTickInterval,
  pixelToTime,
  timeToPixel,
} from '../views/schedules/gantt/ganttUtils';
import { GanttControls } from '../views/schedules/gantt/GanttControls';
import { GanttTimeAxis } from '../views/schedules/gantt/GanttTimeAxis';
import { GanttSwimlane } from '../views/schedules/gantt/GanttSwimlane';
import { GanttOperationDetail } from '../views/schedules/gantt/GanttOperationDetail';
import { GanttBottleneckCard } from '../views/schedules/gantt/GanttBottleneckCard';
import { GanttChart } from '../views/schedules/gantt/GanttChart';
import { DowntimeResponse, ScheduledOperationResponse } from '../types/api';

const mockMachines = [
  { id: 'M1', name: '5-Axis CNC Mill' },
  { id: 'M2', name: 'Precision Lathe' },
];

const mockDowntimes: DowntimeResponse[] = [
  { id: 'dt-1', machine_id: 'M1', start_minute: 30, end_minute: 60, reason: 'Calibration' },
];


const mockOperations: ScheduledOperationResponse[] = [
  {
    operation_id: 'op-1',
    order_id: 'ORD-101',
    sequence_index: 1,
    machine_id: 'M1',
    start_minute: 0,
    end_minute: 25,
    duration: 25,
    slack_minutes: 5,
  },
  {
    operation_id: 'op-2',
    order_id: 'ORD-101',
    sequence_index: 2,
    machine_id: 'M2',
    start_minute: 25,
    end_minute: 60,
    duration: 35,
    slack_minutes: 0,
  },
  {
    operation_id: 'op-3',
    order_id: 'ORD-102',
    sequence_index: 1,
    machine_id: 'M1',
    start_minute: 50,
    end_minute: 80,
    duration: 30,
    slack_minutes: 0,
  },
];

describe('Gantt Mathematical & Utility Calculations', () => {
  it('correctly maps time to pixels and handles boundary conditions', () => {
    expect(timeToPixel(0, 2.0)).toBe(0);
    expect(timeToPixel(30, 2.0)).toBe(60);
    expect(timeToPixel(15, 1.5)).toBe(23);
    expect(timeToPixel(-10, 2.0)).toBe(0);
    expect(timeToPixel(NaN, 2.0)).toBe(0);
  });

  it('correctly maps pixels to time and handles invalid scales', () => {
    expect(pixelToTime(100, 2.0)).toBe(50);
    expect(pixelToTime(0, 2.0)).toBe(0);
    expect(pixelToTime(-50, 2.0)).toBe(0);
    expect(pixelToTime(100, 0)).toBe(0);
    expect(pixelToTime(100, -1)).toBe(0);
  });

  it('formats minute values into readable time labels', () => {
    expect(formatTimeMinutes(0)).toBe('0m');
    expect(formatTimeMinutes(45)).toBe('45m');
    expect(formatTimeMinutes(60)).toBe('1h');
    expect(formatTimeMinutes(90)).toBe('1h 30m');
    expect(formatTimeMinutes(155)).toBe('2h 35m');
    expect(formatTimeMinutes(-5)).toBe('0m');
  });

  it('calculates suitable tick spacing for different zoom levels', () => {
    expect(getTickInterval(5.0)).toBe(15);
    expect(getTickInterval(2.0)).toBe(30);
    expect(getTickInterval(1.0)).toBe(60);
    expect(getTickInterval(0.5)).toBe(120);
    expect(getTickInterval(0.2)).toBe(240);

    const ticks = calculateTimeTicks(100, 2.0);
    expect(ticks[0]).toBe(0);
    expect(ticks[1]).toBe(30);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(100);
  });

  it('generates consistent, deterministic color palettes by order ID', () => {
    const c1 = getOrderColor('ORD-101');
    const c2 = getOrderColor('ORD-101');
    const c3 = getOrderColor('ORD-102');
    expect(c1).toEqual(c2);
    expect(c1.bg).toBeDefined();
    expect(c1.text).toBe('#ffffff');
    expect(typeof c3.bg).toBe('string');
  });

  it('calculates machine utilization and evidence-based bottleneck', () => {
    const { utilizations, bottleneck } = calculateMachineUtilization(mockMachines, mockOperations, 80);
    expect(utilizations).toHaveLength(2);

    const m1Util = utilizations.find((u) => u.machine_id === 'M1');
    expect(m1Util?.busy_minutes).toBe(55); // 25 + 30
    expect(m1Util?.operation_count).toBe(2);
    expect(m1Util?.utilization_pct).toBe(68.8); // (55/80) * 100

    const m2Util = utilizations.find((u) => u.machine_id === 'M2');
    expect(m2Util?.busy_minutes).toBe(35);
    expect(m2Util?.operation_count).toBe(1);

    expect(bottleneck).not.toBeNull();
    expect(bottleneck?.machine_id).toBe('M1'); // Highest busy minutes
  });

  it('handles empty operations and zero makespan without divide-by-zero errors', () => {
    const { utilizations, bottleneck } = calculateMachineUtilization(mockMachines, [], 0);
    expect(utilizations).toHaveLength(2);
    expect(utilizations[0].utilization_pct).toBe(0);
    expect(bottleneck).toBeNull();
  });
});

describe('Gantt Subcomponents Rendering', () => {
  it('renders GanttControls with zoom indicators and accessible buttons', () => {
    const markup = renderToStaticMarkup(
      <GanttControls
        scale={2.0}
        minScale={0.4}
        maxScale={8.0}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        onResetZoom={vi.fn()}
        onFitSchedule={vi.fn()}
      />
    );
    expect(markup).toContain('Timeline Zoom:');
    expect(markup).toContain('100% (2.0x)');
    expect(markup).toContain('Zoom In');
    expect(markup).toContain('Zoom Out');
    expect(markup).toContain('Fit to Screen');
    expect(markup).toContain('Reset (100%)');
    expect(markup).toContain('aria-label="Zoom in timeline"');
  });

  it('renders GanttTimeAxis ruler with formatted minute ticks', () => {
    const markup = renderToStaticMarkup(
      <GanttTimeAxis ticks={[0, 30, 60, 90]} scale={2.0} timelineWidth={400} labelColumnWidth={170} />
    );
    expect(markup).toContain('Workstation Lane');
    expect(markup).toContain('0m');
    expect(markup).toContain('30m');
    expect(markup).toContain('1h');
    expect(markup).toContain('1h 30m');
  });

  it('renders GanttSwimlane with machine info, maintenance downtime, and operation blocks', () => {
    const markup = renderToStaticMarkup(
      <GanttSwimlane
        machineId="M1"
        machineName="5-Axis CNC Mill"
        operations={[mockOperations[0], mockOperations[2]]}
        downtimes={mockDowntimes}
        ticks={[0, 30, 60]}
        scale={2.0}
        timelineWidth={400}
        labelColumnWidth={170}
        selectedOperationId={null}
        onSelectOperation={vi.fn()}
        isEvenRow={true}
      />
    );
    expect(markup).toContain('5-Axis CNC Mill');
    expect(markup).toContain('M1');
    expect(markup).toContain('2 ops (55m)');
    expect(markup).toContain('MAINTENANCE');
    expect(markup).toContain('ORD-101 #1');
    expect(markup).toContain('ORD-102 #1');
  });

  it('renders GanttOperationDetail when an operation is selected', () => {
    const markup = renderToStaticMarkup(
      <GanttOperationDetail
        operation={mockOperations[0]}
        machineName="5-Axis CNC Mill"
        onClose={vi.fn()}
      />
    );
    expect(markup).toContain('Operation Allocation Details');
    expect(markup).toContain('ORD-101');
    expect(markup).toContain('op-1');
    expect(markup).toContain('5-Axis CNC Mill (M1)');
    expect(markup).toContain('[0, 25) min');
    expect(markup).toContain('25 min');
    expect(markup).toContain('5 min');
    expect(markup).toContain('Deselect (Esc)');
  });

  it('renders nothing in GanttOperationDetail when operation is null', () => {
    const markup = renderToStaticMarkup(
      <GanttOperationDetail operation={null} onClose={vi.fn()} />
    );
    expect(markup).toBe('');
  });

  it('renders GanttBottleneckCard with utilization progress bars', () => {
    const { utilizations, bottleneck } = calculateMachineUtilization(mockMachines, mockOperations, 80);
    const markup = renderToStaticMarkup(
      <GanttBottleneckCard utilizations={utilizations} bottleneck={bottleneck} makespanMinutes={80} />
    );
    expect(markup).toContain('Workstation Utilization &amp; Bottleneck Context');
    expect(markup).toContain('Critical Bottleneck:');
    expect(markup).toContain('5-Axis CNC Mill (M1) · 68.8%');
    expect(markup).toContain('55m/80m');
  });
});

describe('GanttChart Root Component', () => {
  it('renders full multi-machine schedule with solver disclosures and SVG lanes', () => {
    const markup = renderToStaticMarkup(
      <GanttChart
        scheduleId="sched-1"
        scheduleName="Batch Optimization Alpha"
        solverStatus="OPTIMAL"
        verificationStatus="VERIFIED"
        makespanMinutes={80}
        operations={mockOperations}
        downtimes={mockDowntimes}
        machines={mockMachines}
      />
    );
    expect(markup).toContain('Production Schedule Timeline: Batch Optimization Alpha');
    expect(markup).toContain('CP-SAT OPTIMAL');
    expect(markup).toContain('VERIFIED');
    expect(markup).toContain('2 Workstations · 3 Operations · Makespan: 80m');
    expect(markup).toContain('5-Axis CNC Mill');
    expect(markup).toContain('Precision Lathe');
    expect(markup).toContain('MAINTENANCE');
    expect(markup).toContain('ORD-101');
    expect(markup).toContain('Critical Bottleneck:');
  });

  it('renders empty schedule state without fabricated operation blocks', () => {
    const markup = renderToStaticMarkup(
      <GanttChart
        scheduleId="sched-empty"
        scheduleName="Empty Run"
        solverStatus="NO_WORK_STATE"
        verificationStatus="VERIFIED"
        makespanMinutes={0}
        operations={[]}
        machines={mockMachines}
      />
    );
    expect(markup).toContain('No Work to Schedule');
    expect(markup).toContain('NO_WORK_STATE');
    expect(markup).not.toContain('ORD-101');
  });

  it('renders infeasible model state with appropriate warning banner', () => {
    const markup = renderToStaticMarkup(
      <GanttChart
        scheduleId="sched-infeasible"
        scheduleName="Infeasible Run"
        solverStatus="INFEASIBLE"
        verificationStatus="SKIPPED"
        makespanMinutes={0}
        operations={[]}
        machines={mockMachines}
      />
    );
    expect(markup).toContain('Model Proven Infeasible');
    expect(markup).toContain('INFEASIBLE');
    expect(markup).toContain('SKIPPED');
  });

  it('accurately derives machine swimlanes when machines array is omitted', () => {
    const markup = renderToStaticMarkup(
      <GanttChart
        scheduleId="sched-inferred"
        scheduleName="Inferred Machines"
        solverStatus="FEASIBLE"
        verificationStatus="VERIFIED"
        makespanMinutes={80}
        operations={mockOperations}
      />
    );
    expect(markup).toContain('Workstation M1');
    expect(markup).toContain('Workstation M2');
    expect(markup).toContain('FEASIBLE');
  });
});

describe('Execution-Aware Gantt & Plant Clock Lifecycle Visualization', () => {
  const lifecycleOperations: ScheduledOperationResponse[] = [
    {
      operation_id: 'op-comp',
      order_id: 'ORD-HIST',
      sequence_index: 1,
      machine_id: 'M1',
      start_minute: 0,
      end_minute: 25,
      duration: 25,
      slack_minutes: 0,
      status: 'COMPLETED',
    },
    {
      operation_id: 'op-prog',
      order_id: 'ORD-ACT',
      sequence_index: 1,
      machine_id: 'M2',
      start_minute: 10,
      end_minute: 40,
      duration: 30,
      slack_minutes: 0,
      status: 'IN_PROGRESS',
    },
    {
      operation_id: 'op-plan',
      order_id: 'ORD-FUT',
      sequence_index: 1,
      machine_id: 'M1',
      start_minute: 30,
      end_minute: 60,
      duration: 30,
      slack_minutes: 0,
      status: 'PLANNED',
    },
  ];

  it('renders plant clock marker on GanttTimeAxis when currentTimeMinute is provided', () => {
    const markup = renderToStaticMarkup(
      <GanttTimeAxis
        ticks={[0, 30, 60]}
        scale={2.0}
        timelineWidth={400}
        labelColumnWidth={170}
        currentTimeMinute={25}
      />
    );
    expect(markup).toContain('NOW (25m)');
    expect(markup).toContain('stroke="#ef4444"');
  });

  it('renders plant clock vertical guideline on GanttSwimlane when currentTimeMinute is provided', () => {
    const markup = renderToStaticMarkup(
      <GanttSwimlane
        machineId="M1"
        machineName="CNC Mill"
        operations={lifecycleOperations.filter((o) => o.machine_id === 'M1')}
        downtimes={[]}
        ticks={[0, 30, 60]}
        scale={2.0}
        timelineWidth={400}
        labelColumnWidth={170}
        currentTimeMinute={25}
        selectedOperationId={null}
        onSelectOperation={vi.fn()}
        isEvenRow={true}
      />
    );
    expect(markup).toContain('stroke="#ef4444"');
    expect(markup).toContain('stroke-dasharray="4 3"');
  });

  it('renders completed operation with checkmark prefix and dashed stroke in GanttSwimlane', () => {
    const markup = renderToStaticMarkup(
      <GanttSwimlane
        machineId="M1"
        machineName="CNC Mill"
        operations={lifecycleOperations.filter((o) => o.status === 'COMPLETED')}
        downtimes={[]}
        ticks={[0, 30, 60]}
        scale={2.0}
        timelineWidth={400}
        labelColumnWidth={170}
        selectedOperationId={null}
        onSelectOperation={vi.fn()}
        isEvenRow={true}
      />
    );
    expect(markup).toContain('✓ ORD-HIST #1');
    expect(markup).toContain('stroke-dasharray="4 2"');
    expect(markup).toContain('Status: COMPLETED');
  });

  it('renders in-progress operation with elapsed shading and active lock boundary in GanttSwimlane', () => {
    const markup = renderToStaticMarkup(
      <GanttSwimlane
        machineId="M2"
        machineName="Lathe"
        operations={lifecycleOperations.filter((o) => o.status === 'IN_PROGRESS')}
        downtimes={[]}
        ticks={[0, 30, 60]}
        scale={2.0}
        timelineWidth={400}
        labelColumnWidth={170}
        currentTimeMinute={25}
        selectedOperationId={null}
        onSelectOperation={vi.fn()}
        isEvenRow={true}
      />
    );
    expect(markup).toContain('● ORD-ACT #1');
    expect(markup).toContain('Status: IN_PROGRESS');
    expect(markup).toContain('Elapsed: [10, 25)m');
    expect(markup).toContain('Remaining Duration: 15m');
    expect(markup).toContain('fill="#000000"');
    expect(markup).toContain('opacity="0.35"');
    expect(markup).toContain('stroke="#38bdf8"');
  });

  it('displays status badge in GanttOperationDetail for completed and in-progress ops', () => {
    const compMarkup = renderToStaticMarkup(
      <GanttOperationDetail
        operation={lifecycleOperations[0]}
        machineName="CNC Mill"
        onClose={vi.fn()}
      />
    );
    expect(compMarkup).toContain('COMPLETED');

    const progMarkup = renderToStaticMarkup(
      <GanttOperationDetail
        operation={lifecycleOperations[1]}
        machineName="Lathe"
        onClose={vi.fn()}
      />
    );
    expect(progMarkup).toContain('IN_PROGRESS');
  });

  it('renders PLANT CLOCK badge in GanttChart header when currentTimeMinute > 0', () => {
    const markup = renderToStaticMarkup(
      <GanttChart
        scheduleId="sched-clock"
        scheduleName="Execution Aware Plan"
        solverStatus="OPTIMAL"
        verificationStatus="VERIFIED"
        makespanMinutes={80}
        operations={lifecycleOperations}
        machines={mockMachines}
        currentTimeMinute={25}
      />
    );
    expect(markup).toContain('PLANT CLOCK: 25m');
    expect(markup).toContain('NOW (25m)');
  });
});

