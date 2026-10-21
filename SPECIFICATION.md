# Opwise — Complete Product and Technical Specification

- **Document ID:** OPW-SPEC-001
- **Status:** APPROVED FOR SPECIFICATION (Phase 0.3 Pre-Implementation Approval Gate)
- **Version:** 1.3.0
- **Last Updated:** 2026-10-16
- **Governance:** Governed by `PROJECT_RULES.md` (Opwise Permanent Constitution)
- **Author:** Senior Software Architect, Operations Research Engineer, QA Lead
- **Project Identity:** Portfolio Project #4 (Job Shop Production Planning & Optimization Platform)

---

## 0. Specification Hierarchy and Single Source of Truth

This document (`SPECIFICATION.md`) is the **authoritative master product specification** for Opwise. Detailed technical domains are codified in accompanying architecture and design documents. In the event of any ambiguity, this document and its linked companions govern implementation:

0. [PROJECT_RULES.md](PROJECT_RULES.md) — Permanent project constitution, ₹0 operating cost, anti-AI-slop UX, code navigation, continuous GitHub backup, and testing discipline.
1. [ARCHITECTURE.md](ARCHITECTURE.md) — Monorepo structure, component responsibilities, dependency flow, tiered deployment topology, and contributor guide.
2. [SOLVER_MODEL.md](SOLVER_MODEL.md) — Mathematical formulation, CP-SAT constraints, objectives, downtime normalization, and independent schedule verification.
3. [DATA_AND_API.md](DATA_AND_API.md) — Relational schema, SQLite WAL persistence, REST API v1 contracts, and CSV/Excel data exchange.
4. [TEST_AND_RELEASE_PLAN.md](TEST_AND_RELEASE_PLAN.md) — Acceptance matrix, test plan, 14-milestone delivery roadmap, and release gates.
5. [DECISIONS.md](DECISIONS.md) — Architecture Decision Records (ADRs 001–012), trade-offs, and boundary assumptions.

---

## 1. Product Definition

### 1.1 Target User and Primary Problem
- **Target User:** Production planners, industrial engineers, manufacturing operations managers, and plant dispatchers in discrete job shops and high-mix low-volume machine environments.
- **Primary Problem:** Discrete job shops face conflicting constraints: fixed machine capacities, multi-stage routing sequences, varying order release times, and tight customer due dates. Planners currently rely on brittle spreadsheets, manual guesswork, or simplistic dispatch rules (FIFO, EDD) that result in excessive lead times, high work-in-progress (WIP), frequent machine idle time, and severe customer delivery penalties. When unexpected disruptions occur (machine breakdowns, rush orders), re-calculating feasible, optimal schedules takes hours of manual effort.
- **Value Proposition:** Opwise provides a local-first, deterministic production planning platform that uses Google OR-Tools CP-SAT to generate provably optimal or high-quality bounded schedules in seconds. It presents interactive Gantt visualizations, audits every result with an independent clean-room verifier, explains schedule trade-offs using mathematical evidence, and simulates disruptions without data loss or cloud costs.

### 1.2 Core Workflow
The end-to-end user journey follows a strict, deterministic sequence:
```
Define Factory
   │
   ▼
Validate Inputs (Detect Empty / Malformed / No-Work States)
   │
   ▼
Optimize Schedule (CP-SAT Multi-Stage Solve)
   │
   ▼
Verify Solution (Clean-Room Verifier)
   │
   ▼
Inspect Gantt Chart & Deterministic Metrics
   │
   ▼
Explain Trade-offs & Bottlenecks
   │
   ▼
Simulate Disruption (Downtime / Rush Order)
   │
   ▼
Compare Scenarios (Divergence & Unlike-Results Disclosures)
   │
   ▼
Export Results (CSV / Excel / Audit Logs)
```

### 1.3 Explicit Non-Goals (MVP Boundary)
To maintain zero cloud cost, local responsiveness, and high reliability, the following are **strictly out of scope for the MVP**:
- **No LLMs, Chatbots, or Generative AI:** All metrics, bottleneck analyses, and explanations are computed mathematically using verifiable operations-research principles. No probabilistic language models are used.
- **No Paid APIs or Cloud Infrastructure:** Strict ₹0 budget. The system runs entirely on localhost with zero external dependencies.
- **No ERP / MES Integration:** No automated SAP, NetSuite, or live OPC-UA shop floor connectors. All data exchange uses local CSV, Excel, or JSON.
- **No Alternative Machines (FJSP):** Operations are assigned to exactly one fixed machine.
- **No Sequence-Dependent Setup Times (SDST):** Changeover times are either zero or included in the fixed processing duration.
- **No Real-Time Plant Execution Tracking:** No live machine clock tracking, RFID, or partial operation preemption. Disruption reoptimization evaluates the full plan from schedule origin ($t=0$) as an offline planning simulation.
- **No Workforce / Tooling Constraints:** Machines are the sole constraining capacity resource.
- **No User-Configurable Weighted-Sum Objective:** Removed from MVP to eliminate arbitrary cross-objective scaling parameters.

### 1.4 Input Classification and Validation Policy
Opwise formally categorizes six input conditions:
1. **Empty Workspace (0 machines, 0 orders):** Viewing returns empty lists; optimization requests are rejected with HTTP 422 `EMPTY_WORKSPACE`.
2. **Factory with Machines but Zero Orders/Operations (No-Work State):** Handled as an explicit `NO_WORK_STATE`. Solver is bypassed; returns HTTP 200 with makespan=0, tardiness=0, 0 scheduled operations. Never labeled as an optimal production schedule.
3. **Orders Without Operations:** Rejected with HTTP 422 `ORDER_WITHOUT_OPERATIONS`.
4. **Operations Referencing Missing Entities:** Rejected with HTTP 422 `REFERENTIAL_INTEGRITY_VIOLATION`.
5. **Valid Non-Empty Factory:** Passed to CP-SAT solver with selected objective mode.
6. **Valid Factory with Infeasible Constraints:** CP-SAT returns status `INFEASIBLE` with diagnostic conflict explanations.

### 1.5 Zero-Cost Operating Constraints & Local-First Invariants (`PROJECT_RULES.md` Rules 1 & 2)
1. **Strict ₹0 Operating Budget:** The entire product is designed, tested, and demonstrated with zero recurring cloud cost. It relies entirely on free, local, open-source software (Python 3.12, FastAPI, OR-Tools CP-SAT, SQLite 3, React 19, TypeScript 5, Vite 6).
2. **Deterministic Solver Execution:** Optimization runs locally via Google OR-Tools CP-SAT C++ native wheels on the user's host CPU. Zero network calls or external optimization APIs are permitted.
3. **Dual Delivery & Demo Modes:**
   - **Full Local Engine (Tier 1):** Unrestricted local execution on `localhost:8000` + `localhost:5173`. Supports arbitrary problem instances, live CP-SAT solving, persistent SQLite WAL storage, disruption re-optimization, and Excel/CSV round-trip I/O.
   - **Static Portfolio Demonstration (Tier 2):** Hosted on GitHub Pages (`https://<username>.github.io/Opwise`). Runs a React SPA in Standalone Client-Side Demo Mode using pre-solved synthetic fixtures (Demos 1–6) and a client-side analytical verifier. Features an unmissable top banner communicating demo mode vs. local full engine capability.
4. **Honest Engineering Integrity:** Opwise explicitly prohibits fake metrics, animated simulation counters, or unproven claims. A schedule is labeled optimal only when proven by CP-SAT, and labeled verified only when passing all 8 clean-room invariant tests.

---

## 2. Scheduling Domain and Mathematical Model Summary

The Opwise mathematical domain model represents a classical Job Shop Scheduling Problem extended with release dates, soft due dates, tardiness weights, and machine downtimes ($Jm | r_j, \text{downtime} | C_{\max}, \sum w_j T_j$).

- **Complete Formulation:** Detailed variables, bounds, integer overflow protections, and constraints are defined in [SOLVER_MODEL.md](SOLVER_MODEL.md).
- **Core Entities & Invariants:**
  - Schedule origin is strictly fixed at $t = 0$. All times are discrete non-negative integer relative minutes ($t \in \mathbb{N}_0$).
  - Machines $M$, Orders $J$, Operations $O_{j,k}$ with duration $p_{j,k} \ge 1$ and machine $m_{j,k}$.
  - Order release time $r_j \ge 0$, due date $d_j \ge 0$, tardiness penalty weight $w_j \ge 0$.
  - Machine downtimes represented as half-open maintenance intervals $[D_{m,s}, D_{m,e})$.
  - Operations occupy half-open intervals $[S_{j,k}, C_{j,k})$ where $C_{j,k} = S_{j,k} + p_{j,k}$.
  - **Boundary Contact Non-Collision:** An operation ending at minute $T$ and downtime starting at minute $T$ ($[S, T) \cap [T, D_e) = \emptyset$) do not intersect. Downtime ending at minute $T$ and an operation starting at minute $T$ do not intersect.
  - **Canonical Normalization:** Overlapping and adjacent downtimes on each machine are merged into disjoint intervals prior to CP-SAT interval construction. Zero-length downtimes are filtered; inverted downtimes are rejected.
- **Makespan Definition:** Strictly the maximum completion time relative to schedule origin $t = 0$:
  $$C_{\max} = \max_{(j,k) \in O} C_{j,k} - 0$$
- **Effective Horizon ($H$) & Overflow Safeguards:**
  $$H = \max_{j \in J}(r_j) + \sum_{(j,k) \in O} p_{j,k} + \sum_{m \in M} \text{MergedDowntime}(m)$$
  Instances with $H > 2^{31}-1$ are rejected with HTTP 422 `INTEGER_OVERFLOW_RISK`. Settings enforce a maximum practical horizon cap of $10,000,000$ minutes ($\approx 19$ years).

---

## 3. Solver Contract & Objective Modes

Opwise supports exactly three optimization modes:
1. **`PURE_MAKESPAN`:** Minimizes schedule makespan from origin $t=0$ ($\min C_{\max}$).
2. **`PURE_WEIGHTED_TARDINESS`:** Minimizes total customer tardiness penalties ($\min \sum w_j T_j$).
3. **`HIERARCHICAL_LEXICOGRAPHIC` (Default):** Two-stage solve prioritizing customer delivery first (Stage 1), then schedule makespan compaction (Stage 2).
   - *Stage 1 Optimality Requirement:* Stage 2 runs with constraint $\sum w_j T_j \le Z_1^*$ only if Stage 1 is proven `OPTIMAL`.
   - *Schedule Return on Stage 2 Timeout:* If Stage 1 is proven `OPTIMAL` but Stage 2 reaches its time limit with only a feasible result, **the Stage 2 schedule is returned to the user** because it preserves minimal tardiness and provides the best makespan found. However, it is explicitly labeled **`FEASIBLE (SUBOPTIMAL - STAGE 2 TIME LIMIT EXPIRED)`** with Stage 2's gap. It is **never** labeled globally optimal.
   - *Suboptimal Gating:* If Stage 1 times out with status `FEASIBLE`, the overall solution is strictly labeled `FEASIBLE (SUBOPTIMAL - STAGE 1 OPTIMALITY UNPROVEN)`. Lexicographic optimality is never claimed without proof.
   - *Failure Gating:* If Stage 1 is `INFEASIBLE`, `MODEL_INVALID`, or `UNKNOWN`, Stage 2 is skipped entirely.

---

## 4. Independent Schedule Verification Engine

Before any schedule is committed or presented to the user, it is audited by a clean-room `ScheduleVerifier` decoupled from OR-Tools:
- **8 Invariant Checks:**
  1. Operation completeness and cardinality (all operations present exactly once).
  2. Duration and machine fidelity ($C_{j,k} - S_{j,k} == p_{j,k}$, machine matches routing).
  3. Release time adherence ($S_{j,1} \ge r_j$).
  4. Sequence precedence fidelity ($S_{j,k+1} \ge C_{j,k}$).
  5. Machine mutual exclusivity (zero overlapping intervals on any machine).
  6. Machine downtime non-collision (zero overlap with merged maintenance windows).
  7. Time horizon and non-negativity bounds ($0 \le S_{j,k} < C_{j,k} \le H$).
  8. Independent metric concordance (re-computed makespan, tardiness, idle times, and net utilizations match solver and metric engine telemetry with 0 delta).
- **Quarantine Policy:** Schedules failing verification are quarantined, tagged `VERIFICATION_FAILED`, and blocked from active planning views.

---

## 5. Metrics and Deterministic Explanations

Opwise provides rigorous, deterministic metrics and operational explanations based strictly on arithmetic facts.

### 5.1 Metric Formulations

| Metric Name | Mathematical Definition | Denominator / Basis | Units | Edge Case Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Makespan ($C_{\max}$)** | $\max_{(j,k) \in O} C_{j,k} - 0$ | Schedule origin ($t=0$) | Minutes | If $\|O\|=0$ or No-Work, makespan is 0. |
| **Weighted Tardiness** | $\sum_{j \in J} w_j \cdot \max(0, C_j - d_j)$ | Penalty sum over all orders | Penalty units | If all orders on time or No-Work, value is 0. |
| **Late Order Count** | $\sum_{j \in J} \mathbf{1}_{\{C_j > d_j\}}$ | Count of overdue orders | Orders | Integer count $\in [0, \|J\|]$. |
| **On-Time Rate** | $\frac{\sum_{j \in J} \mathbf{1}_{\{C_j \le d_j\}}}{\|J\|} \times 100\%$ | Total orders $\|J\|$ | Percentage | If $\|J\|=0$ or No-Work, defined as 100.0%. |
| **Machine Workload ($W_m$)** | $\sum_{(j,k) \in O, m_{j,k}=m} p_{j,k}$ | Total assigned processing | Minutes | Total active machining time on $m$. |
| **Machine Downtime ($D_m^{\text{obs}}$)** | $\sum_{d \in \mathcal{D}_m^{\text{merged}}} \|[d^{\text{start}}, d^{\text{end}}) \cap [0, C_{\max})\|$ | Observation window $[0, C_{\max}]$ | Minutes | Total maintenance minutes within schedule. |
| **Machine Idle Time ($I_m$)** | $\max(0, C_{\max} - W_m - D_m^{\text{obs}})$ | Observation window $[0, C_{\max}]$ | Minutes | Unutilized available time (strictly excludes downtime). |
| **Net Machine Utilization ($U_m$)** | $\frac{W_m}{C_{\max} - D_m^{\text{obs}}} \times 100\%$ | Available capacity window | Percentage | If $C_{\max} - D_m^{\text{obs}} \le 0$, defined as 0.0%. |
| **Gross Machine Utilization** | $\frac{W_m}{C_{\max}} \times 100\%$ | Total makespan window | Percentage | If $C_{\max} \le 0$, defined as 0.0%. |

### 5.2 Deterministic Explanations: Facts vs Heuristics
1. **Facts (Proven Mathematical Invariants):**
   - *"Order ORD-102 completed at minute 145, which is 25 minutes after its due date of minute 120, incurring 50 penalty points ($25 \times 2$)."*
   - *"Machine M1 is actively processing operations for 120 minutes out of a 150-minute makespan, with 30 minutes of planned downtime, resulting in 100% net utilization during available hours."*
2. **Heuristics (Diagnostic Interpretations with Explicit Disclaimers):**
   - **Bottleneck Candidate Indicator:** The machine with the highest workload $W_m$ and the greatest fraction of critical-path operations is highlighted as the *Primary Resource Candidate*.
   - **Explicit Disclaimer:** *"Note: High machine utilization indicates high capacity demand, but does not alone prove that this machine throttled overall throughput. Bottlenecks in job shops can also be induced by transfer delays, order release timing, or upstream starvation."*

---

## 6. Disruption Scenarios & Comparison Rules

Opwise provides a dedicated "Scenario Lab" to simulate real-world shop floor disturbances.

### 6.1 Disruption Types
1. **Machine Downtime Outage:** Planner inserts an unplanned breakdown or emergency maintenance interval $[D_{s}, D_{e})$ on machine $m$.
2. **Urgent Rush Order Insertion:** Planner injects a high-priority order with an immediate release time ($r_j = 0$), tight due date, and high tardiness weight ($w_j \gg 1$).
3. **Compound Disruption:** Simultaneous machine downtime and order set modification.

### 6.2 Full-Plan Reoptimization Boundary
- **Planning Simulation Boundary:** Reoptimization computes a full schedule from schedule origin ($t=0$) incorporating the modified constraints.
- **Explicit Limitation:** This is specified as an **offline planning simulation**, *not* a live shop-floor recovery tool. It does not track live clocks or lock in-progress tasks. Execution-aware rescheduling is scheduled for Phase 2.

### 6.3 Scenario Comparison and Unlike-Results Disclosures
When comparing a Baseline Schedule ($S_{\text{base}}$) to a Scenario Schedule ($S_{\text{scen}}$):
- Opwise computes $\Delta C_{\max}$, $\Delta \text{Weighted Tardiness}$, $\Delta \text{Late Orders}$, and lists displaced operations.
- **Unlike-Results Disclosures:** The system inspects both schedules. If differences in objective type, order set, solver status, or solver time limits are detected, a prominent warning is displayed:
  > **WARNING:** *"Baseline and Scenario differ in objective mode, order set, solver status, or time limit. Metric deltas reflect the compound effect of structural changes and must not be interpreted as pure delay on baseline orders."*

---

## 7. Persistence & REST API Summary

- **Persistence:** Local SQLite 3 operating in Write-Ahead Logging (`WAL`) mode with `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`, and `PRAGMA foreign_keys = ON;` enforced on every connection. Service layer owns atomic transaction boundaries with `with session.begin():`. Safe backups use `VACUUM INTO 'backup.sqlite3'`. Detailed schema definitions are in [DATA_AND_API.md](DATA_AND_API.md).
- **REST API:** Versioned under `/api/v1` with standard `SuccessEnvelope` and `ErrorEnvelope` JSON payloads. Synchronous optimization with 60s timeout cap (client timeout 75s). Full schemas in [DATA_AND_API.md](DATA_AND_API.md#3-rest-api-contract-apiv1).

---

## 8. Frontend and UX Specification

### 8.1 Product Information Architecture & Navigation
Opwise implements a restrained, high-density industrial navigation system organized into six primary functional views:

```
+----------------------------------------------------------------------------------------------------+
|  OPWISE  |  [1. Overview]  [2. Factory]  [3. Schedule]  [4. Scenarios]  [5. Reports]  [6. Settings] |
+----------------------------------------------------------------------------------------------------+
```

1. **Overview View (`/`):** Executive shop floor dashboard showing active workspace summary, machine count, active job orders, latest schedule status badge, and one-click quickstart loaders for Demo Scenarios 1–6.
2. **Factory Management View (`/factory`):** Interactive data grid for Machines, Maintenance Downtime windows, Production Orders, and Operation Sequences. Provides inline editing, validation badges, missing entity alerts, and CSV/Excel import/export triggers.
3. **Schedule Results View (`/schedule`):** The primary production planning canvas. Renders interactive Gantt charts, optimization control panel, deterministic verification badges, and KPI metric cards.
4. **Scenario Lab View (`/scenarios`):** Branching simulation environment for modeling factory disruptions (breakdowns, rush orders, processing delays). Features side-by-side or difference Gantt charts comparing the disrupted scenario against an immutable baseline.
5. **Reports & Analytics View (`/reports`):** In-depth tabular analytics: order tardiness breakdown, machine utilization and idle duration logs, bottleneck reports, and verification audit trails. Includes raw CSV/Excel export actions. Displays an informative empty state when no schedule has been generated.
6. **Settings & Diagnostics View (`/settings`):** Global solver parameters (solver time limit, worker thread count, default objective), database WAL durability toggle (`NORMAL` vs `FULL`), theme mode switcher (Dark Slate vs Clean Paper Light), and Standalone Demo Mode toggle.

### 8.2 The Core Schedule Results Canvas (Zero-Panel-Diving Requirement)
To prevent frustrating cognitive overhead, the primary **Schedule Results View** (`/schedule`) must display the following eleven critical planning data points directly in the primary viewport without requiring the user to open modal dialogs or expand secondary accordions:

1. **Solver Status Badge:** High-visibility semantic badge (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `NO_WORK_STATE`, `TIMEOUT`).
2. **Active Objective Mode:** Explicit indicator of active optimization objective (`PURE_MAKESPAN`, `PURE_WEIGHTED_TARDINESS`, or `HIERARCHICAL_LEXICOGRAPHIC`).
3. **Makespan ($C_{\max}$):** Total scheduled duration from relative minute 0 to final operation completion, formatted in both integer minutes and human-readable hours/days.
4. **Total Weighted Tardiness ($\sum w_j T_j$):** Sum of penalty-weighted late completion minutes, accompanied by the plant on-time delivery percentage ($100 \times N_{\text{on-time}} / N$).
5. **Late Order Count ($N_{\text{late}}$):** Number of orders completing after their contracted due date ($C_{j,\text{last}} > d_j$).
6. **Independent Verification Badge:** Solid green shield badge (`VERIFIED: 8/8 INVARIANTS PASS`) or high-visibility red warning (`VERIFICATION FAILED`).
7. **Machine Utilization Grid:** Net operational utilization for each machine, calculated using the true denominator: $W_m / (C_{\max} - D_m)$.
8. **Interactive Gantt Canvas:** Machine swimlanes with scheduled operations, downtime hatchings, and clear idle capacity segments.
9. **Bottleneck Candidate Callout:** Highlighted machine ID with the highest utilization and longest operation queue (proven mathematically from solver output, never guessed).
10. **Solver Disclosures & Warnings:** Explicit notice if time limit expired before optimality was proven, or if Stage 2 of lexicographic optimization timed out.
11. **Scenario Delta Badges (When comparing scenarios):** Precise comparison tags relative to immutable baseline (e.g. `+45m Makespan`, `+2 Late Orders`, `-$1,400 Penalty`).

### 8.3 Professional Industrial UI/UX Standards (`PROJECT_RULES.md` Rule 3)
- **Aesthetic Direction:** Clean, sober, high-density industrial tool for production engineers.
- **Color Hierarchy:**
  - Background: Dark Slate 900 (`#0f172a`) / Light Slate 50 (`#f8fafc`).
  - Containers & Cards: Slate 800 (`#1e293b`) / White (`#ffffff`) with 1px border lines (`#334155` / `#e2e8f0`).
  - Primary Text: High-contrast Slate 50 (`#f8fafc`) on dark / Slate 900 (`#0f172a`) on light.
  - Numbers & Durations: Formatted strictly in tabular monospace (`JetBrains Mono`, `Consolas`).
- **Semantic Status Color Tokens:**
  - `OPTIMAL` / `VERIFIED`: Crisp Emerald (`#059669` / `#10b981`).
  - `FEASIBLE` (Suboptimal / Timeout): Warning Amber (`#d97706` / `#f59e0b`).
  - `INFEASIBLE` / `VERIFICATION_FAILED`: Critical Crimson (`#dc2626` / `#ef4444`).
  - `NO_WORK_STATE` / `IDLE`: Neutral Slate (`#64748b` / `#94a3b8`).
  - `DOWNTIME`: Distinct 45-degree diagonal stripe pattern or charcoal zinc (`#3f3f46`).
- **Prohibited Anti-Patterns:** Zero generic AI marketing copy, zero glowing floating gradients, zero decorative glassmorphism, zero emoji as icons, zero unskippable onboarding walkthroughs, zero fake animated metrics.

### 8.4 Measurable UX Acceptance Standards (15 States)
Opwise specifies explicit UI behavior for 15 operational states (`PROJECT_RULES.md` Section 3.2):
1. **Initial Empty Workspace:** Neutral card prompting user to load Demo Scenarios (1–6) or import factory data via CSV/Excel.
2. **No-Work State:** Factory with machines but 0 orders. Clearly displays `NO_WORK_STATE`, makespan=0, utilization=0.0%. Never claims "Optimal Schedule".
3. **Invalid Input State:** Table error badges highlighting missing entity references or negative processing times with actionable fix suggestions.
4. **Optimization In Progress:** Non-blocking progress indicator with elapsed stopwatch, active objective mode, and working [Cancel] button.
5. **Solver Timeout State:** Amber badge: "FEASIBLE (Time limit reached: 30s)". Clearly notes that optimality remains unproven.
6. **Globally Optimal Schedule:** Solid green badge: "OPTIMAL (Proven by CP-SAT)". Displays exact solver wall-clock time and gap=0.0%.
7. **Feasible (Unproven) Schedule:** Amber banner warning that a tighter schedule may exist; displays objective bound and gap.
8. **Infeasible Schedule State:** High-visibility crimson alert explaining conflicting constraints (e.g. downtime spans entire horizon).
9. **Verification Failure Alert:** Flashing red alert identifying exact breached invariant (e.g., machine operation overlap).
10. **Import Preview & Errors:** Two-phase staging dialog showing valid rows alongside an error table with column, row, and reason.
11. **Scenario Comparison Warnings:** Dual Gantt view with delta badges; clearly warns if a baseline was modified.
12. **Offline / No Internet State:** Muted green dot in status bar: "Local Mode (Offline)". Zero network timeout popups.
13. **Backend Unavailable State:** Top banner: "Local Backend Disconnected. Viewing cached data. [Retry] [Switch to Demo]".
14. **Empty Reports State:** Informative placeholder: "No schedule generated yet. Solve a scenario to generate analytics."
15. **Small Screen Layout (<768px):** Responsive compact KPI cards, scheduled order table, Gantt horizontal pan with sticky machine headers.

### 8.5 Accessibility, Responsive Behavior, and Keyboard Navigation
- **Keyboard Navigation:** Full Tab/Shift-Tab focus traversal across all controls. Interactive Gantt supports arrow key horizontal panning (`←` / `→`) and timeline zooming (`+` / `-`). Pressing `Enter` or `Space` on an operation block opens its detailed routing and slack inspector.
- **ARIA & Contrast:** Minimum 4.5:1 text contrast ratio (WCAG 2.1 AA). SVG Gantt elements contain explicit `aria-label` tags describing machine, order, start minute, and end minute.
- **Responsive Adaptability:** Layout smoothly adapts from 4K ultrawide multi-machine monitors down to 13-inch laptop screens (1366x768). On compact mobile viewports, the Gantt chart provides a pinned left machine label column with horizontal scrolling.

---

## 9. Data Import and Export Specifications

- **Formats Supported:** Strict CSV bundles and multi-sheet Microsoft Excel (`.xlsx`) workbooks.
- **Required Worksheets / Files:** `Machines`, `Orders`, `Operations`, and optional `Downtimes`.
- **Two-Phase Import:** Phase 1 Preview (validation & memory/DB staging with downtime normalization) followed by Phase 2 Explicit Confirm (atomic database commit). Complete schemas in [DATA_AND_API.md](DATA_AND_API.md#4-csv-and-excel-data-exchange-specifications).

---

## 10. Demo Scenarios Inventory

Opwise includes 6 reproducible, synthetic demo scenarios embedded in the application:
1. **Demo 1: Normal Production (Balanced Shop):** 4 machines, 6 orders, 24 operations. Balanced workloads, achievable due dates. Solves optimal in $<3$s.
2. **Demo 2: Clear Bottleneck:** 4 machines, 8 orders, 24 operations. Machine 1 required by 75% of operations. Machine 1 achieves near 100% net utilization; others idle.
3. **Demo 3: High-Load Factory:** 6 machines, 20 orders, 80 operations. Tight due dates, heavy contention. Hierarchical lexicographic mode prioritizes high-weight orders.
4. **Demo 4: Urgent-Order Insertion:** Demo 1 baseline + 1 emergency rush order ($w=50, r=0, d=60$). Immediately placed at release, displacing lower-priority work.
5. **Demo 5: Machine Downtime Outage:** Demo 1 baseline + 60-min maintenance on M1 during $[30, 90)$. Verifier confirms zero operations in window; downstream operations deferred.
6. **Demo 6: Malformed / Invalid Factory Inputs:** Negative duration on `OP-03`, sequence gap `[1, 2, 4]`, reference to missing `M99`. Pre-solver validation rejects with HTTP 422. Solver never invoked.

---

## 11. Verification Gates Summary & Final Specification Status

All four verification gates are classified under the 4-tier evaluation taxonomy:

1. **Gate 1 (Dependencies):** **METADATA VERIFIED / PENDING PHASE 1 IMPLEMENTATION TESTING.** Python 3.12, OR-Tools 9.15.6755 wheel (`ortools-9.15.6755-cp312-cp312-win_amd64.whl`), FastAPI 0.143.2, Pydantic 2.14.1, SQLAlchemy 2.1.4, Node 24.21.0, npm 11.19.0, Vite 6, React 19.3.1 are verified via package registries. Clean installation and runtime execution await Phase 1 implementation.
2. **Gate 2 (Benchmark Licensing):** **SPECIFICATION DEFINED & METADATA VERIFIED.** Clean-room original synthetic benchmarks bundled for shipped demos. Academic OR-Library benchmarks verified licensed under MIT (J.E. Beasley 2010, accessed 2026-10-16). Optional adapter planned with synthetic augmentation disclosure.
3. **Gate 3 (Performance Limits):** **SPECIFICATION DEFINED & PROTOCOL ESTABLISHED.** Workload profiles (Small, Medium, Large) defined with target solver budgets (5s, 15s, 30–60s). Repeatable benchmark protocol established. Times explicitly disclosed as design targets.
4. **Gate 4 (Persistence Recovery):** **SPECIFICATION DEFINED & RECOVERY TESTS SPECIFIED.** SQLite 3 WAL mode with `PRAGMA synchronous = NORMAL;`, transaction ownership, online backups, and 9 failure-injection acceptance tests (`REC-01` to `REC-09`) specified. Software process termination distinguished from physical power loss.

**Final Specification Status:** The specification package is **complete, internally consistent, and ready for human review and implementation approval.** The application itself has not been implemented or verified.

Detailed findings and acceptance tests are documented in [TEST_AND_RELEASE_PLAN.md](TEST_AND_RELEASE_PLAN.md).
