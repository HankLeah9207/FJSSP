## 1. Problem Interpretation for Question 3

Question 3 extends the single‑crew overhaul scheduling problem (Question 2) to the **joint use of both Crew 1 and Crew 2 equipment pools**. The overarching task is unchanged: complete all overhaul processes in the five workshops A, B, C, D, E in the shortest possible time. However, we now have **32 individually identifiable equipment units** – the 16 units of Crew 1 and the 16 units of Crew 2 – that may be assigned to any process, regardless of crew affiliation.  

The two crews start from different physical bases, so the **initial travel time** of each unit depends on which crew it belongs to. Once a unit reaches its first workshop, all subsequent inter‑workshop travel uses the same symmetric distance matrix, independent of crew.  

Critically, the problem permits **cross‑crew sharing within a single process**: for a two‑equipment‑type process, one unit may come from Crew 1 and the other from Crew 2. This pooling is made possible because the two fundamental innovations of the Q2 model are preserved:  

* **Asynchronous operation‑level start times** – the two equipment operations required by a process may begin at different instants.  
* **Early equipment release** – each unit becomes free immediately after it finishes its own operation, not when the slowest co‑worker in the same process completes.  

The objective is to find assignments and start times for all operations such that the makespan \(C_{\max}\) (the moment the last terminal process finishes) is minimised. The final output must be presented in **Table 3**, detailing for every equipment–operation pair the start time, end time, continuous operation duration, process ID, and crew.

---

## 2. Extracted Data Structure from the Attachment

All data are taken directly from the problem description. Processing times are computed from the given workload and efficiency using the ceiling rule defined in the problem statement.

### 2.1 Workshop Processes and Processing Times

Workshop C contains a three‑round repetition of C3→C4→C5; this is expanded into eleven distinct processes: C1, C2, C3_1, C4_1, C5_1, C3_2, C4_2, C5_2, C3_3, C4_3, C5_3. For every process \(j\) and required equipment type \(t\in E_j\), the processing time \(p_{j,t}\) (in integer seconds) is

\[
p_{j,t} = \left\lceil \frac{\text{workload}_j}{\text{efficiency}_{j,t}} \times 3600 \right\rceil.
\]

Table 2.1 summarises the processes, their required equipment sets, and the computed processing times.

**Table 2.1 – Process data and processing times (seconds)**  

| Process | Workshop | Required types (\(E_j\)) | \(p_{j,\text{ACA}}\) | \(p_{j,\text{ICM}}\) | \(p_{j,\text{PFM}}\) | \(p_{j,\text{ASM}}\) | \(p_{j,\text{HPM}}\) |
|---------|----------|--------------------------|----------------------|----------------------|----------------------|----------------------|----------------------|
| A1      | A        | PFM, ACA                 | 4320                 | –                    | 5400                 | –                    | –                    |
| A2      | A        | HPM, ICM                 | –                    | 7200                 | –                    | –                    | 18000                |
| A3      | A        | ASM                      | –                    | –                    | –                    | 18000                | –                    |
| B1      | B        | ICM                      | –                    | 4320                 | –                    | –                    | –                    |
| B2      | B        | PFM, ACA                 | 18000                | –                    | 27000                | –                    | –                    |
| B3      | B        | PFM                      | –                    | –                    | 3703                 | –                    | –                    |
| B4      | B        | HPM, ASM                 | –                    | –                    | –                    | 12960                | 10800                |
| C1      | C        | ICM, ACA                 | 10368                | 10368                | –                    | –                    | –                    |
| C2      | C        | PFM                      | –                    | –                    | 7406                 | –                    | –                    |
| C3\_r   | C        | PFM, ACA                 | 5184                 | –                    | 6480                 | –                    | –                    |
| C4\_r   | C        | HPM, ICM                 | –                    | 14400                | –                    | –                    | 12000                |
| C5\_r   | C        | ASM                      | –                    | –                    | –                    | 14400                | –                    |
| D1      | D        | ICM                      | –                    | 8640                 | –                    | –                    | –                    |
| D2      | D        | PFM, ACA                 | 9600                 | –                    | 14400                | –                    | –                    |
| D3      | D        | PFM                      | –                    | –                    | 4629                 | –                    | –                    |
| D4      | D        | HPM, ASM                 | –                    | –                    | –                    | 18000                | 45000                |
| D5      | D        | ASM                      | –                    | –                    | –                    | 18000                | –                    |
| D6      | D        | HPM                      | –                    | –                    | –                    | –                    | 25200                |
| E1      | E        | ICM                      | –                    | 14400                | –                    | –                    | –                    |
| E2      | E        | PFM                      | –                    | –                    | 6172                 | –                    | –                    |
| E3      | E        | ASM, ICM                 | –                    | 21600                | –                    | 7200                 | –                    |

*Note:* C3_r, C4_r, C5_r for \(r=1,2,3\) have identical processing times.

### 2.2 Equipment Inventory (Both Crews, 32 Units)

**Table 2.2 – Combined equipment pool**

| Equipment Type (abbr.) | Crew 1 Units (IDs)             | Crew 2 Units (IDs)             | Total |
|------------------------|--------------------------------|--------------------------------|-------|
| Automated Conveying Arm (ACA)   | ACA1‑1 … ACA1‑4   | ACA2‑1 … ACA2‑4   | **8** |
| Industrial Cleaning Machine (ICM) | ICM1‑1 … ICM1‑5 | ICM2‑1 … ICM2‑5 | **10**|
| Precision Filling Machine (PFM) | PFM1‑1 … PFM1‑5 | PFM2‑1 … PFM2‑5 | **10**|
| Automatic Sensing Multi‑Function Machine (ASM) | ASM1‑1 | ASM2‑1 | **2** |
| High‑speed Polishing Machine (HPM) | HPM1‑1 | HPM2‑1 | **2** |
| **Total**                | **16**                         | **16**                         | **32** |

Travel speed for all units: \(v = 2\ \text{m/s}\).

### 2.3 Initial Crew‑Base Distances and Travel Times

**Table 2.3 – Crew‑specific base‑to‑workshop distances and travel times**

| Workshop | \(\delta_1\) (Crew 1, m) | Initial time (Crew 1, s) | \(\delta_2\) (Crew 2, m) | Initial time (Crew 2, s) |
|----------|---------------------------|---------------------------|---------------------------|---------------------------|
| A        | 400                       | 200                       | 500                       | 250                       |
| B        | 620                       | 310                       | 460                       | 230                       |
| C        | 460                       | 230                       | 620                       | 310                       |
| D        | 710                       | 355                       | 680                       | 340                       |
| E        | 400                       | 200                       | 550                       | 275                       |

### 2.4 Inter‑Workshop Distances and Travel Times

All distances are symmetric; travel time = distance / 2 m/s, integer seconds.

**Table 2.4 – Inter‑workshop distances (m) and travel times (s)**

| \(d\) / \(\tau\) | A       | B       | C       | D       | E       |
|------------------|---------|---------|---------|---------|---------|
| A                | 0 / 0   | 1020 / 510 | 1050 / 525 | 900 / 450 | 1400 / 700 |
| B                | 1020 / 510 | 0 / 0   | 1100 / 550 | 1630 / 815 | 720 / 360  |
| C                | 1050 / 525 | 1100 / 550 | 0 / 0   | 520 / 260  | 850 / 425  |
| D                | 900 / 450  | 1630 / 815 | 520 / 260  | 0 / 0      | 1030 / 515 |
| E                | 1400 / 700 | 720 / 360  | 850 / 425  | 1030 / 515 | 0 / 0      |

---

## 3. Sets and Indices

**Workshops**  
\[
\mathcal{W} = \{A, B, C, D, E\}.
\]

**Processes** (expanded)  
Workshop C is expanded into 11 distinct processes. The ordered list of all 27 processes is  

\[
\begin{aligned}
\mathcal{J} = \{&A1, A2, A3,\\
               &B1, B2, B3, B4,\\
               &C1, C2, C3\_1, C4\_1, C5\_1, C3\_2, C4\_2, C5\_2, C3\_3, C4\_3, C5\_3,\\
               &D1, D2, D3, D4, D5, D6,\\
               &E1, E2, E3\}.
\end{aligned}
\]

For each \(j\in\mathcal{J}\), \(w(j)\in\mathcal{W}\) returns its workshop, and \(E_j \subseteq \mathcal{T}\) (defined below) is the set of required equipment types.

**Crews**  
\[
\mathcal{G} = \{1,2\}.
\]

**Equipment types**  
\[
\mathcal{T} = \{\text{ACA}, \text{ICM}, \text{PFM}, \text{ASM}, \text{HPM}\}.
\]

**Equipment units**  
The combined pool \(\mathcal{U}\) contains 32 individually indexed units, partitioned by crew \(\mathcal{U} = \mathcal{U}_1 \cup \mathcal{U}_2\) and by type \(\mathcal{U} = \bigcup_{t\in\mathcal{T}} \mathcal{U}_t\).  
For a unit \(k\in\mathcal{U}\), \(g(k)\in\mathcal{G}\) gives its crew affiliation, and \(\tau(k)\in\mathcal{T}\) its equipment type.  

**Operations**  
An operation is a pair \((j,t)\) with \(j\in\mathcal{J}\) and \(t\in E_j\). Let \(\mathcal{O}\) be the set of all operations.

---

## 4. Parameters

### 4.1 Processing Times  
\(p_{j,t}\in\mathbb{Z}_{>0}\) (seconds) defined in Table 2.1 for all \((j,t)\in\mathcal{O}\).

### 4.2 Transport Times  

**Crew‑specific initial travel**  
Each unit \(k\) starts at its crew’s base. The travel time from the base to the workshop \(w\) of its first assigned process is  

\[
\tau^{\text{init}}(k,w) = \frac{\delta_{g(k)}(w)}{2} \quad (\text{seconds}).
\]

The values are given in Table 2.3.

**Inter‑workshop travel**  
After the initial move, travel between any two workshops uses the symmetric matrix:

\[
\tau(w,w') = \frac{d(w,w')}{2}, \qquad \tau(w,w)=0,
\]

with the values listed in Table 2.4.

### 4.3 Equipment Counts  

\[
|\mathcal{U}_{\text{ACA}}|=8,\; |\mathcal{U}_{\text{ICM}}|=10,\; |\mathcal{U}_{\text{PFM}}|=10,\; |\mathcal{U}_{\text{ASM}}|=2,\; |\mathcal{U}_{\text{HPM}}|=2.
\]

### 4.4 Horizon  
A conservative upper bound for all start times: \(H = 500\,000\) s, sufficient to cover all processing plus maximum travel.

---

## 5. Decision Variables

### 5.1 Operation Start and End Times  

For every operation \((j,t)\in\mathcal{O}\),  
\[
s_{j,t} \in [0, H]\cap\mathbb{Z},\qquad 
e_{j,t} = s_{j,t} + p_{j,t}.
\]
\(s_{j,t}\) is the start time; \(e_{j,t}\) is the operation completion time.

### 5.2 Process Completion Time  

For each process \(j\in\mathcal{J}\),  
\[
PCT_j \in [0, H]\cap\mathbb{Z},
\]
defined so that \(PCT_j = \max_{t\in E_j} e_{j,t}\). In CP‑SAT this is enforced by an `AddMaxEquality` constraint; in MIP by inequalities.

### 5.3 Equipment Assignment  

For every operation \((j,t)\in\mathcal{O}\) and every unit \(k\in\mathcal{U}_t\),  
\[
x_{j,t,k} \in \{0,1\},
\]
with \(x_{j,t,k}=1\) iff unit \(k\) is assigned to perform operation \((j,t)\). The convexity constraint \(\sum_{k\in\mathcal{U}_t} x_{j,t,k}=1\) is imposed.

### 5.4 Equipment Sequencing (Path Arc Literals for CP‑SAT or Disjunctive Variables for MIP)

**CP‑SAT version**  
For each unit \(k\), a directed acyclic circuit model (Angle 7) uses Boolean arc literals:

* \(y_{\texttt{SRC}\to(j,t)}\) – first operation of \(k\) is \((j,t)\).
* \(y_{(i,t)\to(j,t)}\) – \(k\) moves directly from operation \(i\) to \(j\).
* \(y_{(j,t)\to\texttt{SIK}}\) – final operation of \(k\).
* \(y_{\texttt{SRC}\to\texttt{SIK}}\) – \(k\) is idle.
* \(b_{\text{self},(j,t)}\) – self‑loop on operation \((j,t)\) (meaning \(k\) does **not** serve it).

These are linked to the assignment by \(b_{\text{self}} = 1 - x_{j,t,k}\).

**MIP version**  
For each unit \(k\) of type \(t\) and each ordered pair of distinct operations \(i,j\in\mathcal{O}_t\) (where \(\mathcal{O}_t\) is the set of operations requiring type \(t\)), binary sequencing variables \(y_{i,j,k}\in\{0,1\}\) indicate that \(i\) immediately precedes \(j\) on unit \(k\). Additionally, depot arcs \(y_{D_k,j,k}\) specify the first operation. Constraints (2)–(6) in Angle 8 enforce a single ordered chain.

### 5.5 Makespan  

\[
C_{\max} \in [0, H]\cap\mathbb{Z},
\]
constrained by \(C_{\max} \ge PCT_j\) for all terminal processes (A3, B4, C5_3, D6, E3).

---

## 6. Objective Function

Minimise the overall project completion time:

\[
\min \ C_{\max}.
\]

---

## 7. Constraints

### 7.1 Intra‑Workshop Precedence (Per‑Operation)

For every consecutive pair of processes \((pred, succ)\) within the same workshop and for every equipment type \(t\in E_{succ}\),

\[
s_{succ,\,t} \;\ge\; PCT_{pred}. \tag{P}
\]

This ensures that no operation of a successor process may start before the entire predecessor process is finished. For Workshop C, the chain is

C1 → C2 → C3_1 → C4_1 → C5_1 → C3_2 → C4_2 → C5_2 → C3_3 → C4_3 → C5_3.

### 7.2 Equipment Assignment (Convexity)

Every operation must receive exactly one unit of the required type, chosen from the combined two‑crew pool:

\[
\sum_{k\in\mathcal{U}_t} x_{j,t,k} = 1 \qquad \forall (j,t)\in\mathcal{O}. \tag{A}
\]

No crew‑coherence restriction is imposed; the two units of a two‑equipment process may belong to different crews.

### 7.3 Operation Timing

The operation end time is defined by its start time plus the constant processing time:

\[
e_{j,t} = s_{j,t} + p_{j,t} \qquad \forall (j,t)\in\mathcal{O}. \tag{T}
\]

### 7.4 Process Completion (Asynchronous)

A process is complete when the last of its required operations finishes:

\[
PCT_j = \max_{t\in E_j} e_{j,t} \qquad \forall j\in\mathcal{J}. \tag{M}
\]

This is implemented as \(PCT_j \ge e_{j,t}\) for all \(t\in E_j\) together with the objective simplification; in CP‑SAT it is an `AddMaxEquality` constraint.

### 7.5 Early Equipment Release

Each unit is released at its own operation end time, not at the process completion time. Consequently, for any two distinct operations \(i,j\) of the same equipment type that are performed successively on the same unit \(k\), the start of the successor must wait only for the unit’s own completion plus travel:

\[
s_{j,t} \;\ge\; e_{i,t} + \tau\bigl(w(i),\, w(j)\bigr) \quad \text{if unit }k\text{ performs both }i\text{ and }j. \tag{E}
\]

In the path‑based circuit or disjunctive formulations, this is enforced by the sequencing constraints that refer to \(e_{i,t}\) rather than \(PCT_i\). No delay caused by a slower co‑worker is inherited.

### 7.6 Equipment Non‑Overlap with Travel (Crew‑Aware)

For each unit \(k\) of type \(t\), the sequence of operations assigned to it must be feasible with respect to travel times and non‑overlap.

**CP‑SAT version (using circuit arcs):**  
* If \(y_{\texttt{SRC}\to(j,t)} = 1\) then \(s_{j,t} \ge \tau^{\text{init}}(k, w(j))\).  
* If \(y_{(i,t)\to(j,t)} = 1\) then \(s_{j,t} \ge e_{i,t} + \tau(w(i), w(j))\).

These inequalities are guarded by `OnlyEnforceIf(literal)`. The circuit constraint `AddCircuit` ensures that each unit follows a single path from source to sink.

**MIP version (using disjunctive variables):**  
For unit \(k\) of type \(t\),  

\[
\begin{aligned}
s_{j,t} &\ge e_{i,t} + \tau\bigl(w(i),w(j)\bigr) - M\,(1 - y_{i,j,k} - x_{i,t,k} - x_{j,t,k}), \\
s_{j,t} &\ge \tau^{\text{init}}(k, w(j)) - M\,(1 - y_{D_k,j,k}),
\end{aligned}
\]

with adequate big‑\(M\) constants. (See Angle 8 for the full linear ordering constraints.)

### 7.7 Crew‑Specific Initial Transport

The very first operation of each unit \(k\) (if any) must respect the travel time from its crew base. This is embedded in the source‑to‑operation arc constraints above. In the MIP formulation, the depot arcs use the appropriate \(\tau^{\text{init}}(k,\cdot)\) from Table 2.3. In CP‑SAT, the initial‑travel guard is attached to \(y_{\texttt{SRC}\to(j,t)}\).

### 7.8 Makespan  

\[
C_{\max} \;\ge\; PCT_j \qquad \forall \text{ terminal process } j\in\{A3,B4,C5\_3,D6,E3\}. \tag{MS}
\]

---

## 8. Explicit Explanation of Asynchronous Same‑Process Starts and Early Equipment Release

The two central modelling innovations from Question 2 are preserved and extended to the two‑crew setting.

### 8.1 Asynchronous Operation‑Level Start Times  

Consider process A1 (Defect Filling) in Workshop A. It requires a Precision Filling Machine (PFM, 5400 s) and an Automated Conveying Arm (ACA, 4320 s). In a naive synchronous model, both units would be forced to start at the same instant, say \(S_{A1}\), and the process would finish at \(S_{A1} + \max(5400,4320) = S_{A1}+5400\). The ACA, though faster, would be tied up until the PFM finishes, wasting 1080 s of potential utilisation elsewhere.

Our model introduces separate start variables \(s_{A1,\text{PFM}}\) and \(s_{A1,\text{ACA}}\) with no equality constraint between them. This allows the two operations to start at **different times**, as the situation demands. For example, the ACA from Crew 2 might be delayed by a previous assignment and arrive only at \(t=1200\) s, while a PFM from Crew 1 is free at \(t=0\). The schedule can then set  

\[
s_{A1,\text{PFM}} = 0,\qquad s_{A1,\text{ACA}} = 1080\ (\text{or later}),
\]

so both finish simultaneously at \(5400\) s, or the faster unit may start later, reducing its idle time. Because the two start variables are independent, the model can match equipment availabilities optimally. No forced synchronisation ever increases the makespan; it can only be equal or better than any synchronous alternative.

### 8.2 Early Equipment Release  

The release time of an equipment unit after serving process \(j\) is defined as its own operation end time, **never** the process completion time \(PCT_j\). For process A1, the ACA (whether from Crew 1 or Crew 2) ends at  

\[
e_{A1,\text{ACA}} = s_{A1,\text{ACA}} + 4320,
\]

while the PFM ends at \(e_{A1,\text{PFM}} = s_{A1,\text{PFM}} + 5400\). The ACA may depart immediately after its end, even if the PFM is still running for another 1080 s. The next assignment of that ACA, say to process B2 (18000 s), can therefore start as early as  

\[
s_{B2,\text{ACA}} \ge e_{A1,\text{ACA}} + \tau(A,B) = e_{A1,\text{ACA}} + 510\ \text{s}.
\]

If the ACA had to wait for \(PCT_{A1} = e_{A1,\text{PFM}}\), the earliest start would be \(e_{A1,\text{PFM}} + 510\), i.e., 1080 s later. This early departure dramatically reduces potential makespan when the faster unit lies on a critical path.  

Cross‑crew sharing makes early release even more powerful: a fast unit from Crew 2 is never delayed by a slow unit from Crew 1 (and vice‑versa) merely because they happen to be assigned to the same process. Each unit’s schedule respects only its own operation end, ensuring maximum fluidity in the 32‑unit pool.

---

## 9. Two‑Crew Initial‑Location Modeling

The two crews have different base positions, which imposes asymmetric initial travel times. This is captured by the mapping \(g(k)\) that retrieves the crew of unit \(k\). In the path‑based models:

* For each unit \(k\), a distinct **source node** \(\texttt{SRC}_k\) is created. The arc from source to the first operation \((j,t)\) carries the timing constraint  

\[
s_{j,t} \ge \tau^{\text{init}}(k, w(j)),
\]

where \(\tau^{\text{init}}(k,\cdot)\) is taken from Table 2.3 according to \(g(k)\).

* All subsequent arcs use the symmetric inter‑workshop travel times \(\tau(w,w')\), which are identical for units of both crews.

Because the source node is unique to each unit, the model automatically enforces that a Crew 1 unit departing for Workshop B needs 310 s, while a Crew 2 unit departing for the same workshop needs 230 s. No extra constraints are required.

---

## 10. CP‑SAT-Oriented Implementation Guidance

To implement this model in Google OR‑Tools CP‑SAT:

1. **Variables**  
   - For each \((j,t)\in\mathcal{O}\), create an integer variable `s[j,t]` with domain \([0, H]\).  
   - Create auxiliary integer variables `PCT[j]` for each process and a final makespan variable `C_max`.  
   - For each operation and each eligible unit \(k\in\mathcal{U}_t\), create a Boolean variable `x[j,t,k]`.

2. **Assignment**  
   Add constraints \(\sum_{k\in\mathcal{U}_t} x[j,t,k] = 1\) for all \((j,t)\).

3. **Operation end**  
   Compute `e[j,t] = s[j,t] + p[j,t]` (linear expression, no new variable needed).

4. **Process completion**  
   For each process \(j\), use `model.AddMaxEquality(PCT[j], [e[j,t] for t in E_j])`.

5. **Per‑unit circuit**  
   For each unit \(k\) of type \(t\):  
   - Enumerate all operations in \(\mathcal{O}_t\).  
   - Construct Boolean arc literals:  
     * `y_src_op` for SOURCE→operation,  
     * `y_op_op` for operation→operation,  
     * `y_op_sink` for operation→SINK,  
     * `y_src_sink` for idle unit,  
     * `b_self` for operation self‑loop (linking `x[j,t,k] = 1 − b_self`).  
   - Build a list of `(tail, head, literal)` tuples including all arcs and self‑loops, then call `model.AddCircuit(...)`.  
   - For each arc literal, add `OnlyEnforceIf(literal)` on the corresponding timing constraint:  
     * SOURCE→op: `s[j,t] >= τ_init(k, w(j))`  
     * op1→op2: `s[j2,t] >= e[j1,t] + τ(w(j1), w(j2))`  

6. **Precedence**  
   For every (pred, succ) pair, enforce `model.Add(s[succ, t] >= PCT[pred])` for all \(t\in E_{succ}\).

7. **Makespan**  
   `model.AddMaxEquality(C_max, [PCT[j] for j in terminal processes])` and set `model.Minimize(C_max)`.

8. **Symmetry breaking**  
   For identical units within the same crew and same type, impose a descending workload order: `∑ x[j,t,k] >= ∑ x[j,t,k']` for \(k < k'\) in that group.

9. **Search strategy**  
   Provide an initial solution hint from a greedy heuristic. Use `num_search_workers = 8` and consider `DecisionStrategy` to branch first on assignment variables.

---

## 11. Optional MIP / Big‑M Alternative

For MIP solvers lacking a `AddCircuit` primitive, the model can be reformulated with disjunctive sequencing variables and big‑M constraints as detailed in Angle 8.

1. **Binary variables**  
   - Assignment \(x_{j,t,k}\) as before.  
   - For each unit \(k\) of type \(t\), variables \(y_{i,j,k}\) for ordered pairs of distinct operations \(i,j\in\mathcal{O}_t\) (immediate succession).  
   - Depot variables \(y_{D_k,j,k}\) for the first operation.

2. **Assignment and ordering**  
   - Same convexity constraint.  
   - For each unit, flow conservation: \(\sum_{i\neq j} y_{i,j,k} + y_{D_k,j,k} = x_{j,t,k}\).  
   - Unit usage: \(\sum_{j} y_{D_k,j,k} = u_k\) with \(u_k\) binary and bounded by total assigned operations.  
   - No‑cycle and transitivity constraints ensure a single chain (see Angle 8 for explicit inequalities).

3. **Timing**  
   - Big‑M sequencing: \(s_{j,t} \ge e_{i,t} + \tau(w(i),w(j)) - M(1 - y_{i,j,k})\) when both are assigned to \(k\).  
   - Initial travel: \(s_{j,t} \ge \tau^{\text{init}}(k,w(j)) - M(1 - y_{D_k,j,k})\).

4. **Process completion and makespan**  
   - \(PCT_j \ge e_{j,t}\) for all \(t\in E_j\), and \(C_{\max} \ge PCT_j\) for terminal processes.  
   - Minimise \(C_{\max}\).

The number of sequencing variables grows quadratically with the number of operations of each type, but for this 27‑process instance the largest \(\mathcal{O}_t\) contains only 10 operations (PFM), making the MIP tractable.

---

## 12. Table 3 Output Format and Validation Rules

### 12.1 Table Structure  

Table 3 has one row for every equipment–operation assignment (every triple \((j,t,k)\) with \(x_{j,t,k}=1\)). Columns:

| Equipment ID | Start Time (HH:MM:SS) | End Time (HH:MM:SS) | Continuous Operation Duration (s) | Process ID | Crew |
|--------------|-----------------------|---------------------|-----------------------------------|------------|------|
| e.g., “Automated Conveying Arm1‑3” | e.g., 01:23:45 | e.g., 02:35:45 | \(p_{j,t}\) (integer) | e.g., “A1” | 1 or 2 (from unit name) |

A process requiring two equipment types produces **two rows**, and their start times may differ.

### 12.2 Seven Validation Rules

A feasible schedule must satisfy the following, which can be checked directly from Table 3.

1. **Assignment correctness** – For each \((j,t)\in\mathcal{O}\), exactly one row exists with that Process ID and an Equipment ID of type \(t\).

2. **Asynchronous starts permitted** – Rows belonging to the same process are not required to share the same Start Time.

3. **Per‑row precedence** – For every consecutive process pair (pred, succ) in a workshop, **every** row of the successor must have `Start Time ≥ PCT_pred`, where \(PCT_{pred}\) is the maximum End Time among the rows of the predecessor.

4. **PCT consistency** – For any process \(j\), the maximum End Time over its rows equals \(PCT_j\).

5. **Equipment non‑overlap** – For each Equipment ID, when rows are sorted by Start Time, the gap between each consecutive pair must satisfy `Start_{next} ≥ End_{current} + τ(w(current), w(next))`. Zero gap is allowed for same‑workshop transfers.

6. **Crew‑aware initial transport** – For each Equipment ID, the first row’s Start Time must be at least the initial travel time from its crew base to that workshop (Table 2.3).

7. **Early release endpoint** – Each row’s End Time equals its own Start Time plus its own Processing Time (the `Continuous Operation Duration` column). No row is artificially delayed to the process completion time of a co‑worker.

---

## 13. Assumptions and Possible Ambiguities

The modelling rests on the following explicit assumptions, which also clarify ambiguities inherent in the problem statement.

1. **Asynchronous starts within a process** – No constraint forces \(s_{j,t_1}=s_{j,t_2}\). This extension of Q2 is allowed and strictly improves schedule flexibility.

2. **Early equipment release** – A unit is released at its own operation end, not at \(PCT_j\). Cross‑crew co‑workers impose no delay on each other’s release.

3. **Cross‑crew sharing** – A single process may be served by units from different crews. There is no obligation for the co‑workers to belong to the same crew.

4. **No pre‑emption** – Once a unit begins an operation, it remains continuously occupied for the full processing time \(p_{j,t}\).

5. **No workload splitting** – Each operation must be assigned to exactly one unit; parallel service by two units of the same type is not allowed.

6. **No return to base** – Equipment does not travel back to its base after completing its last assignment; the schedule ends when the last process finishes.

7. **Travel times are integer seconds** – All given distances are multiples of 2 m, and speed is 2 m/s, so all travel times are exact integers. Processing times are rounded up to the nearest integer second.

8. **Crew‑base asymmetry** – The initial distances from the two bases to the five workshops are different (Table 2.3), but inter‑workshop distances are symmetric and identical for both crews.

9. **Workshop C expansion** – The three rounds of C3→C4→C5 are executed consecutively in the order C1 → C2 → C3_1 → C4_1 → C5_1 → C3_2 → C4_2 → C5_2 → C3_3 → C4_3 → C5_3. The workload data per round are identical, but each instance is scheduled independently.

10. **Bottleneck resources** – The ASM and HPM remain the primary constraint because only two units of each type exist (one per crew). The abundant pool of ACA, ICM, and PFM reduces contention on those types, but does not eliminate the bottlenecks.

11. **Initial movement timing** – At time 00:00:00 all units are at their respective bases and begin travelling immediately. No work can start before a unit completes its first travel.

12. **Duration semantics** – “Continuous Operation Duration” in Table 3 refers to \(p_{j,t}\), the pure working time, not any interval containing idle time.

All these assumptions are consistent with the description of Question 3 and with the Q2 innovations that were proven to improve makespan. They form a rigorous foundation for both CP‑SAT and MIP implementations.