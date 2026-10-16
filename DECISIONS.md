# Opwise — Architecture Decision Records (ADRs) and Decision Log

- **Document ID:** OPW-DEC-001
- **Status:** APPROVED FOR SPECIFICATION (Phase 0.3 Pre-Implementation Approval Gate)
- **Version:** 1.3.0
- **Last Updated:** 2026-10-16
- **Governance:** Governed by `PROJECT_RULES.md` (Opwise Permanent Constitution)
- **Author:** Senior Software Architect, Operations Research Engineer, QA Lead

---

## 1. Architecture Decision Records

### ADR-001: Local-First Single-User Architecture, SQLite WAL Durability, and Transaction Boundaries

#### Context
Opwise is designed as an operations-engineering platform for job shop scheduling, dispatching, and scenario simulation. Target users (production planners, industrial engineers, plant managers) manage proprietary operational data (machine capacities, customer order lead times, product routings). They require zero setup overhead, zero mandatory internet connectivity, zero subscription cost (strict ₹0 budget), and immediate local responsiveness.

#### Decision
Opwise adopts a local-first client-server model:
1. **Runtimes:**
   - Backend: Python 3.12 running locally with FastAPI, exposing a localhost REST API (`127.0.0.1`).
   - Persistence: Embedded SQLite database operating in Write-Ahead Logging (`WAL`) mode.
   - Frontend: Single-Page Application (SPA) built with React 19, TypeScript 5, and Vite 6, served locally.
2. **Durability & Performance Configuration:**
   - `PRAGMA journal_mode = WAL;` (enables concurrent reads alongside writes).
   - `PRAGMA synchronous = NORMAL;` (chosen durability/performance trade-off):
     - *Trade-off analysis:* In WAL mode, `NORMAL` ensures that the write-ahead log is flushed to disk at every WAL checkpoint, but ordinary transaction commits do not invoke an expensive disk `fsync`. This yields high write throughput while ensuring the database structure cannot become corrupt following an application crash, OS crash, or process kill. However, in the event of an abrupt catastrophic physical power cut before a checkpoint, the most recent uncheckpointed transactions might be rolled back.
     - For environments requiring strict physical power-loss durability at the expense of higher write latency, `PRAGMA synchronous = FULL;` is supported via configuration (`DB_SYNCHRONOUS=FULL`).
   - `PRAGMA busy_timeout = 5000;` (waits up to 5 seconds before returning busy on concurrent writes).
3. **Per-Connection Foreign Key Enforcement:**
   - SQLite disables foreign key constraints by default on every new connection.
   - Opwise enforces foreign keys on *every* database connection via an explicit SQLAlchemy engine connection listener:
     ```python
     @event.listens_for(Engine, "connect")
     def set_sqlite_pragmas(dbapi_connection, connection_record):
         cursor = dbapi_connection.cursor()
         cursor.execute("PRAGMA foreign_keys = ON;")
         cursor.execute("PRAGMA busy_timeout = 5000;")
         cursor.close()
     ```
4. **Transaction Ownership and Boundaries:**
   - The Application Service layer owns transaction boundaries using context managers:
     ```python
     with session.begin():
         # All factory entity updates or import commits occur atomically
     ```
   - Repositories accept an active session and must never call `commit()` internally.
   - If any validation rule, integrity constraint, or unexpected exception occurs, the context manager triggers an automatic rollback, leaving database state unmutated.
5. **Safe Backup and Restoration Procedures with WAL:**
   - Directly copying the `.sqlite3` file using OS file-copy utilities while the database is open risks copying a torn or incomplete state because active data resides in `.sqlite3-wal`.
   - Opwise mandates using SQLite’s Online Backup API (`sqlite3_backup` in Python `sqlite3`) or executing the SQL command `VACUUM INTO 'backup_path.sqlite3';` to generate a transactionally consistent, checkpointed standalone backup.
   - Alternatively, an explicit `PRAGMA wal_checkpoint(TRUNCATE);` must be executed before cold file copying.
6. **Schema Migrations and Version Mismatch Handling:**
   - Database schema migrations are managed via Alembic using transactional DDL.
   - If a migration script fails, the transaction is rolled back, preserving the prior `alembic_version`.
   - On application startup, the backend verifies that the database `alembic_version` matches the expected codebase migration head. If a mismatch or migration failure is detected, application boot is aborted with an informative diagnostic error and instructions to run `alembic upgrade head`.
7. **Failure Mode Realism:**
   - *Tested Behavior:* Process-kill tests (`kill -9`, `taskkill /F`) verify OS-level process cleanup, connection teardown, and uncommitted transaction rollback.
   - *Untested Failure Modes:* True physical power-loss resilience (sudden drive power loss, disk cache write-loss) is distinct from software process termination and is not tested by ordinary process-kill tests.

#### Rationale
Zero external daemon setup friction, zero cloud costs, ACID-compliant local transactions, and isolated portable files.

---

### ADR-002: CP-SAT Formulation, Objective Policy, and Strict Lexicographic Optimality Gating

#### Context
Job Shop Scheduling Problems (JSSP) are strongly NP-hard ($Jm | r_j, \text{downtime} | C_{\max}, \sum w_j T_j$). Planners need clear, predictable optimization objectives without artificial parameter tuning.

#### Decision
1. **Domain Formulation:**
   - Model the shop floor exclusively using CP-SAT interval variables (`NewIntervalVar`) and disjunctive global constraints (`AddNoOverlap`).
   - Planned machine downtimes are modeled as fixed unavailable interval variables participating in machine `AddNoOverlap` sets.
2. **MVP Objective Selection Policy:**
   Opwise supports exactly two primary single objectives and one multi-stage lexicographic mode:
   - **Mode 1: Pure Makespan Minimization (`PURE_MAKESPAN`):**
     $$\min \quad C_{\max}$$
     Minimizes overall schedule completion time relative to origin $t=0$. Maximizes machine throughput.
   - **Mode 2: Pure Total Weighted Tardiness Minimization (`PURE_WEIGHTED_TARDINESS`):**
     $$\min \quad \sum_{j \in J} w_j \cdot T_j$$
     Minimizes penalties for overdue customer deliveries. Recommended default for customer-driven shops.
   - **Mode 3: Hierarchical Lexicographic Optimization (`HIERARCHICAL_LEXICOGRAPHIC`):**
     A two-stage sequential solve prioritizing customer commitments first, then schedule compaction:
     - *Priority Order:* Stage 1 = Total Weighted Tardiness ($\min Z_1 = \sum w_j T_j$); Stage 2 = Makespan ($\min Z_2 = C_{\max}$).
3. **Strict Lexicographic Optimality Gating:**
   - **Stage 1 Execution:**
     - Solve Stage 1 with allocated time budget $t_1$ (default: 70% of total budget).
     - *If Stage 1 status is `OPTIMAL` ($S_1 = 4$):* Record proven optimum $Z_1^*$. Proceed to Stage 2 with a hard constraint: $\sum w_j T_j \le Z_1^*$.
     - *If Stage 1 status is `FEASIBLE` ($S_1 = 2$):* The solver found a valid schedule with objective $Z_1$, but **did not prove mathematical optimality**. $Z_1$ is merely an upper bound, not the true optimum. If Stage 2 proceeds with $\sum w_j T_j \le Z_1$, the resulting schedule **must be strictly reported as `FEASIBLE (SUBOPTIMAL - STAGE 1 OPTIMALITY UNPROVEN)`**, along with Stage 1's best bound and gap. The system **never** claims lexicographic optimality.
     - *If Stage 1 status is `INFEASIBLE` ($S_1 = 3$), `MODEL_INVALID` ($S_1 = 1$), or `UNKNOWN` ($S_1 = 0$):* Stage 2 is **never executed**. The engine terminates immediately and reports Stage 1 status and telemetry.
   - **Stage 2 Execution & Schedule Return Policy:**
     - Solve Stage 2 with remaining time budget $t_2$.
     - *If Stage 1 is `OPTIMAL` and Stage 2 is `OPTIMAL`:* Overall status is `OPTIMAL` (Lexicographically Optimal).
     - *If Stage 1 is `OPTIMAL` and Stage 2 terminates with `FEASIBLE` (timeout):* **The Stage 2 schedule IS returned to the user.** The schedule is valid, respects the proven optimal tardiness bound $Z_1^*$, and provides the best compacted makespan found within $t_2$. However, it is explicitly labeled **`FEASIBLE (SUBOPTIMAL - STAGE 2 TIME LIMIT EXPIRED)`** with Stage 2's optimality gap. It is **never** labeled globally optimal.
     - *If Stage 2 is `UNKNOWN`:* Stage 2 timed out without improving or finding a feasible solution for the secondary objective. The Stage 1 schedule is restored and returned with status `FEASIBLE`.
4. **Rejection of Weighted-Sum for MVP:**
   - **DECISION: REMOVE USER-CONFIGURABLE WEIGHTED-SUM FROM MVP.**
   - *Rationale:* Combining Makespan (minutes) and Weighted Tardiness (penalty points) via an arbitrary scalar weight requires artificial scaling factors ($K_1, K_2$) that lack physical meaning for shop floor planners. Lexicographic optimization provides unambiguous operational semantics.

---

### ADR-003: Clean-Room Independent Schedule Verification Subsystem

#### Context
Solvers are complex software systems. A bug in CP-SAT model construction, integer scaling, or parameter handling could produce an invalid schedule that the solver erroneously marks as feasible or optimal.

#### Decision
Implement a decoupled, clean-room `ScheduleVerifier` component that executes after every solver run.
- Zero dependencies on Google OR-Tools or CP-SAT data structures.
- Evaluates 8 strict operational invariants on raw input entities and output timestamp allocations:
  1. Complete operation coverage (every operation scheduled exactly once).
  2. Duration and machine assignment fidelity ($C_{j,k} - S_{j,k} == p_{j,k}$, machine matches routing).
  3. Release time adherence ($S_{j,1} \ge r_j$).
  4. Sequence precedence fidelity ($S_{j,k+1} \ge C_{j,k}$).
  5. Machine mutual exclusivity (zero overlapping intervals on any machine).
  6. Machine downtime non-collision (zero overlap with maintenance windows).
  7. Time horizon and non-negativity bounds ($0 \le S_{j,k} < C_{j,k} \le H$).
  8. Independent metric re-derivation (makespan and weighted tardiness match solver output with 0 discrepancy).
- If any check fails, the schedule is tagged `VERIFICATION_FAILED`, quarantined, and prevented from being presented as valid.

---

### ADR-004: Synchronous API Optimization with Bounded Execution Window

#### Context
FastAPI endpoints can execute optimization synchronously or asynchronously via background workers.

#### Decision
For Phase 1 MVP, all optimization requests are synchronous HTTP POST requests with a hard server-side timeout cap of 60 seconds (default: 5s–15s).
- Small instances (3–5 machines, 5–10 orders): 5-second solver time limit.
- Medium instances (5–10 machines, 15–30 orders): 15-second solver time limit.
- Large instances (10–20 machines, 50–100 orders): 30–60 second solver time limit.
- Client timeout: 75 seconds (allows solver time limit + 15-second buffer for validation, verification, and database writes).
- If solver time expires, CP-SAT returns status `FEASIBLE` or `UNKNOWN` (HTTP 200). If total request processing exceeds 75s, the server aborts with HTTP 504.

---

### ADR-005: Full-Plan Baseline Snapshot Reoptimization as Planning Simulation

#### Context
When disruptions occur (machine breakdowns, emergency rush orders), production plans must adapt.

#### Decision
For the MVP, Opwise adopts **Full-Plan Snapshot Reoptimization**:
- Every disruption experiment creates a new child `Scenario` branching from an immutable `Schedule` baseline.
- Full-plan reoptimization re-evaluates the entire modified factory from schedule origin $t=0$.
- **Explicit Scope Boundary:** This is formally specified as **offline planning simulation**, *not* real-time shop floor execution recovery. It does not track live plant clocks, worker shifts, or locked in-progress operations. Execution-aware rescheduling is scheduled for Phase 2.
- Comparisons between baseline and scenario schedules must disclose differences in objective, order set, solver status, and time limits.

---

### ADR-006: Deterministic Evidence-Based Explanations vs Generative AI

#### Context
Planners need to understand schedule bottlenecks, delays, and capacity utilization.

#### Decision
All metrics, bottlenecks, and schedule explanations are computed using deterministic algorithms operating on mathematical facts:
- Idle time = Window duration minus total operational runtime minus declared downtime.
- Machine Workload = Sum of processing times assigned to machine $m$.
- Machine Utilization = Net utilization over available capacity window $[0, C_{\max}] \setminus \text{Downtime}$.
- Bottleneck Identification = Machine with maximum workload and longest active critical path segments, accompanied by explicit disclaimers distinguishing utilization from throughput bottlenecks.
- Generative AI, LLMs, and probabilistic chatbots are strictly excluded from the MVP.

---

### ADR-007: Clean-Room Synthetic Demo Scenarios & External Benchmark Licensing Policy

#### Context
Opwise needs realistic demo data out of the box and must support academic benchmarking cleanly.

#### Decision
1. **Default Shipped Demos:** Ship 6 original, handcrafted clean-room synthetic benchmark scenarios with zero third-party licensing dependencies.
2. **External Benchmark Licensing Findings (OR-Library):**
   - *Authoritative Source:* J.E. Beasley, OR-Library Legal Issues, `http://people.brunel.ac.uk/~mastjjb/jeb/orlib/legal.html` (verified access date: 2026-10-16).
   - *Terms:* Released under the **MIT License** (Copyright (c) 2010 J E Beasley). Redistribution of raw benchmark data sets is permitted provided the copyright notice and permission notice are preserved.
   - *Distinction:* Raw data files are permitted for redistribution under MIT; third-party solver code or Fortran/C generator routines from original papers may carry distinct academic terms and are excluded.
3. **Optional Benchmark Adapter:**
   - Academic benchmark import (OR-Library, Taillard) is strictly **optional** and not required for core MVP operation.
   - Classical benchmarks (Fisher & Thompson 1963, Lawrence 1984, Taillard 1993) specify *only* machine routings and durations. They **do not** contain release times ($r_j$), due dates ($d_j$), tardiness weights ($w_j$), or machine downtimes.
   - Any external benchmark loaded through the adapter must synthesize missing fields using explicit, documented rules and **must be clearly labeled in the UI as a synthetically augmented academic instance**.

---

### ADR-008: Dependency Verification Taxonomy and Proposed Lockfile Strategy

#### Context
To guarantee deterministic builds and avoid overstating evidence, dependency compatibility claims must be classified accurately.

#### Decision
1. **Classification of Dependency Status:**
   - **Specification defined:** Architectural choices for Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, OR-Tools CP-SAT, SQLite WAL, React 19, Vite 6, and TypeScript 5 are fully specified.
   - **Metadata verified:** Package existence, version tags, and pre-compiled wheel compatibility verified via official PyPI and npm registries:
     - `ortools == 9.15.6755` wheel `ortools-9.15.6755-cp312-cp312-win_amd64.whl` exists on PyPI (requires Python $\ge 3.9$).
     - `fastapi == 0.143.2`, `pydantic == 2.14.1`, `sqlalchemy == 2.1.4`, `openpyxl == 3.1.5`, `pytest == 9.1.1` verified on PyPI.
     - Node engine requirement for Vite 6 (`^20.19.0 || >=22.12.0`) verified against system Node `v24.21.0`.
   - **Requires implementation testing:** Clean-environment virtualenv creation, pip dependency resolution, lockfile generation, runtime test execution, and production bundling.
   - *Honesty Rule:* Opwise does not claim that a clean installation was tested in Phase 0. Dependency pins are **proposed architectural decisions** subject to Phase 1 implementation verification.
2. **Proposed Dependency Pins:**
   - Backend: Python 3.12, `ortools==9.15.6755`, `fastapi==0.143.2`, `pydantic==2.14.1`, `pydantic-settings==2.8.0`, `sqlalchemy==2.1.4`, `uvicorn==0.54.0`, `openpyxl==3.1.5`, `pytest==9.1.1`, `httpx==0.28.1`.
   - Frontend: Node 24.21.0 LTS, npm 11.19.0, `react==19.3.1`, `react-dom==19.3.1`, `vite==6.2.0`, `typescript==5.8.0`, `tailwindcss==4.0.0`, `lucide-react==1.16.0`, `vitest==3.0.0`.
   - Both backend (`requirements.txt` generated via `pip-compile`) and frontend (`package-lock.json`) will maintain immutable lockfiles upon Phase 1 initialization.

---

### ADR-009: Policy for Empty Factories, Missing Operations, and Input Edge Cases

#### Context
A scheduling engine can encounter diverse edge cases: empty databases, factories with machines but no orders, orders with no operations, or dangling references. A mathematically trivial solution (e.g. 0 orders has makespan 0) must not be reported as a successful production schedule.

#### Decision
Explicitly classify and handle 6 distinct input states:
1. **Case 1: Empty Workspace (0 machines, 0 orders, 0 operations):**
   - *Validation:* Passes structural validation for viewing (`GET /factory` returns empty lists).
   - *Optimize Request:* **Rejected** with HTTP 422 `EMPTY_WORKSPACE` ("Cannot optimize an empty workspace. Add machines and production orders before optimizing."). CP-SAT is not called. No schedule is persisted.
   - *UI State:* Welcome Empty State with "Load Demo Factory" and "Add Machine" prompts.
2. **Case 2: Factory with Machines but Zero Orders/Operations (No-Work State):**
   - *Validation:* Structurally valid factory.
   - *Optimize Request:* **Accepted as an explicit No-Work State (`NO_WORK_STATE`).** CP-SAT solver is bypassed.
   - *API Response:* HTTP 200 with `status: "NO_WORK_STATE"`, `makespan_minutes: 0`, `weighted_tardiness: 0`, 0 operations scheduled.
   - *Persistence:* Persisted with `solver_status: "NO_WORK_STATE"` and `verification_status: "VERIFIED"`. Never labeled `OPTIMAL`.
   - *UI State:* "No Work to Schedule" informational banner. Gantt displays idle machines.
3. **Case 3: Orders Without Operations:**
   - *Validation:* **Rejected** with HTTP 422 `ORDER_WITHOUT_OPERATIONS` ("Order ORD-101 has no operations defined. Every order must contain at least one operation.").
   - *Solver:* Not invoked.
   - *UI State:* Form field validation badge highlighting empty orders.
4. **Case 4: Operations Referencing Missing Orders or Machines:**
   - *Validation:* **Rejected** with HTTP 422 `REFERENTIAL_INTEGRITY_VIOLATION` ("Operation OP-1 references non-existent machine 'M99'").
   - *Solver:* Not invoked.
   - *UI State:* Error modal with line-numbered reference violations.
5. **Case 5: Valid Non-Empty Factory:**
   - *Validation:* Passes.
   - *Solver:* Invoked with selected objective mode (`PURE_MAKESPAN`, `PURE_WEIGHTED_TARDINESS`, or `HIERARCHICAL_LEXICOGRAPHIC`).
   - *API Response:* HTTP 200 with schedule, metrics, and verification report.
   - *UI State:* Full Gantt chart, metric cards, and bottleneck analysis.
6. **Case 6: Valid Factory with No Feasible Schedule:**
   - *Validation:* Passes.
   - *Solver:* Returns `INFEASIBLE` (e.g. downtime occupies entire horizon).
   - *API Response:* HTTP 200 with `solver_status: "INFEASIBLE"`, `verification_status: "SKIPPED"`, 0 scheduled operations, and diagnostic conflict report.
   - *UI State:* High-visibility "Schedule Infeasible" alert explaining conflicting constraints.

---

### ADR-010: Machine Downtime Normalization, Horizon Calculation, and Boundary Policy

#### Context
Planners may enter overlapping or contiguous maintenance entries (e.g., mechanical overhaul $[30, 60)$ and electrical calibration $[50, 90)$), zero-length windows, or downtimes beyond the production horizon. The solver must not crash or create duplicate intervals.

#### Decision
1. **Half-Open Interval Semantics:**
   - Operations occupy $[S, C)$ and downtimes occupy $[D_s, D_e)$.
   - Boundary non-collision: If an operation completes at minute $T$ and downtime begins at minute $T$, $[S, T) \cap [T, D_e) = \emptyset$. **This is fully valid and does not collide.**
   - Similarly, if downtime ends at minute $T$ and an operation begins at minute $T$, $[D_s, T) \cap [T, C) = \emptyset$. **This is fully valid.**
2. **Canonical Downtime Normalization (Merge Policy):**
   - *Merge Rule:* Prior to CP-SAT model construction, all downtime intervals on each machine are sorted by start time and canonically merged:
     - Overlapping intervals ($D_{1,s} \le D_{2,s} < D_{1,e}$) are merged into $[\min(D_{1,s}, D_{2,s}), \max(D_{1,e}, D_{2,e}))$.
     - Adjacent intervals ($D_{1,e} == D_{2,s}$) are merged into $[D_{1,s}, D_{2,e})$.
   - *Rationale:* Industrial planners often log maintenance in separate work orders. Merging them represents the continuous physical unavailability window and prevents CP-SAT redundant interval collision.
3. **Invalid Downtime Filtering & Rejection:**
   - Negative start time ($D_s < 0$): Rejected at input validation with HTTP 422.
   - Inverted interval ($D_s > D_e$): Rejected at input validation with HTTP 422.
   - Zero-length downtime ($D_s == D_e$): Filtered out during normalization with an advisory warning log (0 capacity consumed).
4. **Effective Scheduling Horizon ($H$) & Overflow Safeguards:**
   - Horizon calculation uses merged downtimes:
     $$H = \max_{j \in J}(r_j) + \sum_{(j,k) \in O} p_{j,k} + \sum_{m \in M} \text{MergedDowntimeDuration}(m)$$
   - *Downtimes starting beyond horizon ($D_s \ge H$):* Excluded from CP-SAT intervals with an advisory note in telemetry (they cannot constrain this batch).
   - *Downtimes starting inside horizon and ending beyond ($D_s < H < D_e$):* Included in CP-SAT clamped to $H$.
   - *Overflow Guard:* $H$ capped at 10,000,000 minutes ($\approx 19$ years) via settings. Any instance with $H > 2^{31}-1$ is rejected immediately with HTTP 422 `INTEGER_OVERFLOW_RISK`.

---

### ADR-011: Deployment Topology, ₹0 Operating Cost Strategy, and Static Portfolio Demo Mode

#### Context
Opwise must be demonstrated publicly as Portfolio Project #4 while strictly satisfying Non-Negotiable Rule 1 (₹0 operating budget, zero credit card requirements, and zero risk of unexpected billing). The application architecture has two fundamentally distinct runtime layers:
1. Static frontend assets (React 19, TypeScript, Vite, SVG Gantt, interactive dashboards).
2. Stateful computational backend (Python 3.12, FastAPI, Google OR-Tools CP-SAT C++ wheel, SQLite WAL persistence, multi-threaded optimization).

Evaluation of hosting providers revealed:
- **GitHub Pages:** Rock-solid, permanently free static hosting for public repos with zero credit card requirements, but cannot execute Python, CP-SAT binaries, or SQLite.
- **Vercel Free Tier:** Serverless execution timeouts (10s-60s) are restrictive for multi-stage CP-SAT runs; function package size limits (50MB) are exceeded by the OR-Tools wheel alone (~90MB); ephemeral `/tmp` filesystem destroys SQLite WAL database between requests.
- **Render Free Web Service:** Inactivity spin-down after 15 minutes causes 50-second cold starts; 512MB RAM ceiling risks out-of-memory crashes during CP-SAT parallel branch-and-bound searches; ephemeral storage destroys the database on restart.
- **Railway / Cloud VMs:** Require credit card verification or meter usage past trial limits, violating the non-negotiable ₹0 cost constraint.

#### Decision
Opwise adopts a **Tiered Deployment Architecture**:
1. **Tier 1 — Primary Development & Local Production (Canonical Engine):**
   - Runs locally on `localhost` (FastAPI backend + SQLite 3 WAL + React frontend).
   - Unrestricted CPU multi-threading, durable zero-latency persistence, full live CP-SAT solving, scenario re-optimization, and Excel/CSV I/O.
2. **Tier 2 — Primary Public Portfolio Demonstration (GitHub Pages):**
   - React SPA hosted on GitHub Pages running in **Standalone Client-Side Demo Mode**.
   - Loads comprehensive pre-solved synthetic schedule fixtures (Demo Scenarios 1–6) representing baseline and disrupted conditions.
   - Embeds a client-side analytical verifier engine auditing schedules against all 8 domain invariants in the browser.
   - Features an unmissable top banner: *"Interactive Static Portfolio Demo — Pre-solved synthetic scenarios loaded in client-side simulation. Run locally for custom CP-SAT solving and disruption re-optimization."*
3. **Tier 3 — Portable Reviewer Runner (Local Docker / Script):**
   - Provides a `docker-compose.yml` and native launcher scripts (`run_local.bat` / `run_local.sh`) for technical evaluators wishing to run the complete live backend on their own machines without cloud setup.

#### Rationale & Consequences
- Eliminates 100% of cloud hosting costs, credit card dependencies, and cold-start failures.
- Portfolio visitors experience instant zero-latency loading and full interactive Gantt inspection without waiting for dormant cloud containers to boot.
- Eliminates any risk of public users overloading a shared free container or triggering denial-of-service via combinatorial optimization requests.
- Transparently communicates the boundary between static presentation and local optimization engine without misleading users.

---

### ADR-012: Continuous GitHub Backup Policy, Source Control Hygiene, and Database Backup Separation

#### Context
Development requires continuous disaster-recovery backup, transparent auditability, and protection against accidental data or credential leaks. A common failure mode in portfolio development is treating Git as an afterthought, creating massive "monolithic" commits at the end of the project, or accidentally committing SQLite runtime databases containing local state.

#### Decision
1. **Continuous Backup Schedule:**
   - Source code must be committed and pushed to the public GitHub repository at each of the 14 defined implementation milestones (Milestones 01 to 14).
   - Git operations remain strictly forbidden during Phase 0 planning. Initial repository creation occurs in Milestone 01 upon explicit Phase 1 authorization.
2. **Commit Hygiene & Conventional Prefixes:**
   - Every commit must represent an atomic, self-contained unit of work that compiles cleanly and passes all relevant tests.
   - Mandatory conventional commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `build:`, `ci:`.
   - Mandatory inspection of `git status` and `git diff` prior to every commit.
3. **Strict Git Exclusion Boundaries:**
   - `.gitignore` must strictly exclude: Python virtual environments (`.venv/`), Node dependencies (`node_modules/`), compiled bytecode (`__pycache__/`, `*.pyc`), SQLite database files (`*.sqlite3`, `*.db`, `*.sqlite3-wal`, `*.sqlite3-shm`), environment files (`.env`, `.env.local`), and OS metadata (`.DS_Store`, `Thumbs.db`).
   - Synthetic benchmark fixtures and pre-solved demo JSON files are explicitly tracked in Git.
4. **Separation of Source Code vs. Runtime Database Backups:**
   - Source code disaster recovery is managed through GitHub remote tracking.
   - Runtime SQLite database backups are decoupled from Git and managed via SQLite's safe online backup API: `VACUUM INTO 'backups/opwise_backup_<timestamp>.sqlite3'`.
5. **Workspace Boundary Protection:**
   - All Git commands must verify the working directory is `E:\MHT CET REGISTRATION\BE\Task\Opwise`.
   - Sibling project repositories (`Integris`, `CodeShip`, `PathForge`) must never be touched, modified, or referenced in Git remotes.

#### Rationale & Consequences
- Guarantees immediate recovery in the event of local disk or environment failure.
- Maintains a clean, professional, readable commit log suitable for external technical review.
- Prevents binary churn and repository bloat caused by committing `.sqlite3` runtime databases to Git.

---

## 2. Unresolved Questions & Post-MVP Roadmap

| Item ID | Topic | Current MVP Status | Post-MVP Consideration |
| :--- | :--- | :--- | :--- |
| **UNRES-01** | Sequence-dependent setup times (SDST) | Excluded. Setups assumed 0 or bundled into processing times. | Requires ATSP / circuit constraints in CP-SAT. Scheduled for Phase 3. |
| **UNRES-02** | Multi-machine alternatives (Flexible Job Shop - FJSP) | Excluded. Each operation has an immutable machine assignment. | Requires optional interval variables (`NewOptionalIntervalVar`). Phase 2 candidate. |
| **UNRES-03** | Plant execution tracking (Dynamic Dispatching) | Excluded. Full-plan reoptimization from $t=0$ for simulation. | Requires clock integration, operation state tracking (`PLANNED`, `IN_PROGRESS`, `COMPLETED`), and non-zero schedule origin. Phase 2. |
| **UNRES-04** | Workforce / Operator constraints | Excluded. Machines are the sole constraining resource. | Requires secondary cumulative resource constraints. Phase 3. |
| **UNRES-05** | Weighted-Sum & Pareto Frontier Generation | Excluded from MVP. Removed to avoid arbitrary scaling factors. | Multi-point $\epsilon$-constraint solve loop with interactive trade-off curve. Phase 2. |

---

## 3. Assumptions and Boundary Invariants

1. **Time Representation:** All scheduling calculations operate in non-negative discrete integer relative minutes ($t \in \mathbb{N}_0$, $t \ge 0$).
2. **Schedule Origin:** Schedule origin is strictly defined as relative minute 0 ($t = 0$).
3. **Half-Open Intervals:** Operations occupy $[S_{j,k}, C_{j,k})$ and downtimes occupy $[D_{m,s}, D_{m,e})$. Boundary contact at minute $T$ ($C == T$ and $S == T$) does not collide.
4. **Machine Exclusivity:** Every machine processes at most one operation at any given instant. Preemption is forbidden.
5. **Downtime Priority:** Machine downtime is an unyielding constraint; operations cannot overlap downtime windows under any circumstance.
