/**
 * Pure mathematical utilities and calculations for Gantt timeline rendering.
 * Governed by SPECIFICATION.md Section 4 and DATA_AND_API.md Section 3.4.
 */

import { ScheduledOperationResponse } from '../../../types/api';

export interface MachineDescriptor {
  id: string;
  name: string;
}

export interface MachineUtilization {
  machine_id: string;
  machine_name: string;
  busy_minutes: number;
  utilization_pct: number;
  operation_count: number;
}

export interface OrderColorPalette {
  bg: string;
  border: string;
  text: string;
}

const ORDER_PALETTES: OrderColorPalette[] = [
  { bg: '#1e3a8a', border: '#3b82f6', text: '#ffffff' }, // Blue
  { bg: '#064e3b', border: '#10b981', text: '#ffffff' }, // Emerald
  { bg: '#312e81', border: '#6366f1', text: '#ffffff' }, // Indigo
  { bg: '#78350f', border: '#f59e0b', text: '#ffffff' }, // Amber
  { bg: '#581c87', border: '#a855f7', text: '#ffffff' }, // Purple
  { bg: '#134e4a', border: '#14b8a6', text: '#ffffff' }, // Teal
  { bg: '#881337', border: '#f43f5e', text: '#ffffff' }, // Rose
  { bg: '#164e63', border: '#06b6d4', text: '#ffffff' }, // Cyan
];

/** Convert time in minutes to pixel offset. */
export function timeToPixel(minute: number, pxPerMinute: number): number {
  if (minute <= 0 || !Number.isFinite(minute)) return 0;
  return Math.round(minute * pxPerMinute);
}

/** Convert pixel offset back to time in minutes. */
export function pixelToTime(pixel: number, pxPerMinute: number): number {
  if (pixel <= 0 || pxPerMinute <= 0 || !Number.isFinite(pixel)) return 0;
  return Math.round(pixel / pxPerMinute);
}

/** Format minutes into human-readable duration label (e.g. "0m", "45m", "1h 30m"). */
export function formatTimeMinutes(minute: number): string {
  if (minute < 0 || !Number.isFinite(minute)) return '0m';
  if (minute < 60) return `${minute}m`;
  const hours = Math.floor(minute / 60);
  const mins = minute % 60;
  return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`;
}

/** Calculate appropriate tick interval in minutes based on zoom scale. */
export function getTickInterval(pxPerMinute: number): number {
  if (pxPerMinute >= 4) return 15;
  if (pxPerMinute >= 2) return 30;
  if (pxPerMinute >= 0.8) return 60;
  if (pxPerMinute >= 0.4) return 120;
  return 240;
}

/** Generate aligned tick marks covering the schedule span. */
export function calculateTimeTicks(maxMinute: number, pxPerMinute: number): number[] {
  const effectiveMax = Math.max(maxMinute, 60);
  const interval = getTickInterval(pxPerMinute);
  const ticks: number[] = [];
  for (let t = 0; t <= effectiveMax; t += interval) {
    ticks.push(t);
  }
  if (ticks[ticks.length - 1] < effectiveMax) {
    ticks.push(ticks[ticks.length - 1] + interval);
  }
  return ticks;
}

/** Deterministically assign color palette by order ID. */
export function getOrderColor(orderId: string): OrderColorPalette {
  let hash = 0;
  for (let i = 0; i < orderId.length; i++) {
    hash = (hash << 5) - hash + orderId.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % ORDER_PALETTES.length;
  return ORDER_PALETTES[index];
}

/** Calculate per-machine busy minutes, utilization percentage, and identify bottleneck. */
export function calculateMachineUtilization(
  machines: MachineDescriptor[],
  operations: ScheduledOperationResponse[],
  makespanMinutes: number
): { utilizations: MachineUtilization[]; bottleneck: MachineUtilization | null } {
  const map = new Map<string, { busy: number; count: number }>();
  for (const m of machines) {
    map.set(m.id, { busy: 0, count: 0 });
  }

  for (const op of operations) {
    const entry = map.get(op.machine_id) || { busy: 0, count: 0 };
    entry.busy += Math.max(op.duration, 0);
    entry.count += 1;
    map.set(op.machine_id, entry);
  }

  const effectiveSpan = Math.max(makespanMinutes, 1);
  const utilizations: MachineUtilization[] = machines.map((m) => {
    const data = map.get(m.id) || { busy: 0, count: 0 };
    const pct = makespanMinutes > 0 ? Math.min((data.busy / effectiveSpan) * 100, 100) : 0;
    return {
      machine_id: m.id,
      machine_name: m.name,
      busy_minutes: data.busy,
      utilization_pct: Number(pct.toFixed(1)),
      operation_count: data.count,
    };
  });

  let bottleneck: MachineUtilization | null = null;
  for (const u of utilizations) {
    if (u.busy_minutes > 0 && (!bottleneck || u.busy_minutes > bottleneck.busy_minutes)) {
      bottleneck = u;
    }
  }

  return { utilizations, bottleneck };
}
