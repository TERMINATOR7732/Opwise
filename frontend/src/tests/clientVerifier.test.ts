import { describe, it, expect } from 'vitest';
import {
  verifyScheduleClient,
  auditCardinality,
  auditDurationAndMachine,
  auditReleaseTimes,
  auditPrecedence,
  auditMachineExclusivity,
  auditDowntimeRespect,
  auditHorizonBounds,
  normalizeDowntimes,
} from '../demo/clientVerifier';
import { DEMO_FIXTURES } from '../demo/fixtures';

describe('Client-Side Independent Verifier (Invariants 1-8)', () => {
  it('should verify Demo 1 (Balanced Shop) passes all 8 invariants with 0 violations', () => {
    const fixture = DEMO_FIXTURES['demo-1'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(true);
    expect(result.checks_run).toBe(8);
    expect(result.checks_passed).toBe(8);
    expect(result.violations).toHaveLength(0);
    expect(result.failed_rules).toHaveLength(0);
  });

  it('should verify Demo 2 (Clear Bottleneck) passes all 8 invariants', () => {
    const fixture = DEMO_FIXTURES['demo-2'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(true);
    expect(result.checks_passed).toBe(8);
    expect(result.violations).toHaveLength(0);
  });

  it('should verify Demo 3 (High-Load Factory) passes all 8 invariants', () => {
    const fixture = DEMO_FIXTURES['demo-3'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(true);
    expect(result.checks_passed).toBe(8);
    expect(result.violations).toHaveLength(0);
  });

  it('should verify Demo 4 (Urgent-Order Insertion) passes all 8 invariants', () => {
    const fixture = DEMO_FIXTURES['demo-4'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(true);
    expect(result.checks_passed).toBe(8);
    expect(result.violations).toHaveLength(0);
  });

  it('should verify Demo 5 (Downtime Outage) passes all 8 invariants and respects downtime window', () => {
    const fixture = DEMO_FIXTURES['demo-5'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(true);
    expect(result.checks_passed).toBe(8);
    expect(result.violations).toHaveLength(0);

    // Explicitly verify zero operations on M1 inside [30, 90)
    const m1Ops = fixture.schedule.scheduled_operations.filter((op) => op.machine_id === 'M1');
    for (const op of m1Ops) {
      const overlaps = op.start_minute < 90 && 30 < op.end_minute;
      expect(overlaps).toBe(false);
    }
  });

  it('should reject Demo 6 (Malformed / Invalid Inputs) and report violations', () => {
    const fixture = DEMO_FIXTURES['demo-6'];
    const result = verifyScheduleClient(fixture.factory, fixture.schedule);
    expect(result.is_valid).toBe(false);
    expect(result.failed_rules.length).toBeGreaterThan(0);
    expect(result.violations.length).toBeGreaterThan(0);
  });

  describe('Isolated Invariant Violations', () => {
    it('catches Invariant 1: Duplicate and missing operations', () => {
      const fixture = DEMO_FIXTURES['demo-1'];
      // Duplicate first operation
      const corruptOps = [
        ...fixture.schedule.scheduled_operations,
        { ...fixture.schedule.scheduled_operations[0] },
      ];
      const violations = auditCardinality(fixture.factory, corruptOps);
      expect(violations.some((v) => v.includes('Duplicate scheduled operation'))).toBe(true);
    });

    it('catches Invariant 2: Duration and machine workstation mismatches', () => {
      const fixture = DEMO_FIXTURES['demo-1'];
      const corruptOps = fixture.schedule.scheduled_operations.map((op, idx) =>
        idx === 0 ? { ...op, end_minute: op.start_minute + 999 } : op
      );
      const violations = auditDurationAndMachine(fixture.factory, corruptOps);
      expect(violations.some((v) => v.includes('duration mismatch'))).toBe(true);
    });

    it('catches Invariant 3: Operation starting before order release time', () => {
      const fixture = DEMO_FIXTURES['demo-1'];
      const delayedFactory = {
        ...fixture.factory,
        orders: fixture.factory.orders.map((o) =>
          o.id === 'ORD-01' ? { ...o, release_minute: 500 } : o
        ),
      };
      const violations = auditReleaseTimes(delayedFactory, fixture.schedule.scheduled_operations);
      expect(violations.some((v) => v.includes('prior to release time'))).toBe(true);
    });

    it('catches Invariant 4: Precedence sequence inversion', () => {
      const fixture = DEMO_FIXTURES['demo-1'];
      const corruptOps = fixture.schedule.scheduled_operations.map((op) => {
        if (op.operation_id === 'ORD-01-OP2') {
          return { ...op, start_minute: 0, end_minute: 10 }; // Starts before OP1 ends
        }
        return op;
      });
      const violations = auditPrecedence(fixture.factory, corruptOps);
      expect(violations.some((v) => v.includes('Precedence violation'))).toBe(true);
    });

    it('catches Invariant 5: Machine overlap collisions', () => {
      const corruptOps = [
        {
          operation_id: 'OP-1',
          order_id: 'O1',
          sequence_index: 1,
          machine_id: 'M1',
          start_minute: 10,
          end_minute: 30,
          duration: 20,
          slack_minutes: 0,
        },
        {
          operation_id: 'OP-2',
          order_id: 'O2',
          sequence_index: 1,
          machine_id: 'M1',
          start_minute: 25,
          end_minute: 45,
          duration: 20,
          slack_minutes: 0,
        },
      ];
      const violations = auditMachineExclusivity(corruptOps);
      expect(violations.some((v) => v.includes('overlap collision'))).toBe(true);
    });

    it('catches Invariant 6: Collision with scheduled downtime', () => {
      const mergedDts = [
        { id: 'DT-1', machine_id: 'M1', start_minute: 30, end_minute: 60, duration: 30 },
      ];
      const collidingOps = [
        {
          operation_id: 'OP-COLLIDE',
          order_id: 'O1',
          sequence_index: 1,
          machine_id: 'M1',
          start_minute: 40,
          end_minute: 50,
          duration: 10,
          slack_minutes: 0,
        },
      ];
      const violations = auditDowntimeRespect(mergedDts, collidingOps);
      expect(violations.some((v) => v.includes('collides with downtime'))).toBe(true);
    });

    it('catches Invariant 7: Negative start or horizon overflow', () => {
      const invalidOps = [
        {
          operation_id: 'OP-NEG',
          order_id: 'O1',
          sequence_index: 1,
          machine_id: 'M1',
          start_minute: -5,
          end_minute: 10,
          duration: 15,
          slack_minutes: 0,
        },
        {
          operation_id: 'OP-OVER',
          order_id: 'O2',
          sequence_index: 1,
          machine_id: 'M1',
          start_minute: 100,
          end_minute: 200,
          duration: 100,
          slack_minutes: 0,
        },
      ];
      const violations = auditHorizonBounds(150, invalidOps);
      expect(violations.some((v) => v.includes('negative start time'))).toBe(true);
      expect(violations.some((v) => v.includes('exceeds calculated horizon'))).toBe(true);
    });

    it('correctly normalizes and merges adjacent/overlapping downtimes', () => {
      const raw = [
        { id: 'DT1', machine_id: 'M1', start_minute: 10, end_minute: 25, reason: '' },
        { id: 'DT2', machine_id: 'M1', start_minute: 25, end_minute: 40, reason: '' }, // Adjacent
        { id: 'DT3', machine_id: 'M1', start_minute: 35, end_minute: 50, reason: '' }, // Overlapping
      ];
      const merged = normalizeDowntimes(raw);
      expect(merged).toHaveLength(1);
      expect(merged[0].start_minute).toBe(10);
      expect(merged[0].end_minute).toBe(50);
      expect(merged[0].duration).toBe(40);
    });
  });
});
