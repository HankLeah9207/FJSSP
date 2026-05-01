# Question 4: Joint Equipment Procurement and Two‑Crew Scheduling Model

## 1. Q4 Problem Interpretation

Question 4 extends the two‑crew multi‑workshop overhaul scheduling problem (Q3) by introducing a procurement decision. The enterprise may purchase additional equipment units from a five‑type catalog and assign each unit to either Crew 1 or Crew 2, subject to a hard budget of **$500 000**. The goal is to **jointly** determine the procurement plan and the detailed schedule of operations across all five workshops A–E, such that the makespan (completion time of all terminal processes) is minimized.

Because the purchase decision expands the equipment pool, Question 4 is a **strict generalization of Question 3**. All Q3 primitives are preserved:
- Both crews’ existing equipment pools remain available; they can be freely shared across workshops.
- A process that requires two equipment types may use units belonging to different crews (cross‑crew sharing).
- Asynchronous operation‑level start times are maintained: the two equipment‑type operations of the same process may start at different times.
- Early equipment release is enforced: each unit is released at its own operation‑end time, *not* at the process completion time.
- Workshop precedence is per operation: every operation of a successor process may start only after the entire predecessor process has finished.
- No preemption, no workload splitting, and no return‑to‑base after the final operation are assumed.

The Q4 optimum makespan is therefore at most the Q3 optimum (the Q3 schedule is feasible with zero procurement), so purchase can only improve or keep the makespan. The formulation integrates the procurement decision variables into the scheduling model, either via a single integrated CP‑SAT model or via a two‑stage enumeration strategy.

---

## 2. Raw Data Extracted from the Word Document and Excel Workbook

### 2.1 Process Flow Table (All Workshops)

Workshop orders are fixed chains. Workshop C expands to  
\(\mathrm{C1\to C2\to C3^{(1)}\to C4^{(1)}\to C5^{(1)}\to C3^{(2)}\to C4^{(2)}\to C5^{(2)}\to C3^{(3)}\to C4^{(3)}\to C5^{(3)}}\).

| Process | Name | Required Equipment (efficiency) | Workload |  
|---------|------|---------------------------------|----------|  
| A1 | Defect Filling | PFM 200 m³/h **AND** ACA 250 m³/h | 300 m³ |  
| A2 | Surface Leveling | HPM 100 m³/h **AND** ICM 250 m³/h | 500 m³ |  
| A3 | Strength Testing | ASM 100 m³/h | 500 m³ |  
| B1 | Surface Cleaning | ICM 100 m³/h | 120 m³ |  
| B2 | Base Layer Construction | PFM 200 m³/h **AND** ACA 300 m³/h | 1500 m³ |  
| B3 | Surface Sealing | PFM 350 m³/h | 360 m³ |  
| B4 | Surface Leveling | HPM 120 m³/h **AND** ASM 100 m³/h | 360 m³ |  
| C1 | Old Coating Removal | ICM 250 m³/h **AND** ACA 250 m³/h | 720 m³ |  
| C2 | Base Filling | PFM 350 m³/h | 720 m³ |  
| C3 (each round) | Sealing Coverage | PFM 200 m³/h **AND** ACA 250 m³/h | 360 m³ |  
| C4 (each round) | Surface Grinding | HPM 120 m³/h **AND** ICM 100 m³/h | 400 m³ |  
| C5 (each round) | Quality Inspection | ASM 100 m³/h | 400 m³ |  
| D1 | Debris Removal | ICM 250 m³/h | 600 m³ |  
| D2 | Base Solidification | PFM 200 m³/h **AND** ACA 300 m³/h | 800 m³ |  
| D3 | Surface Sealing | PFM 350 m³/h | 450 m³ |  
| D4 | Surface Leveling | HPM 120 m³/h **AND** ASM 300 m³/h | 1500 m³ |  
| D5 | Load‑bearing Inspection | ASM 300 m³/h | 1500 m³ |  
| D6 | Edge Trimming | HPM 100 m³/h | 700 m³ |  
| E1 | Foundation Treatment | ICM 250 m³/h | 1000 m³ |  
| E2 | Surface Sealing | PFM 350 m³/h | 600 m³ |  
| E3 | Stability Inspection | ASM 300 m³/h **AND** ICM 100 m³/h | 600 m³ |  

Processing time per operation \((j,t)\):  
\[
p_{j,t} = \left\lceil \frac{\text{workload}_j}{\text{efficiency}_{j,t}} \times 3600 \right\rceil \;\text{seconds}.
\]

### 2.2 Existing Two‑Crew Equipment Configuration (before procurement)

**Crew 1 (16 units):**  
ACA1‑1…ACA1‑4 (4), ICM1‑1…ICM1‑5 (5), PFM1‑1…PFM1‑5 (5), ASM1‑1 (1), HPM1‑1 (1)  
**Crew 2 (16 units):**  
ACA2‑1…ACA2‑4 (4), ICM2‑1…ICM2‑5 (5), PFM2‑1…PFM2‑5 (5), ASM2‑1 (1), HPM2‑1 (1)  

Speed for all equipment: \(v = 2\ \text{m/s}\).

### 2.3 Base‑to‑Workshop Distances

| \ (w) | A | B | C | D | E |
|-------|---|---|---|---|---|
| Crew 1 base | 400 m | 620 m | 460 m | 710 m | 400 m |
| Crew 2 base | 500 m | 460 m | 620 m | 680 m | 550 m |

### 2.4 Symmetric Inter‑Workshop Distances (m)

| \  | A    | B    | C    | D    | E    |
|----|------|------|------|------|------|
| A  | 0    | 1020 | 1050 | 900  | 1400 |
| B  | 1020 | 0    | 1100 | 1630 | 720  |
| C  | 1050 | 1100 | 0    | 520  | 850  |
| D  | 900  | 1630 | 520  | 0    | 1030 |
| E  | 1400 | 720  | 850  | 1030 | 0    |

Transport time \(\tau(w,w') = \text{distance}(w,w') / 2\) seconds; \(\tau(w,w)=0\).

### 2.5 Equipment Procurement Catalog and Budget

| Equipment Type (full name) | Unit Price (USD) |
|----------------------------|------------------|
| Automated Conveying Arm (ACA) | \$50 000 |
| Industrial Cleaning Machine (ICM) | \$40 000 |
| Precision Filling Machine (PFM) | \$35 000 |
| Automatic Sensing Multi‑Function Machine (ASM) | \$80 000 |
| High‑speed Polishing Machine (HPM) | \$75 000 |

Total procurement budget: **\$500 000** (hard constraint).

---

## 3. Data Inherited from Q3

The Q4 problem inherits the entire data environment of Q3:
- The two‑crew pool of 32 existing units described in §2.2.
- Uniform travel speed of 2 m/s for all units.
- Base‑to‑workshop distance tables specific to each crew.
- Symmetric inter‑workshop distance matrix (Table in §2.4).
- Workshop process chains, with Workshop C unrolled as a single sequence:
  \[
  \mathrm{C1}\to\mathrm{C2}\to\mathrm{C3}^{(1)}\to\mathrm{C4}^{(1)}\to\mathrm{C5}^{(1)}
  \to\mathrm{C3}^{(2)}\to\mathrm{C4}^{(2)}\to\mathrm{C5}^{(2)}
  \to\mathrm{C3}^{(3)}\to\mathrm{C4}^{(3)}\to\mathrm{C5}^{(3)} .
  \]
- All modeling innovations from Q2/Q3: asynchronous per‑operation start times, early equipment release, and per‑operation workshop precedence (see §13‑§18).

The Q4 formulation simply expands the equipment pool by adding purchased units; no new structural constraints are introduced.

---

## 4. Equipment Prices and Procurement Budget

| Equipment Type (abbreviation) | Unit Price (USD) |
|-------------------------------|------------------|
| ACA                           | 50 000 |
| ICM                           | 40 000 |
| PFM                           | 35 000 |
| ASM                           | 80 000 |
| HPM                           | 75 000 |

Total procurement budget: \(B = 500\,000\) (hard constraint, integer purchases only).

---

## 5. Sets and Indices

- **Workshops:** \(W = \{\mathrm{A, B, C, D, E}\}\).
- **Processes:** \(\mathcal{J}\) – all process instances in the five workshop chains, with Workshop C expanded as above. Terminal processes:  
  \(\mathcal{J}_{\text{term}} = \{\mathrm{A3, B4, C5^{(3)}, D6, E3}\}\).
- **Crews:** \(G = \{1, 2\}\).
- **Equipment types:** \(T = \{\mathrm{ACA, ICM, PFM, ASM, HPM}\}\).
- **Existing units:** For crew \(g\) and type \(t\), the set \(U_{g,t}^{\text{exist}}\) is as given in §2.2. Its size is \(c_{g,t}\), e.g. \(c_{1,\text{ACA}}=4\), \(c_{1,\text{ASM}}=1\), etc.
- **Candidate purchased units:** For each \(g\in G, t\in T\), let \(\mathcal{C}_{g,t}\) be a pre‑defined pool of candidate new units (size derived from budget, see §7). Each candidate \(k\in\mathcal{C}_{g,t}\) is pre‑labeled with crew \(g\) and type \(t\).
- **Effective unit pool:** After procurement decisions, the set of available units of type \(t\) is  
  \[
  U_t^{\text{eff}} = \bigcup_{g\in G}\Bigl(U_{g,t}^{\text{exist}} \cup \{\,k\in\mathcal{C}_{g,t}\mid z_k=1\,\}\Bigr).
  \]
- **Unit functions:** \(\tau(k)\in T\) – type of unit \(k\); \(\gamma(k)\in G\) – owning crew.
- **Process‑required types:** \(E_j\subseteq T\) – set of equipment types that process \(j\) demands (size 1 or 2).

---

## 6. Parameters

- **Processing times:** For every process \(j\) and required type \(t\in E_j\),  
  \[
  p_{j,t} = \Bigl\lceil \frac{\text{workload}_j}{\text{efficiency}_{j,t}} \times 3600 \Bigr\rceil \;\text{seconds}.
  \]
- **Inter‑workshop transport time:** \(\tau(w,w') = \frac{d(w,w')}{2}\) for \(w,w'\in W\), using the symmetric distance matrix from §2.4. \(\tau(w,w)=0\).
- **Crew‑specific initial transport time:** For crew \(g\) to workshop \(w\),  
  \[
  \tau_{\text{init}}(g,w) = \frac{\delta_g(w)}{2},
  \]  
  with \(\delta_g(w)\) given in §2.3.
- **Unit prices:** \(\text{price}_t\) as in §4.
- **Budget:** \(B = 500\,000\).
- **Existing unit counts:** \(c_{g,t}\) – number of existing units of type \(t\) in crew \(g\) (e.g. \(c_{1,\text{ACA}}=4\), \(c_{2,\text{ASM}}=1\), etc.).
- **Horizon bound:** A safe upper bound \(H\) for all time variables, e.g. the sum of all processing times plus maximum possible travel.

---

## 7. Procurement Decision Variables

Two equivalent representations are available.

### 7.1 Integer Counts
\[
y_{g,t} \in \mathbb{Z}_{\ge 0}, \qquad g\in G,\; t\in T,
\]
denotes the number of newly purchased units of type \(t\) assigned to crew \(g\).

### 7.2 Candidate‑unit Binaries
For each \((g,t)\), we pre‑define a finite candidate pool \(\mathcal{C}_{g,t}\) of size  
\[
M_{g,t} = \bigl\lfloor B / \text{price}_t \bigr\rfloor,
\]  
which gives the maximum possible purchases of that type for that crew. Thus  

| Type | \(\text{price}_t\) | \(M_{g,t}\) |
|------|-------------------|-------------|
| ACA  | 50 000            | 10          |
| ICM  | 40 000            | 12          |
| PFM  | 35 000            | 14          |
| ASM  | 80 000            | 6           |
| HPM  | 75 000            | 6           |

Every candidate \(k\in\mathcal{C}_{g,t}\) is assigned a binary variable  
\[
z_k \in \{0,1\},
\]  
with \(z_k=1\) meaning the unit is actually purchased. The two representations are linked by  
\[
y_{g,t} = \sum_{k \in \mathcal{C}_{g,t}} z_k.
\]

Candidates are indexed consecutively; the first new ACA for Crew 1 is candidate “ACA1‑5”, for Crew 2 “ACA2‑5”, etc. This naming convention directly determines the unit ID and the crew label.

---

## 8. Scheduling Decision Variables

All time variables are integer seconds in \([0, H]\).

- **Operation start times:** For each process \(j\) and each required type \(t\in E_j\),  
  \[
  s_{j,t} \in [0, H].
  \]
- **Operation end times (derived):**  
  \[
  e_{j,t} = s_{j,t} + p_{j,t}.
  \]
- **Process completion time:**  
  \[
  \mathit{PCT}_j = \max_{t\in E_j} e_{j,t}.
  \]
- **Assignment variables:** For every process \(j\), every required \(t\in E_j\), and every unit \(k\) in the effective pool \(U_t^{\text{eff}}\),  
  \[
  x_{j,t,k} \in \{0,1\}, \qquad \sum_{k\in U_t^{\text{eff}}} x_{j,t,k} = 1.
  \]
- **Unit routing arcs (CP‑SAT specific):** For each unit \(k\) of type \(t\), a circuit of nodes consisting of a SOURCE node (representing the crew base at time 0) and an array of activity nodes for every process \(j\) that requires type \(t\). Arcs between nodes are modelled with binary variables \(a_{i,j}^{(k)}\) (including a SOURCE→SINK self‑arc). The CP‑SAT `AddCircuit` constraint enforces a Hamiltonian path from SOURCE through the assigned operations to SINK, with a mandatory return arc SINK→SOURCE. Unassigned operations form self‑loops, and for a candidate unit with \(z_k=0\) the only feasible circuit is SOURCE→SINK→SOURCE plus self‑loops – effectively skipping the unit.
- **Makespan variable:**  
  \[
  C_{\max} \in [0, H].
  \]

---

## 9. Objective Function

**Primary objective:** Minimize the makespan \(C_{\max}\).  

**Secondary (lexicographic) tie‑break (optional):** Among schedules achieving the optimal \(C_{\max}\), minimize total procurement cost  
\[
\text{Cost} = \sum_{g\in G}\sum_{t\in T} \text{price}_t \cdot y_{g,t}.
\]  
This can be realized by a two‑phase solve (see §20).

---

## 10. Budget Constraint

\[
\sum_{g\in G}\sum_{t\in T} \text{price}_t \cdot y_{g,t} \le B = 500\,000.
\]

In terms of binary variables:  
\[
\sum_{k\in\bigcup_{g,t}\mathcal{C}_{g,t}} \text{price}_{t(k)}\; z_k \le 500\,000.
\]

---

## 11. Equipment‑Pool Expansion Constraints

For every candidate \(k\in\mathcal{C}_{g,t}\): if \(z_k = 0\) then the unit contributes **no** operation. This is enforced by  
\[
x_{j,t,k} \le z_k \qquad \forall j,\; t\in E_j,\; k\in\mathcal{C}_{g,t}.
\tag{1}
\]

For the CP‑SAT circuit model, when \(z_k=0\) all arc variables except the SOURCE→SINK self‑arc are forced to 0, ensuring the unit is inactive.

---

## 12. Assignment Constraints

For each operation **(j, t)**, exactly one unit from the effective pool of type \(t\) is chosen:

\[
\sum_{k\in U_{t}^{\text{eff}}} x_{j,t,k} = 1, \qquad \forall j \in \mathcal{J},\; t \in E_j.
\tag{2}
\]

Here \(U_t^{\text{eff}}\) includes all existing units of type \(t\) (both crews) plus all activated candidate units (\(\{k\in\mathcal{C}_{g,t}\mid z_k=1\}\)) from both crews. Cross‑crew sharing is allowed: the selected unit may belong to either crew.

---

## 13. Asynchronous Operation‑Start Constraints

No equality is imposed between start times of different equipment types within the same process. For a process \(j\) with \(E_j=\{t_1,t_2\}\), the variables \(s_{j,t_1}\) and \(s_{j,t_2}\) are independent; they are linked only through the process completion constraint (§14).

---

## 14. Process Completion Constraints

\[
\mathit{PCT}_j \ge e_{j,t} \qquad \forall j\in\mathcal{J},\; t\in E_j.
\tag{3}
\]

By modelling \(\mathit{PCT}_j\) as the maximum of the operation ends, condition (3) coupled with the objective (or makespan) enforces  
\[
\mathit{PCT}_j = \max_{t\in E_j} e_{j,t}.
\]

---

## 15. Early Equipment Release Constraints

A unit is released at its own operation end time \(e_{j,t}\), **not** at \(\mathit{PCT}_j\). This is naturally expressed in the unit sequencing constraints (§16) which use \(e_{j,t}\) as the moment the unit becomes available for travel.

---

## 16. Equipment Sequencing and Travel Constraints

For every unit \(k\) of type \(t\), consider any two operations \((i,t)\) and \((j,t)\) that are assigned to \(k\) and occur consecutively (i immediately before j). The temporal relation must be

\[
s_{j,t} \;\ge\; e_{i,t} + \tau\big(w(i),\,w(j)\big),
\tag{4}
\]

where \(w(i)\) is the workshop where process \(i\) takes place. This enforces both the travel gap (no overlap) and the early release (unit departs as soon as its own operation ends). For the first operation assigned to \(k\), a special initial travel constraint applies (see §17).

In the CP‑SAT circuit formulation, (4) is encoded as implications:

\[
a_{i,j}^{(k)} = 1 \;\Longrightarrow\; s_{j,t} \ge s_{i,t} + p_{i,t} + \tau(w_i,w_j),
\qquad
a_{\text{SOURCE},j}^{(k)} = 1 \;\Longrightarrow\; s_{j,t} \ge \tau_{\text{init}}(\gamma(k), w_j).
\]

---

## 17. Crew‑Specific Initial Travel Constraints for Existing AND New Equipment

Every unit starts at time 0 at its crew’s base. Therefore, for the very first operation \((j,t)\) assigned to unit \(k\) (regardless of whether it is existing or purchased), the following must hold:

\[
s_{j,t} \;\ge\; \tau_{\text{init}}\big(\gamma(k), w_j\big),
\tag{5}
\]

where \(\tau_{\text{init}}(g,w) = \delta_g(w)/2\) (distances from §2.3). For a purchased unit, the crew \(\gamma(k)\) is fixed by its candidate label, so (5) is applied identically. If the unit performs no operations (e.g., candidate with \(z_k=0\)), the constraint is vacuously satisfied.

---

## 18. Workshop Precedence Constraints

For every consecutive predecessor‑successor pair \((j_p, j_s)\) in the same workshop (including the expanded Workshop C chain), the following must hold for all equipment types required by the successor:

\[
s_{j_s,\,t} \;\ge\; \mathit{PCT}_{j_p}, \qquad \forall t \in E_{j_s}.
\tag{6}
\]

This “per‑operation precedence” is strictly stronger than a single process‑level start. It guarantees that no equipment operation of the successor begins before the entire predecessor process is complete.

---

## 19. Makespan Constraints

The makespan must be at least the completion time of every terminal process:

\[
C_{\max} \;\ge\; \mathit{PCT}_j \qquad \forall j \in \{\mathrm{A3, B4, C5^{(3)}, D6, E3}\}.
\tag{7}
\]

(The set of terminal processes is defined after Workshop C expansion.)

---

## 20. Optional Lexicographic Objective Explanation

We define a **lexicographic objective**: first minimize \(C_{\max}\), then, among all schedules achieving that optimal makespan, minimize total procurement cost \(\sum_{g,t}\text{price}_t\, y_{g,t}\).  

**Two‑phase CP‑SAT implementation:**  
1. Solve the full model with objective `minimize` \(C_{\max}\) to obtain optimal value \(C^*\).  
2. Add the constraint \(C_{\max} \le C^*\) (or \(C_{\max} = C^*\) if optimality is proved) and re‑solve with objective `minimize` \(\sum_{g,t}\text{price}_t\, y_{g,t}\).

This guarantees a certifyably optimal lexicographic pair. (An alternative weighted scalarization \(\min\, W\cdot C_{\max} + \text{cost}\) with \(W \ge 500\,001\) is also valid but less transparent.)

---

## 21. CP‑SAT Implementation Guidance

### 21.1 Model Building
- Use integer variables for \(s_{j,t}\) and \(C_{\max}\).
- Use Boolean variables for assignment \(x_{j,k}\) (where \(k\) is a unit index) and for procurement literals \(z_k\).
- For each unit \(k\) of type \(t\), construct a fixed node set: SOURCE node, a node for every process that requires \(t\), and a SINK node. Create arc Boolean variables for all possible transitions (including SOURCE→SINK and self‑loops on process nodes). Apply `AddCircuit` to enforce a Hamiltonian path from SOURCE through the assigned operations to SINK, with a return arc SINK→SOURCE.
- Enforce assignment constraints (2) via `exactly_one` or sums.
- Link assignment to circuit arcs: if \(x_{j,k}=1\) then the self‑loop on node \(j\) is 0, and the node must have exactly one incoming and outgoing arc (from the circuit). This can be done using `OnlyEnforceIf`.
- Guard all arcs involving a candidate unit with \(z_k\): if \(z_k=0\) then only the SOURCE→SINK arc and the mandatory return are active, and all other arcs are false.
- Post implications (4) and (5) using `OnlyEnforceIf` on the arc literals.
- Post budget constraint as a linear sum over \(z_k\) with prices as coefficients.
- Post makespan constraints (7) with `AddMaxEquality` or upper bounds.

### 21.2 Search Strategy
- Branch first on procurement decisions \(z_k\), prioritizing expensive types (ASM, HPM). Then branch on assignment \(x_{j,k}\). Then on arc variables and finally on start times.
- Use multiple search workers (e.g., 8 threads) to diversify.

### 21.3 Symmetry Breaking
- For each crew‑type pair \((g,t)\), the candidate purchased units of that type are indistinguishable. Enforce a canonical order:  
  \[
  z_{k_1} \ge z_{k_2} \ge \dots \ge z_{k_{M_{g,t}}},
  \]  
  so that only the first \(y_{g,t}\) candidates are activated.  
- For existing identical units within the same crew (e.g., ACA1‑1…ACA1‑4), they have fixed IDs, so permutation symmetry is limited; a similar ordering on usage (e.g., require that unit ACA1‑1 is used before ACA1‑2 if both are free) can be added but is not mandatory.

### 21.4 Warm‑start
Supply a feasible Q3 solution (zero procurement) as a hint to accelerate the search.

---

## 22. Two‑Stage Enumeration + CP‑SAT Solution Strategy

A practical alternative to the integrated CP‑SAT model is a hierarchical decomposition.

### 22.1 Stage 1 – Enumerate Procurement Plans
Enumerate all vectors \((y_{g,t})\) satisfying the budget. Through saturation analysis, buying extra ACA, ICM, or PFM units **cannot** improve the makespan because the existing numbers already exceed the maximum conceivable parallel demand:
- Max simultaneous need for ACA ≤ 5 (existing 8), ICM ≤ 5 (existing 10), PFM ≤ 5 (existing 10).
- ASM may need up to 5 simultaneous tasks; existing 2, so at most 3 additional ASM units are useful (\(\sum_g y_{g,\text{ASM}} \le 3\)).
- HPM may need up to 4 simultaneous tasks; existing 2, so at most 2 additional HPM units are useful (\(\sum_g y_{g,\text{HPM}} \le 2\)).

Therefore, the relevant plans only involve ASM and HPM purchases, with the above totals. The domain reduces to all integer pairs \((y_{1,\text{ASM}}, y_{2,\text{ASM}})\) summing ≤ 3 and \((y_{1,\text{HPM}}, y_{2,\text{HPM}})\) summing ≤ 2. The Cartesian product yields **60 distinct procurement plans**.

### 22.2 Stage 2 – Solve Q3‑style CP‑SAT for Each Plan
For each plan, expand the equipment pool accordingly (naming new units as per convention) and solve the scheduling problem **exactly as Q3** using the CP‑SAT model described in §§12–19, but with the enlarged unit set. Record the optimal makespan and the fixed procurement cost.

### 22.3 Stage 3 – Lexicographic Selection
Select the plan with the smallest makespan; in case of ties, choose the plan with the smallest procurement cost. Because the enumeration is exhaustive, this yields the certifiably optimal lexicographic pair under the Q3 scheduling assumptions.

The 60 subproblems are independent and can be solved in parallel; each instance is compact enough for a modern CP‑SAT solver to solve quickly, making the two‑stage approach highly practical.

---

## 23. Table 4 Output Format

Table 4 records the schedule at the operation level. Each row corresponds to **one (process, equipment type) pair**, so a process requiring two types yields two rows.

**Columns:**
1. **Number** – sequential row index starting from 1.
2. **Equipment ID** – unique identifier (e.g., `ACA1‑3`, `ICM2‑4` for existing; `ACA1‑5`, `ASM2‑2` for purchased).
3. **Start time (HH:MM:SS)** – displayed with two‑digit hours, minutes, seconds.
4. **End time (HH:MM:SS)** – displayed similarly.
5. **Duration (s)** – integer processing time \(p_{j,t}\).
6. **Process ID** – e.g., `A1`, `C3_2`, `D6` (with Workshop C round subscripts).
7. **Crew** – integer 1 or 2, reflecting the owning crew of the equipment unit.

After all rows, a terminal line is printed:  
`Shortest duration to complete the task of question 4: <C_max> (s)`

---

## 24. Table 5 Procurement Detail Format

Table 5 summarizes the purchases. It has five rows, one per equipment type, in the fixed order:

| Equipment Name | Number purchased by crew 1 | Number purchased by crew 2 | Total procurement Cost |
|----------------|----------------------------|----------------------------|-------------------------|
| Automated Conveying Arm | \(y_{1,\text{ACA}}\) | \(y_{2,\text{ACA}}\) | \(\text{price}_{\text{ACA}}\cdot (y_{1,\text{ACA}}+y_{2,\text{ACA}})\) |
| Industrial Cleaning Machine | … | … | … |
| Precision Filling Machine | … | … | … |
| Automatic Sensing Multi‑Function Machine | … | … | … |
| High‑speed Polishing Machine | … | … | … |

The sum of the **Total procurement Cost** column must not exceed \$500 000.

---

## 25. Validation Rules

To verify the correctness of the generated tables, any feasible solution must satisfy the following nine rules:

1. **One row per operation:** For every process \(j\) and every \(t\in E_j\), there is exactly one Table 4 row with process ID \(j\) and its Duration equal to \(p_{j,t}\).
2. **Asynchronous starts allowed:** No requirement that the two rows of the same process have equal Start times.
3. **Workshop precedence per row:** For every immediate predecessor‑successor pair, the start time of each successor operation row is ≥ \(\mathit{PCT}_{\text{pred}}\) (the maximum End time of the predecessor’s rows).
4. **\(\mathit{PCT}_j\) equals maximum of its rows’ End times:** Calculated from the table.
5. **Per‑equipment non‑overlap with transport gaps:** For consecutive operations of the same unit, End of earlier + \(\tau\)(workshop of earlier, workshop of later) ≤ Start of later. Transport time \(\tau\) uses the distance matrix ÷ 2.
6. **Initial transport from correct crew base:** For the first row of each unit (the earliest Start), Start ≥ \(\delta_g(\text{workshop})/2\) where \(g\) is the unit’s crew.
7. **Early‑release endpoint verification:** For every row, End = Start + Duration, and Duration equals the pre‑computed \(p_{j,t}\).
8. **Table 5 counts match purchased units in Table 4:** For each equipment type \(t\) and crew \(g\), the number of Table 4 rows with purchased IDs (suffix larger than existing maximum) and Crew column \(=g\) must equal the entry in Table 5.
9. **Budget constraint:** The sum of the Total procurement Cost column in Table 5 ≤ \$500 000.

These rules guarantee consistency between the mathematical model and the output tables, and ensure that the schedule respects all physical constraints.

---

## 26. Assumptions and Ambiguity Clarifications

- **Integer procurement:** Only whole units can be purchased; no fractional spending.
- **One‑time crew assignment:** Once a unit is purchased and assigned to a crew, its crew label is immutable and determines its initial base location.
- **Initial availability:** Purchased units start at their assigned crew’s base at time 0, just like existing units. No acquisition delay.
- **Workshop C workloads:** The given workloads are per round; the model treats each C3, C4, C5 instance as a separate process with the same workload.
- **Cross‑crew sharing permitted:** A process may use equipment from both crews simultaneously.
- **No preemption:** Every operation runs uninterruptedly from start to end.
- **No return‑to‑base:** After its final operation, a unit is free; no travel back to its base is required.
- **No workload splitting:** An operation is performed by exactly one unit of the required type.
- **Integer‑second durations and times:** All times are measured in integer seconds; rounding of processing times follows the ceiling rule.

---

## 27. Important Pitfalls to Avoid

- **Do NOT add a crew‑wide simultaneity cap.** Crew affiliation is only ownership and initial‑location information; there is no limit on how many units of a crew can operate at the same time.
- **Do NOT couple two equipment‑type operations of the same process via a shared process start variable.** Each operation must have its own start variable \(s_{j,t}\); forcing synchrony would violate the asynchronous‑start innovation and could lead to suboptimal schedules.
- **Derive upper bounds on \(y_{g,t}\) from the budget, not from guessing.** For example, each crew can buy at most \(\lfloor 500\,000 / \text{price}_t \rfloor\) units of type \(t\). Exceeding this would make candidate pools unnecessarily large and degrade solver performance.
- **Remember the first‑operation initial transport constraint for ALL units, including newly purchased ones.** This constraint is based on the owning crew’s base distances and applies from time 0; omitting it would allow units to appear instantly at any workshop.
- **Ensure that unactivated candidate units contribute nothing to the schedule.** In a CP‑SAT model, use activation literals to guard all assignments and arcs; a candidate with \(z_k=0\) must take a SOURCE→SINK skip arc and not hold any operation.
- **Do not force a process’s two operation rows to have the same End time;** the process completion is the maximum of the two, not the minimum or a forced equality.

By following the rigorous notation, constraints, and guidelines set out in this report, the resulting mathematical model (either integrated or two‑stage) faithfully captures the joint procurement‑scheduling problem of Question 4 and can be directly implemented in a CP‑SAT or MIP solver.