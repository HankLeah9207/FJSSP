# Mathematical Model for the Minimum-Time Overhaul Scheduling Using Crew 1 Equipment (Question 2)

**Abstract**  
This document presents a complete mathematical formulation for the cross‑workshop overhaul scheduling problem posed in Question 2 of the 2026‑MCM Problem B. Crew 1, with a fixed set of 16 mobile equipment units of five types, must execute all required processes in workshops A–E while respecting strict intra‑workshop sequences, simultaneous multi‑equipment requirements, and non‑negligible inter‑workshop transport times. The model is an **asynchronous operation‑level model**: when a process requires two different equipment types, the two equipment operations are independent variables that may start at different times, and the process is considered complete only when all its required equipment operations have finished. The model minimises the overall makespan by exploiting **early equipment release**, i.e., the fact that a unit is free for reuse immediately after its own operation completes, rather than waiting for the entire process to finish. We define all sets, parameters, variables, and constraints, and provide implementation guidance for both CP‑SAT and MIP solvers. The report also specifies the exact structure of the output Table 2 and lists all modelling assumptions.

## 1. Problem Interpretation for Question 2

Crew 1 possesses a pool of 16 equipment units comprising five different types. These units are the sole resources available to carry out all over‑haul processes prescribed for the five independent workshops A, B, C, D, and E. Each workshop defines a fixed linear sequence of processes; for Workshop C the subsequence C3→C4→C5 is repeated three times. Several processes demand the simultaneous use of two different equipment types, both of which must complete the full workload independently.

All equipment moves at a constant speed of 2 m s⁻¹. Transport time between workshops (and from the initial Crew 1 base) is significant and must be accounted for. Within the same workshop, movement between consecutive processes incurs no time penalty. The problem asks for the schedule that minimises the time at which the last process of every workshop is finished – the *makespan* – and for the corresponding equipment‑level work plan (Table 2).

This is a **multi‑workshop flexible job‑shop scheduling problem** with shared, mobile resources and sequence‑dependent setup (transport) times. We adopt an **asynchronous operation‑level model**: when a process requires two equipment types, each equipment operation has its own start variable and the two operations may begin at different times. The process is considered complete only after all its required equipment operations finish. The cardinal modelling innovation is the *early equipment release* principle (Section 8), which allows a fast machine to depart for another workshop immediately after it finishes its own operation, without waiting for a slower co‑worker. This distinction dramatically reduces idle time and is the key to achieving the minimum possible makespan.

## 2. Extracted Data Structure from the Attachment

All numerical data are reproduced below and converted to the formal parameters of the model. Processing times are computed as  
\[
p_{j,t} = \left\lceil \frac{\text{Workload}_j}{\text{Efficiency}_{j,t}} \times 3600 \right\rceil \;\text{seconds},
\]
and transport times are obtained as distance divided by speed (2 m s⁻¹).

### 2.1 Process Flows and Processing Times

**Workshop A** – sequence: A1 → A2 → A3

| Process | Name | Equipment (efficiency) | Workload (m³) | Proc. time (s) |
|---------|------|------------------------|---------------|----------------|
| A1 | Defect Filling | Precision Filling Machine (200 m³/h) <br> Automated Conveying Arm (250 m³/h) | 300 | 5400 <br> 4320 |
| A2 | Surface Leveling | High‑speed Polishing Machine (100 m³/h) <br> Industrial Cleaning Machine (250 m³/h) | 500 | 18000 <br> 7200 |
| A3 | Strength Testing | Automatic Sensing Multi‑Function Machine (100 m³/h) | 500 | 18000 |

**Workshop B** – sequence: B1 → B2 → B3 → B4

| Process | Name | Equipment (efficiency) | Workload (m³) | Proc. time (s) |
|---------|------|------------------------|---------------|----------------|
| B1 | Surface Cleaning | Industrial Cleaning Machine (100 m³/h) | 120 | 4320 |
| B2 | Base Layer Construction | Precision Filling Machine (200 m³/h) <br> Automated Conveying Arm (300 m³/h) | 1500 | 27000 <br> 18000 |
| B3 | Surface Sealing | Precision Filling Machine (350 m³/h) | 360 | 3703 |
| B4 | Surface Leveling | High‑speed Polishing Machine (120 m³/h) <br> Automatic Sensing Multi‑Function Machine (100 m³/h) | 360 | 10800 <br> 12960 |

**Workshop C** – sequence: C1 → C2 → (C3 → C4 → C5) × 3  
*Workload given per round for C3–C5.*

| Process | Name | Equipment (efficiency) | Workload (m³) | Proc. time (s) |
|---------|------|------------------------|---------------|----------------|
| C1 | Old Coating Removal | Industrial Cleaning Machine (250 m³/h) <br> Automated Conveying Arm (250 m³/h) | 720 | 10368 <br> 10368 |
| C2 | Base Filling | Precision Filling Machine (350 m³/h) | 720 | 7406 |
| C3 (×3) | Sealing Coverage | Precision Filling Machine (200 m³/h) <br> Automated Conveying Arm (250 m³/h) | 360 | 6480 <br> 5184 |
| C4 (×3) | Surface Grinding | High‑speed Polishing Machine (120 m³/h) <br> Industrial Cleaning Machine (100 m³/h) | 400 | 12000 <br> 14400 |
| C5 (×3) | Quality Inspection | Automatic Sensing Multi‑Function Machine (100 m³/h) | 400 | 14400 |

**Workshop D** – sequence: D1 → D2 → D3 → D4 → D5 → D6

| Process | Name | Equipment (efficiency) | Workload (m³) | Proc. time (s) |
|---------|------|------------------------|---------------|----------------|
| D1 | Debris Removal | Industrial Cleaning Machine (250 m³/h) | 600 | 8640 |
| D2 | Base Solidification | Precision Filling Machine (200 m³/h) <br> Automated Conveying Arm (300 m³/h) | 800 | 14400 <br> 9600 |
| D3 | Surface Sealing | Precision Filling Machine (350 m³/h) | 450 | 4629 |
| D4 | Surface Leveling | High‑speed Polishing Machine (120 m³/h) <br> Automatic Sensing Multi‑Function Machine (300 m³/h) | 1500 | 45000 <br> 18000 |
| D5 | Load‑bearing Inspection | Automatic Sensing Multi‑Function Machine (300 m³/h) | 1500 | 18000 |
| D6 | Edge Trimming | High‑speed Polishing Machine (100 m³/h) | 700 | 25200 |

**Workshop E** – sequence: E1 → E2 → E3

| Process | Name | Equipment (efficiency) | Workload (m³) | Proc. time (s) |
|---------|------|------------------------|---------------|----------------|
| E1 | Foundation Treatment | Industrial Cleaning Machine (250 m³/h) | 1000 | 14400 |
| E2 | Surface Sealing | Precision Filling Machine (350 m³/h) | 600 | 6172 |
| E3 | Stability Inspection | Automatic Sensing Multi‑Function Machine (300 m³/h) <br> Industrial Cleaning Machine (100 m³/h) | 600 | 7200 <br> 21600 |

### 2.2 Crew 1 Equipment Inventory

| Equipment Type | Unit IDs | Qty | Speed (m/s) |
|---------------|----------|-----|--------------|
| Automated Conveying Arm (ACA) | ACA1‑1 … ACA1‑4 | 4 | 2 |
| Industrial Cleaning Machine (ICM) | ICM1‑1 … ICM1‑5 | 5 | 2 |
| Precision Filling Machine (PFM) | PFM1‑1 … PFM1‑5 | 5 | 2 |
| Automatic Sensing Multi‑Function Machine (ASM) | ASM1‑1 | 1 | 2 |
| High‑speed Polishing Machine (HPM) | HPM1‑1 | 1 | 2 |

### 2.3 Distance and Transport Time Matrices

**Distances (m)**  

| Origin | A | B | C | D | E |
|--------|---|---|---|---|---|
| Crew 1 | 400 | 620 | 460 | 710 | 400 |
| A | 0 | 1020 | 1050 | 900 | 1400 |
| B | – | 0 | 1100 | 1630 | 720 |
| C | – | – | 0 | 520 | 850 |
| D | – | – | – | 0 | 1030 |
| E | – | – | – | – | 0 |

**Transport times (distance / 2 m s⁻¹, integer seconds)**

| From \ To | A | B | C | D | E |
|-----------|---|---|---|---|---|
| Crew 1 | 200 | 310 | 230 | 355 | 200 |
| A | 0 | 510 | 525 | 450 | 700 |
| B | 510 | 0 | 550 | 815 | 360 |
| C | 525 | 550 | 0 | 260 | 425 |
| D | 450 | 815 | 260 | 0 | 515 |
| E | 700 | 360 | 425 | 515 | 0 |

Within a workshop, transport time is zero by assumption.

## 3. Sets and Indices

* **Workshops**  
  \( W = \{A, B, C, D, E\} \).  
  Add the Crew 1 base as location index \( 0 \).

* **Processes**  
  For each workshop, processes are ordered; the repetition in Workshop C is expanded:
  \[
  \begin{aligned}
  J_A &= \{ A1, A2, A3 \}, \\
  J_B &= \{ B1, B2, B3, B4 \}, \\
  J_C &= \{ C1, C2, C3^{[1]}, C4^{[1]}, C5^{[1]}, C3^{[2]}, C4^{[2]}, C5^{[2]}, C3^{[3]}, C4^{[3]}, C5^{[3]} \}, \\
  J_D &= \{ D1, D2, D3, D4, D5, D6 \}, \\
  J_E &= \{ E1, E2, E3 \}.
  \end{aligned}
  \]
  \( J = \bigcup_{w} J_w \), \( |J| = 27 \).  
  For brevity we write e.g. \( C5_3 \) for the third round of C5.

  Additionally, define a dummy process \( 0_k \) for each equipment unit \( k \), with location \( w(0_k) = 0 \) (Crew 1 base), zero processing time, and assigned only to unit \( k \). The set of all dummy processes is \( D \). The full set of processes (including dummies) used for sequencing is \( J' = J \cup D \).

* **Precedence**  
  For each workshop \( w \), let \( \mathcal{P}_w \) be the ordered list of its real processes. If \( i \rightarrow j \) denotes an immediate successor, the precedence relation is \( i \prec j \). For Workshop C the chain is:  
  \( C1 \rightarrow C2 \rightarrow C3_1 \rightarrow C4_1 \rightarrow C5_1 \rightarrow C3_2 \rightarrow C4_2 \rightarrow C5_2 \rightarrow C3_3 \rightarrow C4_3 \rightarrow C5_3 \).

* **Equipment types**  
  \( T = \{\text{ACA, ICM, PFM, ASM, HPM}\} \).  
  Abbreviations: ACA – Automated Conveying Arm; ICM – Industrial Cleaning Machine; PFM – Precision Filling Machine; ASM – Automatic Sensing Multi‑Function Machine; HPM – High‑speed Polishing Machine.

* **Equipment units**  
  For each \( t \in T \), let \( K_t \) be the set of unit indices. The inventory yields:
  \[
  |K_{\text{ACA}}| = 4,\; |K_{\text{ICM}}| = 5,\; |K_{\text{PFM}}| = 5,\; |K_{\text{ASM}}| = 1,\; |K_{\text{HPM}}| = 1.
  \]
  The complete set of units is \( K = \bigcup_{t \in T} K_t \), with \( |K| = 16 \).  
  For a unit \( k \), let \( t(k) \in T \) denote its type.

* **Process‑to‑workshop mapping**  
  For any process \( j \in J \), its workshop is \( w(j) \in W \). For dummy processes, \( w(0_k) = 0 \).

* **Required equipment per process**  
  For each \( j \in J \), let \( E_j \subseteq T \) be the set of equipment types required. If \( |E_j| = 2 \), both types must be used.

## 4. Parameters

* **Processing times**  
  For each process \( j \) and required type \( t \in E_j \):
  \[
  p_{j,t} = \left\lceil \frac{W_j}{\eta_{j,t}} \times 3600 \right\rceil \quad \text{(integer seconds)},
  \]
  where \( W_j \) (m³) is the workload and \( \eta_{j,t} \) (m³/h) is the efficiency of equipment type \( t \) for that process. These values are tabulated in Section 2.

* **Transport times**  
  Between any two locations \( u,v \in \{0,A,B,C,D,E\} \):
  \[
  \tau_{u,v} = \frac{\text{dist}(u,v)}{2}\; \text{(seconds)}.
  \]
  The distances are given in Section 2.3, leading to the transport‑time matrix above.

* **Big‑M constant**  
  \( M \) is a sufficiently large integer, e.g. the sum of all processing times plus twice the maximum travel time; \( M = 500\,000 \) is safe.

## 5. Decision Variables

* **Operation start time** (asynchronous)  
  \( s_{j,t} \in \mathbb{Z}_{\ge 0} \) for each process \( j \in J \) and each required equipment type \( t \in E_j \). Each equipment operation has its own start variable; operations of the same process may begin at different times. The process completion time \( PCT_j \) (below) is the maximum over its operation completion times.

* **Process completion time**  
  \( PCT_j \in \mathbb{R}_{\ge 0} \) (or integer) for \( j \in J \). Defined by constraints to equal the maximum of the operation completion times of the required equipment.

* **Equipment assignment**  
  \( y_{j,t,k} \in \{0,1\} \) for each \( j \in J \), \( t \in E_j \), \( k \in K_t \). Equals 1 if unit \( k \) of type \( t \) is assigned to serve process \( j \) for the requirement of type \( t \).

* **Sequencing on a unit**  
  For each unit \( k \in K \), type \( t = t(k) \), and for every ordered pair of distinct processes \( i \neq j \) in \( J' \) that both require type \( t \) (with the convention that dummy processes also require the corresponding type), define
  \[
  z_{i,j,k} \in \{0,1\},
  \]
  where \( z_{i,j,k}=1 \) means process \( i \) is scheduled immediately before process \( j \) on unit \( k \) (or more precisely, \( i \) precedes \( j \) on that unit). The ordering will be enforced transitively by the constraints.

* **Makespan**  
  \( C_{\max} \ge 0 \), integer.

In the implementation we replace the per‑unit dummy nodes by a **path‑style direct‑successor arc model** (one source/sink pair per equipment unit) that more cleanly captures the initial transport from the Crew 1 base; see Section 9. Travel time is applied only to consecutive operations along the chosen path of each unit, not to non‑consecutive pairs.

## 6. Objective Function

\[
\min \; C_{\max}
\]
subject to the makespan definition (Section 7.i).

## 7. Constraints

### (a) Intra‑workshop process precedence

For every immediate successor pair \( i \rightarrow j \) within a workshop (including the repeated blocks of Workshop C), every operation of \( j \) must wait for the predecessor to complete:

\[
s_{j,t} \ge PCT_i \qquad \forall\, t \in E_j .
\]

Examples: \( s_{A2,\,\text{HPM}} \ge PCT_{A1} \) and \( s_{A2,\,\text{ICM}} \ge PCT_{A1} \) — the two operations of A2 may begin asynchronously but both must start after A1 is fully complete.

### (b) Equipment assignment

For each real process \( j \in J \) and each required type \( t \in E_j \):

\[
\sum_{k \in K_t} y_{j,t,k} = 1. \tag{1}
\]

Thus exactly one unit of type \( t \) is allocated to process \( j \). For types not required, \( y_{j,t,k}=0 \). For dummy processes, the assignment is fixed: \( y_{0_k, t(k), k} = 1 \).

### (c) Operation start and completion times

Every operation has its own start variable. When a unit \( k \) of type \( t \) is assigned to a real process \( j \) (\( y_{j,t,k}=1 \)), the operation occupies the interval
\[
[\,s_{j,t},\; s_{j,t} + p_{j,t}\,].
\]
The operation completion time is

\[
e_{j,t} = s_{j,t} + p_{j,t}.
\]

This is a linear expression in the decision variable \( s_{j,t} \); no auxiliary variable is required. The release time of the assigned unit on this operation equals \( e_{j,t} \).

### (d) Process completion as maximum of required equipment operations

For each real process \( j \) and each required type \( t \in E_j \):

\[
PCT_j \ge e_{j,t} = s_{j,t} + p_{j,t}. \tag{2}
\]

Because the objective minimises \( C_{\max} \) and, via the terminal constraints, forces \( PCT_j \) downward, at optimality
\[
PCT_j = \max_{t \in E_j} \; e_{j,t},
\]
i.e. the process finishes when the latest of its required equipment operations completes. Because \( s_{j,t} \) are independent decision variables, different operations of the same process may begin at different times.

### (e) Early equipment release

The release time of unit \( k \) from process \( j \) is defined as its own operation completion:

\[
R_{j,k} = e_{j,t} = s_{j,t} + p_{j,t} \qquad (\text{if } y_{j,t,k}=1).
\]

A unit becomes available for a new assignment at \( R_{j,k} = e_{j,t} \), **not** at \( PCT_j \). Because \( s_{j,t} \) is asynchronous with the start of any other operation of process \( j \), the unit's release time is decoupled from the slowest co‑worker. This principle is the cornerstone of the model and is implemented in the non‑overlap constraints (f).

### (f) Equipment non‑overlap with transport (early‑release disjunctive constraints)

For each unit \( k \in K \) of type \( t(k) \), consider the set \( J'_t \) of all processes (real and dummy) that require that type. For every ordered pair of distinct processes \( i \neq j \) in \( J'_t \) we have the binary sequencing variable \( z_{i,j,k} \). The following must hold:

**Linking assignment and ordering:**

\[
z_{i,j,k} \le y_{i,t,k}, \quad z_{i,j,k} \le y_{j,t,k} \tag{3}
\]
\[
z_{i,j,k} + z_{j,i,k} \ge y_{i,t,k} + y_{j,t,k} - 1, \qquad z_{i,j,k} + z_{j,i,k} \le 1. \tag{4}
\]

Thus if both \( i \) and \( j \) are assigned to the same unit \( k \), exactly one of the two precedence variables equals 1; otherwise both are 0.

**Temporal disjunctive constraints (big‑M):**

For each unit \( k \) of type \( t = t(k) \) and for all \( i \neq j \in J'_t \):

\[
s_{j,t} \ge e_{i,t} + \tau_{w(i),\, w(j)} \;-\; M\,\bigl(1 - z_{i,j,k}\bigr), \tag{5}
\]
\[
s_{i,t} \ge e_{j,t} + \tau_{w(j),\, w(i)} \;-\; M\,\bigl(1 - z_{j,i,k}\bigr), \tag{6}
\]

where \( e_{i,t} = s_{i,t} + p_{i,t} \). When \( z_{i,j,k}=1 \), (5) forces operation \( (j,t) \) to start no earlier than the release of unit \( k \) from operation \( (i,t) \) plus the travel time from workshop \( w(i) \) to workshop \( w(j) \). The use of \( e_{i,t} \) (the unit's own operation completion) instead of \( PCT_i \) embodies the early‑release mechanism.

In our preferred implementation (Section 9) the dummy‑process construct is replaced by a path‑style direct‑successor arc model with explicit SOURCE and SINK nodes per unit. The arc \( \text{SOURCE} \rightarrow (j,t) \) carries the timing constraint

\[
s_{j,t} \ge \tau_{0,\, w(j)},
\]

ensuring that the first real operation of unit \( k \) cannot start until the unit has travelled from the base. This avoids the big‑M weakness of dummy processes and prevents travel time from being applied to non‑consecutive operations on the same unit.

### (g) Inter‑workshop transportation

The transport time between workshops is directly embedded in the disjunctive constraints (5)–(6) via \( \tau_{w(i), w(j)} \). No separate constraints are needed.

### (h) Initial movement from Crew 1 base

The path‑style arc model (Section 9) places a SOURCE node per unit at the Crew 1 base. Whichever real operation \( (j,t) \) is chosen as the first node on unit \( k \) must satisfy \( s_{j,t} \ge \tau_{0,w(j)} \). If a unit is not used at all, the SOURCE node connects directly to SINK and no timing constraint is imposed.

### (i) Makespan definition

Let \( J_{\text{term}} = \{ A3,\; B4,\; C5_3,\; D6,\; E3 \} \) be the terminal processes of the five workshops. Then

\[
C_{\max} \ge PCT_j \qquad \forall\, j \in J_{\text{term}}. \tag{7}
\]

The objective minimises \( C_{\max} \), thereby completing the earliest possible overall finish.

## 8. Explanation of Why Early Release Is Valid and Useful for Question 2

The problem statement explicitly says: *“If a process requires two different types of equipment, both must independently complete the full workload. The process is complete only after both have finished.”* This rule governs **intra‑workshop precedence** (the next process in the same workshop cannot start until both are done). However, it does **not** forbid one of the machines from leaving the workshop earlier and starting a job in another workshop. The statement *“each piece of equipment can serve only one process at a time”* simply forbids overlapping operation intervals of the same unit; it does not force a fast machine to remain idle until the slower co‑worker finishes.

**Example: A2 → B1 transition of an Industrial Cleaning Machine**  
Process A2 requires both HPM (18000 s) and ICM (7200 s). Process B1 requires only ICM (4320 s), and transport A→B takes 510 s.  
- If the ICM were released only at the process completion time of A2 (18000 s), it could start B1 at earliest 18000+510 s, finishing B1 at 22830 s.  
- With early release, the ICM finishes A2 at 7200 s, travels to B (510 s), and can start B1 at 7710 s, finishing at 12030 s – a saving of **10800 s (3 hours)**. If B’s chain is on the critical path, the overall makespan shrinks by the same amount.

The early‑release principle therefore decouples the individual units’ availability from the process‑level completion, allowing the scarce bottleneck machines (especially the single‑unit HPM and ASM) to be routed efficiently while their faster partners serve other workshops concurrently. This is the single most important modelling feature for achieving the minimum makespan in the multi‑workshop scenario of Question 2.

## 9. CP‑SAT‑Oriented Implementation Notes

The model is designed to be directly implementable in both CP‑SAT and MIP solvers. Below we sketch an implementation strategy using Google OR‑Tools CP‑SAT, which often excels for scheduling problems of this size.

**Key elements (asynchronous operation‑level model):**

1. **Operation start variables** – For every process \( j \) and every required type \( t \in E_j \), create an integer variable `op_start[j,t]` with domain \( [0, \text{horizon}] \). The corresponding operation end is the linear expression `op_start[j,t] + p_{j,t}` — no extra variable is needed. Different operations of the same process are independent.

2. **Assignment literals**  
   For each process \( j \), required type \( t \), and unit \( k \in K_t \), create a Boolean literal `assign[j,t,k]`. Enforce `model.Add(sum(assign[j,t,k] for k in K_t) == 1)` for every required `(j,t)`.

3. **Process completion and intra‑workshop precedence**  
   For each process \( j \), define `PCT_j` and enforce `model.AddMaxEquality(PCT_j, [op_start[j,t] + p_{j,t} for t in E_j])`. For each precedence pair \( i \rightarrow j \) and every \( t \in E_j \), add `model.Add(op_start[j,t] >= PCT_i)`. Note: every operation of the successor must wait for the predecessor's *full* completion; only the within‑process equipment operations are asynchronous.

4. **Path‑style direct‑successor arc model per equipment unit (preferred)**  
   For each unit \( k \) of type \( t \), build a directed graph whose nodes are SOURCE, the candidate operations \( \{(j,t) : t \in E_j\} \), and SINK. Use CP‑SAT's `AddCircuit` constraint with the following arcs (each carrying a Boolean literal):
   - `SOURCE → (j,t)` for every candidate; `OnlyEnforceIf` imposes `op_start[j,t] >= τ(BASE, w(j))`. The arc literal also implies `assign[j,t,k]`.
   - `(i,t) → (j,t)` for every ordered pair of distinct candidates; the literal implies both `assign[i,t,k]` and `assign[j,t,k]`, and `OnlyEnforceIf` imposes `op_start[j,t] >= op_start[i,t] + p_{i,t} + τ(w(i), w(j))`. This is the early‑release transport rule applied to *consecutive* operations on the same unit only.
   - `(j,t) → SINK` for every candidate; the literal implies `assign[j,t,k]`. No timing constraint.
   - `SOURCE → SINK` (unit unused). The literal implies `Not(assign[j,t,k])` for every candidate.
   - **Self‑loop** `(j,t) → (j,t)` whose literal equals `Not(assign[j,t,k])`. Self‑loops let `AddCircuit` skip candidates that are not assigned to this unit.

   `model.AddCircuit(arcs)` then enforces flow conservation (every assigned candidate has exactly one in‑arc and one out‑arc among the chosen arcs, while unassigned candidates use their self‑loop). Travel time is therefore applied only to the directly chosen successor of each operation, never to non‑consecutive pairs — which is the correct early‑release rule.

5. **Makespan**  
   Create `C_max`, add `model.Add(C_max >= PCT_j)` for every terminal process, and set `model.Minimize(C_max)`.

**MIP alternative:**  
The same operation‑level variables \( s_{j,t} \) and big‑M constraints (3)–(6) can be given to a MIP solver. The model contains approximately 138 assignment binaries, about 1200 sequencing binaries, and a few thousand constraints – well within the capacity of commercial solvers. The LP relaxation may be weak due to the big‑M values; supplying a strong lower bound (the machine‑based bound of ~136 450 s for the HPM) can help. Without `AddCircuit` support, the MIP must either include all pairwise big‑M disjunctions or use a single‑commodity flow encoding to avoid applying transport time to non‑consecutive operations.

**Trade‑offs:**  
- CP‑SAT’s native interval reasoning often prunes the search space more effectively.  
- MIP solvers can exploit cutting planes and are easier to tune for absolute optimality gaps.  
- Both approaches are viable; the formulation presented here is solver‑independent.

## 10. Table 2 Output Requirements

Table 2 presents the optimal schedule at the equipment operation level. Its format and validation rules ensure the schedule is executable and respects all constraints.

### 10.1 Columns

| Column | Description |
|--------|-------------|
| **Equipment ID** | Unique identifier of the unit (e.g., `Automated Conveying Arm1‑3`). |
| **Start Time** (HH:MM:SS) | Wall‑clock time when the unit **begins processing** its assigned operation on a process. |
| **End Time** (HH:MM:SS) | Wall‑clock time when the unit **finishes** that operation (i.e., its release time). |
| **Continuous Operation Duration (s)** | The processing time \( p_{j,t} \) (a constant, integer). |
| **Corresponding Process ID** | The label of the process (e.g., `A1`, `C3‑2`). For Workshop C rounds, append the round number (e.g., `C3‑1`). |

- For processes requiring two equipment types, two separate rows appear (one per unit). In the asynchronous operation‑level model these rows **may have different Start Times** and different End Times; the process completion time is the maximum of their End Times.
- Transport times are **not** shown as separate rows; they appear as idle gaps between consecutive rows of the same unit.

### 10.2 Interpretation of gaps

For a given equipment unit, the gap between its previous End Time \( t^e_{\text{prev}} \) and its next Start Time \( t^s_{\text{next}} \) must satisfy
\[
t^s_{\text{next}} - t^e_{\text{prev}} \ge \tau_{w_{\text{prev}},\, w_{\text{next}}},
\]
where \( w_{\text{prev}} \) and \( w_{\text{next}} \) are the workshops of the two jobs. For the very first row of a unit, the gap from 00:00:00 to the first Start Time must be at least \( \tau_{0, w_{\text{first}}} \).

### 10.3 Validation rules

A complete Table 2 can be cross‑checked against the model constraints by verifying:

1. **Compatibility** – Each equipment ID belongs to a type required by the process.
2. **Unique assignment (asynchronous starts allowed)** – For each process instance, exactly one unit of each required type appears. Rows belonging to the same Process ID **may have different Start Times**; this is intended in the asynchronous operation‑level model.
3. **Intra‑workshop precedence** – Let \( PCT_P = \max\{ \text{End Time of rows for process } P\} \). For consecutive processes \( P \rightarrow Q \), **every row** of \( Q \) must satisfy \( \text{Start Time} \ge PCT_P \).
4. **Unit non‑overlap** – For each unit, sort its rows by Start Time; ensure End Time₍ᵢ₎ ≤ Start Time₍ᵢ₊₁₎.
5. **Transport gaps with early release** – For consecutive rows of the same unit, the difference must be at least the transport time between the corresponding workshops (or from base for the first row). The release endpoint is the row's End Time, **not** the process completion time.
6. **Coverage** – All process instances (A1,…,C5‑3,…) are listed exactly as required, with the correct number of units.

If all checks pass, the table represents a feasible schedule.

## 11. Assumptions and Possible Ambiguities

The following assumptions underpin the model and are consistent with the problem statement:

1. **Initial position** – At \( t = 00:00:00 \) all equipment units are at the Crew 1 base. The first operation may only begin after travel from the base.
2. **Workshop C workload** – The workload given for C3, C4, C5 is **per round**, as indicated by the column header. The three rounds each require the full amount.
3. **Asynchronous starts (workshop and within‑process)** – Different workshops have no global start synchronisation; additionally, the two equipment operations of a single process may begin at different times. Synchronisation across operations of the same process is **not** required.
4. **Non‑preemption** – Once an equipment unit begins an operation, it works continuously until the operation is finished. No splitting of workloads.
5. **One unit per required type, indivisible workload** – A process that needs a given equipment type is served by exactly one unit of that type, and that unit must complete the entire workload. Multiple identical units cannot collaborate on the same process. When a process requires two different types, the two equipment operations are independent and may start asynchronously (see assumption 3).
6. **Equipment type coverage** – Crew 1 possesses all types required by the five workshops; the type‑to‑process mapping is covered.
7. **Early equipment release** – As argued in Section 8, this is a valid interpretation; no problem rule forbids a unit from leaving a workshop before its co‑worker finishes.
8. **Transport model** – Equipment moves independently at constant speed 2 m s⁻¹; no congestion, no loading/calibration delays beyond the transport time; intra‑workshop relocation is instantaneous.
9. **Identical units** – All units of the same type are completely interchangeable; their efficiencies and speeds are identical.
10. **No return to base required** – Equipment may finish anywhere; there is no need to bring it back to the base.
11. **Precise rounding** – Processing times are ceiling‑rounded to integer seconds (as specified), and the same precision applies to start/end times.

Potential ambiguities that should be confirmed:
- Whether equipment may be pre‑positioned at a workshop before its assigned job without an explicit task. The model allows this implicitly (a unit could travel and start later), but the optimal schedule will likely move units only when a job is assigned.
- The interpretation of “continuous operation duration” in Table 2: it is clearly the processing time \( p_{j,k} \), not the whole process duration.

The formulation above is self‑consistent, respects all explicit requirements, and is ready for implementation and solution.