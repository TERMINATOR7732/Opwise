/**
 * Clean-Room TypeScript Independent Schedule Verifier (Invariants 1-8)
 * Governed by SOLVER_MODEL.md Section 6, PROJECT_RULES.md, and SPECIFICATION.md Section 1.1.
 * Pure TypeScript, zero external dependencies.
 */

import {
  DowntimeResponse,
  FactoryConfigResponse,
  ScheduleDetailResponse,
  ScheduledOperationResponse,
  VerificationReportResponse,
} from '../types/api';

export interface MergedDowntime {
  id: string;
  machine_id: string;
  start_minute: number;
  end_minute: number;
  duration: number;
}

export interface ClientRecomputedMetrics {
  makespan_minutes: number;
  total_weighted_tardiness: number;
  late_order_count: number;
  on_time_rate: number;
  machine_utilizations: Record<
    string,
    {
      machine_id: string;
      workload_minutes: number;
      downtime_minutes: number;
      idle_minutes: number;
      net_utilization_pct: number;
      gross_utilization_pct: number;
    }
  >;
}

export interface ClientVerificationResult extends VerificationReportResponse {
  passed_rules: string[];
  failed_rules: string[];
  recomputed_metrics: ClientRecomputedMetrics;
}

export function normalizeDowntimes(downtimes: DowntimeResponse[]): MergedDowntime[] {
  const byMachine = new Map<string, DowntimeResponse[]>();
  for (const dt of downtimes) {
    if (dt.start_minute < 0 || dt.start_minute >= dt.end_minute) continue;
    const list = byMachine.get(dt.machine_id) || [];
    list.push(dt);
    byMachine.set(dt.machine_id, list);
  }

  const merged: MergedDowntime[] = [];
  for (const [mId, list] of byMachine.entries()) {
    list.sort((a, b) => a.start_minute - b.start_minute || a.end_minute - b.end_minute);
    let curr = { ...list[0] };
    for (let i = 1; i < list.length; i++) {
      const next = list[i];
      if (curr.end_minute >= next.start_minute) {
        curr.end_minute = Math.max(curr.end_minute, next.end_minute);
      } else {
        merged.push({
          id: curr.id,
          machine_id: mId,
          start_minute: curr.start_minute,
          end_minute: curr.end_minute,
          duration: curr.end_minute - curr.start_minute,
        });
        curr = { ...next };
      }
    }
    merged.push({
      id: curr.id,
      machine_id: mId,
      start_minute: curr.start_minute,
      end_minute: curr.end_minute,
      duration: curr.end_minute - curr.start_minute,
    });
  }
  return merged;
}

export function calculateEffectiveHorizon(factory: FactoryConfigResponse, mergedDts: MergedDowntime[]): number {
  const maxRelease = factory.orders.reduce((max, o) => Math.max(max, o.release_minute), 0);
  const totalProcessing = factory.orders.reduce(
    (sum, o) => sum + o.operations.reduce((s, op) => s + op.processing_minutes, 0),
    0
  );
  const totalDowntime = mergedDts.reduce((sum, dt) => sum + dt.duration, 0);
  return maxRelease + totalProcessing + totalDowntime;
}

export function auditCardinality(factory: FactoryConfigResponse, ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const factoryOps = new Set(factory.orders.flatMap((o) => o.operations.map((op) => op.id)));
  const seenOps = new Set<string>();

  for (const op of ops) {
    if (seenOps.has(op.operation_id)) {
      violations.push(`Duplicate scheduled operation '${op.operation_id}'.`);
    }
    seenOps.add(op.operation_id);
    if (!factoryOps.has(op.operation_id)) {
      violations.push(`Scheduled operation '${op.operation_id}' not found in factory definition.`);
    }
  }

  for (const fOpId of factoryOps) {
    if (!seenOps.has(fOpId)) {
      violations.push(`Factory operation '${fOpId}' is missing from schedule.`);
    }
  }
  return violations;
}

export function auditDurationAndMachine(factory: FactoryConfigResponse, ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const opMap = new Map(factory.orders.flatMap((o) => o.operations.map((op) => [op.id, op] as const)));

  for (const sop of ops) {
    const fop = opMap.get(sop.operation_id);
    if (!fop) continue;
    const actualDuration = sop.end_minute - sop.start_minute;
    if (actualDuration !== fop.processing_minutes) {
      violations.push(
        `Operation '${sop.operation_id}' duration mismatch: span [${sop.start_minute}, ${sop.end_minute}) = ${actualDuration}m, expected ${fop.processing_minutes}m.`
      );
    }
    if (sop.machine_id !== fop.machine_id) {
      violations.push(
        `Operation '${sop.operation_id}' scheduled on machine '${sop.machine_id}', expected required machine '${fop.machine_id}'.`
      );
    }
  }
  return violations;
}

export function auditReleaseTimes(factory: FactoryConfigResponse, ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const opsByOrder = new Map<string, ScheduledOperationResponse[]>();
  for (const sop of ops) {
    const list = opsByOrder.get(sop.order_id) || [];
    list.push(sop);
    opsByOrder.set(sop.order_id, list);
  }

  for (const order of factory.orders) {
    const orderOps = opsByOrder.get(order.id) || [];
    if (orderOps.length === 0) continue;
    const firstOp = orderOps.reduce((min, cur) => (cur.sequence_index < min.sequence_index ? cur : min), orderOps[0]);
    if (firstOp.start_minute < order.release_minute) {
      violations.push(
        `Order '${order.id}' first operation '${firstOp.operation_id}' starts at minute ${firstOp.start_minute}, prior to release time ${order.release_minute}.`
      );
    }
  }
  return violations;
}

export function auditPrecedence(factory: FactoryConfigResponse, ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const opsByOrder = new Map<string, ScheduledOperationResponse[]>();
  for (const sop of ops) {
    const list = opsByOrder.get(sop.order_id) || [];
    list.push(sop);
    opsByOrder.set(sop.order_id, list);
  }

  for (const order of factory.orders) {
    const orderOps = (opsByOrder.get(order.id) || []).slice().sort((a, b) => a.sequence_index - b.sequence_index);
    for (let i = 0; i < orderOps.length - 1; i++) {
      const curr = orderOps[i];
      const next = orderOps[i + 1];
      if (next.start_minute < curr.end_minute) {
        violations.push(
          `Precedence violation in order '${order.id}': operation '${next.operation_id}' starts at minute ${next.start_minute} before preceding operation '${curr.operation_id}' ends at minute ${curr.end_minute}.`
        );
      }
    }
  }
  return violations;
}

export function auditMachineExclusivity(ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const opsByMachine = new Map<string, ScheduledOperationResponse[]>();
  for (const sop of ops) {
    const list = opsByMachine.get(sop.machine_id) || [];
    list.push(sop);
    opsByMachine.set(sop.machine_id, list);
  }

  for (const [mId, mOps] of opsByMachine.entries()) {
    const sorted = mOps.slice().sort((a, b) => a.start_minute - b.start_minute || a.end_minute - b.end_minute);
    for (let i = 0; i < sorted.length - 1; i++) {
      const curr = sorted[i];
      const next = sorted[i + 1];
      if (next.start_minute < curr.end_minute) {
        violations.push(
          `Machine '${mId}' overlap collision: operation '${next.operation_id}' starts at minute ${next.start_minute} before operation '${curr.operation_id}' completes at minute ${curr.end_minute}.`
        );
      }
    }
  }
  return violations;
}

export function auditDowntimeRespect(mergedDts: MergedDowntime[], ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  const dtsByMachine = new Map<string, MergedDowntime[]>();
  for (const dt of mergedDts) {
    const list = dtsByMachine.get(dt.machine_id) || [];
    list.push(dt);
    dtsByMachine.set(dt.machine_id, list);
  }

  for (const sop of ops) {
    const machineDts = dtsByMachine.get(sop.machine_id) || [];
    for (const dt of machineDts) {
      if (sop.start_minute < dt.end_minute && dt.start_minute < sop.end_minute) {
        violations.push(
          `Operation '${sop.operation_id}' on machine '${sop.machine_id}' in [${sop.start_minute}, ${sop.end_minute}) collides with downtime '${dt.id}' in [${dt.start_minute}, ${dt.end_minute}).`
        );
      }
    }
  }
  return violations;
}

export function auditHorizonBounds(horizon: number, ops: ScheduledOperationResponse[]): string[] {
  const violations: string[] = [];
  for (const sop of ops) {
    if (sop.start_minute < 0) {
      violations.push(`Operation '${sop.operation_id}' has negative start time ${sop.start_minute}.`);
    }
    if (sop.end_minute <= sop.start_minute) {
      violations.push(
        `Operation '${sop.operation_id}' has non-positive duration interval [${sop.start_minute}, ${sop.end_minute}).`
      );
    }
    if (sop.end_minute > horizon) {
      violations.push(
        `Operation '${sop.operation_id}' completion minute ${sop.end_minute} exceeds calculated horizon ${horizon}.`
      );
    }
  }
  return violations;
}

export function recomputeMetrics(
  factory: FactoryConfigResponse,
  schedule: ScheduleDetailResponse,
  mergedDts: MergedDowntime[]
): ClientRecomputedMetrics {
  const ops = schedule.scheduled_operations;
  const makespan = ops.reduce((max, op) => Math.max(max, op.end_minute), 0);

  const opsByOrder = new Map<string, ScheduledOperationResponse[]>();
  for (const op of ops) {
    const list = opsByOrder.get(op.order_id) || [];
    list.push(op);
    opsByOrder.set(op.order_id, list);
  }

  let totalWeightedTardiness = 0;
  let lateOrders = 0;
  const totalOrders = factory.orders.length;

  for (const order of factory.orders) {
    const orderOps = opsByOrder.get(order.id) || [];
    const cJ = orderOps.reduce((max, op) => Math.max(max, op.end_minute), 0);
    const tardiness = Math.max(0, cJ - order.due_minute);
    if (orderOps.length > 0 && cJ > order.due_minute) {
      lateOrders++;
    }
    totalWeightedTardiness += order.tardiness_weight * tardiness;
  }

  const onTimeRate =
    totalOrders === 0 ? 100.0 : Math.round(((totalOrders - lateOrders) / totalOrders) * 10000) / 100;

  const machineUtils: ClientRecomputedMetrics['machine_utilizations'] = {};
  const opsByMachine = new Map<string, ScheduledOperationResponse[]>();
  for (const op of ops) {
    const list = opsByMachine.get(op.machine_id) || [];
    list.push(op);
    opsByMachine.set(op.machine_id, list);
  }

  for (const machine of factory.machines) {
    const mOps = opsByMachine.get(machine.id) || [];
    const workload = mOps.reduce((sum, op) => sum + (op.end_minute - op.start_minute), 0);
    const mDts = mergedDts.filter((dt) => dt.machine_id === machine.id);
    let observedDowntime = 0;
    for (const dt of mDts) {
      const start = Math.max(0, dt.start_minute);
      const end = Math.min(makespan, dt.end_minute);
      if (end > start) observedDowntime += end - start;
    }

    const available = makespan - observedDowntime;
    const idle = Math.max(0, available - workload);
    const netUtil = available > 0 ? Math.round((workload / available) * 10000) / 100 : 0.0;
    const grossUtil = makespan > 0 ? Math.round((workload / makespan) * 10000) / 100 : 0.0;

    machineUtils[machine.id] = {
      machine_id: machine.id,
      workload_minutes: workload,
      downtime_minutes: observedDowntime,
      idle_minutes: idle,
      net_utilization_pct: netUtil,
      gross_utilization_pct: grossUtil,
    };
  }

  return {
    makespan_minutes: makespan,
    total_weighted_tardiness: totalWeightedTardiness,
    late_order_count: lateOrders,
    on_time_rate: onTimeRate,
    machine_utilizations: machineUtils,
  };
}

export function auditMetricConcordance(
  schedule: ScheduleDetailResponse,
  recomputed: ClientRecomputedMetrics
): string[] {
  const violations: string[] = [];
  const kpis = schedule.metrics;
  if (kpis.makespan_minutes !== recomputed.makespan_minutes) {
    violations.push(`Makespan discrepancy: claimed ${kpis.makespan_minutes}m, recomputed ${recomputed.makespan_minutes}m.`);
  }
  if (kpis.weighted_tardiness !== recomputed.total_weighted_tardiness) {
    violations.push(
      `Tardiness discrepancy: claimed ${kpis.weighted_tardiness}, recomputed ${recomputed.total_weighted_tardiness}.`
    );
  }
  if (kpis.late_order_count !== recomputed.late_order_count) {
    violations.push(`Late count discrepancy: claimed ${kpis.late_order_count}, recomputed ${recomputed.late_order_count}.`);
  }
  if (Math.abs(kpis.on_time_rate - recomputed.on_time_rate) > 0.05) {
    violations.push(`On-time rate discrepancy: claimed ${kpis.on_time_rate}%, recomputed ${recomputed.on_time_rate}%.`);
  }
  return violations;
}

export function verifyScheduleClient(
  factory: FactoryConfigResponse,
  schedule: ScheduleDetailResponse,
  stage1Bound?: number | null
): ClientVerificationResult {
  const mergedDts = normalizeDowntimes(factory.downtimes);
  const horizon = calculateEffectiveHorizon(factory, mergedDts);

  const ruleResults: Record<string, string[]> = {
    INV_1_CARDINALITY: auditCardinality(factory, schedule.scheduled_operations),
    INV_2_DURATION_MACHINE: auditDurationAndMachine(factory, schedule.scheduled_operations),
    INV_3_RELEASE_TIME: auditReleaseTimes(factory, schedule.scheduled_operations),
    INV_4_PRECEDENCE: auditPrecedence(factory, schedule.scheduled_operations),
    INV_5_MACHINE_OVERLAP: auditMachineExclusivity(schedule.scheduled_operations),
    INV_6_DOWNTIME_COLLISION: auditDowntimeRespect(mergedDts, schedule.scheduled_operations),
    INV_7_HORIZON_BOUNDS: auditHorizonBounds(horizon, schedule.scheduled_operations),
  };

  const recomputed = recomputeMetrics(factory, schedule, mergedDts);
  const metricViolations = auditMetricConcordance(schedule, recomputed);
  if (stage1Bound !== undefined && stage1Bound !== null && recomputed.total_weighted_tardiness > stage1Bound) {
    metricViolations.push(
      `Stage-1 preservation breached: recomputed tardiness ${recomputed.total_weighted_tardiness} exceeds Stage-1 bound ${stage1Bound}.`
    );
  }
  ruleResults.INV_8_METRIC_CONCORDANCE = metricViolations;

  const passedRules: string[] = [];
  const failedRules: string[] = [];
  const allViolations: string[] = [];

  for (const [rule, violations] of Object.entries(ruleResults)) {
    if (violations.length === 0) {
      passedRules.push(rule);
    } else {
      failedRules.push(rule);
      allViolations.push(...violations);
    }
  }

  const isValid = failedRules.length === 0;

  return {
    is_valid: isValid,
    checks_run: Object.keys(ruleResults).length,
    checks_passed: passedRules.length,
    violations: allViolations,
    passed_rules: passedRules,
    failed_rules: failedRules,
    recomputed_metrics: recomputed,
  };
}
