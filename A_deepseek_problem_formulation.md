## 1. Problem Interpretation for Question 1

Question 1 concerns a single-workshop overhaul task performed exclusively by Crew 1 in Workshop A. The workshop contains three compulsory processes—A1 (Defect Filling), A2 (Surface Leveling), and A3 (Strength Testing)—that **must** be executed in the exact sequential order A1 → A2 → A3. Each process involves one or more distinct types of equipment working **simultaneously** on the full process workload; a process is not considered complete until **all** its required equipment types have finished their independent operations. Crew 1 owns all the necessary equipment, and no equipment unit can work on more than one process at a time. Equipment movement inside the same workshop incurs zero time.

The objective is to **formulate a mathematical model** that yields the minimum total time (makespan) needed to finish all processes, and to produce **Table 1** recording, for each piece of equipment used, its start time, end time, continuous operation duration, and the process it serves. The start of the operational timeline is defined as 00:00:00 (HH:MM:SS). This question serves as the foundational building block for later multi‑crew, multi‑workshop scenarios, so the model must be rigorous yet clear, and it must explicitly expose the early‑release property of equipment.

## 2. Extracted Data for Workshop A and Crew 1

### Process Data for Workshop A

| Process | Workload (m³) | Required Equipment Types (and efficiencies) |
|---------|---------------|---------------------------------------------|
| A1      | 300           | Precision filling machine (200 m³/h), Automated conveying arm (250 m³/h) |
| A2      | 500           | High-speed polishing machine (100 m³/h), Industrial cleaning machine (250 m³/h) |
| A3      | 500           | Automatic sensing multi‑function machine (100 m³/h) |

### Crew 1 Equipment Available (relevant to Workshop A)

| Equipment Type                           | Equipment ID(s)               | Qty | Move Speed |
|------------------------------------------|--------------------------------|-----|-------------|
| Precision filling machine                | 精密灌装机1‑1 ~ 1‑5            | 5   | 2 m/s       |
| Automated conveying arm                  | 自动化输送臂1‑1 ~ 1‑4          | 4   | 2 m/s       |
| High-speed polishing machine             | 高速抛光机1‑1                  | 1   | 2 m/s       |
| Industrial cleaning machine              | 工业清洗机1‑1 ~ 1‑5            | 5   | 2 m/s       |
| Automatic sensing multi‑function machine | 自动传感多功能机1‑1            | 1   | 2 m/s       |

### Distance Information

- Crew 1 base to Workshop A: 400 m
- Equipment move speed: 2 m/s → travel time = 400/2 = 200 s

## 3. Assumptions

1. **Process order** – The sequence A1 → A2 → A3 is strictly enforced; no process may start until its immediate predecessor is fully completed.
2. **Parallel equipment within a process** – All equipment types assigned to the same process start simultaneously. Each equipment type must independently work through the **entire** workload of the process (i.e., the workload is **not** divided among units of the same type). A process finishes only when the **last** equipment type completes its work.
3. **Unit assignment** – For Question 1, exactly one unit of each required equipment type is employed. Extra identical units are treated as spares and are not used simultaneously on the same process (the workload is indivisible per type).
4. **No equipment sharing across processes** – Each equipment type appears in exactly one process. Thus an equipment unit never conflicts with a different process.
5. **Intra‑workshop transfers** – All equipment is already positioned in Workshop A once it starts; no transport time within the workshop is considered.
6. **Start time reference** – The default interpretation follows the problem statement: the first operation begins at 00:00:00. The alternative interpretation, which includes the 200 s travel from Crew 1’s base to Workshop A, is also discussed but not used in the recommended Table 1.
7. **Time resolution** – All durations are computed in seconds and rounded up (ceiling) to the next whole second, according to the requirement “durations are in seconds, rounded up (ceiling)”.
8. **Equipment release** – A piece of equipment becomes available immediately after it finishes its own workload, regardless of whether the rest of the process is still ongoing. This early‑release property, while not exploited in Question 1, is essential for subsequent questions and is formalised in the model.

## 4. Mathematical Notation

### Sets and Indices
- \(I = \{1,2,3\}\) – set of processes, where \(1 = \text{A1},\; 2 = \text{A2},\; 3 = \text{A3}\).
- \(T_i\) – set of equipment **types** required for process \(i\).
  - \(T_1 = \{\text{Precision filling machine},\; \text{Automated conveying arm}\}\)
  - \(T_2 = \{\text{High‑speed polishing machine},\; \text{Industrial cleaning machine}\}\)
  - \(T_3 = \{\text{Automatic sensing multi‑function machine}\}\)
- For each equipment type \(t \in T_i\), there is a set of identical units available; for simplicity, we select exactly one unit to perform the workload. The chosen unit for type \(t\) is denoted by its equipment ID, e.g., \(u_{i,t}\).

### Parameters
- \(W_i\) – workload of process \(i\) (m³): \(W_1 = 300,\; W_2 = 500,\; W_3 = 500\).
- \(r_t\) – efficiency (processing rate) of equipment type \(t\) (m³/h).
  - \(r_{\text{PrecisionFill}} = 200,\; r_{\text{AutoArm}} = 250,\; r_{\text{HighPolish}} = 100,\; r_{\text{IndClean}} = 250,\; r_{\text{AutoSens}} = 100\).
- \(p_{i,t}\) – operation duration (seconds) for equipment type \(t\) in process \(i\), defined as
  \[
  p_{i,t} = \left\lceil \frac{W_i}{r_t} \times 3600 \right\rceil .
  \]
- \(\Delta_{\text{base}} = 200\) s – optional initial transport time (used only in the alternative interpretation).

### Decision Variables
- \(S_i \ge 0\) – start time of process \(i\) (seconds).
- \(C_i \ge S_i\) – completion time of process \(i\) (seconds).
- \(s_{i,t}\) – start time of equipment type \(t\) in process \(i\) (equals \(S_i\) in this model).
- \(c_{i,t}\) – finish time of equipment type \(t\) in process \(i\).
- \(D_i\) – duration of process \(i\), \(D_i = C_i - S_i\).

### Auxiliary Variables (for generalized modelling)
- \(x_{i,t}\) – binary, 1 if equipment type \(t\) is used in process \(i\) (in Q1, this is fixed by the problem design).
- \(y_{i,i'}\) – precedence indicator (fixed: \(y_{1,2}=1, y_{2,3}=1\)).

## 5. Objective Function

The goal is to **minimize the overall makespan**, i.e., the time at which the last process is completed and all equipment has finished its work. With the strict sequential flow, the makespan equals the completion time of Process A3:

\[
\min \quad C_{\max} = C_3 .
\]

Equivalently, when all processes run in series without gaps and the start of A1 is set to zero, the makespan is the sum of the three process durations:

\[
C_{\max} = \sum_{i=1}^{3} D_i .
\]

For Question 1, every process duration is determined solely by the maximum of its equipment operation times, so the objective value becomes a deterministic quantity; the optimization reduces to verifying that no alternative scheduling can produce a smaller value under the given constraints.

## 6. Constraints

### 6.1 Process Precedence
Process must be completed before Process i+1 can start:
\[
S_{i+1} \ge C_i \quad \forall\, i = 1,2 .
\]

### 6.2 Within‑Process Parallel Execution
In each process \(i\), every equipment type \(t \in T_i\) starts simultaneously at \(S_i\) and works without interruption for \(p_{i,t}\) seconds:
\[
s_{i,t} = S_i \quad \forall\, t \in T_i ,
\]
\[
c_{i,t} = s_{i,t} + p_{i,t} \quad \forall\, t \in T_i .
\]

### 6.3 Process Completion Rule
A process \(i\) is considered complete only when **all** its constituent equipment types have finished their operations. Thus,
\[
C_i \ge c_{i,t} \quad \forall\, t \in T_i .
\]

To enforce equality (since no other task can delay the process beyond the slowest equipment), we set
\[
C_i = \max_{t \in T_i} c_{i,t} .
\]

### 6.4 Equipment Non‑Overlap (general form)
For any equipment unit, it can serve at most one process at a time. In Question 1, each equipment type participates in exactly one process, so non‑overlap constraints are automatically satisfied. For completeness, the general constraint would be:
\[
c_{i,t} \le S_{i'} \quad \text{or} \quad C_{i'} \le S_i
\]
for any pair of processes \((i,i')\) that share the same equipment unit. Here, no sharing exists, so these constraints are inactive.

### 6.5 Start Time Reference
With no initial transport delay:
\[
S_1 = 0 .
\]
Under the alternative interpretation, \(S_1 = \Delta_{\text{base}} = 200\) s.

### 6.6 Mixed‑Integer Programming Perspective (Angle 3)
Although not required for the direct solution of Question 1, the problem can be formulated as a Mixed‑Integer Program (MIP) with binary variables \(x_{i,k}\) indicating whether equipment unit \(k\) is assigned to process \(i\), continuous start/finish times, and constraints linking process completion to the maximum of assigned equipment finish times. For Question 1, the assignment is fixed and the MIP immediately collapses to the closed‑form solution. This MIP framework becomes valuable in later questions where equipment can be shared among workshops; it is mentioned here to stress that the present model is a special case of a more general, reusable structure.

## 7. Early Equipment Release Modeling

A key operational nuance, formalised in Angle 2, is the **early release** of equipment. Even though all equipment types within a process start at the same time, they may finish at different instants. The moment an equipment unit completes its workload, it becomes **free** for other tasks—this is the **operation completion time** (OCT). The **process completion time** (PCT) is the maximum of all OCTs in that process; the remaining process time after the fastest equipment finishes is “idle” time for that equipment, during which it could theoretically be redeployed.

For Question 1, the strict sequential nature of Workshop A guarantees that no subsequent task can start until the entire process finishes. Therefore, even though the automated conveying arm (A1) and the industrial cleaning machine (A2) finish well before their respective processes end, they must wait for the next process to begin. As a result, early release does **not** reduce the makespan for this specific question. The mechanism, however, is essential for Questions 2–4 where released equipment can be transferred to other workshops, enabling parallel execution across multiple locations.

We formally define:

- **Operation time** of equipment \(k\) in process \(i\): \(d_{i,k} = \lceil W_i / \eta_k \times 3600 \rceil\).
- **Operation completion time**: \(\text{OCT}_{i,k} = S_i + d_{i,k}\).
- **Process completion time**: \(\text{PCT}_i = \max_{k \in \mathcal{E}_i} \text{OCT}_{i,k}\).
- **Equipment release time**: \(R_{i,k} = \text{OCT}_{i,k}\). After this instant, the equipment unit is free for reallocation.

Because \(\text{PCT}_i\) is determined by the slowest equipment, the equipment with shorter operation time experiences an idle gap of \(\text{PCT}_i - \text{OCT}_{i,k}\) within the process. These gaps are recorded in Table 1, where, for example, the automated conveying arm finishes A1 at 01:12:00 while the process itself ends at 01:30:00.

## 8. Solution Logic

The optimal schedule for Question 1 follows directly from the constraints and the absence of resource sharing. The logic is:

1. **Compute individual equipment operation times** for each process using the ceiling formula.
2. **Determine process duration** as the maximum of the operation times of the required equipment types.
3. **Schedule processes back‑to‑back** in the order A1 → A2 → A3, since no benefit can be gained from inserting idle time; any delay would only increase the makespan.
4. **Set the start of A1 to 00:00:00** (default interpretation). The start of A2 equals the completion time of A1, and the start of A3 equals the completion time of A2.
5. **Record start/end times for each equipment unit** as the process start time (start) and start plus its own operation duration (end).

The resulting schedule is provably optimal because every process must be fully completed before the next can begin, and the completion time of each process is lower‑bounded by its slowest equipment operation. Summing these lower bounds yields an absolute lower bound for the makespan; the schedule achieves this bound exactly, confirming optimality.

## 9. Computed Processing Durations

### Process A1 (Defect Filling)
- Precision filling machine: \(p_{1,\text{fill}} = \lceil 300/200 \times 3600 \rceil = \lceil 5400 \rceil = 5400\) s.
- Automated conveying arm: \(p_{1,\text{arm}} = \lceil 300/250 \times 3600 \rceil = \lceil 4320 \rceil = 4320\) s.
- Process A1 duration: \(D_1 = \max(5400, 4320) = 540