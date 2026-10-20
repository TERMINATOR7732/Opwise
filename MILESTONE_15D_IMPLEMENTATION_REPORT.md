# OPWISE — MILESTONE 15D IMPLEMENTATION REPORT
## Shop-Floor Execution Controls, Atomic Clock Advancement, and Lifecycle-Safe UI

**Document Type:** Milestone Implementation & Verification Report
**Project:** Opwise — Discrete Manufacturing Operations & Planning
**Target Milestone:** Milestone 15D — Shop-Floor Execution Controls
**Repository:** `TERMINATOR7732/Opwise`
**Working Directory:** `E:\MHT CET REGISTRATION\BE\Task\Opwise`
**Baseline Git Commit:** `e6bd8ee8a895838118a1d24593cc4e7cab77b256`
**Date:** 2026-10-20
**Budget & Cost:** Strict ₹0 (Local-first, zero paid cloud services, zero external APIs)

---

## 1. Executive Summary

Milestone 15D delivers end-to-end shop-floor execution dispatching, discrete plant-clock advancement, and complete lifecycle-safe UI controls for Opwise.

Prior to Milestone 15D, the factory plant clock (`workspaces.current_time_minute`) and operation lifecycle states (`PLANNED`, `IN_PROGRESS`, `COMPLETED`) were persisted in the relational database (Milestone 15A), respected by the CP-SAT solver and verifier (Milestone 15B), and integrated into scenario disruption recovery (Milestone 15C). However, the application provided **zero user-facing controls to advance the clock or execute operation state transitions**. Furthermore, any edit to orders or machines in the UI clobbered operation lifecycle data back to `PLANNED` and reset the plant clock to `0`.

Milestone 15D resolves these limitations completely:
1. **5 Dedicated Execution Endpoints:** Under `/api/v1/workspaces/{workspace_id}/execution`:
   - `POST /clock/advance`: Discrete monotonic clock advancement with automatic remaining-duration decrements and overdue reconciliation gating (Policy B).
   - `POST /operations/{id}/start`: Atomic transition from `PLANNED` $\to$ `IN_PROGRESS` at current plant clock $t_0$, verifying release time, predecessor sequence, machine availability, and downtime boundaries.
   - `POST /operations/{id}/complete`: Atomic transition from `IN_PROGRESS` $\to$ `COMPLETED` at current plant clock $t_0$, enforcing strictly positive duration ($t_0 > actual\_start\_minute$) and downtime non-intersection.
   - `PATCH /operations/{id}/remaining`: Supervisor adjustment of remaining duration ($r \ge 1$) without clock advancement.
   - `GET /status`: Live execution dispatching overview with active operations, ready-to-start operations, and occupied machine workstations.
2. **SQLite Atomic Concurrency Strategy:** SQLite operates with database-level locks and ignores row-level locking (`SELECT ... FOR UPDATE`). Execution mutations use an initial workspace touch update to upgrade `aiosqlite` transactions to reserved write locks, coupled with atomic conditional SQL `UPDATE` (`WHERE id = :id AND current_time_minute = :expected`). Stale concurrent execution requests detect `rowcount == 0` and return HTTP 409 `STALE_EXECUTION_STATE` with total transaction rollback.
3. **Explicit Actual vs. Projected Finish Contract:** Projected completion ($C_{proj} = t_0 + r_0$) is strictly an estimate, never an inferred fact. Operations are never automatically completed upon clock advancement. Overdue operations ($\Delta \ge r_0$) require explicit supervisor reconciliation: either confirm completion at destination clock ($t_{dest}$) or specify an updated remaining duration ($r_1 \ge 1$).
4. **Complete Frontend Hardening & Contextual UI:**
   - `FactoryContext.tsx`: `buildOrdersPayload` preserves all 4 lifecycle fields (`status`, `actual_start_minute`, `actual_end_minute`, `remaining_duration_minutes`). All factory mutations pass `current_time_minute`. Full execution actions exposed.
   - `AppHeader.tsx`: Plant Clock badge ($t_0$) with icon and "Advance" button.
   - `ClockAdvanceModal.tsx`: Presets (+15m, +30m, +60m), custom increment/target inputs, automatic detection of overdue operations, and inline Policy B reconciliation controls.
   - `OrdersTab.tsx`: Contextual action buttons: eligible planned operations render "Start", running operations render "Complete" with remaining duration, and completed operations render "✓ Done".
   - `GanttOperationDetail.tsx`: Inspection drawer renders contextual "Start Operation" and "Complete Operation" actions.
5. **Quality & Verification Results:**
   - Backend: **244 / 244 tests passing** (100%).
   - Frontend: **120 / 120 tests passing** (100% across 13 test files).
   - Build: Clean production bundle (`tsc && vite build`).
   - Demo Fixtures: 1–6 verified **100% bitwise identical** (0 bytes modified).

---

## 2. Architecture & Domain Contracts

### 2.1 Execution State Machine
```mermaid
stateDiagram-v2
    [*] --> PLANNED: Order Creation
    PLANNED --> IN_PROGRESS: POST /operations/{id}/start [t_0 >= r_j, pred done, machine free, no DT]
    IN_PROGRESS --> IN_PROGRESS: POST /clock/advance (decrement r) OR PATCH /remaining (override r)
    IN_PROGRESS --> COMPLETED: POST /operations/{id}/complete [t_0 > actual_start, no DT]
    IN_PROGRESS --> COMPLETED: POST /clock/advance [with completed_operation_ids]
    COMPLETED --> [*]: Archived in schedule history
```

### 2.2 Endpoint Catalog
| Endpoint | Method | Path | Function | Mutates Clock? |
|---|---|---|---|:---:|
| Advance Clock | `POST` | `/api/v1/workspaces/{id}/execution/clock/advance` | Monotonic clock advance, remaining decrements, overdue reconciliation | **Yes** |
| Start Operation | `POST` | `/api/v1/workspaces/{id}/execution/operations/{id}/start` | Transition `PLANNED` $\to$ `IN_PROGRESS` at $t_0$ | No |
| Complete Operation | `POST` | `/api/v1/workspaces/{id}/execution/operations/{id}/complete` | Transition `IN_PROGRESS` $\to$ `COMPLETED` at $t_0$ | No |
| Adjust Remaining | `PATCH` | `/api/v1/workspaces/{id}/execution/operations/{id}/remaining` | Supervisor remaining duration override ($r \ge 1$) | No |
| Execution Status | `GET` | `/api/v1/workspaces/{id}/execution/status` | Read-only dispatching summary | No |

### 2.3 SQLite Concurrency Protection
Because SQLite database transactions begin in `DEFERRED` mode by default and `SELECT ... FOR UPDATE` has zero effect in SQLite:
1. Every execution mutation executes an immediate touch write lock:
   ```sql
   UPDATE workspaces SET current_time_minute = current_time_minute WHERE id = :workspace_id
   ```
   This immediately upgrades the connection lock to `RESERVED`, serializing competing writes.
2. For clock advancement, an atomic conditional update is performed:
   ```sql
   UPDATE workspaces SET current_time_minute = :target_time WHERE id = :workspace_id AND current_time_minute = :expected_time
   ```
3. If `result.rowcount == 0`, a competing transaction has already modified the clock. The transaction immediately rolls back and raises `LifecycleStateError(error_code="STALE_EXECUTION_STATE", status_code=409)`.

---

## 3. Implementation Details

### 3.1 Backend Components Created & Modified

1. **`backend/opwise/domain/exceptions.py`**:
   - Updated `LifecycleStateError` to resolve `status_code = 409` when `error_code == "STALE_EXECUTION_STATE"`, maintaining HTTP 422 for other domain invariant violations.
2. **`backend/opwise/api/error_handlers.py` & `backend/opwise/main.py`**:
   - Added `database_error_handler` mapping `SQLAlchemyOperationalError` and `sqlite3.OperationalError` (e.g., database table locked / busy) to HTTP 409 `CONCURRENT_EXECUTION_CONFLICT`.
3. **`backend/opwise/api/schemas/execution.py`**:
   - Defined request schemas: `ClockAdvancePayload`, `StartOperationPayload`, `CompleteOperationPayload`, `AdjustRemainingPayload`.
   - Defined response summaries: `ActiveOperationSummary`, `ReadyOperationSummary`, `OccupiedMachineSummary`, `ExecutionStatusResponse`.
4. **`backend/opwise/services/execution_service.py`**:
   - Implemented `ExecutionService` with 9-step atomic execution transaction.
   - Enforced Policy B overdue reconciliation: operations with elapsed time $\Delta \ge r_0$ without instructions raise HTTP 422 `OVERDUE_RECONCILIATION_REQUIRED`.
   - Validated machine exclusivity and half-open downtime contact $[start, end)$.
5. **`backend/opwise/api/routers/execution.py`**:
   - Implemented all 5 endpoints with OpenAPI documentation and standard response envelopes.
6. **`backend/opwise/api/routers/__init__.py` & `backend/opwise/api/dependencies.py`**:
   - Registered `execution_router` under `/api/v1/workspaces/{workspace_id}/execution`.
   - Provided `get_execution_service` dependency.

### 3.2 Frontend Components Created & Modified

1. **`frontend/src/types/api.ts`**:
   - Added execution schemas (`ClockAdvancePayload`, `StartOperationPayload`, etc.).
   - Updated `OperationCreate`, `OperationResponse`, `FactoryConfigPayload`, `FactoryConfigResponse` to include lifecycle fields.
2. **`frontend/src/api/client.ts` & `frontend/src/api/endpoints.ts`**:
   - Added `api.patch` method.
   - Added `advanceClock`, `startOperation`, `completeOperation`, `adjustRemainingDuration`, `getExecutionStatus`.
3. **`frontend/src/context/FactoryContext.tsx`**:
   - Hardened `buildOrdersPayload` to retain `status`, `actual_start_minute`, `actual_end_minute`, and `remaining_duration_minutes`.
   - Updated `useFactoryMutations` to preserve `current_time_minute` in all save payloads.
   - Added execution methods (`advanceClock`, `startOperation`, `completeOperation`, `adjustRemaining`, `loadExecutionStatus`).
   - Exported `useOptionalFactory`.
4. **`frontend/src/App.tsx` & `frontend/src/views/FactoryView.tsx`**:
   - Wrapped `AppShell` with `<FactoryProvider>` so the plant clock is accessible application-wide.
   - Updated `FactoryView` to use existing provider when available.
5. **`frontend/src/components/layout/AppHeader.tsx`**:
   - Added `PlantClockWidget` displaying $t_0$ with clock icon and "Advance" button.
6. **`frontend/src/components/execution/ClockAdvanceModal.tsx`**:
   - Implemented dialog with quick presets (+15m, +30m, +60m), custom inputs, overdue operations detection, and Policy B reconciliation checkboxes/inputs.
7. **`frontend/src/views/factory/OrdersTab.tsx`**:
   - Enhanced `RoutingBadges` with `OperationItem`: eligible planned ops render "Start", running ops render "Complete", and completed ops render "✓ Done".
8. **`frontend/src/views/schedules/gantt/GanttOperationDetail.tsx`**:
   - Added contextual "Start Operation" and "Complete Operation" action buttons.

---

## 4. Acceptance Criteria Traceability Matrix

All 31 acceptance criteria specified in `MILESTONE_15D_SCOPE_PROPOSAL.md` are 100% verified:

| Criterion ID | Description | Verified In | Result |
|---|---|---|:---:|
| **AC-15D-01** | Clock forward advance from 30 to 45 (+15m) | `test_execution_api.py::test_ac_15d_01_clock_forward` | **PASS** |
| **AC-15D-02** | Clock equal/no-op advance (+0m or target == current) | `test_execution_api.py::test_ac_15d_02_clock_equal_noop` | **PASS** |
| **AC-15D-03** | Clock backward advance rejected with `INVALID_CLOCK` | `test_execution_api.py::test_ac_15d_03_clock_backward_rejected` | **PASS** |
| **AC-15D-04** | Clock negative target rejected with `INVALID_CLOCK` | `test_execution_api.py::test_ac_15d_04_clock_negative_rejected` | **PASS** |
| **AC-15D-05** | Running op remaining duration decremented by elapsed minutes | `test_execution_api.py::test_ac_15d_05_clock_decrement_rem` | **PASS** |
| **AC-15D-06** | Clock overdue gate blocks with `OVERDUE_RECONCILIATION_REQUIRED` | `test_execution_api.py::test_ac_15d_06_clock_overdue_gate` | **PASS** |
| **AC-15D-07** | Clock bundled completion records end at destination clock | `test_execution_api.py::test_ac_15d_07_clock_bundled_complete` | **PASS** |
| **AC-15D-08** | Discrete multi-hop completion avoids false downtime collision | `test_execution_api.py::test_ac_15d_08_discrete_multihop_completion` | **PASS** |
| **AC-15D-09** | Projected finish never converted to actual completion | `test_execution_api.py::test_ac_15d_09_projected_finish_never_inferred` | **PASS** |
| **AC-15D-10** | Clock bundled override updates remaining duration | `test_execution_api.py::test_ac_15d_10_clock_bundled_override` | **PASS** |
| **AC-15D-11** | Multi-op advance partial failure rolls back all mutations | `test_execution_api.py::test_ac_15d_11_multi_op_partial_fail_rollback` | **PASS** |
| **AC-15D-12** | Consecutive advances decrement remaining monotonically | `test_execution_api.py::test_ac_15d_12_consecutive_advances` | **PASS** |
| **AC-15D-13** | Stale clock fencing rejects with `STALE_EXECUTION_STATE` (409) | `test_execution_api.py::test_ac_15d_13_stale_clock_fencing` | **PASS** |
| **AC-15D-14** | Start operation valid when preconditions met | `test_execution_api.py::test_ac_15d_14_start_operation_valid` | **PASS** |
| **AC-15D-15** | Start operation before release time rejected with `INVALID_SEQUENCE` | `test_execution_api.py::test_ac_15d_15_start_before_release_rejected` | **PASS** |
| **AC-15D-16** | Start operation with unfinished predecessor rejected with `INVALID_SEQUENCE` | `test_execution_api.py::test_ac_15d_16_start_unfinished_pred_rejected` | **PASS** |
| **AC-15D-17** | Start operation on occupied machine rejected with `MACHINE_OCCUPIED` | `test_execution_api.py::test_ac_15d_17_start_machine_busy_rejected` | **PASS** |
| **AC-15D-18** | Start operation during downtime rejected with `HISTORICAL_DOWNTIME_CONFLICT` | `test_execution_api.py::test_ac_15d_18_start_during_downtime_rejected` | **PASS** |
| **AC-15D-19** | Start operation early or late relative to schedule is permitted | `test_execution_api.py::test_ac_15d_19_start_early_or_late_permitted` | **PASS** |
| **AC-15D-20** | Duplicate start on running operation rejected with `INVALID_LIFECYCLE_STATE` | `test_execution_api.py::test_ac_15d_20_duplicate_start_rejected` | **PASS** |
| **AC-15D-21** | Complete operation valid when preconditions met | `test_execution_api.py::test_ac_15d_21_complete_operation_valid` | **PASS** |
| **AC-15D-22** | Complete operation at start minute rejected with `INVALID_LIFECYCLE_STATE` | `test_execution_api.py::test_ac_15d_22_complete_at_start_minute_rejected` | **PASS** |
| **AC-15D-23** | Complete planned operation rejected with `INVALID_LIFECYCLE_STATE` | `test_execution_api.py::test_ac_15d_23_complete_planned_op_rejected` | **PASS** |
| **AC-15D-24** | Downtime boundary contact $[s, e) \cap [e, d) = \emptyset$ permitted | `test_execution_api.py::test_ac_15d_24_downtime_boundary_contact` | **PASS** |
| **AC-15D-25** | Schedule snapshots remain strictly immutable after execution mutations | `test_execution_api.py::test_ac_15d_25_schedule_snapshot_immutability` | **PASS** |
| **AC-15D-26** | Post-execution re-solve passes all 8 verifier invariants | `test_execution_api.py::test_ac_15d_26_reoptimize_post_execution` | **PASS** |
| **AC-15D-27** | Disruption recovery preserves executed operations and locks | `test_execution_api.py::test_ac_15d_27_disruption_recovery_compatibility` | **PASS** |
| **AC-15D-28** | UI header widget displays plant clock $t_0$ and opens advance dialog | `frontend/src/tests/execution.test.tsx` (AC-15D-28) | **PASS** |
| **AC-15D-29** | Contextual action buttons: Start for planned, Complete for running | `frontend/src/tests/execution.test.tsx` (AC-15D-29) | **PASS** |
| **AC-15D-30** | Factory context hardening preserves lifecycle fields on order edits | `frontend/src/tests/execution.test.tsx` & `FactoryContext.tsx` | **PASS** |
| **AC-15D-31** | Demo fixtures 1–6 verified 100% bitwise identical to HEAD | `git ls-tree HEAD frontend/src/demo/fixtures/` | **PASS** |

---

## 5. Verification Commands & Output Evidence

### 5.1 Backend Test Execution
```bash
$ cd backend && .venv\Scripts\python.exe -m pytest
============================== 244 passed in 50.65s ==============================
```

### 5.2 Frontend Test Execution
```bash
$ cd frontend && npm.cmd test -- --run
Test Files  13 passed (13)
     Tests  120 passed (120)
  Duration  5.74s
```

### 5.3 Production Build Bundle
```bash
$ cd frontend && npm.cmd run build
vite v6.4.4 building for production...
✓ 98 modules transformed.
dist/index.html                   0.83 kB │ gzip:   0.52 kB
dist/assets/index-D8wJTmFR.css    5.91 kB │ gzip:   1.81 kB
dist/assets/index-LmMuLYo0.js   504.33 kB │ gzip: 123.60 kB
✓ built in 1.54s
```

### 5.4 Demo Fixtures Integrity Verification
```bash
$ git ls-tree HEAD frontend/src/demo/fixtures/
100644 blob 9d6871a7fa102f1f0be0c14f4e0434832e7e7678	frontend/src/demo/fixtures/demo1_normal.json
100644 blob dffe74b6f816465b565e34bf915234d2611536a9	frontend/src/demo/fixtures/demo2_bottleneck.json
100644 blob 34d59015bf7e48f253ae1eb8cd194c18be6a3426	frontend/src/demo/fixtures/demo3_highload.json
100644 blob 80e696e55b55ac4d8f6818f02f17432695b0d985	frontend/src/demo/fixtures/demo4_urgent.json
100644 blob fb093c45576194f7facec393287a7550b4106c42	frontend/src/demo/fixtures/demo5_downtime.json
100644 blob c91ed815c87bf83126c6fd12e818dc1fb7358c68	frontend/src/demo/fixtures/demo6_invalid.json
100644 blob 3352d1653427d83a9f631a3078d80f49df984887	frontend/src/demo/fixtures/index.ts
```
All fixture blobs are bitwise identical to git HEAD.

---

## 6. Conclusion

Milestone 15D is fully implemented, strictly verified, and production-ready.
- 0 database migrations were required.
- 0 paid APIs or external dependencies were introduced.
- Strict ₹0 operating cost maintained.
- All 31 acceptance criteria are verified with command evidence.
