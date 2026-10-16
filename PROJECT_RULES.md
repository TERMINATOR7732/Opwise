# Opwise — Permanent Project Constitution and Engineering Rules

**Document Version:** 1.0.0  
**Phase Status:** Phase 0.3 Pre-Implementation Approval Gate  
**Project:** Opwise (Portfolio Project #4)  
**Workspace:** `E:\MHT CET REGISTRATION\BE\Task\Opwise`  
**Applicability:** Universal and non-negotiable across all project phases, design documents, source code, tests, CI/CD pipelines, and git operations.

---

## 0. Preamble and Single Source of Truth

Opwise is a local-first production planning and mathematical optimization platform for a job shop manufacturing environment. It uses Google OR-Tools CP-SAT to solve real discrete scheduling problems ($Jm \mid r_j, \text{downtime} \mid C_{\max}, \sum w_j T_j$), visualizes them on an interactive Gantt chart, provides deterministic evidence-backed explanations of planning trade-offs, and simulates industrial disruptions.

Opwise is an engineering and operations research application, not a generic SaaS demo or an AI-generated wrapper. Every metric, status, and verification claim must be mathematically sound, verifiable, and strictly honest.

This Constitution establishes seven non-negotiable operational rules and two mandatory checklists governing all development on Opwise.

---

## 1. Non-Negotiable Rule 1: ₹0 Operating Cost

### 1.1 Core Cost Principle
Opwise must be designed, developed, tested, demonstrated, and maintained with a **strict ₹0 recurring operating budget**. This is an inviolable architectural constraint, not a guideline.

- **Zero Paid APIs:** No external paid optimization engines, solvers, or cloud endpoints.
- **Zero Paid LLMs / AI Services:** No OpenAI, Anthropic, Google Gemini API, Pinecone, or other paid language model APIs. Scheduling is performed exclusively via deterministic operations research (OR-Tools CP-SAT).
- **Zero Paid Hosting / Compute:** No paid virtual machines, paid container instances, or subscription PaaS.
- **Zero Paid Databases:** No managed cloud databases (RDS, Supabase, Neon paid tiers). Persistence is purely local SQLite.
- **Zero Paid Telemetry or Analytics:** No Datadog, Sentry paid plans, Segment, or Google Analytics. Logging is local structured console/file logging.
- **Zero Domain or Subscription Requirements:** The system must function completely on `localhost` or free static hosting with zero required custom domain purchases.

### 1.2 Component Cost Audit & Verification

| Component | Technology | Cost Tier | License / Terms | Cost Safety & Limits |
| :--- | :--- | :--- | :--- | :--- |
| **Python Runtime** | Python 3.12 | Free & Local | Python Software Foundation License | Unlimited local execution. Zero cost. |
| **Backend Framework** | FastAPI + Uvicorn | Free & Local | MIT License | Localhost server. Zero cost. |
| **Optimization Solver** | Google OR-Tools CP-SAT (9.15+) | Free & Local | Apache 2.0 License | C++ native wheel runs locally on CPU. Zero cost. |
| **Persistence Engine** | SQLite 3 | Free & Local | Public Domain | Serverless, zero configuration, zero cost. |
| **ORM / Data Access** | SQLAlchemy 2.0 | Free & Local | MIT License | In-process library. Zero cost. |
| **Spreadsheet I/O** | openpyxl | Free & Local | MIT License | In-process Python library. Zero cost. |
| **Frontend Framework** | React 19 + TypeScript 5 | Free & Local | MIT / Apache 2.0 | Local client execution. Zero cost. |
| **Frontend Build Tool** | Vite 6 | Free & Local | MIT License | Local bundler. Zero cost. |
| **Backend Test Suite** | pytest + pytest-asyncio | Free & Local | MIT License | Local CLI execution. Zero cost. |
| **Frontend Test Suite** | vitest + Testing Library | Free & Local | MIT License | Local CLI execution. Zero cost. |
| **Source Control Backup** | GitHub Public Repository | Free with limits | GitHub Terms of Service | Free for public repositories (unlimited public repos, 2GB soft repo size limit). |
| **Automated CI/CD** | GitHub Actions | Free with limits | GitHub Terms of Service | Free for public repositories (unlimited standard runners; 2,000 mins/mo for private). |
| **Static Demo Hosting** | GitHub Pages | Free with limits | GitHub Terms of Service | Free for public repos (100GB/mo soft bandwidth limit, 1GB site limit). |
| **Data Persistence** | Local Filesystem (`.sqlite3`) | Free & Local | Local OS Filesystem | Constrained only by local disk space. |
| **Academic Benchmarks** | Beasley OR-Library (Jm) | Free academic | Public / Academic Citation | Public research datasets. Cached locally. Zero cost. |

### 1.3 Cost Categorization Taxonomy
1. **Free and Local (Zero Cost, Zero Dependencies):** Python, FastAPI, OR-Tools CP-SAT, SQLite, React, Vite, pytest, vitest. These operate 100% offline with zero cloud touchpoints.
2. **Free with Usage Limits (Permitted under strict zero-budget ceiling):** GitHub Pages (static hosting, 100GB/mo bandwidth), GitHub Actions (standard Linux/Windows runners on public repositories).
3. **Free Only Under Particular Terms (Permitted with governance):** Public GitHub repository (must remain public to retain zero-cost CI/CD and hosting).
4. **Potentially Billable (PROHIBITED without prior authorization):** Render, Railway, Fly.io, Heroku, AWS, GCP, Azure. These platforms carry cold-start shutdowns, credit card requirements, or auto-billing risks.
5. **Paid and Excluded (STRICTLY PROHIBITED):** OpenAI, Anthropic Claude, Gemini API, Gurobi, CPLEX, managed cloud SQL, telemetry SaaS.

### 1.4 Offline Operation Guarantee
Opwise must remain 100% functional on a developer's or user's local machine without an active internet connection once initial open-source packages are installed. Synthetic demo scenarios must be baked directly into application fixtures and require no network fetching.

---

## 2. Non-Negotiable Rule 2: Free Hosting and Deployment Topology

### 2.1 Architectural Separation of Runtimes
The application separates its computational and presentation layers:
- **Presentation Layer (Frontend):** React 19 SPA, TypeScript, Vite, SVG/Canvas Gantt chart, interactive scenario comparison, Excel/CSV file loaders. Compiles to static HTML, JS, CSS, and SVG assets.
- **Computation & Persistence Layer (Backend):** Python 3.12, FastAPI, OR-Tools CP-SAT (C++ binaries), SQLite WAL persistence, deterministic verification engine. Requires a long-running process, POSIX/Windows filesystem with durable fsync, and CPU-intensive multi-threading.

### 2.2 Technical Evaluation of Free Hosting Alternatives

```
+---------------------------------------------------------------------------------------------------+
| Provider             | Python/CP-SAT | Persistent SQLite | Cold Starts / Quotas | Verdict         |
+---------------------------------------------------------------------------------------------------+
| GitHub Pages         | NO (Static)   | NO (No backend)   | None (Static CDN)    | APPROVED (Demo) |
| Vercel (Hobby Free)  | Partial (50MB)| NO (Ephemeral tmp)| 10s-60s timeout      | REJECTED (BE)   |
| Render (Free Tier)   | YES           | NO (Ephemeral disk| 50s cold start / OOM | REJECTED (BE)   |
| Railway              | YES           | Requires Paid Vol | Card required ($5 cr)| REJECTED        |
| PythonAnywhere Free  | Restricted    | YES (File storage)| CPU seconds throttle | REJECTED        |
| Localhost / Docker   | YES (Full)    | YES (Full WAL)    | None (Instant CPU)   | APPROVED (Dev/Pr|
+---------------------------------------------------------------------------------------------------+
```

- **GitHub Pages:** Cannot execute Python or run CP-SAT binaries. Cannot host SQLite. However, it is rock-solid, permanently free, and requires no credit card for static web assets.
- **Vercel Free Tier:** Serverless functions have hard limits (50MB uncompressed bundle size; OR-Tools alone exceeds 90MB with C++ wheels). Severely restricted runtime execution (10s limit on free hobby tier). Filesystem is read-only and ephemeral; SQLite writes are lost upon instance spin-down.
- **Render Free Tier:** Web services sleep after 15 minutes of inactivity (causing 50+ second cold-start delays for visitors). RAM is capped at 512MB (CP-SAT multi-threading with 8 workers risks sudden Out-Of-Memory termination). Ephemeral disk wipes `.sqlite3` files on restart.
- **Railway:** Requires credit card registration. Provides only a one-time $5 trial credit before transitioning to metered billing. Violates strict ₹0 and zero-credit-card constraints.
- **PythonAnywhere Free:** CPU time is throttled after 100 seconds per day; no WebSocket or asynchronous FastAPI event loop support on free accounts.

### 2.3 Tiered Deployment Strategy
To guarantee a ₹0 budget while providing an impressive public portfolio demonstration, Opwise adopts a **three-tier deployment topology**:

```
+---------------------------------------------------------------------------------------------------+
| TIER 1: PRIMARY DEVELOPMENT & LOCAL PRODUCTION (Canonical Full Engine)                            |
| Target: Localhost (127.0.0.1:8000 + localhost:5173 or packaged desktop/local launcher)           |
| Engine: Full FastAPI + OR-Tools CP-SAT (9.15+) + SQLite 3 WAL + React 19 Frontend                |
| Capability: Live solving, custom job creation, disruption simulation, full persistence, Excel I/O |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| TIER 2: PUBLIC PORTFOLIO DEMO (Static GitHub Pages Web App)                                       |
| Target: GitHub Pages (https://<username>.github.io/Opwise)                                         |
| Engine: React 19 SPA running in "Standalone Client-Side Demo Mode"                               |
| Data: Pre-solved synthetic schedule fixtures (Demo Scenarios 1-6) + Client-Side Verifier          |
| Capability: Interactive Gantt exploration, scenario comparisons, metrics inspection, CSV download|
| Notice: High-visibility banner stating: "Interactive Static Portfolio Demo — Live CP-SAT solving  |
|         and custom re-optimization run via the local-first engine."                              |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| TIER 3: PORTABLE REVIEWER RUNNER (Optional Containerized / Scripted Execution)                     |
| Target: Local Docker (`docker compose up`) or Windows script (`run_local.bat`)                    |
| Capability: Complete local reproduction for technical reviewers wanting live on-demand solving    |
+---------------------------------------------------------------------------------------------------+
```

### 2.4 Feature Boundary: Static Demo vs. Full Local Engine

| Feature | Static Portfolio Demo (Tier 2) | Full Local Engine (Tier 1) |
| :--- | :---: | :---: |
| **Inspect Pre-solved Scenarios (1-6)** | YES (Instant interactive Gantt) | YES |
| **Interactive Gantt (Zoom, Hover, Filter)** | YES | YES |
| **Compare Baseline vs. Disrupted Scenarios**| YES (Pre-calculated fixtures) | YES (On-demand live re-solve) |
| **Deterministic Verification Audit** | YES (Client-side verifier engine) | YES (Dual-layer backend verifier)|
| **Download Schedule CSV / Report** | YES | YES |
| **Edit Orders, Machines, Downtimes** | Read-Only / Preview | Full CRUD |
| **Live CP-SAT Optimization Solver** | NO (Displays pre-solved runs) | YES (Live CP-SAT execution) |
| **Custom Excel / CSV Upload & Re-solve** | NO (Instructs user to run local) | YES |
| **Durable SQLite Database Storage** | NO (Session memory only) | YES (Durable WAL SQLite file) |

---

## 3. Non-Negotiable Rule 3: Professional Industrial UI/UX (Anti-AI-Slop)

### 3.1 Design Philosophy & Aesthetic
Opwise is professional industrial software designed for manufacturing planners, operations research engineers, and shop-floor supervisors. It must reflect precision, density, reliability, and sobriety.

- **Prohibited AI-Slop Patterns:**
  - NO generic landing page heroes with marketing fluff ("Transform your manufacturing with AI!").
  - NO floating abstract pastel blobs, neon gradients, or dark-mode purple glowing spheres.
  - NO decorative glassmorphism that obscures text readability.
  - NO emoji icons masquerading as professional interface elements.
  - NO cards or UI blocks containing hardcoded, fake, or animated "live simulation" numbers.
  - NO buttons that do nothing or trigger empty "Coming Soon" alerts.
  - NO unskippable multi-step onboarding modals.
  - NO layout shifts or decorative bounce animations.

- **Required Industrial Design Standard:**
  - **Color Palette:** High-contrast, sober slate and zinc foundation:
    - Base background: `#0f172a` (Slate 900) or `#ffffff` (Clean Paper Light) with high-contrast borders (`#334155` / `#cbd5e1`).
    - Primary text: `#f8fafc` (Slate 50) on dark / `#0f172a` (Slate 900) on light.
    - Neutral borders and grid lines: `#1e293b` (Slate 800) / `#e2e8f0` (Slate 200).
  - **Semantic Status Color Tokens:**
    - `OPTIMAL` / `VERIFIED`: Crisp Emerald Green (`#059669` / `#10b981`).
    - `FEASIBLE` (Suboptimal / Timeout): Warning Amber (`#d97706` / `#f59e0b`).
    - `INFEASIBLE` / `VERIFICATION_FAILED`: Critical Crimson Red (`#dc2626` / `#ef4444`).
    - `NO_WORK_STATE` / `IDLE`: Neutral Muted Slate (`#64748b` / `#94a3b8`).
    - `DOWNTIME`: Distinct Diagonal Striped Pattern or Charcoal Zinc (`#3f3f46`).
  - **Typography:** System UI sans-serif (`Inter`, system-ui) for interface labels; strict tabular monospace font (`JetBrains Mono`, `Consolas`, monospace) for all numeric values, timestamps, durations, and metrics to prevent alignment jitter.
  - **Information Density:** High density, compact row spacing, clear tabular alignments, zero wasted whitespace.

### 3.2 Measurable UX Acceptance Requirements Across 15 States

```
+----------------------------------------------------------------------------------------------------+
| State ID | UI State Description         | Required Presentation & Acceptance Standard             |
+----------------------------------------------------------------------------------------------------+
| UX-01    | Initial Empty Workspace      | Neutral banner: "No factory configured. Load Demo or     |
|          |                              | Import CSV/Excel." Action buttons: [Load Demo] [Import].|
+----------------------------------------------------------------------------------------------------+
| UX-02    | No-Work State                | Info card: "0 production orders loaded. Factory ready."  |
|          | (Machines, 0 orders/ops)     | Makespan: 0m. Utilization: 0.0%. Status: NO_WORK_STATE. |
+----------------------------------------------------------------------------------------------------+
| UX-03    | Invalid Input State          | Form banner + table highlight showing exact entity, row, |
|          |                              | and validation reason (e.g., "Op 3 references missing M4)|
+----------------------------------------------------------------------------------------------------+
| UX-04    | Optimization In Progress     | Non-blocking progress indicator with elapsed stopwatch, |
|          |                              | active objective mode, and working [Cancel] button.      |
+----------------------------------------------------------------------------------------------------+
| UX-05    | Solver Timeout State         | Amber badge: "FEASIBLE (Time limit reached: 30s)".      |
|          | (Best feasible found)        | Subtitle: "Schedule found but optimality unproven."     |
+----------------------------------------------------------------------------------------------------+
| UX-06    | Globally Optimal Schedule    | Solid emerald badge: "OPTIMAL (Proven by CP-SAT)".       |
|          |                              | Objective value, wall-clock solve time, proof displayed. |
+----------------------------------------------------------------------------------------------------+
| UX-07    | Feasible (Unproven) Schedule | Amber badge: "FEASIBLE (Unproven)". Banner warning that  |
|          |                              | tighter schedule may exist; explicit optimality gap.    |
+----------------------------------------------------------------------------------------------------+
| UX-08    | Infeasible Schedule State    | High-visibility crimson alert: "INFEASIBLE". Displays    |
|          |                              | conflicting constraints (e.g. Downtime spans horizon).   |
+----------------------------------------------------------------------------------------------------+
| UX-09    | Verification Failure Alert   | Flashing red critical alert: "VERIFICATION FAILED".      |
|          |                              | Lists exact violated invariant (e.g., machine overlap).  |
+----------------------------------------------------------------------------------------------------+
| UX-10    | Import Preview & Errors      | Staged two-phase import modal. Displays valid row count  |
|          |                              | alongside table of errors with column, row, & fix advice.|
+----------------------------------------------------------------------------------------------------+
| UX-11    | Scenario Comparison Warnings | Dual Gantt / Delta table. Clear delta badges (+15m span, |
|          |                              | +2 late jobs). Warns if baseline schedule was modified.  |
+----------------------------------------------------------------------------------------------------+
| UX-12    | Offline / No Internet State  | Muted green dot in status bar: "Local Mode (Offline)".   |
|          |                              | Zero broken UI elements or network timeout alerts.       |
+----------------------------------------------------------------------------------------------------+
| UX-13    | Backend Unavailable State    | Top notification banner: "Local Backend Disconnected.    |
|          |                              | Viewing cached data. [Retry Connection] [Switch to Demo]"|
+----------------------------------------------------------------------------------------------------+
| UX-14    | Empty Reports State          | Neutral placeholder: "No schedule generated yet. Solve a |
|          |                              | scenario to unlock utilization & tardiness analytics."   |
+----------------------------------------------------------------------------------------------------+
| UX-15    | Small Screen / Mobile Layout | Responsive view: Compact KPI summary cards, scheduled    |
|          | (< 768px width)              | order list table, Gantt horizontal pan with pinned labels|
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Non-Negotiable Rule 4: Organized, Human-Readable Code

### 4.1 Architecture Discipline & Unidirectional Dependencies
The Opwise codebase must be immediately understandable to any qualified software engineer without requiring conversational guidance.

- **Strict Dependency Direction:**
  - `domain`: Pure business models and scheduling definitions. Zero dependencies on database, solver, or HTTP.
  - `verifier`: Clean-room independent verifier. Depends ONLY on `domain`. MUST NOT import OR-Tools or solver code.
  - `solver`: CP-SAT model formulation and status mapping. Depends on `domain`.
  - `persistence`: SQLAlchemy models and SQLite WAL engine. Depends on `domain`.
  - `api`: FastAPI routers, request/response serialization, and exception handlers. Orchestrates `domain`, `solver`, `verifier`, and `persistence`.
  - `frontend`: React UI consuming API contracts. Completely decoupled from backend internals.

```
   +-------------------------------------------------------------+
   |                     FastAPI REST API Layer                   |
   +-------------------------------------------------------------+
             |                     |                     |
             v                     v                     v
   +------------------+  +------------------+  +------------------+
   |  OR-Tools Solver |  |  Clean Verifier  |  |   Persistence    |
   | (CP-SAT Engine)  |  | (Pure Math Audit)|  |  (SQLite WAL)    |
   +------------------+  +------------------+  +------------------+
             \                     |                     /
              \                    |                    /
               v                   v                   v
   +-------------------------------------------------------------+
   |                      Domain Model Core                      |
   |         (Entities, Invariants, Canonical Norms, Math)       |
   +-------------------------------------------------------------+
```

### 4.2 Code Standards & Review Thresholds
- **Python Conventions:**
  - Modern Python 3.12+ type hints (`list[str]`, `dict[str, Any]`, `X | None`).
  - Strict type checking via `mypy --strict`. Zero `Any` in domain, verifier, or solver contracts.
  - Naming: `snake_case` for functions/variables, `PascalCase` for classes/Pydantic models, `UPPER_SNAKE` for constants.
  - Small, focused functions: target < 50 lines per function.
  - Small, cohesive modules: target < 350 lines per module. Split files based on single responsibility.
- **TypeScript / React Conventions:**
  - TypeScript 5+ strict mode enabled (`noImplicitAny`, `strictNullChecks`).
  - Functional React 19 components with explicit props interfaces.
  - Zero arbitrary `any` casts. Explicit domain types matching backend OpenAPI schemas.
  - Naming: `camelCase` for functions/variables, `PascalCase` for components and types.
- **No Unexplained Magic Numbers:** All scheduling horizons, time limits, default weights, and UI scale factors must be defined in documented constants or configuration modules.
- **Explicit Comments on Complex Math:** CP-SAT interval creation, downtime merging, two-stage lexicographic clamping, and machine utilization denominators must include explicit docstrings citing the mathematical formula.

### 4.3 Readability Navigation Directory ("Where Do I Find...?")

| Responsibility | Implementation Target Location |
| :--- | :--- |
| **Domain Entities & Types** | `backend/opwise/domain/models.py` |
| **Input Validation Rules** | `backend/opwise/domain/validators.py` |
| **Downtime Merge Normalization** | `backend/opwise/domain/downtime.py` |
| **CP-SAT Interval & NoOverlap Constraints** | `backend/opwise/solver/constraints.py` |
| **Objective Formulations & Clamping** | `backend/opwise/solver/objectives.py` |
| **Lexicographic Solver Engine** | `backend/opwise/solver/engine.py` |
| **Solver Status Translation** | `backend/opwise/solver/status_mapper.py` |
| **Clean-Room Independent Verifier** | `backend/opwise/verifier/independent_verifier.py` |
| **KPI & Utilization Calculations** | `backend/opwise/domain/metrics.py` |
| **Scenario Disruption & Comparison** | `backend/opwise/domain/scenarios.py` |
| **SQLite WAL Engine & Transactions** | `backend/opwise/persistence/database.py` |
| **SQLAlchemy ORM Entities** | `backend/opwise/persistence/models.py` |
| **FastAPI Route Handlers** | `backend/opwise/api/routes/` |
| **CSV & Excel Parsing / Export** | `backend/opwise/io/` |
| **Gantt Chart SVG Rendering** | `frontend/src/features/gantt/GanttChart.tsx` |
| **Gantt Coordinate Transform Math** | `frontend/src/features/gantt/ganttTransform.ts` |
| **Client-Side Demo Verifier** | `frontend/src/features/demo/clientVerifier.ts` |
| **Pre-Solved Synthetic Fixtures** | `frontend/src/features/demo/fixtures/` |
| **Backend Unit & Regression Tests** | `backend/tests/unit/`, `backend/tests/integration/` |
| **Frontend Component & Hook Tests** | `frontend/src/__tests__/` |

---

## 5. Non-Negotiable Rule 5: GitHub as Continuous Backup

### 5.1 Remote Backup Discipline
GitHub is the authoritative, continuous remote backup mechanism throughout development. It is not an end-of-project export step.

- **Mandatory Policy:** Development must progress through small, coherent, verified commits pushed to GitHub at every major milestone.
- **Phase 0 Boundary:** During Phase 0.3, Git initialization is strictly FORBIDDEN. Repository creation and initial commit occur only upon explicit Phase 1 authorization.

### 5.2 Commit Hygiene & Category Taxonomy
Every commit must represent a single logical unit of work that passes relevant static checks and unit tests.

- **Conventional Commit Prefixes:**
  - `feat:` A new user-facing capability, solver constraint, or API route.
  - `fix:` A bug fix in domain logic, solver formulation, or UI rendering.
  - `test:` Adding or refining unit, property, or integration tests.
  - `docs:` Specification, architecture, ADR, or documentation updates.
  - `refactor:` Code restructuring without functional changes.
  - `build:` Build tooling, package dependencies, or configuration changes.
  - `ci:` GitHub Actions workflow and automated testing scripts.
- **Pre-Commit Verification Routine:**
  1. Inspect `git status` to verify modified and untracked files.
  2. Inspect `git diff` to verify exact line changes.
  3. Ensure no `.env`, database `.sqlite3`, cache `__pycache__`, or node_modules files are tracked.
  4. Run relevant tests and verify 100% passing.
  5. Commit with an informative, descriptive message.

### 5.3 Mandatory Backup Checkpoints (14 Implementation Milestones)

```
[Milestone 01: Repo & Tooling]   --> Commit & Push to GitHub
[Milestone 02: Domain Core]      --> Commit & Push to GitHub
[Milestone 03: Clean Verifier]   --> Commit & Push to GitHub
[Milestone 04: CP-SAT Formulation]--> Commit & Push to GitHub
[Milestone 05: Lexicographic]    --> Commit & Push to GitHub
[Milestone 06: Metrics Engine]   --> Commit & Push to GitHub
[Milestone 07: Persistence & API]--> Commit & Push to GitHub
[Milestone 08: Frontend Shell]   --> Commit & Push to GitHub
[Milestone 09: Gantt Chart View] --> Commit & Push to GitHub
[Milestone 10: Scenarios Engine] --> Commit & Push to GitHub
[Milestone 11: CSV / Excel I/O]  --> Commit & Push to GitHub
[Milestone 12: E2E Quality Gate] --> Commit & Push to GitHub
[Milestone 13: Demo Mode & Host] --> Commit & Push to GitHub
[Milestone 14: Release Audit]    --> Commit & Push to GitHub
```

### 5.4 Separation of Source Code vs. Runtime Database Backups
- **Source Code Backup:** Handled via Git and GitHub remote repository.
- **Runtime Database Backup:** `.sqlite3` databases are strictly excluded from Git via `.gitignore`. Runtime persistence backups must be performed using SQLite's online safe backup API:
  ```sql
  VACUUM INTO 'backups/opwise_backup_YYYYMMDD_HHMMSS.sqlite3';
  ```
- **Recovery Procedure:** If local disk corruption occurs, clone the GitHub repository, install pinned dependencies, and restore the desired `.sqlite3` database snapshot from the local backup directory.

---

## 6. Rule 6: Testing Discipline and Honest Verification

### 6.1 Honest Claim & Status Taxonomy
To eliminate false claims of readiness or functionality, all progress reports, test logs, and documentation must adhere to the **Four-Tier Gravitas Verification Taxonomy**:

1. **`Specification defined`:** The requirement, mathematical model, schema, or invariant is formally documented in specifications. No executable code exists.
2. **`Metadata verified`:** Verified through static inspection of environment tools, package registries, or licenses. No runtime execution performed.
3. **`Requires implementation testing`:** Executable code exists but requires running tests to verify behavior.
4. **`Implementation tested`:** Executed against automated unit/integration tests with reported command output and 100% pass rate.
5. **`Unresolved`:** An open engineering trade-off or technical question where empirical proof is pending.

### 6.2 Mathematical Model & Invariant Preservation
The three MVP optimization modes are strictly fixed:
- `PURE_MAKESPAN` ($\min C_{\max}$)
- `PURE_WEIGHTED_TARDINESS` ($\min \sum w_j T_j$)
- `HIERARCHICAL_LEXICOGRAPHIC` (Stage 1: $\min \sum w_j T_j$; Stage 2: $\min C_{\max}$ subject to $T \le T^*$).

Weighted-sum objectives remain excluded from the MVP. The 6 input classifications, canonical downtime merge normalization, 7-case lexicographic state transition matrix, and 8 clean-room verifier invariants are inviolable architectural commitments.

### 6.3 Independent Verification Principle
The verifier module (`backend/opwise/verifier/independent_verifier.py`) must remain completely independent of Google OR-Tools. It audits schedules using pure analytical Python logic against all 8 domain invariants:
1. Operation Precedence ($C_{j,k} \le S_{j,k+1}$)
2. Release Time ($r_j \le S_{j,0}$)
3. Operation Duration ($C_{j,k} - S_{j,k} = p_{j,k}$)
4. Machine No-Overlap (Half-open non-collision $[S_a, C_a) \cap [S_b, C_b) = \emptyset$)
5. Machine Downtime Avoidance ($[S, C) \cap [D_s, D_e) = \emptyset$)
6. Integer Time Grid ($S, C \in \mathbb{N}_0$)
7. Objective Value Concordance ($C_{\max} = \max C_{j,k}$; $T_j = \max(0, C_{j,\text{last}} - d_j)$)
8. Lexicographic Stage-1 Preservation ($T_{\text{stage2}} \le T_{\text{stage1}}^*$)

---

## 7. Rule 7: Privacy, Local Security, Dependencies, and Licensing

### 7.1 Data Privacy & Zero Telemetry
- **Default Local Privacy:** Opwise operates entirely within the user's local operating environment. Zero tracking pixels, telemetry events, usage pings, or diagnostic crash reports are transmitted over the network.
- **Factory Data Isolation:** Production schedules, machine names, order quantities, and customer due dates never leave the local machine.

### 7.2 Local File Security & Input Sanitization
- **Spreadsheet Security:** Excel (`.xlsx`) imports via `openpyxl` must enforce secure XML parsing to prevent XML Entity Expansion (Billion Laughs) and External Entity Injection (XXE).
- **CSV Injection Prevention:** Any exported CSV strings beginning with formula trigger characters (`=`, `+`, `-`, `@`) must be prepended with a single quote (`'`) to protect spreadsheet applications from formula injection.
- **Filesystem Traversal Protection:** All file export paths must be validated against a whitelist directory and sanitized to reject `..` path traversal sequences.

### 7.3 Dependency Governance & Open-Source Licensing
- **Strict Pinning:** All Python dependencies in `requirements.txt` and Node dependencies in `package-lock.json` must be pinned to exact versions.
- **Permissive Open-Source Licenses:** Every dependency must use a business-friendly, permissive open-source license (MIT, Apache 2.0, BSD-3-Clause, Public Domain). Copyleft licenses (GPLv3, AGPL) are prohibited to ensure maximum portability.
- **Attribution Discipline:** If academic benchmark instances (e.g., Beasley OR-Library) are imported, proper academic citation must be embedded in the fixture metadata without imposing licensing encumbrances on the core codebase.

---

## 8. Mandatory Operational Checklists

### 8.1 Pre-Change Checklist
Before writing or modifying any specification document, configuration, or code:
- [ ] **1. Inspect Before Editing:** Verify current directory, Git status, and existing files.
- [ ] **2. Scope Identification:** Confirm exact files to be modified; verify sibling projects (`Integris`, `CodeShip`, `PathForge`) are unaffected.
- [ ] **3. Invariant Protection:** Confirm proposed change does not weaken ₹0 budget, mathematical model, or independent verifier.
- [ ] **4. Dependency Audit:** Verify no paid APIs, cloud services, or unvetted libraries are introduced.
- [ ] **5. Architecture Alignment:** Verify change follows unidirectional dependency flow.
- [ ] **6. Tooling Verification:** Ensure appropriate linters, typecheckers, and test runners are configured.
- [ ] **7. Risk Assessment:** Identify failure modes or breaking changes prior to execution.

### 8.2 Completion Checklist
Before declaring any task, phase, or milestone complete:
- [ ] **1. Verification Execution:** Execute all relevant unit, integration, or lint checks. Verify 100% passing.
- [ ] **2. Zero Fabricated Claims:** Verify all reported metrics, outputs, and statuses reflect actual command execution.
- [ ] **3. Clean Git Status:** Review `git status` and `git diff` to ensure zero untracked junk, secrets, or accidental edits.
- [ ] **4. Build & Typecheck Cleanliness:** Verify TypeScript (`tsc --noEmit`) and Python (`mypy --strict`) report zero errors.
- [ ] **5. Cross-Document Concordance:** Verify all affected documentation files are updated and mutually consistent.
- [ ] **6. Milestone Remote Backup:** Perform conventional commit and push to GitHub remote (when authorized in Phase 1+).
- [ ] **7. Honest Reporting:** Report status using strict Gravitas taxonomy (`Specification defined`, `Implementation tested`, etc.) and document unresolved items.
