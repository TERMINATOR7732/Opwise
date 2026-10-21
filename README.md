# Opwise — Local-First Production Planning & Optimization Platform

**Portfolio Project #4** | *Operations Research & Job Shop Scheduling*

Opwise is a local-first production planning, discrete optimization, and shop-floor operations platform engineered for discrete job shops. Powered by Google OR-Tools CP-SAT constraint programming, Opwise solves complex multi-machine, multi-job sequencing problems with proven bounds, renders interactive Gantt visualizations, audits schedules with an independent clean-room verifier, simulates real-time machine breakdowns and rush orders, and tracks physical shop-floor execution against a simulated plant clock.

---

## 1. Key Engineering Capabilities

- **Constraint Programming Optimization Engine:**
  - Formulated with Google OR-Tools CP-SAT 9.15.
  - Supports `PURE_MAKESPAN` ($\min C_{\max}$), `PURE_WEIGHTED_TARDINESS` ($\min \sum w_j T_j$), and two-stage hierarchical lexicographic multi-objective optimization with strict proof gating.
  - Enforces machine exclusivity (`AddNoOverlap`), half-open non-collision intervals $[start, end)$, and maintenance window boundaries $[s, e) \cap [e, d) = \emptyset$.
- **Clean-Room Independent Schedule Verifier:**
  - Audits 8 core domain invariants (precedence, machine exclusivity, downtime non-collision, release time compliance, non-zero durations, sequence continuity, horizon bounds, and objective consistency).
  - Decoupled from OR-Tools and persistence; implemented in both pure Python (backend) and TypeScript (frontend client).
  - Validated by mutant test suites injecting falsified schedules and constraint reversals.
- **Shop-Floor Execution Controls & Plant Clock (Milestone 15):**
  - Discrete, monotonic plant-clock advancement with linear remaining-duration decrements.
  - Operation lifecycle states: `PLANNED`, `IN_PROGRESS`, and `COMPLETED`.
  - Policy B Overdue Reconciliation: Requires supervisor action (marking completed at destination clock or overriding remaining work) when elapsed time reaches or exceeds estimates.
  - Optimistic concurrency fencing (`expected_current_time_minute` token returning HTTP 409 `STALE_EXECUTION_STATE`) and SQLite touch write-lock serialization.
- **Interactive High-Density Gantt Canvas:**
  - Horizontal machine swimlanes with minute-precision half-open blocks, diagonal downtime hatchings, zoom/pan navigation, and hover precedence highlighting.
  - Contextual dispatching controls (`Start`, `Complete`, `Running`) embedded in the Orders Tab and Gantt Inspection Drawer.
- **Scenario Disruption & Recovery Lab:**
  - Branch from immutable baseline schedules to inject rush orders, machine breakdown windows, or operation duration delays.
  - Side-by-side comparative Gantt charts and differential KPI badges ($\Delta C_{\max}$, $\Delta$ late orders).
- **Two-Phase CSV & Microsoft Excel Data Exchange:**
  - Phase 1 in-memory preview with row-level validation and canonical downtime normalization (merging overlapping or contiguous intervals).
  - Phase 2 atomic database commit with formula injection escaping (`'` prefix on `=, +, -, @`) and XXE-safe workbook parsing.
- **Zero-Cost Local Architecture:**
  - ₹0 operating budget, zero external paid cloud dependencies, zero AI chat wrappers.
  - Local SQLite 3 WAL persistence with foreign key constraints, transactional rollback, and Alembic schema migrations.

---

## 2. System Architecture

Opwise is organized as a clean, decoupled monorepo:

```
Opwise/
├── backend/                        # FastAPI + SQLAlchemy + OR-Tools Backend
│   ├── alembic/                    # Database migrations (revisions 001–004)
│   ├── opwise/
│   │   ├── api/                    # Versioned REST routers (/api/v1) & schemas
│   │   ├── domain/                 # Pure domain entities, validators & metrics
│   │   ├── io/                     # CSV & Excel parsers and templates
│   │   ├── persistence/            # SQLite models & repositories (WAL mode)
│   │   ├── services/               # Execution, factory, scenario & optimization services
│   │   ├── solver/                 # CP-SAT model formulation & lexicographic solver
│   │   └── verifier/               # 8-invariant independent schedule verifier
│   └── tests/                      # 244 unit, mutant, integration & concurrency tests
├── frontend/                       # React 19 + TypeScript + Vite Frontend
│   ├── src/
│   │   ├── api/                    # Typed HTTP client & endpoints
│   │   ├── components/             # Reusable UI, layout, Gantt & execution modals
│   │   ├── context/                # Workspace & factory mutation providers
│   │   ├── demo/                   # Standalone client demo mode & fixtures 1–6
│   │   ├── views/                  # 6 navigation pillars (Factory, Schedules, Scenarios, etc.)
│   │   └── tests/                  # 155 Vitest unit, component & verifier tests
└── .github/workflows/              # Automated CI & GitHub Pages deployment workflows
```

---

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Service** | Python 3.12, FastAPI 0.115, Pydantic v2.10, Uvicorn |
| **Optimization** | Google OR-Tools CP-SAT 9.11+ |
| **Database & ORM** | SQLite 3 (WAL mode, PRAGMA synchronous=NORMAL, foreign_keys=ON), SQLAlchemy 2.0 (asyncio), Alembic |
| **Frontend SPA** | React 19, TypeScript 5.7, Vite 6.0 |
| **Data Exchange** | OpenPyXL (Excel), Python CSV reader/writer with formula sanitization |
| **Testing** | pytest, pytest-cov, pytest-asyncio, Vitest |
| **Code Hygiene** | Ruff (linter/formatter), Mypy (strict static typing) |

---

## 4. Local Setup & Execution Guide

### Prerequisites
- Python 3.12 or newer
- Node.js 22 or newer (with npm 10+)
- Git

### 1. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install production and development dependencies
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# Run database migrations to latest schema revision
alembic upgrade head

# Start local FastAPI backend (runs on http://127.0.0.1:8000)
uvicorn opwise.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup
```bash
# In a separate terminal, navigate to frontend directory
cd frontend

# Install npm dependencies
npm ci

# Start Vite development server (runs on http://localhost:5173)
npm run dev
```

Open `http://localhost:5173` in your browser. The Vite development proxy forwards all `/api` requests to `http://127.0.0.1:8000`.

---

## 5. Automated Verification & Quality Gates

Run the project verification commands from their respective directories:

### Backend Checks
```bash
cd backend

# 1. Code hygiene and linting (Ruff)
ruff check .

# 2. Strict static type analysis (Mypy)
mypy --strict opwise

# 3. Unit, integration, concurrency, and verifier tests with coverage
pytest tests/ -v --cov=opwise --cov-report=term-missing
```
*Current test suite status: **244 / 244 passed** (83% overall coverage).*

### Frontend Checks
```bash
cd frontend

# 1. ESLint static analysis
npm run lint

# 2. Strict TypeScript type check
npm run typecheck

# 3. Vitest unit, component, and client-verifier tests
npm run test

# 4. Production bundle build
npm run build

# 5. Standalone static demo bundle build
npm run build:demo
```
*Current test suite status: **155 / 155 passed** across 14 test files.*

---

## 6. Portfolio Demo Deployment & URL

Opwise is deployed as a standalone client-side demo with zero external cloud dependencies:

- **Primary Live Demo URL:** [https://opwise.vercel.app](https://opwise.vercel.app)
- **Alternative / Legacy Deployment:** [https://terminator7732.github.io/Opwise/](https://terminator7732.github.io/Opwise/) (GitHub Pages workflow configured in [`.github/workflows/deploy-demo.yml`](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/.github/workflows/deploy-demo.yml))
- **Client-Side Demo Features:**
  - 6 pre-solved synthetic industrial demo fixtures (Normal, Bottleneck, High Load, Urgent Orders, Machine Downtime, and Invalid/Corrupt Input).
  - Standalone Plant Clock & Shop-Floor Execution Simulation (in-memory clock advance, operation lifecycle state tracking, remaining-duration adjustments, and supervisor reconciliation).
  - 8-Step Interactive Guided Tour introducing core production scheduling workflows.
  - Pure TypeScript Clean-Room Verifier running entirely in the browser to audit the 8 domain invariants live.
  - Interactive Gantt chart with zoom, pan, machine utilization, and automated bottleneck diagnostics without requiring a running Python backend.

---

## 7. Specification & Governance Archive

| Document | Description |
|---|---|
| [PROJECT_RULES.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/PROJECT_RULES.md) | Permanent constitution: ₹0 operating cost, anti-AI-slop UI, evidence-backed tests. |
| [SPECIFICATION.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SPECIFICATION.md) | Authoritative product specification, workflows, and 6 synthetic demo definitions. |
| [ARCHITECTURE.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/ARCHITECTURE.md) | Monorepo blueprint, component responsibilities, and deployment topology. |
| [SOLVER_MODEL.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SOLVER_MODEL.md) | Mathematical formulation, half-open interval contact, and verifier contracts. |
| [DATA_AND_API.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DATA_AND_API.md) | Relational schema, SQLite WAL configuration, and OpenAPI 3.1 endpoint envelopes. |
| [TEST_AND_RELEASE_PLAN.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/TEST_AND_RELEASE_PLAN.md) | Verification protocol, 16 test categories, and 12 production release gates. |
| [DECISIONS.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DECISIONS.md) | Architecture Decision Records (ADRs 001–012). |
| [MILESTONE_14_RELEASE_AUDIT.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/MILESTONE_14_RELEASE_AUDIT.md) | Phase 1 release readiness audit and verification log. |
| [MILESTONE_15D_SCOPE_PROPOSAL.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/MILESTONE_15D_SCOPE_PROPOSAL.md) | Phase 2 shop-floor execution controls specification of record. |
| [MILESTONE_15D_POST_IMPLEMENTATION_AUDIT_REPORT.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/MILESTONE_15D_POST_IMPLEMENTATION_AUDIT_REPORT.md) | Phase 2 independent post-implementation audit & release remediation log. |

---

## 8. License

Opwise is open-source software licensed under the [MIT License](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/LICENSE).
