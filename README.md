# Opwise — Local-First Production Planning & Optimization Platform

**Portfolio Project #4** | *Operations Research & Job Shop Scheduling*

Opwise is a local-first production planning and discrete optimization platform designed for discrete job shops. The application uses Google OR-Tools CP-SAT constraint programming to generate provably optimal or bounded schedules, render interactive Gantt visualizations, audit schedules with an independent clean-room verifier, provide deterministic explanations, and simulate disruption scenarios.

---

## Phase 0.3: Project Constitution, Zero-Cost Architecture & GitHub Readiness Gate

This workspace houses the complete, audited **Phase 0.3 Pre-Implementation Specification Package and Project Constitution**. In strict accordance with the Phase 0 scope boundary, application source code has not yet been initialized, no packages have been installed, no database has been created, and Git has not been initialized.

### Specification & Governance Suite

| Document | Description |
| :--- | :--- |
| **[PROJECT_RULES.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/PROJECT_RULES.md)** | **Permanent Project Constitution** — Non-negotiable rules governing ₹0 operating cost, tiered deployment topology, professional industrial UI/UX (anti-AI-slop), readable code, continuous GitHub backup, test-first verification, security/licensing, and mandatory operational checklists. |
| **[SPECIFICATION.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SPECIFICATION.md)** | **Authoritative Master Specification** — Product definition, workflows, MVP boundaries, 6 input edge cases, downtime normalization, unified metrics, deterministic explanations, disruption simulation rules, 6 navigation pillars, schedule results canvas requirements, and 6 synthetic demo scenarios. |
| **[ARCHITECTURE.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/ARCHITECTURE.md)** | **System Architecture & Blueprint** — Clean monorepo structure, component responsibilities, dependency flow, tiered deployment topology (Localhost, GitHub Pages, Docker), contributor code navigation guide, configuration, and logging. |
| **[SOLVER_MODEL.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/SOLVER_MODEL.md)** | **Mathematical Formulation & Solver Contract** — Input classification, downtime boundary non-collision, canonical merge normalization, horizon overflow safeguards, objectives, lexicographic state transition matrix, and 8-invariant independent verifier. |
| **[DATA_AND_API.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DATA_AND_API.md)** | **Persistence & REST API Specification** — Relational SQLite WAL schema, SQLAlchemy 2.0 models, OpenAPI 3.1 endpoints (`/api/v1`), explicit error envelopes for empty/invalid inputs, static demo mode limitations, and CSV/Excel import/export formats. |
| **[TEST_AND_RELEASE_PLAN.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/TEST_AND_RELEASE_PLAN.md)** | **Acceptance Matrix & Verification Protocol** — 23-row final acceptance matrix, 16-category test matrix, 14-milestone practical implementation roadmap, resolution of the 4 verification gates, persistence recovery tests, and 12 production release gates. |
| **[DECISIONS.md](file:///e:/MHT%20CET%20REGISTRATION/BE/Task/Opwise/DECISIONS.md)** | **Architecture Decision Records (ADRs)** — ADR 001–012 documenting rationale for local-first SQLite WAL durability, CP-SAT formulation, clean-room verification, synthetic benchmarks, version pinning, empty input policies (ADR-009), downtime normalization (ADR-010), ₹0 deployment topology (ADR-011), and continuous GitHub backup policy (ADR-012). |

---

## Technology Stack & Deployment Topology

- **Backend:** Python 3.12, FastAPI 0.143, Pydantic v2.14, SQLAlchemy 2.1, Uvicorn *(Metadata Verified)*
- **Optimization:** Google OR-Tools CP-SAT 9.15.6755 (`ortools-9.15.6755-cp312-cp312-win_amd64.whl` on PyPI) *(Metadata Verified)*
- **Verification:** Decoupled Clean-Room Invariant Verifier (8 operational invariants audited in Python backend and TypeScript frontend) *(Specification Defined)*
- **Persistence:** Local SQLite 3 (WAL mode, `synchronous = NORMAL`, per-connection foreign keys, `VACUUM INTO` backups) *(Specification Defined)*
- **Frontend:** React 19, TypeScript 5.8, Vite 6.2, Tailwind CSS *(Metadata Verified)*
- **Data Exchange:** Strict CSV and Microsoft Excel (`.xlsx` via openpyxl) with canonical downtime normalization and formula injection escaping *(Specification Defined)*
- **Testing:** pytest (backend), Vitest / React Testing Library (frontend), Playwright (E2E) *(Specification Defined)*
- **Deployment Topology:**
  - **Tier 1 (Canonical Engine):** Localhost execution (`127.0.0.1:8000` + `localhost:5173`) with live CP-SAT solving and durable SQLite WAL storage.
  - **Tier 2 (Public Portfolio Demo):** Permanent ₹0 static web app hosted on GitHub Pages running Standalone Client-Side Demo Mode (pre-solved synthetic fixtures Demo 1–6 + client-side verifier).
  - **Tier 3 (Reviewer Runner):** Portable Docker Compose container or native launcher script for on-demand local evaluation.

