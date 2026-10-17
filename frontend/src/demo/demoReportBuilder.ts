/**
 * Analytical report generator for Standalone Demo Mode
 * Governed by SPECIFICATION.md Section 5.1 and Section 8.1.
 */

import { ScheduleDetailResponse, FactoryConfigResponse } from '../types/api';
import {
  ScheduleReportResponse,
  MachineUtilizationItem,
  OrderPerformanceItem,
  BottleneckReportItem,
  ScheduleExplanationItem,
} from '../types/reports';
import { ClientVerificationResult } from './clientVerifier';

export function buildDemoReport(
  factory: FactoryConfigResponse,
  schedule: ScheduleDetailResponse,
  verification: ClientVerificationResult
): ScheduleReportResponse {
  const recomputed = verification.recomputed_metrics;
  const makespan = recomputed.makespan_minutes;
  const totalOrders = factory.orders.length;
  const lateOrders = recomputed.late_order_count;

  const machineItems = buildMachineUtilizationItems(factory, schedule, recomputed);
  const orderItems = buildOrderPerformanceItems(factory, schedule);
  const bottleneck = buildBottleneckReport(machineItems);
  const explanations = buildScheduleExplanations(orderItems, bottleneck);

  return {
    workspace_id: schedule.workspace_id,
    schedule_id: schedule.id,
    schedule_name: schedule.name,
    objective_type: schedule.objective_type,
    solver_status: schedule.solver_status,
    verification_status: verification.is_valid ? 'VERIFIED' : 'VERIFICATION_FAILED',
    created_at: schedule.created_at,
    summary: {
      makespan_minutes: makespan,
      total_weighted_tardiness: recomputed.total_weighted_tardiness,
      late_order_count: lateOrders,
      on_time_order_count: totalOrders - lateOrders,
      total_order_count: totalOrders,
      on_time_rate_pct: recomputed.on_time_rate,
      solver_wall_clock_seconds: schedule.solver_telemetry?.wall_clock_time_seconds ?? 0,
      solver_deterministic_time: schedule.solver_telemetry?.deterministic_time ?? null,
    },
    machine_utilization: machineItems,
    order_performance: orderItems,
    bottleneck,
    explanations,
    verification_audit: {
      is_valid: verification.is_valid,
      checks_run: verification.checks_run,
      checks_passed: verification.checks_passed,
      violations: verification.violations,
    },
  };
}

function buildMachineUtilizationItems(
  factory: FactoryConfigResponse,
  schedule: ScheduleDetailResponse,
  recomputed: ClientVerificationResult['recomputed_metrics']
): MachineUtilizationItem[] {
  return factory.machines.map((m) => {
    const u = recomputed.machine_utilizations[m.id] || {
      workload_minutes: 0,
      downtime_minutes: 0,
      idle_minutes: 0,
      net_utilization_pct: 0,
      gross_utilization_pct: 0,
    };
    const assignedOps = schedule.scheduled_operations.filter((op) => op.machine_id === m.id).length;
    const available = recomputed.makespan_minutes - u.downtime_minutes;
    return {
      machine_id: m.id,
      machine_name: m.name,
      workload_minutes: u.workload_minutes,
      downtime_minutes: u.downtime_minutes,
      idle_minutes: u.idle_minutes,
      available_capacity_minutes: Math.max(0, available),
      net_utilization_pct: u.net_utilization_pct,
      gross_utilization_pct: u.gross_utilization_pct,
      assigned_operation_count: assignedOps,
      is_oversubscribed: u.net_utilization_pct >= 90.0,
    };
  });
}

function buildOrderPerformanceItems(
  factory: FactoryConfigResponse,
  schedule: ScheduleDetailResponse
): OrderPerformanceItem[] {
  return factory.orders.map((o) => {
    const oOps = schedule.scheduled_operations.filter((op) => op.order_id === o.id);
    const completion = oOps.reduce((max, op) => Math.max(max, op.end_minute), 0);
    const tardiness = Math.max(0, completion - o.due_minute);
    const totalProcessing = o.operations.reduce((sum, op) => sum + op.processing_minutes, 0);
    const slack = o.due_minute - completion;
    return {
      order_id: o.id,
      order_code: o.external_id,
      release_minute: o.release_minute,
      due_date_minute: o.due_minute,
      completion_minute: completion,
      tardiness_minutes: tardiness,
      tardiness_weight: o.tardiness_weight,
      weighted_tardiness: o.tardiness_weight * tardiness,
      slack_minutes: slack,
      is_late: completion > o.due_minute,
      is_on_time: completion <= o.due_minute,
      operation_count: o.operations.length,
      total_processing_minutes: totalProcessing,
    };
  });
}

function buildBottleneckReport(machines: MachineUtilizationItem[]): BottleneckReportItem {
  if (machines.length === 0) {
    return {
      primary_bottleneck_machine_id: null,
      primary_bottleneck_machine_name: null,
      highest_workload_minutes: 0,
      highest_net_utilization_pct: 0,
      ranked_machines: [],
      disclaimer: 'No machines configured in shop floor model.',
    };
  }

  const sorted = machines.slice().sort((a, b) => b.net_utilization_pct - a.net_utilization_pct);
  const primary = sorted[0];

  return {
    primary_bottleneck_machine_id: primary.machine_id,
    primary_bottleneck_machine_name: primary.machine_name,
    highest_workload_minutes: primary.workload_minutes,
    highest_net_utilization_pct: primary.net_utilization_pct,
    ranked_machines: sorted.map((m) => `${m.machine_name} (${m.net_utilization_pct}%)`),
    disclaimer: 'Ranked by analytical net utilization rate within makespan boundary.',
  };
}

function buildScheduleExplanations(
  orders: OrderPerformanceItem[],
  bottleneck: BottleneckReportItem
): ScheduleExplanationItem[] {
  const items: ScheduleExplanationItem[] = [];

  if (bottleneck.primary_bottleneck_machine_id) {
    items.push({
      category: 'BOTTLENECK',
      entity_type: 'Machine',
      entity_id: bottleneck.primary_bottleneck_machine_id,
      summary: `Workstation '${bottleneck.primary_bottleneck_machine_name}' is the primary shop floor constraint.`,
      measured_value: `${bottleneck.highest_net_utilization_pct}% net utilization`,
      threshold_or_target: '85%',
      mathematical_formula: 'Net Utilization = Workload / (Makespan - Maintenance)',
      reason: 'Pacing workstation determines overall plant throughput and critical paths.',
    });
  }

  const lateOrders = orders.filter((o) => o.is_late);
  if (lateOrders.length > 0) {
    const worst = lateOrders.reduce((w, o) => (o.tardiness_minutes > w.tardiness_minutes ? o : w), lateOrders[0]);
    items.push({
      category: 'LATENESS',
      entity_type: 'Order',
      entity_id: worst.order_id,
      summary: `Order '${worst.order_code}' completed ${worst.tardiness_minutes}m past due date.`,
      measured_value: `Completion ${worst.completion_minute}m vs Due ${worst.due_date_minute}m`,
      threshold_or_target: `${worst.due_date_minute}m`,
      mathematical_formula: 'Tardiness = max(0, Completion - DueDate)',
      reason: 'Displaced by higher-weight orders or scheduled machine downtime intervals.',
    });
  }

  return items;
}
