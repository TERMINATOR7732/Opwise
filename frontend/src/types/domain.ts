/**
 * Opwise Domain Models & Type Definitions
 * Shared Frontend Types aligned with Backend Domain Models & OpenAPI Schemas
 * Governed by PROJECT_RULES.md, SPECIFICATION.md, and DATA_AND_API.md
 */

export type ScheduleStatus =
  | 'OPTIMAL'
  | 'FEASIBLE'
  | 'INFEASIBLE'
  | 'NO_WORK_STATE'
  | 'TIMEOUT'
  | 'MODEL_INVALID';

export type ObjectiveMode =
  | 'PURE_MAKESPAN'
  | 'PURE_WEIGHTED_TARDINESS'
  | 'HIERARCHICAL_LEXICOGRAPHIC';

export type InputClassificationCase =
  | 'EMPTY_WORKSPACE'
  | 'NO_WORK_STATE'
  | 'ORDER_WITHOUT_OPERATIONS'
  | 'REFERENTIAL_INTEGRITY_VIOLATION'
  | 'VALID_NON_EMPTY_FACTORY'
  | 'INFEASIBLE_CONSTRAINTS';

export interface Machine {
  id: string;
  name: string;
  description?: string;
}

export interface MachineDowntime {
  id: string;
  machineId: string;
  startMinute: number;
  endMinute: number;
  reason?: string;
}

export interface Operation {
  id: string;
  orderId: string;
  sequenceNumber: number;
  machineId: string;
  processingDurationMinutes: number;
}

export interface ProductionOrder {
  id: string;
  orderCode: string;
  releaseTimeMinutes: number;
  dueDateMinutes: number;
  tardinessWeight: number;
  operations: Operation[];
}

export interface Factory {
  workspaceId: string;
  machines: Machine[];
  downtimes: MachineDowntime[];
  orders: ProductionOrder[];
}

export interface ScheduledOperation {
  operationId: string;
  orderId: string;
  machineId: string;
  sequenceNumber: number;
  startMinute: number;
  endMinute: number;
  processingDurationMinutes: number;
  slackMinutes: number;
}

export interface ScheduleKPIs {
  makespanMinutes: number;
  totalWeightedTardiness: number;
  lateOrderCount: number;
  onTimeRate: number;
}

export interface Schedule {
  id: string;
  workspaceId: string;
  status: ScheduleStatus;
  objectiveMode: ObjectiveMode;
  kpis: ScheduleKPIs;
  scheduledOperations: ScheduledOperation[];
  verified: boolean;
  createdAt: string;
}
