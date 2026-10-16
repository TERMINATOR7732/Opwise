# Opwise — Test Plan, Release Gates, and Verification Protocol

- **Document ID:** OPW-TST-001
- **Status:** APPROVED FOR SPECIFICATION (Phase 0.3 Pre-Implementation Approval Gate)
- **Version:** 1.3.0
- **Last Updated:** 2026-10-16
- **Governance:** Governed by `PROJECT_RULES.md` (Opwise Permanent Constitution)
- **Discipline:** Gravitas Core Evidence-Backed Verification, Zero Fabricated Test Results

---

## 1. Quality Philosophy and Invariants

1. **Evidence-Backed Verification:** No test is ever reported as passed based on assumption, expectation, or model self-review. A test passes only when actual executable runner output (`pytest`, `vitest`, `playwright`) confirms zero exit errors and 100% passing assertions after code execution.
2. **Deterministic Reproducibility:** Solvers and test suites must run with pinned seeds (`random_seed=42`), single-worker search (`num_search_workers=1`), and bounded execution budgets.
3. **Clean-Room Verification:** The schedule verifier independently audits all schedules produced by the CP-SAT engine. Mutant test injection verifies that the verifier correctly catches illegal schedules.
4. **Honest Status Classification:**
   - **Specification defined:** Requirement and expected behavior are documented.
   - **Metadata verified:** External package registries or legal documents have been queried and verified.
   - **Requires implementation testing:** Actionable only through actual execution in Phase 1 implementation.
   - **Unresolved:** A real decision or evidence gap remains.

---

## 2. Comprehensive Test Matrix (12 Categories)

| Category ID | Category Name | Target Component | Verification Scope |
| :---: | :--- | :--- | :--- |
| **TM-01** | Domain Validation | `opwise.domain.validators` | Empty/no-work inputs, non-negative bounds, sequence continuity, valid machine references. |
| **TM-02** | Solver Correctness | `opwise.solver.cp_sat_model` | CP-SAT formulation, precedence, machine non-overlap, downtime boundaries, lexicographic gating. |
| **TM-03** | Verifier Audit & Mutant Injection | `opwise.verifier` | Clean-room detection of artificial invalid schedules (mutants). |
| **TM-04** | Objective Math & Edge Cases | `opwise.domain.metrics` | Origin $t=0$ makespan, idle time vs downtime, net utilization, no-work empty schedules. |
| **TM-05** | Infeasible & Timeout Handling | `opwise.solver` | Impossible downtime intervals, conflicting release times, time limit timeouts. |
| **TM-06** | API Routes & Error Envelopes | `opwise.api` | OpenAPI conformance, 422 Unprocessable Entity, 404, 500, 504 error envelopes. |
| **TM-07** | Database Transactions & WAL | `opwise.persistence` | Atomic multi-record commits, failed transaction rollbacks, SQLite WAL concurrency, recovery tests. |
| **TM-08** | Import / Export Round-Trip | `opwise.io` | CSV / Excel parsing, downtime normalization, header validation, malformed file rejections. |
| **TM-09** | Scenario Branching & Immutability | `opwise.persistence` | Baseline immutability, disruption deltas, scenario comparisons, unlike disclosures. |
| **TM-10** | Frontend Components & Gantt | `frontend/src/components` | SVG/Canvas Gantt rendering, tooltip accuracy, metric cards. |
| **TM-11** | Accessibility & Layout | `frontend/src` | WCAG 2.1 AA keyboard navigation, contrast, responsive layouts. |
| **TM-12** | Clean Install & Build Integrity | Build & Toolchain | Python wheel compatibility, TypeScript compilation, Vite build. |

---

### Detailed Test Specifications

#### TM-01: Domain Validation & Empty-State Tests
- **Test 01.1: Empty Workspace Optimize Request**
  - *Behavior:* Optimizing an empty workspace (0 machines, 0 orders) returns HTTP 422 `EMPTY_WORKSPACE`.
  - *Evidence Needed to Pass:* Runner verifies HTTP 422 with message `"Cannot optimize an empty workspace"`.
- **Test 01.2: No-Work State Factory**
  - *Behavior:* Factory with 3 machines but 0 orders returns HTTP 200 with `status: "NO_WORK_STATE"`, makespan=0, tardiness=0, 0 scheduled operations.
  - *Evidence Needed to Pass:* Schedule persisted with status `NO_WORK_STATE`, not `OPTIMAL`.
- **Test 01.3: Orders Without Operations**
  - *Behavior:* Submitting an order without operations returns HTTP 422 `ORDER_WITHOUT_OPERATIONS`.
  - *Evidence Needed to Pass:* Runner captures validation failure on order ID.
- **Test 01.4: Dangling Entity Reference**
  - *Behavior:* Operation referencing non-existent machine `M99` returns HTTP 422 `REFERENTIAL_INTEGRITY_VIOLATION`.
  - *Evidence Needed to Pass:* Error detail contains `"Machine 'M99' not found in workspace"`.

#### TM-02: Solver Correctness, Downtime Boundaries & Lexicographic Gating
- **Test 02.1: Simple 2-Job 2-Machine Flow Shop**
  - *Behavior:* Given 2 jobs and 2 machines, CP-SAT finds proven optimal makespan.
  - *Evidence Needed to Pass:* Solver status is `OPTIMAL`, verifier returns `is_valid = True`.
- **Test 02.2: Downtime Boundary Non-Collision**
  - *Behavior:* Operation ending at minute 60 and downtime starting at minute 60 do NOT collide. Downtime ending at minute 90 and operation starting at minute 90 do NOT collide.
  - *Evidence Needed to Pass:* Verifier passes with 0 downtime violations.
- **Test 02.3: Overlapping Downtime Canonical Merge**
  - *Behavior:* Two downtimes on M1 at $[30, 60)$ and $[50, 90)$ are merged into $[30, 90)$.
  - *Evidence Needed to Pass:* Telemetry confirms 1 merged downtime interval; no operation scheduled in $[30, 90)$.
- **Test 02.4: Adjacent Downtime Canonical Merge**
  - *Behavior:* Two adjacent downtimes $[30, 60)$ and $[60, 90)$ are merged into $[30, 90)$.
  - *Evidence Needed to Pass:* Merged interval occupies $[30, 90)$.
- **Test 02.5: Zero-Length Downtime Filtering**
  - *Behavior:* Downtime $[60, 60)$ is filtered out with advisory log.
  - *Evidence Needed to Pass:* Normalizer logs advisory message; CP-SAT interval count reduced.
- **Test 02.6: Lexicographic Stage 1 Optimal -> Stage 2 Optimal**
  - *Behavior:* Stage 1 proves tardiness optimum $Z_1^*$; Stage 2 solves $\min C_{\max}$ subject to $\sum w_j T_j \le Z_1^*$ and proves optimality.
  - *Evidence Needed to Pass:* `overall_status == "OPTIMAL"`, `stage1_status == "OPTIMAL"`, `stage2_status == "OPTIMAL"`.
- **Test 02.7: Lexicographic Stage 1 Optimal -> Stage 2 Feasible (Timeout)**
  - *Behavior:* Stage 1 is optimal, Stage 2 times out. The Stage 2 schedule **is returned** but labeled `FEASIBLE`.
  - *Evidence Needed to Pass:* `overall_status == "FEASIBLE"`, `stage1_status == "OPTIMAL"`, `stage2_status == "FEASIBLE"`, Stage 2 gap displayed.
- **Test 02.8: Lexicographic Stage 1 Feasible (Timeout) -> Suboptimal Reporting**
  - *Behavior:* Stage 1 times out. Stage 2 executes subject to $\sum w_j T_j \le Z_1$.
  - *Evidence Needed to Pass:* `overall_status == "FEASIBLE"`, labeled `FEASIBLE (SUBOPTIMAL - STAGE 1 OPTIMALITY UNPROVEN)`.

#### TM-03: Independent Verifier Mutant Injection Tests
- **Test 03.1: Overlapping Operations Mutant**
  - *Behavior:* Inject candidate schedule where Operation B starts on Machine 1 before Operation A completes.
  - *Evidence Needed to Pass:* Verifier returns `is_valid = False` with `INV_MACHINE_OVERLAP_DETECTED`.
- **Test 03.2: Downtime Collision Mutant**
  - *Behavior:* Inject schedule where operation runs during maintenance $[60, 90)$.
  - *Evidence Needed to Pass:* Verifier returns `is_valid = False` with `INV_DOWNTIME_COLLISION`.
- **Test 03.3: Precedence Violation Mutant**
  - *Behavior:* Inject schedule where Operation 2 starts before Operation 1 finishes.
  - *Evidence Needed to Pass:* Verifier returns `is_valid = False` with `INV_PRECEDENCE_VIOLATED`.
- **Test 03.4: Metric Discrepancy Mutant**
  - *Behavior:* Inject schedule with falsified makespan metric ($C_{\max} - 10$).
  - *Evidence Needed to Pass:* Verifier returns `is_valid = False` with `INV_METRIC_DISCREPANCY`.

#### TM-04: Objective Math & Edge Cases
- **Test 04.1: Schedule Origin Makespan**
  - *Behavior:* Schedule with operations from minute 30 to 90 has makespan 90, not 60.
  - *Evidence Needed to Pass:* `makespan_minutes == 90` ($C_{\max} = \max C_{j,k} - 0$).
- **Test 04.2: Machine Idle Time vs Planned Downtime**
  - *Behavior:* Machine with 40 min machining and 30 min downtime across a 100 min makespan has idle time $100 - 40 - 30 = 30$ min.
  - *Evidence Needed to Pass:* `idle_time == 30`.
- **Test 04.3: Net Utilization Denominator**
  - *Behavior:* On same machine, net utilization is $40 / (100 - 30) = 57.14\%$. Gross utilization is $40 / 100 = 40.0\%$.
  - *Evidence Needed to Pass:* `net_utilization == 57.14`, `gross_utilization == 40.0`.

#### TM-05: Infeasible & Timeout Handling
- **Test 05.1: 100% Downtime Infeasible Instance**
  - *Behavior:* Maintenance on M1 spans $[0, H)$, preventing required operations from fitting.
  - *Evidence Needed to Pass:* Solver returns status `INFEASIBLE`, verifier notes unschedulable instance.
- **Test 05.2: Solver Timeout Graceful Handling**
  - *Behavior:* Large instance solved with 1.0s limit terminates with `FEASIBLE` or `UNKNOWN` without crashing.
  - *Evidence Needed to Pass:* HTTP 200 returned, status is `FEASIBLE` or `UNKNOWN`, elapsed time $\le 1.5\text{s}$.

#### TM-06: API Routes & Error Envelopes
- **Test 06.1: Validation Error Envelope**
  - *Behavior:* Submitting invalid input returns HTTP 422 with structured `ErrorEnvelope`.
  - *Evidence Needed to Pass:* Response body contains `{"success": false, "error": {"code": "...", ...}}`.
- **Test 06.2: Request Timeout Enforcement**
  - *Behavior:* Request exceeding server-side execution envelope returns HTTP 504 Gateway Timeout.
  - *Evidence Needed to Pass:* HTTP 504 returned with structured error envelope.

#### TM-07: Database Transactions & Durability Tests
- **Test 07.1: Multi-Record Rollback on Mid-Transaction Failure**
  - *Behavior:* Constraint violation during bulk insert rolls back all records in transaction.
  - *Evidence Needed to Pass:* Target workspace remains in exact pre-update state.
- **Test 07.2: Process-Kill Recovery (OS Teardown)**
  - *Behavior:* Killing process mid-write leaves SQLite database uncorrupted. Upon restart, WAL replayed and uncommitted transaction rolled back.
  - *Evidence Needed to Pass:* `PRAGMA integrity_check;` returns `ok`.
  - *Honesty Note:* Verifies OS cleanup and WAL rollback; does not test physical power loss.
- **Test 07.3: Database Migration Mismatch on Startup**
  - *Behavior:* Database with outdated `alembic_version` causes startup to abort safely.
  - *Evidence Needed to Pass:* Application exits with code 1 and diagnostic message.

#### TM-08: Import / Export Round-Trip
- **Test 08.1: Clean CSV Round-Trip**
  - *Behavior:* Exporting factory to CSV and re-importing yields identical entities.
  - *Evidence Needed to Pass:* Zero deltas between exported and re-imported data.
- **Test 08.2: Excel Multi-Sheet Import Preview & Normalization**
  - *Behavior:* Uploading workbook with overlapping downtimes previews normalized merged intervals.
  - *Evidence Needed to Pass:* Preview table displays merged downtime rows.

#### TM-09: Scenario Branching & Unlike-Results Disclosures
- **Test 09.1: Baseline Schedule Immutability**
  - *Behavior:* Reoptimizing a scenario does not modify baseline timestamps.
  - *Evidence Needed to Pass:* Hash of baseline scheduled operations is unchanged.
- **Test 09.2: Unlike Comparison Warning**
  - *Behavior:* Comparing baseline (Makespan) with scenario (Tardiness) flags `objective_diff_detected: true` and includes warning text.
  - *Evidence Needed to Pass:* Warning banner present in comparison payload.

#### TM-10: Frontend Components & Gantt Rendering
- **Test 10.1: Operation Block Coordinates**
  - *Behavior:* Operation $[30, 60)$ renders with proportional width and X-offset.
  - *Evidence Needed to Pass:* DOM inspector verifies `rect` attributes `x = 30 * scale` and `width = 30 * scale`.
- **Test 10.2: Machine Downtime Visual Distinction**
  - *Behavior:* Downtime renders with distinct hatched pattern and "Planned Maintenance" tooltip.
  - *Evidence Needed to Pass:* Accessible role and pattern fill confirmed.

#### TM-11: Accessibility & Layout
- **Test 11.1: Keyboard Navigation on Gantt Elements**
  - *Behavior:* Full keyboard focus navigation across operation blocks via `Tab` and `Enter`.
  - *Evidence Needed to Pass:* ARIA attributes and focus rings verified.

#### TM-12: Clean Installation & Production Build
- **Test 12.1: Zero Lint and Type Errors**
  - *Behavior:* `tsc --noEmit` and `ruff check` complete with 0 errors.
  - *Evidence Needed to Pass:* Build commands return exit code 0.

#### TM-13: ₹0 Operating Cost & Dependency Governance
- **Test 13.1: Zero Remote API Invocations**
  - *Behavior:* During full solver execution, scenario simulation, and import/export, zero outbound network sockets are opened.
  - *Evidence Needed to Pass:* Automated mock network check verifies zero external HTTP/HTTPS requests.
- **Test 13.2: Dependency License Compliance**
  - *Behavior:* All backend and frontend dependencies use permissive licenses (MIT, Apache 2.0, BSD-3, Public Domain).
  - *Evidence Needed to Pass:* Automated license audit tool (`pip-licenses`, `license-checker`) returns 0 non-compliant licenses.

#### TM-14: Code Maintainability & Readability Acceptance
- **Test 14.1: Module and Function Review Thresholds**
  - *Behavior:* Functions target < 50 lines; modules target < 350 lines; zero cyclic imports.
  - *Evidence Needed to Pass:* Static linter scan reports compliance across domain, solver, verifier, and API packages.
- **Test 14.2: Architectural Boundary Enforcement**
  - *Behavior:* `domain/` and `verifier/` packages have zero imports from `persistence/`, `api/`, or `ortools`.
  - *Evidence Needed to Pass:* `import-linter` contract verification returns exit code 0.

#### TM-15: Continuous GitHub Backup & Source Control Hygiene
- **Test 15.1: Git Exclusion Boundary Audit**
  - *Behavior:* `.gitignore` properly excludes virtualenvs, `.sqlite3` runtime files, `.env` files, and build directories.
  - *Evidence Needed to Pass:* `git status --ignored` verifies runtime databases and node_modules are ignored.
- **Test 15.2: Database Backup Independence**
  - *Behavior:* `VACUUM INTO` creates an atomic database backup without locking or interfering with Git source tracking.
  - *Evidence Needed to Pass:* Backup file verified readable and integer-consistent via SQLite integrity check.

#### TM-16: Standalone Client-Side Demo Mode & Fallback
- **Test 16.1: Static Demo Build & Bundle Size**
  - *Behavior:* `npm run build:demo` completes with zero errors and outputs static assets suitable for GitHub Pages.
  - *Evidence Needed to Pass:* Vite build exit code 0; bundle contains all pre-solved demo JSON fixtures.
- **Test 16.2: Client-Side Analytical Verifier**
  - *Behavior:* In-browser TypeScript verifier (`clientVerifier.ts`) validates all 8 invariants across all 6 demo fixtures.
  - *Evidence Needed to Pass:* 100% pass rate reported by vitest on demo fixtures.

---

## 3. Concise Final Acceptance Matrix (Gate 4)

The following matrix maps each critical architectural requirement to its specification section, expected behavior, verification method, and execution phase:

| Req ID | Requirement Area | Specification Section | Expected Behavior | Verification Method | Execution Phase |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **REQ-EMPTY-1** | Empty Workspace | `DATA_AND_API.md` §3.3<br>`SOLVER_MODEL.md` §1 | Reject optimization with HTTP 422 `EMPTY_WORKSPACE`. Zero solver calls. | Unit & API Test | Requires Implementation Testing |
| **REQ-EMPTY-2** | No-Work State Factory | `DATA_AND_API.md` §3.3<br>`SOLVER_MODEL.md` §1 | Factory with machines but 0 orders accepted as `NO_WORK_STATE`. Solver bypassed. HTTP 200, metrics=0. | Unit & API Test | Requires Implementation Testing |
| **REQ-EMPTY-3** | Incomplete Orders | `DATA_AND_API.md` §3.3<br>`SOLVER_MODEL.md` §1 | Orders without operations rejected with HTTP 422 `ORDER_WITHOUT_OPERATIONS`. | Unit & API Test | Requires Implementation Testing |
| **REQ-STATUS-1** | Single Objective Status | `SOLVER_MODEL.md` §4 | Status `OPTIMAL` only if proven; `FEASIBLE` with gap if timeout. | Solver Integration Test | Requires Implementation Testing |
| **REQ-STATUS-2** | Lexicographic Proof Gate | `SOLVER_MODEL.md` §5.1 | Stage 1 must be `OPTIMAL` to fix $Z_1^*$. If Stage 1 is `FEASIBLE`, overall status strictly `FEASIBLE`. | Multi-Stage Test | Requires Implementation Testing |
| **REQ-STATUS-3** | Stage 2 Timeout Return | `SOLVER_MODEL.md` §5.1 | If Stage 1 is optimal and Stage 2 times out, Stage 2 schedule **is returned** with status `FEASIBLE`. | Multi-Stage Test | Requires Implementation Testing |
| **REQ-VERIF-1** | Schedule Verification | `SOLVER_MODEL.md` §6 | Clean-room verifier audits 8 invariants. Rejects and quarantines invalid schedules. | Verifier Test & Mutants | Requires Implementation Testing |
| **REQ-DOWN-1** | Downtime Boundaries | `SOLVER_MODEL.md` §3.1 | Boundary contact at minute $T$ ($[S, T)$ and $[T, D_e)$) does not collide. | Boundary Invariant Test | Requires Implementation Testing |
| **REQ-DOWN-2** | Downtime Merge Policy | `SOLVER_MODEL.md` §3.2 | Overlapping and adjacent downtimes canonically merged. Zero-length filtered; inverted rejected. | Normalizer Unit Test | Requires Implementation Testing |
| **REQ-DOWN-3** | Horizon & Overflow | `SOLVER_MODEL.md` §3.3 | $H = \max(r) + \sum p + \sum \text{Downtime}$. Reject $> 2^{31}-1$; cap at $10^7$ min. | Horizon Unit Test | Requires Implementation Testing |
| **REQ-METRIC-1** | Schedule Origin Makespan| `SPECIFICATION.md` §5.1<br>`SOLVER_MODEL.md` §2.1 | $C_{\max} = \max C_{j,k} - 0$ relative to $t=0$, not span $\max C - \min S$. | Metrics Math Test | Requires Implementation Testing |
| **REQ-METRIC-2** | Idle Time vs Downtime | `SPECIFICATION.md` §5.1 | Idle time strictly excludes planned downtime ($I_m = \max(0, C_{\max} - W_m - D_m)$). | Metrics Math Test | Requires Implementation Testing |
| **REQ-METRIC-3** | Net Utilization | `SPECIFICATION.md` §5.1 | $U_m = \frac{W_m}{C_{\max} - D_m} \times 100\%$. Available window denominator. | Metrics Math Test | Requires Implementation Testing |
| **REQ-SNAP-1** | Baseline Immutability | `DATA_AND_API.md` §1.1 | Scenarios branch from immutable baseline schedules. Baseline timestamps never mutate. | Persistence Test | Requires Implementation Testing |
| **REQ-COMP-1** | Scenario Disclosures | `DATA_AND_API.md` §1.1 | Comparisons between unlike objectives, order sets, or statuses display warning banners. | Comparison API Test | Requires Implementation Testing |
| **REQ-IMPORT-1**| Two-Phase Atomic Import| `DATA_AND_API.md` §4.3 | Phase 1 Preview (staged). Phase 2 Confirm (atomic commit/rollback). Zero silent drops. | Import Service Test | Requires Implementation Testing |
| **REQ-PERSIST-1| SQLite WAL Durability | `DATA_AND_API.md` §2.1 | `synchronous = NORMAL`, per-connection foreign keys, service transaction ownership. | DB Concurrency Test | Requires Implementation Testing |
| **REQ-PERSIST-2| WAL Backup Safety | `DATA_AND_API.md` §2.2 | Backups use `VACUUM INTO 'backup.sqlite3'` or SQLite Online Backup API. | Backup Restore Test | Requires Implementation Testing |
| **REQ-BUILD-1** | Build & Type Integrity | `TEST_AND_RELEASE_PLAN.md` §2 | Zero type errors (`tsc --noEmit`), clean bundle (`vite build`), 0 lint warnings. | CI Build Pipeline | Requires Implementation Testing |
| **REQ-COST-1**  | Strict ₹0 Budget       | `PROJECT_RULES.md` §1  | Zero paid APIs, zero remote LLMs, all OSS dependencies, runs offline. | Network & License Test | Requires Implementation Testing |
| **REQ-CODE-1**  | Code Maintainability   | `PROJECT_RULES.md` §4  | Unidirectional dependencies, zero cyclic imports, <50 line functions, <350 line modules. | Linter & Import Rule | Requires Implementation Testing |
| **REQ-GIT-1**   | Continuous GitHub Backup| `PROJECT_RULES.md` §5 | Backups committed & pushed at 14 milestones. Database `.sqlite3` excluded via .gitignore. | Git Audit & Status | Requires Implementation Testing |
| **REQ-DEMO-1**  | Standalone Static Demo | `PROJECT_RULES.md` §2  | GitHub Pages static SPA runs 6 demo fixtures with client-side verifier & clear banner. | Demo E2E Test | Requires Implementation Testing |

---

## 4. Resolution of the Four Verification Gates

### Gate 1: Dependency Compatibility
- **Status:** **METADATA VERIFIED / PENDING PHASE 1 IMPLEMENTATION TESTING.**
- **Evidence:**
  - Python 3.12.0 verified on host (`C:\Python312\python.exe`).
  - PyPI JSON API confirms pre-compiled wheel `ortools-9.15.6755-cp312-cp312-win_amd64.whl` (requires Python $\ge 3.9$).
  - PyPI JSON API confirms `fastapi==0.143.2`, `pydantic==2.14.1`, `sqlalchemy==2.1.4`, `openpyxl==3.1.5`, `pytest==9.1.1`.
  - Host Node.js `v24.21.0` and npm `11.19.0` verified. Vite 6 engine requirements (`^20.19.0 || >=22.12.0`) satisfied.
  - **Honesty Rule:** No clean virtualenv installation was executed during Phase 0. Pins are proposed architectural decisions.

### Gate 2: Benchmark Licensing
- **Status:** **SPECIFICATION DEFINED & METADATA VERIFIED.**
- **Evidence:**
  - J.E. Beasley, OR-Library Legal Issues, `http://people.brunel.ac.uk/~mastjjb/jeb/orlib/legal.html` (verified live HTTP access date: 2026-10-16).
  - Released under the **MIT License** (Copyright (c) 2010 J E Beasley). Raw benchmark data redistribution is permitted with copyright attribution. Surrounding author source code is excluded.
  - Shipped default demos are 100% clean-room original synthetic benchmarks.
  - Classic benchmarks lack release times, due dates, weights, and downtime; any imported classic benchmark synthesized with these fields must be explicitly labeled in the UI.

### Gate 3: Performance Limits and Benchmark Protocol
- **Status:** **SPECIFICATION DEFINED & PROTOCOL ESTABLISHED.**
- **Workload Profiles & Targets:**
  - Small (3–5 machines, 5–10 orders): 5.0s solver limit, $\le 6.0$s response target.
  - Medium (5–10 machines, 15–30 orders): 15.0s solver limit, $\le 16.5$s response target.
  - Large (10–20 machines, 50–100 orders): 30–60s solver limit, $\le 62.0$s response target.
- **Mandatory Disclosure:** Numbers are **engineering design targets**, not empirically measured benchmarks from this session. Time limits define an execution budget, not an optimality guarantee.

### Gate 4: Persistence and Recovery Acceptance Tests
- **Status:** **SPECIFICATION DEFINED & RECOVERY TESTS SPECIFIED.**
- **Durability Model:** SQLite 3 WAL mode with `PRAGMA synchronous = NORMAL;`, `PRAGMA foreign_keys = ON;`, `PRAGMA busy_timeout = 5000;`.
- **Failure Realism:** Software process-kill tests verify OS cleanup and SQLite WAL rollback; they do not test sudden physical power cuts.
- **Acceptance Tests:** REC-01 through REC-09 specify rollback, crash recovery, referential restrict, concurrent read/write isolation, safe online backups via `VACUUM INTO`, and startup migration mismatch halting.

---

## 5. Practical 14-Milestone Implementation and Delivery Plan

The following sequential roadmap breaks down future implementation into fourteen discrete, disciplined milestones. Each milestone defines strict prerequisites, deliverables, acceptance criteria, verification tests, git commit checkpoints, and definitions of done.

```
[M01: Scaffold]  ──> [M02: Domain] ──> [M03: Verifier] ──> [M04: CP-SAT]  ──> [M05: Lexicographic]
                                                                                   │
[M09: Gantt Canvas] <── [M08: UI Shell] <── [M07: Persistence & API] <── [M06: Metrics Engine]
      │
      └──> [M10: Scenarios Lab] ──> [M11: CSV/Excel I/O] ──> [M12: Hardening]
                                                                  │
[M14: Final Release] <── [M13: Demo Mode & Hosting] <────────────┘
```

---

### Milestone 01: Repository Scaffold, Monorepo Setup & CI Tooling
- **Scope:** Initialize git repository, configure `.gitignore` (strictly excluding `.venv`, `node_modules`, `*.sqlite3`, `.env`), scaffold directory structure (`backend/`, `frontend/`, `.github/`), configure Python 3.12 dependencies (`pyproject.toml`, `requirements.txt`), configure React 19 + TypeScript 5 dependencies (`package.json`), and set up GitHub Actions CI workflow (`ci.yml`).
- **Prerequisites:** Explicit user authorization to begin Phase 1.
- **Expected Files:** `.gitignore`, `backend/pyproject.toml`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/package.json`, `frontend/vite.config.ts`, `.github/workflows/ci.yml`.
- **Acceptance Criteria:** `pip install -r requirements.txt` and `npm ci` complete cleanly with 0 errors. CI workflow executes lint and typecheck on pull request / push. Runtime databases, logs, and venvs are strictly untracked.
- **Relevant Tests:** TM-12.1 (Lint and typecheck), TM-15.1 (Git exclusion boundaries).
- **Git Commit Checkpoint:** `build: initialize monorepo scaffold, pinned dependencies, and CI workflows`
- **GitHub Push Checkpoint:** Verify remote `main` branch created and initial commit pushed to GitHub.
- **Known Risks:** Windows line endings (`CRLF` vs `LF`) or native wheel installation issues on Windows.
- **Definition of Done:** CI pipeline runs green on GitHub; clean checkout verified in fresh directory.

---

### Milestone 02: Pure Domain Model, Invariants & Canonical Downtime Normalization
- **Scope:** Implement pure Python domain entities (`Machine`, `Order`, `Operation`, `Downtime`, `Schedule`), domain validators (6 input classifications, referential checks, positive processing times), and canonical downtime merge normalizer.
- **Prerequisites:** Milestone 01 complete.
- **Expected Files:** `backend/opwise/domain/entities.py`, `validators.py`, `exceptions.py`, `backend/tests/unit/test_domain.py`, `test_downtime_normalizer.py`.
- **Acceptance Criteria:** Domain models are pure Python dataclasses with zero framework or solver dependencies. Canonical merge correctly consolidates overlapping and contiguous downtimes; zero-length windows filter out; negative/inverted intervals reject with explicit errors; empty/no-work factories classified correctly.
- **Relevant Tests:** TM-01 (Empty & No-Work), TM-02 (Downtime boundaries & normalization).
- **Git Commit Checkpoint:** `feat(domain): implement core entities, validation rules, and canonical downtime merge`
- **GitHub Push Checkpoint:** Push to GitHub; unit tests pass with 100% success rate.
- **Known Risks:** Subtle off-by-one errors in half-open downtime merge intervals ($[S, E)$).
- **Definition of Done:** 100% unit test pass rate covering all 6 input cases and downtime edge cases.

---

### Milestone 03: Clean-Room Independent Schedule Verifier & Mutant Tests
- **Scope:** Implement `ScheduleVerifier` in pure Python, auditing schedules against all 8 domain invariants completely decoupled from OR-Tools. Implement mutant injection test suite to empirically prove the verifier flags any constraint violation.
- **Prerequisites:** Milestone 02 complete.
- **Expected Files:** `backend/opwise/verifier/schedule_verifier.py`, `verification_types.py`, `backend/tests/unit/test_verifier.py`, `test_mutant_injection.py`.
- **Acceptance Criteria:** Verifier evaluates any schedule in < 5ms without importing OR-Tools. Invariant audit returns `PASS` on valid schedules and `FAIL` with exact entity IDs on mutated schedules (precedence reversal, overlapping operations, downtime collisions, duration drift).
- **Relevant Tests:** TM-03 (Independent Verifier Mutant Injection Tests).
- **Git Commit Checkpoint:** `feat(verifier): implement clean-room independent verifier and mutant test suite`
- **GitHub Push Checkpoint:** Push to GitHub; verifier test coverage $\ge 95\%$.
- **Known Risks:** Shared-mode failure if verifier inadvertently imports solver constants or helpers.
- **Definition of Done:** Verifier detects 100% of injected constraint mutants in test suite.

---

### Milestone 04: Core CP-SAT Formulation & Scheduling Constraints
- **Scope:** Implement Google OR-Tools CP-SAT model builder: integer variables, interval variables, non-preemptive operation routing, machine `AddNoOverlap` constraints, downtime fixed interval constraints, and horizon calculation with overflow guards.
- **Prerequisites:** Milestones 02 and 03 complete.
- **Expected Files:** `backend/opwise/solver/cp_sat_model.py`, `solver_types.py`, `backend/tests/unit/test_solver_model.py`.
- **Acceptance Criteria:** Model correctly translates domain problem into CP-SAT constraints. Half-open interval contact at minute $T$ ($[S, T)$ and $[T, D_e)$) does not collide. Horizon calculation safeguards against integer overflow. Schedules generated pass Milestone 03 independent verifier.
- **Relevant Tests:** TM-02 (Solver correctness, downtime non-collision), TM-05 (Horizon overflow protection).
- **Git Commit Checkpoint:** `feat(solver): implement CP-SAT interval scheduling formulation and non-overlap constraints`
- **GitHub Push Checkpoint:** Push to GitHub; solver constraint unit tests pass.
- **Known Risks:** Horizon $H$ overflow exceeding $2^{31}-1$ on degenerate user inputs (safeguard rejects $> 10^7$).
- **Definition of Done:** Generated schedules for 10 test problem instances pass independent verification.

---

### Milestone 05: Objective Modes, Lexicographic Optimization & Honest Solver Status
- **Scope:** Implement single-objective builders (`PURE_MAKESPAN`, `PURE_WEIGHTED_TARDINESS`) and two-stage hierarchical lexicographic solver (`multi_objective.py`) with strict optimality gating. Map CP-SAT solver statuses to honest domain statuses (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `TIMEOUT`).
- **Prerequisites:** Milestone 04 complete.
- **Expected Files:** `backend/opwise/solver/multi_objective.py`, `backend/tests/integration/test_lexicographic.py`.
- **Acceptance Criteria:** Stage 1 must be proven `OPTIMAL` before Stage 2 can fix $Z_1^*$. If Stage 1 times out (`FEASIBLE`), overall solve status is strictly `FEASIBLE`. If Stage 2 times out, best feasible Stage 2 schedule is returned with status `FEASIBLE`. Solver statuses adhere to the 7-case transition matrix.
- **Relevant Tests:** TM-02 (Lexicographic proof gating), TM-05 (Timeout & Infeasible handling).
- **Git Commit Checkpoint:** `feat(solver): implement objective modes, two-stage lexicographic solver, and status contracts`
- **GitHub Push Checkpoint:** Push to GitHub; all 7 state transition cases pass.
- **Known Risks:** Stage 2 constraint infeasibility due to integer round-off (handled by exact integer equality).
- **Definition of Done:** All 7 cases in the lexicographic state transition matrix verified by integration tests.

---

### Milestone 06: Deterministic Metrics Engine & Explanations Math
- **Scope:** Implement deterministic KPI metrics calculations: schedule origin makespan ($C_{\max} - 0$), exact weighted tardiness ($\sum w_j T_j$), late order count ($N_{\text{late}}$), on-time percentage, machine net utilization ($W_m / (C_{\max} - D_m)$), idle duration ($I_m = C_{\max} - W_m - D_m$), and mathematical bottleneck identification.
- **Prerequisites:** Milestone 02 complete.
- **Expected Files:** `backend/opwise/domain/metrics.py`, `backend/tests/unit/test_metrics.py`.
- **Acceptance Criteria:** Makespan measured strictly relative to $t=0$. Machine idle time strictly excludes downtime. Zero division by zero on zero-length windows. Explanations cite exact mathematical values without heuristic guessing.
- **Relevant Tests:** TM-04 (Objective Math & Edge Cases).
- **Git Commit Checkpoint:** `feat(domain): implement deterministic metrics engine and bottleneck identification`
- **GitHub Push Checkpoint:** Push to GitHub; metrics unit tests pass.
- **Known Risks:** Zero-denominator division on idle machines with $C_{\max} == D_m$ (handled by clamp to 0.0%).
- **Definition of Done:** Metrics match analytical reference values across all 6 demo scenarios.

---

### Milestone 07: SQLite WAL Persistence, Migrations & REST API Layer
- **Scope:** Implement SQLAlchemy 2.0 ORM entities, Alembic migrations, SQLite connection event listeners (`WAL` mode, `PRAGMA synchronous = NORMAL;`, `foreign_keys = ON;`). Implement FastAPI application factory, Pydantic schemas, and versioned REST endpoints (`/api/v1/workspaces`, `/optimize`, `/schedules`).
- **Prerequisites:** Milestones 02–06 complete.
- **Expected Files:** `backend/opwise/persistence/`, `backend/opwise/api/`, `backend/alembic/`, `backend/tests/integration/test_api.py`.
- **Acceptance Criteria:** All 6 input cases return documented HTTP response envelopes; database transactions commit atomically; foreign key integrity verified; safe online backup via `VACUUM INTO` verified.
- **Relevant Tests:** TM-06 (API Routes & Error Envelopes), TM-07 (Database Durability & REC-01 to REC-09).
- **Git Commit Checkpoint:** `feat(api): implement SQLite WAL persistence, Alembic migrations, and REST endpoints`
- **GitHub Push Checkpoint:** Push to GitHub; API integration tests pass 100%.
- **Known Risks:** Database locking during long optimization runs (mitigated by background thread offload).
- **Definition of Done:** All REST endpoints pass OpenAPI schema validation and persistence recovery tests.

---

### Milestone 08: React 19 Frontend Shell, Information Architecture & API Client
- **Scope:** Initialize React 19 SPA with TypeScript and Vite. Implement high-contrast industrial theme (Slate/Zinc palette), layout navigation shell (Header, Sidebar, Navigation), typed API client with robust error handling, and 6 view routes (`/`, `/factory`, `/schedule`, `/scenarios`, `/reports`, `/settings`).
- **Prerequisites:** Milestone 07 complete.
- **Expected Files:** `frontend/src/views/`, `frontend/src/components/layout/`, `frontend/src/api/`.
- **Acceptance Criteria:** Navigation across the 6 pillars operates smoothly; typed API client deserializes backend schemas; offline detection status banner renders cleanly when backend is unreachable.
- **Relevant Tests:** TM-10 (Frontend Shell), TM-11 (Layout & Accessibility).
- **Git Commit Checkpoint:** `feat(frontend): implement industrial navigation shell, views, and typed API client`
- **GitHub Push Checkpoint:** Push to GitHub; frontend component tests pass.
- **Known Risks:** Styling inconsistencies without a coherent tokenized design system.
- **Definition of Done:** All 6 views mount cleanly without console warnings or layout shift.

---

### Milestone 09: High-Density Interactive Gantt Canvas & Real-Time Visualization
- **Scope:** Implement SVG/Canvas Gantt chart components: horizontal machine swimlanes, half-open interval rendering, diagonal maintenance striping, interactive zoom/pan controls, precedence highlighting on hover, and full keyboard navigation. Implement the 11 zero-panel-diving schedule results items.
- **Prerequisites:** Milestone 08 complete.
- **Expected Files:** `frontend/src/components/gantt/`, `frontend/src/components/metrics/`.
- **Acceptance Criteria:** Operation blocks position accurately to the minute; downtime hatchings overlay cleanly; tooltips show exact start, end, duration, and slack; full keyboard focus traversal supported.
- **Relevant Tests:** TM-10 (Gantt Rendering), TM-11 (Accessibility).
- **Git Commit Checkpoint:** `feat(frontend): implement high-density interactive Gantt canvas and metric dashboard`
- **GitHub Push Checkpoint:** Push to GitHub; Gantt component tests pass.
- **Known Risks:** Sub-pixel rounding jitter causing 1px overlap glitches (resolved by strict floor/ceil math).
- **Definition of Done:** Visual and automated tests confirm accurate rendering for 100+ operations.

---

### Milestone 10: Scenario Disruption Lab & Immutable Baseline Comparison
- **Scope:** Implement Scenario Simulation engine: branching from baseline schedules, applying disruptions (machine breakdown window injection, urgent order insertion, processing duration delay), re-optimizing with CP-SAT, and rendering side-by-side or difference Gantt charts with delta metric badges (`+15m Makespan`, `+2 Late Orders`). Ensure baseline schedules remain strictly immutable.
- **Prerequisites:** Milestones 07 and 09 complete.
- **Expected Files:** `backend/opwise/domain/scenarios.py`, `frontend/src/views/ScenarioLabView.tsx`.
- **Acceptance Criteria:** Baseline schedule timestamps are never modified; delta metrics calculate correctly; unlike-scenario comparison warnings display appropriately.
- **Relevant Tests:** TM-09 (Scenario Branching & Disclosures).
- **Git Commit Checkpoint:** `feat(scenarios): implement disruption simulation, immutable baselines, and delta comparisons`
- **GitHub Push Checkpoint:** Push to GitHub; scenario integration tests pass.
- **Known Risks:** Accidental mutation of baseline schedule rows during re-solve (prevented by cloning).
- **Definition of Done:** Disruption scenarios create separate database entities and render delta comparisons.

---

### Milestone 11: CSV and Excel Data Exchange (Two-Phase Import/Export)
- **Scope:** Implement two-phase import engine: Phase 1 Preview (in-memory parse, schema validation, canonical downtime normalization, row-level error reporting), Phase 2 Confirm (atomic commit to database). Implement CSV and Excel (`openpyxl`) export with formula injection escaping (`'` prefix on `=, +, -, @`) and XXE-safe XML ingestion.
- **Prerequisites:** Milestone 07 complete.
- **Expected Files:** `backend/opwise/io/`, `frontend/src/components/io/`.
- **Acceptance Criteria:** Valid CSV and Excel workbooks import cleanly; malformed files return line-numbered error tables; formula injection characters are escaped; exports round-trip successfully.
- **Relevant Tests:** TM-08 (Import/Export Round-Trip), TM-13.2 (Safe XML parsing).
- **Git Commit Checkpoint:** `feat(io): implement two-phase CSV/Excel import with downtime normalization and safe export`
- **GitHub Push Checkpoint:** Push to GitHub; import/export tests pass 100%.
- **Known Risks:** Memory exhaustion on giant spreadsheets (capped at 1,000 orders / 100 ops per order).
- **Definition of Done:** 100% round-trip fidelity between export and import verified across test datasets.

---

### Milestone 12: Automated Quality Hardening, Browser UX & Accessibility Testing
- **Scope:** Execute comprehensive automated test matrix across all 16 categories: unit tests, mutant injections, database durability (REC-01 to REC-09), API contracts, frontend component tests, and browser-level UX verification across all 15 operational states. Audit contrast ratios (WCAG 2.1 AA) and keyboard focus traversal.
- **Prerequisites:** Milestones 01–11 complete.
- **Expected Files:** `backend/tests/`, `frontend/tests/`.
- **Acceptance Criteria:** 100% test pass rate reported by pytest and vitest; zero lint warnings; zero type errors (`tsc --noEmit`, `mypy --strict`); all 15 UX states verified.
- **Relevant Tests:** TM-01 through TM-16.
- **Git Commit Checkpoint:** `test: execute comprehensive quality hardening, durability, and UX verification`
- **GitHub Push Checkpoint:** Push to GitHub; CI pipeline completes 100% green.
- **Known Risks:** Flaky asynchronous test timing in browser environments (mitigated by deterministic clock waits).
- **Definition of Done:** Test suites pass with reported command logs; code coverage $\ge 90\%$.

---

### Milestone 13: Standalone Client-Side Demo Mode & GitHub Pages Deployment
- **Scope:** Author pre-solved synthetic JSON fixtures for Demo Scenarios 1–6. Implement pure TypeScript clean-room verifier (`clientVerifier.ts`) in frontend. Build static demo bundle (`npm run build:demo`) and configure GitHub Actions deployment workflow (`.github/workflows/deploy-demo.yml`) to deploy to GitHub Pages for ₹0. Embed unmissable demo mode disclaimer banner.
- **Prerequisites:** Milestones 08, 09, 12 complete.
- **Expected Files:** `frontend/src/demo/`, `.github/workflows/deploy-demo.yml`.
- **Acceptance Criteria:** GitHub Pages site loads in < 2 seconds; interactive Gantt renders all 6 demo scenarios; client-side verifier audits all 8 invariants in browser; banner directs users to local engine for custom solves.
- **Relevant Tests:** TM-16 (Demo Mode & Fallback).
- **Git Commit Checkpoint:** `feat(demo): implement standalone client-side demo mode and GitHub Pages deployment workflow`
- **GitHub Push Checkpoint:** Push to GitHub; static demo successfully deployed to GitHub Pages.
- **Known Risks:** Relative path resolution for assets on GitHub Pages subpaths (`/Opwise/`).
- **Definition of Done:** Public URL verified live, interactive, and completely free of charge.

---

### Milestone 14: Release Readiness Audit, Backup Verification & Phase 1 Sign-Off
- **Scope:** Conduct complete end-to-end audit: verify ₹0 operating cost, verify local offline operation, test database backup (`VACUUM INTO`) and disaster recovery restore, review git log hygiene, verify all 12 release gates, and assemble final release evidence report.
- **Prerequisites:** Milestones 01–13 complete.
- **Expected Files:** Final release documentation, verification logs.
- **Acceptance Criteria:** All 12 production release gates (R-1 through R-12) checked and verified with command output; complete disaster recovery test passes.
- **Relevant Tests:** Full regression suite.
- **Git Commit Checkpoint:** `docs(release): complete Phase 1 production verification audit and release documentation`
- **GitHub Push Checkpoint:** Tag `v1.0.0` pushed to GitHub; final backup verified.
- **Known Risks:** Unresolved issues masked to meet release deadline (strictly forbidden by `PROJECT_RULES.md`).
- **Definition of Done:** Formal verification report signed off with 100% evidence-backed claims.

---

## 6. Production Release Gates Checklist

```
[ ] GATE R-1:  All unit tests in TM-01, TM-04, TM-08 pass with 100% success.
[ ] GATE R-2:  Solver correctness (TM-02) and mutant injection (TM-03) tests pass.
[ ] GATE R-3:  Independent Schedule Verifier audits 100% of generated test schedules.
[ ] GATE R-4:  SQLite WAL recovery tests (REC-01 through REC-09) verified.
[ ] GATE R-5:  6 embedded synthetic demo scenarios load, solve, and render without error.
[ ] GATE R-6:  OpenAPI 3.1 schema matches all backend endpoint contracts.
[ ] GATE R-7:  Frontend builds cleanly (`npm run build`) with zero TypeScript compiler errors.
[ ] GATE R-8:  Responsive Gantt chart renders correctly across desktop viewports (1280px to 2560px).
[ ] GATE R-9:  Strict ₹0 budget compliance verified (zero paid API keys, zero cloud infrastructure).
[ ] GATE R-10: Continuous GitHub remote backup verified across all 14 milestone commits.
[ ] GATE R-11: Code maintainability and readability thresholds verified (<50 lines/fn, <350 lines/mod).
[ ] GATE R-12: Standalone Static Demo Mode deployed and verified live on GitHub Pages.
```

