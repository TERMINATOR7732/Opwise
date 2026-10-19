# OPWISE — MILESTONE 15C: DISCOVERY, PRODUCT GAP ANALYSIS & SPECIFICATION PROPOSAL

**Document Type:** Discovery, Architecture Review, Product Gap Analysis & Scope Proposal  
**Project:** Opwise — Intelligent Operations. Optimized Decisions.  
**Repository:** `TERMINATOR7732/Opwise`  
**Working Directory:** `E:\MHT CET REGISTRATION\BE\Task\Opwise`  
**Target Milestone:** Milestone 15C — Proposed Scope  
**Author:** Software Verification Specialist, OR Engineer, Release Auditor  
**Date:** 2026-10-19  
**Implementation Authorization Status:** **NOT GRANTED / PROPOSAL ONLY**  
**Operating Budget:** Strict ₹0 (Local-first, zero paid APIs, zero external cloud dependencies)

---

## 1. Executive Summary

Milestone 15B successfully introduced execution-aware production scheduling to Opwise, incorporating the factory plant clock ($t_0$), operation lifecycle states (`PLANNED`, `IN_PROGRESS`, `COMPLETED`), independent schedule verification across all 8 core invariants, and a 4-bar lifecycle visualization in the primary Gantt canvas. That milestone was verified, hardened, and committed at SHA `954b6a7` with 200 backend tests and 107 frontend tests passing.

Following the completion of Milestone 15B, an exhaustive discovery and source code audit was conducted across the backend, frontend, solver, persistence, and verification modules to evaluate the end-to-end product decision loop:
$$\text{Configure Production} \longrightarrow \text{Validate Constraints} \longrightarrow \text{Optimize Schedule} \longrightarrow \text{Understand Result} \longrightarrow \text{Simulate Disruption} \longrightarrow \text{Compare Outcomes} \longrightarrow \text{Choose Better Plan}$$

The audit uncovered a **critical architectural disconnect** between Milestone 15B's execution-aware scheduling engine and the rest of the application:
1. **Scenario Disruption Engine Disconnect (Primary Blocker):** While the CP-SAT solver and independent verifier are fully execution-aware, the scenario branching and recovery service (`ScenarioService` in `backend/opwise/services/scenario_service.py` and `synthesize_disrupted_factory` in `backend/opwise/services/scenario_math.py`) completely discards execution state. When synthesizing a disrupted factory from an execution-aware baseline schedule, `synthesize_disrupted_factory` silently drops `current_time_minute` (reverting to $t_0 = 0$) and strips all operation lifecycle attributes (`status`, `actual_start_minute`, `actual_end_minute`, and `remaining_duration_minutes` revert to `PLANNED`). Consequently, reoptimizing a disruption (machine breakdown or rush order) resurrects already completed operations from $t=0$, ignores in-progress locked commitments, and produces invalid recovery schedules.
2. **Frontend Dual Gantt Omission:** `DualGanttComparison.tsx` fails to forward `currentTimeMinute` to the baseline and recovery Gantt charts, hiding the plant clock line and lifecycle visual cues during scenario analysis.
3. **Execution Dispatch Controls Gap:** In the factory management UI (`OrdersTab.tsx` and `OrderModal.tsx`), users cannot view or edit operation lifecycles or advance the plant clock interactively; execution state can currently only be loaded via direct API requests.
4. **Operation-Level Constraint Attribution Gap:** Schedule explanations (`domain/explanations.py`) summarize macro metrics (makespan, tardiness, utilization, bottleneck), but provide no root-cause attribution explaining *why* an individual operation was scheduled at its specific start time (e.g., machine clash, routing precedence, downtime collision, release time, or plant clock lock).

To close these gaps while maintaining strict ₹0 operating costs and local-first determinism, this document analyzes three candidate directions for Milestone 15C:
- **Candidate 1 (Recommended):** *Execution-Aware Disruption Recovery & Rescheduling (Scenario Lifecycle Integration)*
- **Candidate 2:** *Shop Floor Execution Dispatcher & Plant Clock Control (Execution UI & Live State Tracking)*
- **Candidate 3:** *Deterministic Operation Delay & Constraint Binding Attribution Engine (Root-Cause Delay Attribution)*

**Recommendation:** Candidate 1 is recommended as the immediate scope for Milestone 15C. It repairs the broken mathematical foundation of the disruption simulation engine, prevents invalid recovery solves, preserves snapshot integrity across what-if branches, and completes the core promise of execution-aware scheduling. Candidate 2 is recommended as the natural follow-on (Milestone 15D) to expose execution dispatch controls in the user interface.

Implementation of Milestone 15C is **prohibited until explicit user approval is granted**.

---

## 2. Verified Repository Baseline

A rigorous read-only Git preflight was conducted on the local checkout. All findings below are categorized using the four formal evidentiary standards (**Verified**, **Reported**, **Inferred**, **Unknown**):

| Dimension | Audit Finding | Standard | Evidence / Command |
|---|---|---|---|
| **Repository Root** | `E:\MHT CET REGISTRATION\BE\Task\Opwise` | **Verified** | `Get-Location` |
| **Current Branch** | `main` | **Verified** | `git status` |
| **Current HEAD SHA** | `954b6a7e0a81ea4fba9d4cbe2001ba0aa10a5eb5` | **Verified** | `git rev-parse HEAD` |
| **Short SHA** | `954b6a7` | **Verified** | `git log -n 1 --oneline` |
| **Working Tree Status** | Clean (0 modified, 0 untracked, 0 staged) | **Verified** | `git status --porcelain` |
| **Upstream Sync** | Up to date with `origin/main` (+0 / -0) | **Verified** | `git status` |
| **Recent Commit History** | `954b6a7` test(scheduling): verify execution-aware solver...<br>`b56e2ad` feat(scheduling): execution-aware CP-SAT...<br>`ffc9a0f` fix(persistence): persist factory plant clock<br>`df50aad` feat(domain): implement execution-aware...<br>`ad773ed` docs(audit): complete Milestone 14 release... | **Verified** | `git log -n 5 --oneline` |
| **Milestone 15B Audit Report** | Present and committed at repository root: `MILESTONE_15B_POST_IMPLEMENTATION_AUDIT_REPORT.md` | **Verified** | File inspection in `git log` |
| **Demo Fixtures** | Bitwise identical to baseline across all 6 fixtures (`demo1_normal.json` .. `demo6_invalid.json`) | **Verified** | `git diff ffc9a0f HEAD -- frontend/src/demo/fixtures` (empty) |
| **Sibling Projects** | `..\Integris`, `..\CodeShip`, `..\PathForge` exist and are untouched | **Verified** | Filesystem inspection (`Test-Path`) |

No repository discrepancies, uncommitted changes, or detached HEAD states were detected. The baseline is solid.

---

## 3. Source Documents Reviewed

The following canonical engineering and governance documents were reviewed in full:

1. [`PROJECT_RULES.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/PROJECT_RULES.md): Governing permanent constitution, ₹0 budget mandate, local-first rule, anti-AI-slop UX, testing discipline, Git safety.
2. [`SPECIFICATION.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SPECIFICATION.md): Document ID OPW-SPEC-001 (v1.3.0). Master product specification, user journeys, 6 input classifications, MVP non-goals.
3. [`SOLVER_MODEL.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SOLVER_MODEL.md): Mathematical formulation, decision variables, half-open intervals $[S, C)$, downtime normalization, lexicographic gating.
4. [`DATA_AND_API.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DATA_AND_API.md): Relational database schema, SQLite WAL persistence, REST API v1 contracts, and error structures.
5. [`TEST_AND_RELEASE_PLAN.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/TEST_AND_RELEASE_PLAN.md): 14-milestone roadmap, test matrix TM-01 to TM-10, release readiness gates.
6. [`DECISIONS.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DECISIONS.md): Architecture Decision Records ADR-001 to ADR-012, post-MVP roadmap (UNRES-01 to UNRES-05).
7. [`MILESTONE_14_RELEASE_AUDIT.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/MILESTONE_14_RELEASE_AUDIT.md): Phase 1 completion and sign-off report.
8. [`MILESTONE_15A_POST_COMMIT_AUDIT_REPORT.md`](file:///C:/Users/Admin/.gemini/antigravity/brain/10e8d50f-8816-4025-a03f-67bb3f4f1d27/MILESTONE_15A_POST_COMMIT_AUDIT_REPORT.md): Audit identifying `AC-CLOCK-01` persistence gap resolved in Milestone 15A.1.
9. [`MILESTONE_15B_POST_IMPLEMENTATION_AUDIT_REPORT.md`](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/MILESTONE_15B_POST_IMPLEMENTATION_AUDIT_REPORT.md): Audit certifying solver, verifier, Gantt lifecycle visualization, and 200 backend tests.

---

## 4. Current Architecture and Behavior Summary

The current architecture reflects the successful completion of Milestones 01 through 15B:

```mermaid
flowchart TD
    subgraph Frontend["React 19 + TypeScript SPA (frontend/)"]
        FV[FactoryView / Machines & Orders]
        PV[PlanningView / CP-SAT Parameters]
        SV[SchedulesView / Detail & Verification]
        SCV[ScenariosView / Disruption & Dual Gantt]
        RV[ReportsView / KPIs & Explanations]
        GC[GanttChart Component / 4-Bar Lifecycle Visualizer]
    end

    subgraph API["FastAPI REST API v1 (backend/opwise/api/)"]
        WF[workspaces.py & factory.py]
        OPT[optimization.py]
        SCH[schedules.py]
        SCN[scenarios.py]
        REP[reports.py]
    end

    subgraph DomainServices["Application Services & Domain Layer (backend/opwise/)"]
        FS[factory_service.py]
        OS[optimization_service.py]
        SS[scenario_service.py]
        SM[scenario_math.py]
        SN[snapshot.py]
        DV[domain/validators.py]
        DM[domain/metrics.py]
        DX[domain/explanations.py]
    end

    subgraph SolverVerifier["Optimization & Verification Engines"]
        CP[solver/engine.py & cp_sat_model.py<br/>OR-Tools CP-SAT Execution-Aware Scheduler]
        VER[verifier/schedule_verifier.py & invariant_auditor.py<br/>Clean-Room Independent Verifier (8 Invariants)]
    end

    subgraph Persistence["Persistence Layer (backend/opwise/persistence/)"]
        DB[(SQLite 3 WAL Database)]
        MOD[models.py: Workspaces, Machines, Orders, Operations, Schedules, Scenarios]
        MIG[Alembic Migrations 001 to 004]
    end

    FV -->|PUT /factory| WF
    PV -->|POST /optimize| OPT
    SV -->|POST /verify| SCH
    SCV -->|POST /scenarios| SCN
    RV -->|GET /reports| REP

    WF --> FS
    OPT --> OS
    SCN --> SS
    REP --> DM

    OS --> CP
    OS --> VER
    OS --> SN
    SS --> SM
    SS --> CP
    SS --> VER

    FS --> MOD
    OS --> MOD
    SS --> MOD
    MOD --> DB
    GC -.->|Renders| SV
    GC -.->|Renders| SCV
```

### Module Responsibilities & Key Locations
- **Domain Lifecycle & Plant Clock:** Persisted in `workspaces.current_time_minute` (Migration 004) and `operations` (`status`, `actual_start_minute`, `actual_end_minute`, `remaining_duration_minutes`). Validated in `backend/opwise/domain/validators.py`.
- **Execution-Aware CP-SAT Solver:** Implemented in `backend/opwise/solver/cp_sat_model.py` and `engine.py`. Pins completed operations to history, locks in-progress operations in machine `NoOverlap` sets for $[t_0, t_0 + \text{remaining})$, and bounds planned operations to $S \ge \max(r_j, t_0)$.
- **Independent Schedule Verifier:** Implemented in `backend/opwise/verifier/schedule_verifier.py` and `invariant_auditor.py`. Audits all 8 invariants independently, including clock concordance (`schedule.current_time_minute == factory.current_time_minute`).
- **Schedule Persistence & Snapshots:** Implemented in `backend/opwise/services/snapshot.py` and `persistence/repository.py`. Serializes full factory state and plant clock into `schedules.input_snapshot_json` for immutable on-demand re-verification.
- **Frontend Gantt Visualization:** Implemented in `frontend/src/views/schedules/gantt/GanttChart.tsx`. Renders solid completed bars, striped elapsed bars, locked commitment bars, and vertical plant clock markers.
- **Scenario Simulation Engine:** Implemented in `backend/opwise/services/scenario_service.py` and `scenario_math.py`. Currently simulates machine downtimes and urgent rush orders, reoptimizing with CP-SAT and computing schedule divergence deltas.

---

## 5. Milestone 15B Claim-Verification Summary

All specific claims recorded in `MILESTONE_15B_POST_IMPLEMENTATION_AUDIT_REPORT.md` were re-tested directly against the current repository checkout. The verification results are summarized below:

| Milestone 15B Audit Claim | Claimed Value | Audit Verification Result | Status |
|---|---|---|---|
| **Backend Test Suite** | 200 passed | Executed: `.venv\Scripts\pytest.exe tests`<br>Result: **200 passed in 27.63s** | **Verified** |
| **Backend Code Coverage** | 87% overall, 100% solver/verifier core | Executed: `.venv\Scripts\pytest.exe --cov=opwise tests`<br>Result: **87% overall (3532/3981 stmts)**<br>• `cp_sat_model.py`: 100%<br>• `engine.py`: 100%<br>• `schedule_verifier.py`: 100%<br>• `invariant_auditor.py`: 100% | **Verified** |
| **Backend Code Quality** | Clean Ruff lint | Executed: `.venv\Scripts\ruff.exe check .`<br>Result: **All checks passed!** | **Verified** |
| **Backend Type Safety** | 0 mypy type errors in 66 source files | Executed: `.venv\Scripts\mypy.exe opwise`<br>Result: **Success: no issues found in 66 source files** | **Verified** |
| **Frontend Test Suite** | 107 passed across 12 test files | Executed: `npm test -- --run` in `frontend/`<br>Result: **12 passed, 107 passed in 5.64s** | **Verified** |
| **Frontend Production Build** | Clean build with 0 type errors | Executed: `npm run build` in `frontend/`<br>Result: **`tsc && vite build` built in 1.29s (0 errors)** | **Verified** |
| **Demo Fixture Preservation** | Demos 1–6 bitwise unchanged | Executed: `git diff ffc9a0f HEAD -- frontend/src/demo/fixtures`<br>Result: **Zero diff / Clean** | **Verified** |
| **Sibling Project Isolation** | Integris, CodeShip, PathForge untouched | Executed: `Test-Path` on sibling paths<br>Result: **All paths exist and unaltered** | **Verified** |
| **Audit Commit Deployment** | Commit `954b6a7` pushed to `origin/main` | Executed: `git status`<br>Result: **Up to date with `origin/main` at `954b6a7`** | **Verified** |

All claims made in the Milestone 15B post-implementation audit report are truthful, accurate, and completely verified.

---

## 6. Current Product Workflow Assessment

Evaluating the live Opwise implementation against the intended 7-stage operational decision loop reveals both significant strengths and acute operational gaps:

### Stage 1: Configure Production
- **Implemented:** Users can create workspaces, add/edit/delete machines, configure maintenance downtimes, and define production orders with multi-step routings via `FactoryView`.
- **Limitation:** In `frontend/src/views/factory/OrderModal.tsx`, operations are configured exclusively with `processing_minutes` and `machine_id`. The UI provides no controls for setting an operation's lifecycle status (`IN_PROGRESS` or `COMPLETED`) or entering `actual_start_minute`, `actual_end_minute`, or `remaining_duration_minutes`. Similarly, `FactoryView` displays no plant clock widget and provides no mechanism to advance $t_0$.

### Stage 2: Validate Constraints
- **Implemented:** `backend/opwise/domain/validators.py` rigorously validates the 6 input classifications, non-negative bounds, referential integrity, half-open intervals, order sequence monotonicity, historical machine exclusivity, and downtime collisions relative to $t_0$. Pre-solve validation is surfaced in `FactoryValidationCard.tsx`.
- **Limitation:** In the disruption lab (`CreateScenarioModal.tsx`), validation does not check added downtimes or rush orders against the baseline schedule's plant clock $t_0$.

### Stage 3: Optimize Schedule
- **Implemented:** `CPSATScheduler` solves single-objective makespan, weighted tardiness, or two-stage hierarchical lexicographic models. In Milestone 15B, execution-awareness was added: completed operations are pinned to history, in-progress operations are locked for their remaining durations, and planned operations are constrained to $S \ge \max(r_j, t_0)$.
- **Limitation:** When optimizing through `PlanningView`, `OptimizationParametersForm` does not display the active workspace plant clock or allow an explicit clock override.

### Stage 4: Understand the Result
- **Implemented:** `ScheduleDetailCard.tsx` displays KPI summary tiles, solver telemetry, an interactive Gantt chart with lifecycle markers, and an allocated operations sequence table with status badges.
- **Limitation:** In `frontend/src/views/reports/ScheduleExplanationsCard.tsx` and `backend/opwise/domain/explanations.py`, explanations are computed only at aggregate levels (makespan, tardiness, machine utilization, bottleneck). Planners cannot inspect why an individual operation was scheduled at its given start time or what constraint caused its delay.

### Stage 5: Simulate Disruption
- **Implemented:** `ScenariosView.tsx` allows creating isolated scenarios branched from baseline schedules, injecting machine downtimes or urgent rush orders, and computing recovery plans.
- **Critical Flaw:** In `backend/opwise/services/scenario_math.py` (`synthesize_disrupted_factory`), the baseline factory's `current_time_minute` is discarded (defaulting to 0), and all operation lifecycle statuses are wiped (reverting to `PLANNED`). Simulating a disruption on an active factory causes the solver to re-schedule already completed work from $t=0$, violating physical reality and producing meaningless recovery plans.

### Stage 6: Compare Outcomes
- **Implemented:** `ScenarioComparisonCard.tsx` and `DualGanttComparison.tsx` compare baseline and recovery schedules, computing metric deltas ($\Delta C_{\max}, \Delta \sum w_j T_j$, late order count, on-time delivery rate) and operation timing divergences (`DELAYED`, `EXPEDITED`, `UNMODIFIED`).
- **Limitation:** In `DualGanttComparison.tsx`, `currentTimeMinute` is not passed to the `GanttChart` instances. As a result, the dual comparator omits the vertical plant clock line and lifecycle visual cues.

### Stage 7: Choose a Better Plan
- **Limitation:** There is currently no workflow action in `ScenariosView` to "Promote Recovery Plan to Active Schedule" or apply the recovery plan back to the live workspace factory state.

---

## 7. Evidence-Based Gap Analysis

A systematic gap analysis categorizing the current system state:

### 7.1 Implemented and Usable
- Workspace and Factory entity management with SQLite WAL durability (`persistence/`).
- 6 formal input classification rules and referential validation (`domain/validators.py`).
- Single and hierarchical lexicographic CP-SAT optimization (`solver/engine.py`).
- Execution-aware CP-SAT scheduling respecting $t_0$, completed operations, and locked in-progress durations (`solver/cp_sat_model.py`).
- Independent clean-room schedule verifier auditing all 8 invariants (`verifier/schedule_verifier.py`).
- Factory snapshot persistence and immutable schedule reconstruction (`services/snapshot.py`).
- 4-bar lifecycle visualization in primary Gantt chart with plant clock line (`GanttChart.tsx`).
- Scenario branching, delta persistence, and comparison data structures (`services/scenario_service.py`).
- Client-side static demo mode with pre-solved fixtures (`frontend/src/demo/`).

### 7.2 Implemented but Incomplete or Disconnected
- **Scenario Disruption Factory Synthesis (`synthesize_disrupted_factory`):**
  - *Evidence:* In `backend/opwise/services/scenario_math.py`, lines 80–93 copy operations without preserving `status`, `actual_start_minute`, `actual_end_minute`, or `remaining_duration_minutes`. Line 117 constructs `Factory(...)` without passing `current_time_minute`.
  - *Effect:* Reoptimization of a scenario branches from $t=0$ as an offline batch, breaking execution awareness.
- **Disruption Input Validation (`validate_disruption`):**
  - *Evidence:* In `backend/opwise/services/scenario_math.py`, lines 29–51 validate that machines exist and downtime intervals are positive, but do not validate that added downtimes end after $t_0$, do not check for collisions with active in-progress operations, and do not validate that rush orders have release dates $\ge t_0$.
- **Dual Gantt Timeline Comparison (`DualGanttComparison.tsx`):**
  - *Evidence:* In `frontend/src/views/scenarios/DualGanttComparison.tsx`, lines 95–104 and 125–134 instantiate `GanttChart` for baseline and recovery schedules without providing the `currentTimeMinute` prop.
  - *Effect:* The comparator canvas does not render the plant clock line or lifecycle badges.

### 7.3 Specified but Missing from UI
- **Shop Floor Execution Dispatch Controls:**
  - *Evidence:* `frontend/src/views/factory/OrderModal.tsx` provides no input fields for operation status or execution timestamps. `FactoryView.tsx` provides no clock display or clock advancement controls.
  - *Effect:* Execution-aware factories cannot be configured through the web interface; they can only be created via raw API calls.

### 7.4 Absent from Both Code and Current Specifications
- **Operation-Level Constraint Attribution:**
  - Neither the backend nor the frontend identifies the active binding constraint for individual operation start times ($S_{j,k} == \text{bound}$).
- **Scenario Promotion / Plan Commitment:**
  - No mechanism exists to replace the live factory schedule with an approved recovery scenario.

---

## 8. Candidate Milestone 15C Directions

Three candidate directions are proposed, each addressing a verified, distinct product need.

---

### Candidate 1: Execution-Aware Disruption Recovery & Rescheduling (Scenario Lifecycle Integration)

#### 1. Name and Objective
- **Title:** *Execution-Aware Disruption Recovery & Rescheduling (Scenario Lifecycle Integration)*
- **Objective:** Reconcile the Disruption Scenario engine with Milestone 15B's execution-aware domain model. Ensure that scenario synthesis preserves the plant clock and operation lifecycles, disruption injection validates against the execution horizon, reoptimization solves an execution-aware recovery plan from $t_0$, and the dual Gantt comparator visualizes the plant clock and lifecycle bars.

#### 2. Current-State Evidence
- `backend/opwise/services/scenario_math.py` (lines 80–93, 117): Strips operation lifecycle fields and drops `current_time_minute`.
- `backend/opwise/services/scenario_math.py` (lines 29–51): Disruption validation ignores plant clock boundaries.
- `frontend/src/views/scenarios/DualGanttComparison.tsx` (lines 95–104, 125–134): Omits `currentTimeMinute` prop from `GanttChart`.
- `frontend/src/views/scenarios/CreateScenarioModal.tsx` (lines 38, 43): Defaults downtime start and rush order release to 0 instead of baseline $t_0$.

#### 3. User Journey
- **Starting State:** User has an active workspace with plant clock $t_0 = 50$, one completed operation, one in-progress operation (locked until $t=80$), and several planned operations. A baseline schedule is generated and verified.
- **User Action:** User navigates to `ScenariosView` and clicks "+ New Disruption Scenario".
- **System Behavior:** Modal pre-fills downtime start or rush order release date with baseline clock $t_0 = 50$. Disruption validation verifies that injected downtime does not collide with the locked in-progress operation on the affected machine.
- **Reoptimization:** User clicks "⚡ Reoptimize Scenario". CP-SAT solves the recovery plan: completed operations remain pinned in history, the in-progress operation remains locked until $t=80$, and remaining planned operations plus the disruption are scheduled starting at or after $t_0 = 50$.
- **Result:** Dual Gantt displays baseline and recovery schedules with aligned plant clock lines ($t_0 = 50$), striped elapsed bars, solid locked bars, and divergence highlights showing only operations that shifted in the future ($t \ge 50$).

#### 4. Technical Scope
- **Backend:**
  - Modify `synthesize_disrupted_factory` in `scenario_math.py` to preserve `base_factory.current_time_minute` and copy `status`, `actual_start_minute`, `actual_end_minute`, and `remaining_duration_minutes` for all existing operations.
  - Enhance `validate_disruption` in `scenario_math.py` to enforce that added downtimes satisfy $dt.\text{end} > t_0$, do not collide with active in-progress operations at $t_0$, and that added rush orders satisfy $r_j \ge t_0$.
  - Update `ScenarioService` in `scenario_service.py` to ensure recovery schedules persist `current_time_minute` in the schedule model and snapshot.
  - Update divergence calculation in `compute_operation_divergences` to verify that completed historical operations are never flagged as diverged.
- **Frontend:**
  - Update `CreateScenarioModal.tsx`, `DowntimeDisruptionForm.tsx`, and `RushOrderDisruptionForm.tsx` to initialize timestamps with the baseline schedule's `current_time_minute`.
  - Update `DualGanttComparison.tsx` to forward `currentTimeMinute={baselineSchedule.current_time_minute}` and `currentTimeMinute={recoverySchedule.current_time_minute}` to both `GanttChart` instances.
- **Tests:**
  - Unit tests in `test_scenario_math.py` testing execution-aware disruption synthesis and validation.
  - Integration tests in `test_scenarios_api.py` verifying full reoptimization flow with plant clock $> 0$ and mixed lifecycle operations.
  - Frontend tests in `scenarios.test.tsx` verifying dual Gantt clock rendering and form initialization.

#### 5. Correctness Risks
- **Downtime vs In-Progress Collisions:** Injected downtime starting during an in-progress locked window must be caught and rejected gracefully with HTTP 422 `HISTORICAL_DOWNTIME_CONFLICT` rather than causing solver infeasibility.
- **Historical Immutability:** Pre-disruption completed operations must remain bitwise identical between baseline and recovery schedules.

#### 6. Acceptance Criteria
- `AC-15C-01`: `synthesize_disrupted_factory` preserves `current_time_minute` and all operation lifecycle states from baseline factory.
- `AC-15C-02`: `validate_disruption` rejects downtimes ending before $t_0$ or colliding with in-progress operations at $t_0$.
- `AC-15C-03`: `validate_disruption` rejects rush orders with release time $< t_0$.
- `AC-15C-04`: Recovery schedule generated via `POST /api/v1/workspaces/{id}/scenarios/{id}/reoptimize` preserves $t_0$, pins completed operations, respects in-progress locks, and passes independent verification with `VERIFIED`.
- `AC-15C-05`: `compute_operation_divergences` reports 0 divergence for historical completed operations.
- `AC-15C-06`: `DualGanttComparison` renders the plant clock line and lifecycle bars for both baseline and recovery schedules.

#### 7. Out of Scope
- Shop floor clock advancement UI in `FactoryView` (belongs to Candidate 2).
- Automatic promotion of recovery schedule to active factory state.
- Probabilistic disruption simulation (MTBF/MTTR distributions).

#### 8. Complexity & Risk
- **Complexity:** Medium (3–4 days).
- **Schema Migration:** None required. `scenarios` and `schedules` tables already possess required JSON columns and `current_time_minute`.
- **Operating Cost:** ₹0 (Local CP-SAT and SQLite).

#### 9. Portfolio Value
Demonstrates advanced operations research software engineering by solving the realistic industrial problem of dynamic schedule repair under execution commitments. Proves that scenario simulation accounts for physical plant state rather than resetting to a naive origin.

#### 10. Dependency Analysis
- **Prerequisite:** Milestone 15B (completed and verified).
- **Relationship:** Foundational; unlocks true value of Milestone 15B before user-facing dispatch controls are introduced.

---

### Candidate 2: Shop Floor Execution Dispatcher & Plant Clock Control (Execution UI & Live State Tracking)

#### 1. Name and Objective
- **Title:** *Shop Floor Execution Dispatcher & Plant Clock Control (Execution UI & Live State Tracking)*
- **Objective:** Provide interactive UI controls in `FactoryView` and `PlanningView` to view and advance the plant clock ($t_0$) and manage operation lifecycle transitions (`PLANNED` $\to$ `IN_PROGRESS` $\to$ `COMPLETED`), making Milestone 15's execution-aware engine accessible to human planners through the web application.

#### 2. Current-State Evidence
- `frontend/src/views/factory/OrderModal.tsx`: Lacks fields for operation status, actual start, actual end, or remaining duration.
- `frontend/src/views/FactoryView.tsx`: Displays no plant clock widget and provides no mechanism to advance $t_0$.
- `frontend/src/views/planning/OptimizationParametersForm.tsx`: Does not display the active workspace plant clock or allow an explicit clock override.

#### 3. User Journey
- **Starting State:** Factory has 3 orders with planned operations at clock $t_0 = 0$.
- **User Action:** In `FactoryView`, user clicks "Advance Plant Clock" to set $t_0 = 30$. In `OrdersTab`, user clicks on Order 1 Step 1 and transitions status to `COMPLETED` (start: 0, end: 25). User transitions Step 2 to `IN_PROGRESS` (start: 25, remaining: 20).
- **System Behavior:** Client-side form validates monotonic order sequence, checks actual start against order release date, and validates that completed end is $\le 30$. `PUT /api/v1/workspaces/{id}/factory` persists the state.
- **Optimization:** In `PlanningView`, user sees "Active Plant Clock: Minute 30" with a summary badge "1 In-Progress, 1 Completed". Optimization runs and displays the execution-aware Gantt.

#### 4. Technical Scope
- **Backend:**
  - Verify that `PUT /api/v1/workspaces/{id}/factory` handles partial operation updates cleanly.
  - Optional convenience endpoint: `POST /api/v1/workspaces/{id}/factory/advance-clock` with delta minutes.
- **Frontend:**
  - Add `PlantClockCard` component to `FactoryView` showing current clock, status, and an "Advance Clock" modal with validation.
  - Update `OrderModal.tsx` to include an expandable "Execution Status & Timestamps" section per operation step.
  - Add client-side validation in `OrderModal.tsx` matching domain rules (e.g. at most one in-progress op per order, monotonic timestamps).
  - Update `OptimizationParametersForm.tsx` in `PlanningView` to display current plant clock and provide an optional clock override input.
- **Tests:**
  - Frontend Vitest tests for `PlantClockCard`, `OrderModal` lifecycle fields, and form validation.
  - End-to-end integration tests for UI-driven factory clock advancement and optimization.

#### 5. Correctness Risks
- **Client/Server Validation Desynchronization:** Complex lifecycle rules in `domain/validators.py` must be faithfully mirrored in TypeScript form validation to avoid unexpected 422 errors.

#### 6. Acceptance Criteria
- `AC-15C-01`: `FactoryView` displays the current plant clock and provides an "Advance Clock" dialog.
- `AC-15C-02`: Advancing clock persists value via API and updates workspace state.
- `AC-15C-03`: `OrderModal` allows marking operations as `IN_PROGRESS` or `COMPLETED` with appropriate timestamp fields.
- `AC-15C-04`: `OrderModal` prevents invalid transitions (e.g., negative duration, end before start).
- `AC-15C-05`: `PlanningView` displays active plant clock and forwards optional clock override to optimization request.

#### 7. Out of Scope
- Scenario disruption synthesis (Candidate 1).
- Live WebSocket execution streaming.
- Barcode/RFID scanner hardware integration.

#### 8. Complexity & Risk
- **Complexity:** Medium (3–4 days).
- **Schema Migration:** None required.
- **Operating Cost:** ₹0.

#### 9. Portfolio Value
Showcases production-grade frontend engineering, complex form state management, and ergonomic UX design for operations management software.

#### 10. Dependency Analysis
- **Prerequisite:** Milestone 15B.
- **Relationship:** Complementary to Candidate 1; provides the user-facing entry point for execution state.

---

### Candidate 3: Deterministic Operation Delay & Constraint Binding Attribution Engine (Root-Cause Delay Attribution)

#### 1. Name and Objective
- **Title:** *Deterministic Operation Delay & Constraint Binding Attribution Engine (Root-Cause Delay Attribution)*
- **Objective:** Augment Opwise's schedule explanation engine with mathematical delay attribution for every scheduled operation. Determine the exact binding constraint ($S_{j,k} == \text{bound}$) that determined each operation's start time: routing sequence predecessor, machine clash with another order, machine downtime window, raw material release date, or plant clock execution lock.

#### 2. Current-State Evidence
- `backend/opwise/domain/explanations.py`: Generates explanations only for makespan, plant-wide delivery performance, order tardiness, machine utilization, and primary bottleneck.
- `frontend/src/views/schedules/gantt/GanttOperationDetail.tsx`: Displays only static interval timestamps without explaining why the operation was scheduled there.

#### 3. User Journey
- **Starting State:** User inspects a schedule where Order 3 completes 40 minutes late.
- **User Action:** In the Gantt chart, user clicks on Operation 2 of Order 3.
- **System Behavior:** Operation detail modal opens with a dedicated "Start Time Attribution" card:
  - *Start Time:* Minute 85.
  - *Binding Constraint:* `MACHINE_QUEUE_DELAY`.
  - *Explanation:* "Operation waited 35 minutes for Machine 2 to be released by Order 1 Operation 1 (completed at minute 85). Predecessor completed at minute 50 (slack: 35m). Release time was minute 0."
  - *Constraint Hierarchy:* Predecessor end = 50, Machine available = 85, Downtime = None, Release = 0, Plant Clock = 30 $\to$ Binding bound is Machine 2 at minute 85.

#### 4. Technical Scope
- **Backend:**
  - Create `backend/opwise/domain/attribution.py` implementing `analyze_operation_binding_constraints(factory, schedule)`.
  - Calculate for each operation:
    $$\text{binding\_source} = \operatorname{argmax} \left( \text{end}(O_{j, k-1}), \text{prev\_machine\_op\_end}(m), \text{downtime\_end}(m), r_j, t_0 \right)$$
  - Expose attribution data in `GET /api/v1/workspaces/{id}/schedules/{id}/explanations` or schedule response.
- **Frontend:**
  - Update `GanttOperationDetail.tsx` to render binding constraint badges and detailed narrative explanations.
  - Add "Delay Attribution" tab or breakdown in `ReportsView`.
- **Tests:**
  - Unit tests in `test_attribution.py` validating correct identification of all 5 binding constraint types.
  - Integration tests for attribution API serialization.

#### 5. Correctness Risks
- **Multiple Simultaneous Bounds:** When two constraints coincide exactly (e.g., predecessor ends at 50 and machine becomes free at 50), the system must report joint binding constraints deterministically without arbitrary preference.

#### 6. Acceptance Criteria
- `AC-15C-01`: Attribution engine correctly classifies `PRECEDENCE_BOUND`, `MACHINE_QUEUE_BOUND`, `DOWNTIME_BOUND`, `RELEASE_BOUND`, and `CLOCK_LOCK_BOUND`.
- `AC-15C-02`: Coincident bounds are reported as `JOINT_BOUND` with all active constraints enumerated.
- `AC-15C-03`: `GanttOperationDetail` renders binding constraint badges and mathematical rationale.

#### 7. Out of Scope
- Dynamic constraint relaxation / LP dual sensitivity analysis.
- Scenario disruption synthesis (Candidate 1).

#### 8. Complexity & Risk
- **Complexity:** Low-Medium (2–3 days).
- **Schema Migration:** None required.
- **Operating Cost:** ₹0.

#### 9. Portfolio Value
Demonstrates advanced operations research concepts (KKT/slack analysis, binding constraint detection) made accessible through intuitive UI explanations.

#### 10. Dependency Analysis
- **Prerequisite:** Milestone 15B.
- **Relationship:** Analytical value-add; can be implemented independently of scenario synthesis or UI clock controls.

---

## 9. Candidate Scoring Matrix & Scoring Definitions

To select the most valuable increment objectively, the candidates are evaluated across eight explicit criteria scored from 1 (lowest) to 5 (highest):

### Scoring Criteria Definitions
1. **Core Product Value (Weight: 20%):** Direct alignment with the Opwise mission: deterministic optimization, disruption simulation, and explainable operations decisions. (5 = Solves broken core functionality; 1 = Nice-to-have cosmetic feature).
2. **Missing/Inadequate Evidence (Weight: 15%):** Degree to which actual source code proves the current implementation is broken, contradictory, or absent. (5 = Active bug/blocker in existing feature; 1 = Feature never planned).
3. **Engineering Depth (Weight: 15%):** Demonstrates sophisticated algorithmic, domain, or architectural engineering. (5 = Multi-layer OR and domain reconciliation; 1 = Basic CRUD).
4. **User-Visible Usefulness (Weight: 15%):** Immediate tangible impact on a planner using the platform. (5 = Essential for intended user workflow; 1 = Minor convenience).
5. **Milestone Feasibility (Weight: 10%):** Tightly bounded scope achievable within a single focused release without bloat. (5 = Cleanly isolated, low refactor risk; 1 = Open-ended, high blast radius).
6. **Testability & Invariant Verification (Weight: 10%):** Amenable to automated verification, clean-room invariant testing, and mutation auditing. (5 = 100% deterministic test coverage; 1 = Difficult to test deterministically).
7. **Architectural Compatibility (Weight: 10%):** Fits existing FastAPI, SQLite WAL, React, and CP-SAT structure without schema churn. (5 = 100% compatible; 1 = Requires major breaking changes).
8. **₹0 Local-First Requirement (Weight: 5%):** Guarantees zero cloud cost, no paid APIs, and no external dependencies. (All candidates must score 5).

### Evaluation Matrix

| Criterion | Weight | Candidate 1: Disruption Recovery | Candidate 2: Execution Dispatcher | Candidate 3: Delay Attribution |
|---|:---:|:---:|:---:|:---:|
| 1. Core Product Value | 20% | **5** (1.00) | **4** (0.80) | **4** (0.80) |
| 2. Missing/Inadequate Evidence | 15% | **5** (0.75) | **4** (0.60) | **3** (0.45) |
| 3. Engineering Depth | 15% | **5** (0.75) | **3** (0.45) | **4** (0.60) |
| 4. User-Visible Usefulness | 15% | **4** (0.60) | **5** (0.75) | **4** (0.60) |
| 5. Milestone Feasibility | 10% | **4** (0.40) | **4** (0.40) | **5** (0.50) |
| 6. Testability & Invariant Verification | 10% | **5** (0.50) | **4** (0.40) | **5** (0.50) |
| 7. Architectural Compatibility | 10% | **5** (0.50) | **4** (0.40) | **5** (0.50) |
| 8. ₹0 Local-First Fit | 5% | **5** (0.25) | **5** (0.25) | **5** (0.25) |
| **Weighted Total Score** | **100%** | **4.75 / 5.00** | **4.05 / 5.00** | **4.15 / 5.00** |
| **Rank** | | **1st (Primary)** | **3rd** | **2nd** |

---

## 10. Risk Comparison

| Risk Category | Candidate 1: Disruption Recovery | Candidate 2: Execution Dispatcher | Candidate 3: Delay Attribution |
|---|---|---|---|
| **Mathematical Correctness Risk** | **Medium:** Must guarantee that disruption synthesis cannot produce infeasible historical locks or violate half-open intervals. | **Low:** Domain validators already enforce all invariants on the server. | **Low:** Pure post-solve analytical classification; cannot break schedules. |
| **Schema Migration Risk** | **Zero:** Existing database schema and snapshot JSON structures already support all required fields. | **Zero:** `workspaces` and `operations` tables already have columns from Migrations 003 & 004. | **Zero:** No database schema changes needed. |
| **Regression Blast Radius** | **Low:** Confined to `scenario_math.py`, `scenario_service.py`, and `DualGanttComparison.tsx`. | **Medium:** Modifies core `FactoryView` and `OrderModal.tsx` editing flows. | **Low:** Additive only; touches explanation generator and detail modal. |
| **UI Usability Risk** | **Low:** Enhances existing Dual Gantt comparator with plant clock lines and lifecycle badges. | **Medium:** Risk of cluttered modal forms when entering multiple timestamps per step. | **Low:** Adds clear, informative pill badges to existing modal. |

---

## 11. Recommended Candidate and Justification

### Primary Recommendation: Candidate 1 — Execution-Aware Disruption Recovery & Rescheduling (Scenario Lifecycle Integration)

#### Justification
1. **Eliminates a Severe Architectural Defect:** The scenario engine currently contains an active architectural defect: it strips execution state and resets $t_0 \to 0$ when branching what-if disruptions from execution-aware schedules. Leaving this unaddressed while building UI features on top would compound technical debt and produce invalid recovery schedules.
2. **Completes the Core Opwise Value Proposition:** Opwise is marketed as an operations intelligence platform whose primary differentiator is simulating disruptions (machine breakdowns and rush orders) and comparing outcomes to choose a better recovery plan. Candidate 1 ensures that disruption simulation reflects physical plant reality.
3. **Directly Builds Upon Milestone 15B:** Milestone 15B created the execution-aware CP-SAT solver and verifier. Candidate 1 connects the scenario engine to this solver, realizing the full potential of Milestone 15B's mathematical formulation.
4. **Zero Migration & Zero Cost:** Candidate 1 requires zero database migrations, zero new dependencies, and maintains strict ₹0 operating costs.

#### Recommended Sequence
- **Milestone 15C (Immediate):** Candidate 1 — Execution-Aware Disruption Recovery & Rescheduling.
- **Milestone 15D (Follow-on):** Candidate 2 — Shop Floor Execution Dispatcher & Plant Clock Control.
- **Milestone 15E (Subsequent):** Candidate 3 — Deterministic Operation Delay & Constraint Binding Attribution.

---

## 12. Preliminary Scope and Exclusions for Milestone 15C

### In Scope
1. **Disrupted Factory Synthesis (`synthesize_disrupted_factory`):**
   - Retain `base_factory.current_time_minute` in the synthesized factory.
   - Preserve all operation lifecycle fields (`status`, `actual_start_minute`, `actual_end_minute`, `remaining_duration_minutes`) for existing baseline operations.
   - Tag newly added rush order operations explicitly as `OperationStatus.PLANNED`.
2. **Disruption Input Validation (`validate_disruption`):**
   - Validate that added machine downtimes have $dt.\text{end} > t_0$ (downtimes ending in the past are rejected with HTTP 422 `HISTORICAL_DOWNTIME_CONFLICT`).
   - Validate that added machine downtimes do not overlap active in-progress operations at $t_0$ on the affected machine.
   - Validate that added rush orders have $r_j \ge t_0$.
3. **Execution-Aware Scenario Reoptimization (`ScenarioService`):**
   - Ensure `reoptimize_scenario` passes the synthesized execution-aware factory to `CPSATScheduler`.
   - Preserve `current_time_minute` in the resulting recovery schedule model and snapshot.
   - Verify recovery schedules with independent `ScheduleVerifier` including Invariant 3 clock concordance.
4. **Operation Timing Divergence Analysis (`compute_operation_divergences`):**
   - Ensure completed historical operations are never classified as `DELAYED` or `EXPEDITED`.
   - Restrict divergence reporting to operations with $t \ge t_0$.
5. **Frontend Dual Gantt Comparison (`DualGanttComparison.tsx`):**
   - Forward `currentTimeMinute` to both baseline and recovery `GanttChart` instances.
   - Render vertical plant clock markers and 4-bar lifecycle representations across both timeline lanes.
6. **Disruption Form Initialization (`CreateScenarioModal.tsx`):**
   - Initialize downtime start times and rush order release dates with the baseline schedule's `current_time_minute`.
7. **Comprehensive Automated Verification:**
   - Unit tests in `backend/tests/unit/test_scenario_math.py`.
   - Integration tests in `backend/tests/integration/test_scenarios_api.py`.
   - Frontend tests in `frontend/src/tests/scenarios.test.tsx`.

### Out of Scope
- Shop floor clock advancement controls in `FactoryView` (deferred to Milestone 15D).
- Direct lifecycle editing modal in `OrdersTab` (deferred to Milestone 15D).
- Root-cause delay attribution engine (deferred to Milestone 15E).
- Automatic promotion of recovery schedule to active factory state.
- Dynamic stochastic simulation (Poisson breakdown arrivals).

---

## 13. Compatibility and Migration Assessment

- **Database Migrations:** **NONE.** The database schema already possesses `workspaces.current_time_minute` (Migration 004), `schedules.current_time_minute` (Migration 003), and `operations` lifecycle columns (Migration 003). `scenarios.disruption_delta_json` and `scenario_comparisons.critical_path_divergence_json` are flexible JSON fields.
- **API Contracts:** **Fully backwards compatible.** No endpoint URLs or request body schemas change. Existing requests continue to work; validation merely rejects invalid past disruptions relative to $t_0$.
- **Demo Fixtures:** **100% Unaltered.** Demos 1–6 operate under static fixture definitions and remain completely untouched.
- **Operating Cost:** **Strictly ₹0.** All computation is executed locally via Python 3.12, SQLite 3, OR-Tools CP-SAT, and React 19.

---

## 14. Proposed Acceptance Register for Milestone 15C

| Acceptance ID | Category | Expected Behavior | Verification Test Layer |
|---|---|---|---|
| **AC-15C-01** | Synthesis | `synthesize_disrupted_factory` clones `base_factory` preserving `current_time_minute` and all operation lifecycle fields (`status`, `actual_start`, `actual_end`, `rem_dur`). | Unit (`test_scenario_math.py`) |
| **AC-15C-02** | Validation | `validate_disruption` rejects downtime with $\text{end} \le t_0$ with HTTP 422 `HISTORICAL_DOWNTIME_CONFLICT`. | Unit & Integration |
| **AC-15C-03** | Validation | `validate_disruption` rejects downtime overlapping an active in-progress operation at $t_0$ on the same machine. | Unit & Integration |
| **AC-15C-04** | Validation | `validate_disruption` rejects rush orders with release time $< t_0$ with HTTP 422 `INVALID_SEQUENCE`. | Unit & Integration |
| **AC-15C-05** | Solver | Reoptimizing a scenario with baseline $t_0 > 0$ pins completed operations, locks in-progress operations for remaining duration, schedules rush orders $\ge t_0$, and produces `OPTIMAL` or `FEASIBLE`. | Integration (`test_scenarios_api.py`) |
| **AC-15C-06** | Verifier | Reoptimized recovery schedule passes independent verification (`VERIFIED`) auditing all 8 invariants and clock concordance. | Integration (`test_scenarios_api.py`) |
| **AC-15C-07** | Divergence | `compute_operation_divergences` classifies historical completed operations as `UNMODIFIED` (0 delta) and measures divergence only for planned operations. | Unit (`test_scenario_math.py`) |
| **AC-15C-08** | Infeasibility | An infeasible recovery disruption (e.g. rush order cannot be scheduled within horizon) returns status `INFEASIBLE`, verification `SKIPPED`, and empty operations cleanly. | Integration (`test_scenarios_api.py`) |
| **AC-15C-09** | UI Comparator | `DualGanttComparison` renders vertical plant clock lines and 4-bar lifecycle representations for both baseline and recovery schedules. | Frontend (`scenarios.test.tsx`) |
| **AC-15C-10** | UI Modal | `CreateScenarioModal` pre-populates disruption downtime start and rush order release date with baseline `current_time_minute`. | Frontend (`scenarios.test.tsx`) |

---

## 15. Specification-Change Plan

Upon approval of Milestone 15C, the following documentation updates should be staged:

| Document | Required Modification | Rationale | Timing |
|---|---|---|---|
| `SPECIFICATION.md` | Update Section 1.3 line 70 and Section 6.1: revise *"reoptimization evaluates the full plan from schedule origin ($t=0$)"* to reflect execution-aware recovery from plant clock $t_0$. | Align master specification with execution-aware recovery behavior. | Milestone 15C Release |
| `SOLVER_MODEL.md` | Update Section 6 (Disruption Model): document execution-aware recovery formulation ($S \ge \max(r_j, t_0)$, in-progress locking under disruption). | Ensure mathematical specification reflects recovery constraints. | Milestone 15C Release |
| `DATA_AND_API.md` | Update Section 3.2 (Scenario Endpoints): document clock-aware disruption validation rules and error codes (`HISTORICAL_DOWNTIME_CONFLICT`). | Maintain accurate API contract documentation. | Milestone 15C Release |
| `DECISIONS.md` | Add ADR-013: *Execution-Aware Disruption Recovery and Snapshot Reconciliation*. | Formally record architecture decision and trade-offs. | Milestone 15C Release |

---

## 16. Open Questions and Unresolved Decisions

1. **Question 1: Rush Order Preemption of In-Progress Operations:**
   - *Issue:* Should a high-priority rush order ever be allowed to preempt an active `IN_PROGRESS` operation on the shop floor?
   - *Current Decision:* **No.** Milestone 15 established non-preemption as an unyielding boundary invariant (`DECISIONS.md` Section 3). In-progress operations must run to completion for their `remaining_duration_minutes`.
2. **Question 2: Recovery Schedule Promotion:**
   - *Issue:* When a recovery plan is approved by the user, should clicking "Promote Plan" overwrite the live workspace factory state?
   - *Current Decision:* Deferred to Milestone 15D. Milestone 15C focuses on analytical comparison and schedule repair without destructive live workspace mutation.

---

## 17. Implementation Approval Gate

Milestone 15C is currently in **PROPOSAL ONLY** status.

- **Source Code Edits:** 0 files modified.
- **Test Edits:** 0 files modified.
- **Migration Edits:** 0 files added.
- **Dependency Changes:** 0 packages added.
- **Git State:** 0 commits made, 0 branches created.

**Implementation will not begin until explicit authorization is granted by the user.**

---

## 18. References to Source Files and Tests

- `backend/opwise/services/scenario_service.py` ([scenario_service.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/opwise/services/scenario_service.py#L233-L280))
- `backend/opwise/services/scenario_math.py` ([scenario_math.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/opwise/services/scenario_math.py#L29-L117))
- `backend/opwise/services/snapshot.py` ([snapshot.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/opwise/services/snapshot.py#L19-L105))
- `backend/opwise/solver/cp_sat_model.py` ([cp_sat_model.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/opwise/solver/cp_sat_model.py#L30-L120))
- `backend/opwise/verifier/invariant_auditor.py` ([invariant_auditor.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/opwise/verifier/invariant_auditor.py#L197-L218))
- `backend/tests/integration/test_scenarios_api.py` ([test_scenarios_api.py](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/backend/tests/integration/test_scenarios_api.py#L46-L120))
- `frontend/src/views/scenarios/DualGanttComparison.tsx` ([DualGanttComparison.tsx](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/frontend/src/views/scenarios/DualGanttComparison.tsx#L95-L135))
- `frontend/src/views/scenarios/CreateScenarioModal.tsx` ([CreateScenarioModal.tsx](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/frontend/src/views/scenarios/CreateScenarioModal.tsx#L35-L50))
- `frontend/src/views/schedules/gantt/GanttChart.tsx` ([GanttChart.tsx](file:///E:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/frontend/src/views/schedules/gantt/GanttChart.tsx#L21-L47))
