# Opwise — Mathematical Solver Model and Verification Specification

- **Document ID:** OPW-MOD-001
- **Status:** APPROVED FOR SPECIFICATION (Phase 0.3 Pre-Implementation Approval Gate)
- **Version:** 1.3.0
- **Last Updated:** 2026-10-16
- **Governance:** Governed by `PROJECT_RULES.md` (Opwise Permanent Constitution)
- **Domain:** Discrete Job Shop Scheduling with Release Times, Soft Due Dates, Tardiness Weights, and Machine Downtimes ($Jm | r_j, \text{downtime} | C_{\max}, \sum w_j T_j$)

---

## 1. Input Classification and Validation Policy

The Opwise scheduling engine formally distinguishes six distinct input conditions to prevent silent failures and ensure deterministic handling:

| Case ID | Input Condition | Factory Data State | Validation Result | Solver Action | API Response | Schedule Persistence & UI State |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **INP-1** | Empty Workspace | 0 machines, 0 orders, 0 operations. | Valid for viewing (`GET /factory` returns empty lists). | Solver **not invoked**. Optimize request rejected. | HTTP 422 `EMPTY_WORKSPACE` | No schedule saved. UI renders Welcome Empty State. |
| **INP-2** | Factory with Machines but No Orders (No-Work) | $\ge 1$ machines, 0 orders, 0 operations. | Valid structure, $|J|=0$. | Solver **bypassed**. Evaluated analytically as No-Work. | HTTP 200 with `status: "NO_WORK_STATE"`, metrics=0. | Persisted with status `NO_WORK_STATE`. UI displays "No Work Scheduled" badge. |
| **INP-3** | Order Without Operations | Order exists with 0 associated operations. | **Fails validation**. Incomplete order definition. | Solver **not invoked**. | HTTP 422 `ORDER_WITHOUT_OPERATIONS` | No schedule saved. UI highlights order row with error badge. |
| **INP-4** | Dangling / Missing Entity Reference | Operation references non-existent order or machine. | **Fails validation**. Foreign key reference missing. | Solver **not invoked**. | HTTP 422 `REFERENTIAL_INTEGRITY_VIOLATION` | No schedule saved. UI renders line-numbered reference violation error. |
| **INP-5** | Valid Non-Empty Factory | $\ge 1$ machines, $\ge 1$ orders, each order has contiguous operations $1 \dots n_j$. | **Passes validation**. | Solver **invoked** with selected objective mode. | HTTP 200 with schedule, telemetry, and verification report. | Persisted with solver status (`OPTIMAL` or `FEASIBLE`). UI renders Gantt and metrics. |
| **INP-6** | Valid Factory with Infeasible Constraints | Valid structure, but constraints cannot be met (e.g. 100% downtime over horizon). | Passes structural check; CP-SAT proves contradiction. | CP-SAT runs and returns status `INFEASIBLE`. | HTTP 200 with `solver_status: "INFEASIBLE"`, 0 operations. | Persisted with status `INFEASIBLE`. UI renders "Schedule Infeasible" alert. |

---

## 2. Domain Problem Definition & Invariants

### 2.1 Structural Properties
1. **Schedule Origin ($t = 0$):**
   - All time expressions are non-negative discrete integer relative minutes ($t \in \mathbb{N}_0$, $t \ge 0$).
   - The schedule origin is strictly fixed at $t = 0$.
2. **Fixed Machine Assignment:**
   - Every operation $O_{j,k}$ is assigned to exactly one predetermined machine $m \in M$. Dynamic machine substitution or alternative machine sets (Flexible Job Shop) are excluded from the MVP.
3. **Non-Preemptive Operations:**
   - Once an operation begins processing on a machine, it executes continuously for its entire specified duration $p_{j,k} \ge 1$ without pause or preemption.
4. **Strict Intra-Order Precedence:**
   - Each production order $j \in J$ comprises a strictly ordered sequence of operations $\langle O_{j,1}, O_{j,2}, \dots, O_{j,n_j} \rangle$. Operation $O_{j,k+1}$ cannot start until operation $O_{j,k}$ has completely finished.
5. **Machine Exclusivity:**
   - A machine $m \in M$ can process at most one operation at any given instant. Concurrent operations on the same machine are prohibited.
6. **Half-Open Interval Semantics:**
   - Operations and machine downtimes are modeled as half-open intervals $[start, end)$.
   - An operation occupying $[S_{j,k}, C_{j,k})$ consumes minutes $t$ where $S_{j,k} \le t < C_{j,k}$.
   - Boundary contact rule: At boundary minute $C_{j,k}$, processing is complete. The machine is immediately available for the next scheduled operation at minute $C_{j,k}$.
7. **Order Release Times ($r_j$):**
   - Each order $j$ has an integer release time $r_j \ge 0$ relative to origin $t=0$.
   - No operation of order $j$ may commence before $r_j$ ($S_{j,1} \ge r_j$).
8. **Soft Due Dates ($d_j$) and Tardiness Weights ($w_j$):**
   - Target delivery due date $d_j \ge 0$ relative to origin $t=0$ and penalty weight $w_j \ge 0$.
   - Tardiness $T_j = \max(0, C_j - d_j)$. Exceeding a due date incurs penalty $w_j \cdot T_j$ but does not render the schedule infeasible.
9. **Makespan Definition:**
   - Makespan ($C_{\max}$) is defined strictly as the **maximum completion time relative to schedule origin $t = 0$**:
     $$C_{\max} = \max_{(j,k) \in O} C_{j,k} - 0$$
   - It is **not** defined as $\max C - \min S$. A schedule spanning $[30, 100)$ has makespan 100, reflecting elapsed shop floor time from schedule origin.

---

## 3. Machine Downtime Normalization, Horizon & Boundary Rules

### 3.1 Half-Open Boundary Non-Collision
- **Operation Contacting Downtime Start:**
  If operation $A$ is scheduled over $[S_a, T)$ and downtime begins at minute $T$ ($[T, D_e)$):
  $$[S_a, T) \cap [T, D_e) = \emptyset$$
  Because the operation ends at minute $T$ (open upper bound) and downtime starts at minute $T$ (closed lower bound), there is zero intersection. **This is valid and legal.**
- **Operation Contacting Downtime End:**
  If downtime occupies $[D_s, T)$ and operation $B$ begins at minute $T$ ($[T, C_b)$):
  $$[D_s, T) \cap [T, C_b) = \emptyset$$
  The machine becomes available immediately at minute $T$. **This is valid and legal.**

### 3.2 Canonical Downtime Normalization (Merge Policy)
Planners may enter maintenance windows that overlap or touch. Opwise applies an automated canonical normalization pre-pass on each machine $m$:
1. **Sort:** Sort all declared downtime intervals on machine $m$ by `start_minute` ascending.
2. **Merge Overlaps:** For any two intervals where $D_{1,s} \le D_{2,s} < D_{1,e}$, merge into a single interval:
   $$[D_{\text{merged}, s}, D_{\text{merged}, e}) = [\min(D_{1,s}, D_{2,s}), \max(D_{1,e}, D_{2,e}))$$
3. **Merge Adjacencies:** For any two intervals where $D_{1,e} == D_{2,s}$, merge into:
   $$[D_{1,s}, D_{2,e})$$
4. **Zero-Length Downtimes:** Intervals where $D_s == D_e$ consume 0 capacity and are filtered out with an advisory log message.
5. **Invalid Intervals:** Intervals with $D_s > D_e$ or $D_s < 0$ are rejected during input validation with HTTP 422.

The resulting canonical set $\mathcal{D}_m^{\text{merged}}$ contains disjoint, non-adjacent, strictly positive half-open intervals.

### 3.3 Dynamic Horizon Calculation ($H$) & Overflow Protection
To guarantee CP-SAT variables operate within safe integer domains, the worst-case serial horizon $H$ is computed from normalized downtimes:
$$H = \max_{j \in J}(r_j) + \sum_{(j,k) \in O} p_{j,k} + \sum_{m \in M} \sum_{d \in \mathcal{D}_m^{\text{merged}}} (d^{\text{end}} - d^{\text{start}})$$

#### Boundary Behaviors Relative to Horizon:
1. **Downtime starting beyond $H$ ($D_s \ge H$):** Excluded from the CP-SAT interval set. Telemetry logs an advisory note: *"Downtime $[D_s, D_e)$ is beyond effective horizon $H$ and cannot constrain this production batch."*
2. **Downtime starting inside and ending beyond $H$ ($D_s < H < D_e$):** Clamped to $[D_s, H)$ for CP-SAT interval construction.
3. **Downtime covering entire relevant horizon ($[0, H)$):** Permitted as input. CP-SAT attempts solve; if operations assigned to machine cannot fit, solver returns `INFEASIBLE`.
4. **Integer Overflow Guard:** If calculated $H > 2^{31} - 1$ (2,147,483,647 minutes), validation immediately rejects with HTTP 422 `INTEGER_OVERFLOW_RISK`. Opwise settings enforce a maximum practical horizon cap of $10,000,000$ minutes ($\approx 19$ years).

---

## 4. Formal Mathematical Formulation

### 4.1 Sets, Parameters, and Variables
- Sets: Machines $M$, Orders $J$, Operations $O_{j,k}$, Merged Downtimes $\mathcal{D}_m^{\text{merged}}$.
- Parameters: Duration $p_{j,k} \ge 1$, Machine $m_{j,k} \in M$, Release $r_j \ge 0$, Due Date $d_j \ge 0$, Weight $w_j \ge 0$, Horizon $H \in [1, 10^7]$.
- Variables:
  - $S_{j,k} \in [0, H]$: Start time.
  - $C_{j,k} \in [0, H]$: Completion time ($C_{j,k} = S_{j,k} + p_{j,k}$).
  - $I_{j,k}$: CP-SAT Interval Variable over $[S_{j,k}, C_{j,k}]$ of size $p_{j,k}$.
  - $C_j = C_{j, n_j}$: Order completion time.
  - $T_j \ge 0, T_j \ge C_j - d_j$: Order tardiness.
  - $C_{\max} \ge C_j$: Schedule makespan.
  - $I_{m,d}^{\text{down}}$: Fixed CP-SAT Interval Variable over $[d^{\text{start}}, d^{\text{end}}]$ for $d \in \mathcal{D}_m^{\text{merged}}$.

### 4.2 Constraints
1. **Intra-Order Precedence:** $S_{j, k+1} \ge C_{j, k}$ for all $j \in J, k < n_j$.
2. **Release Time Adherence:** $S_{j, 1} \ge r_j$ for all $j \in J$.
3. **Machine Exclusivity & Downtime Respect:**
   For every $m \in M$:
   $$\text{NoOverlap}\left( \{I_{j,k} \mid m_{j,k} = m\} \cup \{I_{m,d}^{\text{down}} \mid d \in \mathcal{D}_m^{\text{merged}}\} \right)$$
   Guarantees:
   - For all operations $a \ne b$ on machine $m$: $[S_a, C_a) \cap [S_b, C_b) = \emptyset$.
   - For all operations $a$ on machine $m$ and downtimes $d \in \mathcal{D}_m^{\text{merged}}$: $[S_a, C_a) \cap [d^{\text{start}}, d^{\text{end}}) = \emptyset$.

---

## 5. Optimization Contract & Solver Status Mapping

Opwise supports three optimization modes:
1. `PURE_MAKESPAN` ($\min C_{\max}$)
2. `PURE_WEIGHTED_TARDINESS` ($\min \sum w_j T_j$)
3. `HIERARCHICAL_LEXICOGRAPHIC` (Two-stage solve with optimality gating)

### 5.1 Hierarchical Lexicographic State Transition Matrix

Stage 1 solves $\min Z_1 = \sum w_j T_j$ with budget $t_1$. Stage 2 solves $\min Z_2 = C_{\max}$ subject to $\sum w_j T_j \le Z_1$ with budget $t_2$.

| Stage 1 Status ($S_1$) | Stage 2 Action | Stage 2 Status ($S_2$) | Overall Schedule Status | Schedule Returned to User? | UI Display Badge |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **`OPTIMAL`** | Execute Stage 2 with $\sum w_j T_j \le Z_1^*$ | **`OPTIMAL`** | **`OPTIMAL`** | **YES (Stage 2)** | `Optimal (Proven)` (Green) |
| **`OPTIMAL`** | Execute Stage 2 with $\sum w_j T_j \le Z_1^*$ | **`FEASIBLE`** (timeout) | **`FEASIBLE`** | **YES (Stage 2)** | `Feasible (Stage 2 Suboptimal - Gap: X%)` (Amber) |
| **`OPTIMAL`** | Execute Stage 2 with $\sum w_j T_j \le Z_1^*$ | **`UNKNOWN`** (no makespan bound) | **`FEASIBLE`** | **YES (Stage 1 fallback)** | `Feasible (Stage 1 Optimal, Stage 2 Unsolved)` (Amber) |
| **`FEASIBLE`** (timeout) | Execute Stage 2 with $\sum w_j T_j \le Z_1$ | **`OPTIMAL`** or **`FEASIBLE`** | **`FEASIBLE`** | **YES (Stage 2)** | `Feasible (Stage 1 Suboptimal - Gap: X%)` (Amber) |
| **`INFEASIBLE`** | **Skip Stage 2** | `null` | **`INFEASIBLE`** | **NO** (0 operations) | `Infeasible (No Schedule Possible)` (Red) |
| **`UNKNOWN`** | **Skip Stage 2** | `null` | **`UNKNOWN`** | **NO** (0 operations) | `Timeout (No Solution Found)` (Gray) |
| **`MODEL_INVALID`**| **Skip Stage 2** | `null` | **`MODEL_INVALID`** | **NO** (0 operations) | `Model Error` (Red) |

#### Critical Rules:
1. **Schedule Return on Stage 2 Timeout:** When Stage 1 is proven `OPTIMAL` but Stage 2 terminates with `FEASIBLE`, the Stage 2 schedule **is returned** because it preserves the proven optimal weighted tardiness $Z_1^*$ and improves makespan. However, the overall status is strictly reported as `FEASIBLE`, displaying Stage 2's optimality gap.
2. **Honesty Invariant:** Opwise **never** labels a lexicographic result as `OPTIMAL` unless **both** Stage 1 is `OPTIMAL` **AND** Stage 2 is `OPTIMAL`.

### 5.2 Persisted Telemetry Schema
Every completed solve persists:
- `objective_type`: `MAKESPAN` | `WEIGHTED_TARDINESS` | `HIERARCHICAL`
- `solver_status`: overall status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, `MODEL_INVALID`, `NO_WORK_STATE`)
- `stage1_status`, `stage1_objective_value`, `stage1_best_bound`, `stage1_wall_clock_seconds`
- `stage2_status`, `stage2_objective_value`, `stage2_best_bound`, `stage2_wall_clock_seconds`
- `makespan_minutes`, `weighted_tardiness`, `late_order_count`, `on_time_rate`
- `verification_status`: `VERIFIED` | `VERIFICATION_FAILED` | `SKIPPED`

---

## 6. Independent Schedule Verification Engine

Before any schedule is presented to the user, the clean-room `ScheduleVerifier` audits the output timestamps against normalized factory inputs:
- **Invariant 1 (Cardinality):** Exactly one timestamp record per operation in $O$.
- **Invariant 2 (Duration & Machine):** $C_{j,k} - S_{j,k} == p_{j,k}$ and $m == m_{j,k}$.
- **Invariant 3 (Release Time):** $S_{j,1} \ge r_j$.
- **Invariant 4 (Precedence):** $S_{j,k+1} \ge C_{j,k}$.
- **Invariant 5 (Machine Exclusivity):** On every machine, sorted operations satisfy $C_i \le S_{i+1}$.
- **Invariant 6 (Normalized Downtime Respect):** For every operation and every interval in $\mathcal{D}_m^{\text{merged}}$, $[S_a, C_a) \cap [D_s, D_e) = \emptyset$.
- **Invariant 7 (Horizon Bounds):** $0 \le S_{j,k} < C_{j,k} \le H$.
- **Invariant 8 (Metric Concordance):** Independently computed makespan ($C_{\max} = \max C_{j,k} - 0$), weighted tardiness, idle times, and net utilizations match solver and metric engine reported numbers with 0 delta.

Any schedule failing verification is quarantined with status `VERIFICATION_FAILED`.
