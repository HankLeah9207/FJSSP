#!/usr/bin/env python3
"""
Multi-agent DeepSeek API workflow for Question 4 of 2026-51MCM Problem B.

Generates a rigorous mathematical model for jointly determining the equipment
procurement plan and the scheduling strategy under a $500,000 budget such that
the makespan of all overhaul tasks across the five workshops A, B, C, D, E is
minimized. Inherits all Q3 modeling assumptions: two crews, combined equipment
pool, asynchronous operation-level start times, early equipment release,
process completion as max-of-operation-ends, crew-specific initial travel,
inter-workshop travel, and Table-3-style schedule output - now extended with
procurement decisions and a Table 5 for procurement details.

Workflow: 12 API calls total
  1. Design / refine 10 distinct modeling angles for Q4
  2. Run 10 parallel modeling agents (one per angle)
  3. Aggregate into a final Markdown report
"""

import os
import sys
import json
import time
import datetime
import httpx
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "FJSSP")
OUTPUT_MD = os.path.join(OUTPUT_DIR, "Q4_deepseek_problem_formulation.md")
OUTPUT_ANGLES_JSON = os.path.join(OUTPUT_DIR, "Q4_deepseek_angle_outputs.json")
OUTPUT_LOG = os.path.join(OUTPUT_DIR, "Q4_deepseek_problem_formulation_log.json")

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

MAX_RETRIES = 3
BASE_BACKOFF = 2.0
REQUEST_TIMEOUT = 180

# ---------------------------------------------------------------------------
# Problem data (extracted from attachments, Question 4)
# ---------------------------------------------------------------------------

PROBLEM_DATA = """
## Problem Statement (Question 4)

To reduce the operational makespan, the enterprise intends to allocate an
additional equipment procurement budget totaling $500,000 to supplement
various types of equipment resources across the crews. Formulate a
mathematical model to jointly determine the equipment procurement plan and
the scheduling strategy under the budget constraint, such that the
completion time of all tasks is minimized. Then, in Table 4, record for each
piece of equipment: the equipment ID, start time, end time, continuous
operation duration, process ID, and associated crew; and in Table 5, record
the equipment procurement details.

Question 4 is a strict generalization of Question 3: BOTH Crew 1 and Crew 2
equipment pools are still available, equipment is shared across all five
workshops A, B, C, D, E, and a process requiring two equipment types may use
units belonging to different crews. The Q3 modeling innovations - inherited
from Q2 - must be preserved:
- Asynchronous operation-level start times: when a process needs two
  equipment types, the two equipment operations may start at DIFFERENT times.
- Early equipment release: each equipment unit is released at its OWN
  operation-end time, NOT at the process completion time.

Question 4 introduces a new dimension on top of Q3: the enterprise may now
purchase additional equipment from a five-type catalog and assign each
purchased unit to either Crew 1 or Crew 2, subject to the $500,000 hard
budget constraint. The crew assignment of a purchased unit is meaningful
because it determines (a) the unit's crew label in Table 4, (b) the unit's
count in Table 5, and (c) the unit's initial base-to-workshop travel time.

## Q4 Procurement Catalog and Budget

| Equipment Type (Table 5 Name) | Unit Price (USD) |
|---|---|
| Automated Conveying Arm (ACA) | 50000 |
| Industrial Cleaning Machine (ICM) | 40000 |
| Precision Filling Machine (PFM) | 35000 |
| Automatic Sensing Multi-Function Machine (ASM) | 80000 |
| High-speed Polishing Machine (HPM) | 75000 |

Total procurement budget: **$500,000** (hard constraint).

Primary objective: minimize makespan C_max.
Optional secondary (lexicographic) objective: among schedules achieving the
same optimal C_max, minimize total procurement cost.

## Process Flow Data for All Five Workshops (from "Process Flow Table")

### Workshop A (Process order: A1 -> A2 -> A3)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| A1 | Defect Filling | Precision Filling Machine 200 m^3/h AND Automated Conveying Arm 250 m^3/h | 300 m^3 |
| A2 | Surface Leveling | High-speed Polishing Machine 100 m^3/h AND Industrial Cleaning Machine 250 m^3/h | 500 m^3 |
| A3 | Strength Testing | Automatic Sensing Multi-Function Machine 100 m^3/h | 500 m^3 |

### Workshop B (Process order: B1 -> B2 -> B3 -> B4)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| B1 | Surface Cleaning | Industrial Cleaning Machine 100 m^3/h | 120 m^3 |
| B2 | Base Layer Construction | Precision Filling Machine 200 m^3/h AND Automated Conveying Arm 300 m^3/h | 1500 m^3 |
| B3 | Surface Sealing | Precision Filling Machine 350 m^3/h | 360 m^3 |
| B4 | Surface Leveling | High-speed Polishing Machine 120 m^3/h AND Automatic Sensing Multi-Function Machine 100 m^3/h | 360 m^3 |

### Workshop C (Process order: C1 -> C2 -> [C3 -> C4 -> C5] x 3)

Note: Processes C3, C4, C5 are repeated three times. Expand the chain as:
C1 -> C2 -> C3_1 -> C4_1 -> C5_1 -> C3_2 -> C4_2 -> C5_2 -> C3_3 -> C4_3 -> C5_3.

| Process | Name | Equipment Required (efficiency) | Workload (per round) |
|---------|------|--------------------------------|----------|
| C1 | Old Coating Removal | Industrial Cleaning Machine 250 m^3/h AND Automated Conveying Arm 250 m^3/h | 720 m^3 |
| C2 | Base Filling | Precision Filling Machine 350 m^3/h | 720 m^3 |
| C3 | Sealing Coverage | Precision Filling Machine 200 m^3/h AND Automated Conveying Arm 250 m^3/h | 360 m^3 |
| C4 | Surface Grinding | High-speed Polishing Machine 120 m^3/h AND Industrial Cleaning Machine 100 m^3/h | 400 m^3 |
| C5 | Quality Inspection | Automatic Sensing Multi-Function Machine 100 m^3/h | 400 m^3 |

### Workshop D (Process order: D1 -> D2 -> D3 -> D4 -> D5 -> D6)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| D1 | Debris Removal | Industrial Cleaning Machine 250 m^3/h | 600 m^3 |
| D2 | Base Solidification | Precision Filling Machine 200 m^3/h AND Automated Conveying Arm 300 m^3/h | 800 m^3 |
| D3 | Surface Sealing | Precision Filling Machine 350 m^3/h | 450 m^3 |
| D4 | Surface Leveling | High-speed Polishing Machine 120 m^3/h AND Automatic Sensing Multi-Function Machine 300 m^3/h | 1500 m^3 |
| D5 | Load-bearing Inspection | Automatic Sensing Multi-Function Machine 300 m^3/h | 1500 m^3 |
| D6 | Edge Trimming | High-speed Polishing Machine 100 m^3/h | 700 m^3 |

### Workshop E (Process order: E1 -> E2 -> E3)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| E1 | Foundation Treatment | Industrial Cleaning Machine 250 m^3/h | 1000 m^3 |
| E2 | Surface Sealing | Precision Filling Machine 350 m^3/h | 600 m^3 |
| E3 | Stability Inspection | Automatic Sensing Multi-Function Machine 300 m^3/h AND Industrial Cleaning Machine 100 m^3/h | 600 m^3 |

Processing-time rule (per process j and required equipment type t):

  p[j, t] = ceil( workload[j] / efficiency[j, t] * 3600 ) seconds.

## Existing Two-Crew Equipment Configuration (32 units total, before procurement)
(from "Crew Configuration Table")

### Crew 1 Equipment (16 units)

| Equipment Type | Equipment IDs | Qty | Speed (m/s) |
|---|---|---|---|
| Automated Conveying Arm | ACA1-1 ~ ACA1-4 | 4 | 2 |
| Industrial Cleaning Machine | ICM1-1 ~ ICM1-5 | 5 | 2 |
| Precision Filling Machine | PFM1-1 ~ PFM1-5 | 5 | 2 |
| Automatic Sensing Multi-Function Machine | ASM1-1 | 1 | 2 |
| High-speed Polishing Machine | HPM1-1 | 1 | 2 |

### Crew 2 Equipment (16 units)

| Equipment Type | Equipment IDs | Qty | Speed (m/s) |
|---|---|---|---|
| Automated Conveying Arm | ACA2-1 ~ ACA2-4 | 4 | 2 |
| Industrial Cleaning Machine | ICM2-1 ~ ICM2-5 | 5 | 2 |
| Precision Filling Machine | PFM2-1 ~ PFM2-5 | 5 | 2 |
| Automatic Sensing Multi-Function Machine | ASM2-1 | 1 | 2 |
| High-speed Polishing Machine | HPM2-1 | 1 | 2 |

### Combined Equipment Pool (per equipment type, before procurement)

| Equipment Type | Crew 1 Units | Crew 2 Units | Total |
|---|---|---|---|
| Automated Conveying Arm | 4 | 4 | 8 |
| Industrial Cleaning Machine | 5 | 5 | 10 |
| Precision Filling Machine | 5 | 5 | 10 |
| Automatic Sensing Multi-Function Machine | 1 | 1 | 2 |
| High-speed Polishing Machine | 1 | 1 | 2 |

All equipment travels at speed 2 m/s.

### Naming Convention for Newly Purchased Equipment

Every newly purchased unit must be assigned to exactly one crew at purchase
time and must be given a unique ID continuing the existing numbering of its
crew, e.g.:
- ACA1-5, ACA1-6, ... for additional Automated Conveying Arms assigned to Crew 1
- ACA2-5, ACA2-6, ... for additional Automated Conveying Arms assigned to Crew 2
- ICM1-6, ICM1-7, ... and ICM2-6, ICM2-7, ...
- PFM1-6, PFM1-7, ... and PFM2-6, PFM2-7, ...
- ASM1-2, ASM1-3, ... and ASM2-2, ASM2-3, ...
- HPM1-2, HPM1-3, ... and HPM2-2, HPM2-3, ...

The crew label of each purchased unit determines its initial base location
and its row in Table 5.

## Distance Tables (from "Workshop Distance Table")

### Initial Distances from Crew 1 Base

| Origin | Destination | Distance (m) |
|--------|-------------|---------------|
| Crew 1 | A | 400 |
| Crew 1 | B | 620 |
| Crew 1 | C | 460 |
| Crew 1 | D | 710 |
| Crew 1 | E | 400 |

### Initial Distances from Crew 2 Base

| Origin | Destination | Distance (m) |
|--------|-------------|---------------|
| Crew 2 | A | 500 |
| Crew 2 | B | 460 |
| Crew 2 | C | 620 |
| Crew 2 | D | 680 |
| Crew 2 | E | 550 |

### Inter-Workshop Distances (symmetric)

| Origin | Destination | Distance (m) |
|--------|-------------|---------------|
| A | B | 1020 |
| A | C | 1050 |
| A | D | 900 |
| A | E | 1400 |
| B | C | 1100 |
| B | D | 1630 |
| B | E | 720 |
| C | D | 520 |
| C | E | 850 |
| D | E | 1030 |

Transport time = distance / speed, where speed = 2 m/s for all equipment
(both existing and newly purchased). Initial transport time uses the
base-to-workshop distance specific to the crew the equipment unit belongs to,
and applies identically to existing and purchased units.

## Modeling Continuity from Question 3

The Q4 model migrates from Q3 and must preserve all of the following:
1. Both Crew 1 and Crew 2 equipment pools are simultaneously available.
2. Equipment may be shared across all five workshops A-E.
3. A process requiring two equipment types may use equipment from different
   crews (cross-crew sharing within one process is permitted).
4. Same-process operations are asynchronous: different equipment types in the
   same process are NOT forced to start at the same time.
5. Early equipment release: each equipment unit is released immediately after
   its own operation ends, not after the whole process completion time.
6. The process completion time is the maximum end time among its required
   equipment operations:
     PCT_j = max_{t in E_j} ( s_{j,t} + p_{j,t} ).
7. The next process in the same workshop can start only after the previous
   process is fully complete (per-equipment-type precedence on PCT_pred).
8. Initial travel time depends on the crew to which the equipment belongs.
9. Inter-workshop travel times are symmetric and independent of crew.
10. No preemption.
11. No workload splitting (a single operation cannot be split across two
    units of the same type running in parallel).
12. No return-to-base requirement after the final operation.

## Q4-Specific Modeling Requirements

### Procurement decision variables

The formulation should define variables such as:
- y[g, t] in Z_>=0  =  number of newly purchased units of type t assigned to
  crew g, for g in {1, 2} and t in {ACA, ICM, PFM, ASM, HPM};
or, equivalently, candidate-style binaries:
- z[k] in {0, 1}  =  1 iff candidate purchased unit k is actually purchased.

Each candidate purchased unit is pre-labeled with its crew g(k) at modeling
time, so its base distance (and thus initial travel time) is determined.

### Budget constraint

  sum over g in {1, 2}, t in T  of  unit_price[t] * y[g, t]  <=  500000.

### Equipment-pool expansion

Let U_t^{exist}_g denote the existing units of type t in crew g (sizes given
above). The effective unit pool used for scheduling becomes:

  U_t^{eff}_g  =  U_t^{exist}_g  union  { purchased units of type t assigned
                                           to crew g  }.

The scheduling sub-model is structurally identical to Q3, but the unit set
U_t = U_t^{eff}_1 union U_t^{eff}_2 may now be larger.

### Crew label and initial location of purchased units

A purchased unit assigned to crew g
- carries crew label g in Table 4,
- contributes 1 to the "Number purchased by crew g" cell of Table 5,
- starts at the crew-g base, so its initial travel time to workshop w is
  delta_g(w) / speed.

### IMPORTANT MODELING CLARIFICATION

Do NOT introduce a crew-wide human-capacity constraint (e.g., a cap on the
number of simultaneous operations a single crew can perform). In this
problem, crew affiliation should be treated purely as **equipment ownership
and initial-location information**, not as a single labor resource that
limits simultaneous operations.

### Recommended solution approaches

The final formulation must discuss BOTH of the following:

1. **Integrated CP-SAT model**: define a fixed "candidate purchased unit"
   pool large enough to be unbounded in practice (e.g., add a generous upper
   bound on y[g, t] derived from the budget); each candidate unit carries an
   activation literal z[k] guarding all its assignment, sequencing, and
   timing arcs. The integrated model jointly optimizes procurement and
   scheduling.

2. **Two-stage approach**: enumerate feasible procurement plans (g, t) -> y
   under the $500,000 budget; for each procurement plan, solve a Q3-style
   CP-SAT scheduling subproblem with the expanded equipment pool; choose the
   plan minimizing makespan; if a tie-break is desired, prefer the plan with
   smaller total procurement cost. This decouples a difficult joint problem
   into many easier scheduling-only problems and is often more practical.

## Output Requirements

### Table 4 (per equipment-operation row)

Columns:
- Number
- Equipment ID
- Start time (HH:MM:SS)
- End time (HH:MM:SS)
- Duration (s)
- Process ID
- Crew

Followed by:
"Shortest duration to complete the task of question 4: (s)"

Each process j requiring two equipment types yields TWO Table 4 rows (one per
equipment-operation), with possibly different Start/End times. Existing and
newly purchased units appear identically in Table 4.

### Table 5 (procurement details)

Columns:
- Equipment Name
- Number purchased by crew 1
- Number purchased by crew 2
- Total procurement Cost

Equipment-name rows (in order):
1. Automated Conveying Arm
2. Industrial Cleaning Machine
3. Precision Filling Machine
4. Automatic Sensing Multi-Function Machine
5. High-speed Polishing Machine

The "Total procurement Cost" cell on each row equals
unit_price[t] * (y[1, t] + y[2, t]); the sum of all rows must be at most
$500,000.

## Critical Modeling Innovations Inherited from Question 2 -> Question 3

### Innovation 1 - Asynchronous operation-level start times

For a process j requiring equipment types t1 and t2, do NOT introduce a
single shared start variable S_j. Instead, introduce one start variable per
operation:
  s_{j,t1}, s_{j,t2}
The two operations may start at different times. The process completion is
the maximum of the two operation ends:
  PCT_j = max(s_{j,t1} + p_{j,t1}, s_{j,t2} + p_{j,t2})

### Innovation 2 - Early equipment release

Each equipment unit is released at its own operation-end time, not at the
process completion time:
  - Operation Completion Time: e_{j,t} = s_{j,t} + p_{j,t}
  - Process Completion Time:   PCT_j   = max_{t in E_j} e_{j,t}
  - Equipment Release Time:    R_{j,k,t} = e_{j,t}  (NOT PCT_j)
  - Next-use constraint: s_{j',t} >= e_{j,t} + transport_time(w_j, w_{j'})
    when the same unit k serves both j and j'.

### Innovation 3 - Per-operation precedence (not per-process)

Workshop precedence is enforced per equipment-type operation of the
successor process:
  s_{succ, t} >= PCT_{pred}   for every t in E_{succ}.
"""

# ---------------------------------------------------------------------------
# Predefined ten modeling angles (Question 4)
# ---------------------------------------------------------------------------

ANGLE_DEFINITIONS = [
    {
        "id": 1,
        "title": "Q3-to-Q4 Migration: Preservation of Asynchronous Starts and Early Release Under Procurement",
        "description": (
            "Frame Question 4 as a strict generalization of Question 3 in which "
            "the two-crew equipment pool may be expanded by procurement under a "
            "$500,000 hard budget. Show that all Q3 modeling primitives carry "
            "over: per-operation start variables s_{j,t}, end expressions "
            "e_{j,t} = s_{j,t} + p_{j,t}, process completion time "
            "PCT_j = max_{t in E_j} e_{j,t}, early equipment release at "
            "e_{j,t}, per-operation precedence "
            "s_{succ,t} >= PCT_pred, no preemption, no return-to-base, and the "
            "5-workshop process chains with Workshop C unrolled into "
            "C1 -> C2 -> C3_1 -> C4_1 -> C5_1 -> C3_2 -> C4_2 -> C5_2 -> "
            "C3_3 -> C4_3 -> C5_3. Argue rigorously that the optimal Q4 "
            "makespan is at most the optimal Q3 makespan (the Q3 optimum is "
            "feasible for Q4 with zero procurement). Identify which Q3 "
            "bottlenecks (single-per-crew ASM and HPM) are the most likely "
            "procurement targets."
        ),
    },
    {
        "id": 2,
        "title": "Procurement Decision Variables, Budget Constraint, and Equipment-Pool Expansion",
        "description": (
            "Define the procurement-side decision variables rigorously. Provide "
            "two equivalent formulations: (a) integer counts "
            "y[g, t] in Z_>=0 = number of new units of type t given to crew g, "
            "for g in {1, 2} and t in {ACA, ICM, PFM, ASM, HPM}; "
            "(b) candidate-unit binaries z[k] in {0, 1} where each candidate "
            "is pre-labeled with type and crew. State the bidirectional mapping "
            "y[g, t] = sum over k in candidates(g, t) of z[k]. Write the budget "
            "constraint sum_{g,t} unit_price[t] * y[g, t] <= 500000 with prices "
            "ACA 50000, ICM 40000, PFM 35000, ASM 80000, HPM 75000. Derive a "
            "tight upper bound on y[g, t] given the budget alone "
            "(e.g., y_PFM <= 14, y_ICM <= 12, ...) so the candidate-unit pool "
            "can be sized finitely. Define the expanded effective unit set "
            "U_t = U_t^{exist}_1 cup U_t^{exist}_2 cup U_t^{new}_1 cup "
            "U_t^{new}_2, and explain how it replaces Q3's fixed 32-unit pool."
        ),
    },
    {
        "id": 3,
        "title": "Crew Ownership, Initial-Location Modeling, and Purchased-Equipment Indexing",
        "description": (
            "Formalize the crew-of-unit map g: U -> {1, 2} so that it is "
            "well-defined for both existing and newly purchased units. For "
            "existing units the crew is read off the unit's name (the digit "
            "before the dash). For purchased units the crew is fixed at "
            "modeling time by the candidate's pre-labeled assignment. Specify "
            "the naming convention for new units: ACA1-5, ACA1-6, ... for new "
            "Crew-1 ACAs, ACA2-5, ACA2-6, ... for Crew-2; analogously for ICM, "
            "PFM, ASM, HPM. Derive the initial transport time of unit k as "
            "tau_init(k, w) = delta_{g(k)}(w) / speed using BOTH base-distance "
            "tables (Crew 1: A=400, B=620, C=460, D=710, E=400; Crew 2: A=500, "
            "B=460, C=620, D=680, E=550). Emphasize that crew affiliation is "
            "ONLY ownership and initial-location information; do NOT add any "
            "crew-wide labor or simultaneity cap."
        ),
    },
    {
        "id": 4,
        "title": "Operation-Level Scheduling Variables, Process Completion, and Workshop Precedence",
        "description": (
            "Define the scheduling-side variables on the expanded pool: for "
            "every (j, t) with t in E_j, an integer start variable s_{j,t} on "
            "[0, H], the linear end expression e_{j,t} = s_{j,t} + p_{j,t}, "
            "and the process completion variable "
            "PCT_j = max_{t in E_j} e_{j,t}. Show with concrete numbers the "
            "ceiling-based processing times "
            "p_{j,t} = ceil(workload_j / efficiency_{j,t} * 3600) for at least "
            "two illustrative processes (e.g., A1 PFM: p = ceil(300/200 * 3600) "
            "= 5400 s; A1 ACA: p = ceil(300/250 * 3600) = 4320 s). State the "
            "per-operation workshop precedence: for each ordered consecutive "
            "pair (pred, succ) in the same workshop and each t in E_succ, "
            "s_{succ, t} >= PCT_pred. Justify this is strictly stronger than "
            "synchronous precedence and remains valid under procurement."
        ),
    },
    {
        "id": 5,
        "title": "Equipment Sequencing, Travel Times, No-Overlap, and Early Release on the Expanded Pool",
        "description": (
            "Model how each equipment unit (existing or purchased) is routed "
            "across workshops. For two consecutive operations (i, t) and "
            "(j, t) on the same unit k, enforce "
            "s_{j,t} >= e_{i,t} + tau(w(i), w(j)), where tau(w, w') = "
            "d(w, w') / speed and tau(w, w) = 0. This both eliminates overlap "
            "and embeds the early-release rule (note we use e_{i,t}, not "
            "PCT_i). Provide the symmetric inter-workshop transport-time "
            "matrix derived from speed = 2 m/s. Use the full distance table "
            "(A-B 1020, A-C 1050, A-D 900, A-E 1400, B-C 1100, B-D 1630, "
            "B-E 720, C-D 520, C-E 850, D-E 1030). Explicitly emphasize that "
            "the ABSENCE of a return-to-base requirement means the model only "
            "fires the initial-base arc on the FIRST operation of each unit."
        ),
    },
    {
        "id": 6,
        "title": "Integrated CP-SAT Formulation with Candidate Purchased Units",
        "description": (
            "Provide the full CP-SAT integrated model that jointly decides "
            "procurement and scheduling in a single solve. For every "
            "type-crew pair (g, t), introduce a fixed-size candidate pool "
            "C_{g,t} of pre-indexed possible purchases (size derived from the "
            "budget cap), each with an activation literal z[k]. Build all "
            "scheduling arcs and assignment binaries x_{j,t,k} as in Q3, but "
            "guard them with z[k]: assign(j, t, k) implies z[k]; an "
            "unactivated candidate must take the SOURCE_k -> SINK_k closing "
            "arc (i.e., contributes nothing to the schedule). State the "
            "AddCircuit per unit including the SOURCE -> SINK self-skip arc "
            "for candidates with z[k] = 0. Couple the budget constraint via "
            "sum_k unit_price[t(k)] * z[k] <= 500000. Provide search-strategy "
            "hints (DecisionStrategy, num_search_workers, hinting, symmetry "
            "breaking across identical units of the same type within the same "
            "crew, including identical CANDIDATE units)."
        ),
    },
    {
        "id": 7,
        "title": "Two-Stage Solution Strategy: Procurement Enumeration + Q3-Style CP-SAT",
        "description": (
            "Describe the practical two-stage decomposition. Stage 1: "
            "enumerate all feasible procurement plans, i.e., all integer "
            "vectors (y[1, t], y[2, t]) for t in T satisfying "
            "sum unit_price[t] * (y[1, t] + y[2, t]) <= 500000 (and any "
            "tightening upper bounds derived from saturation analysis - e.g., "
            "buying more than 4 ASMs is unlikely to help because all 9 "
            "ASM-using operations C5_1, C5_2, C5_3, A3, B4, D4, D5, E3 are "
            "few). Stage 2: for each plan, solve the Q3-style CP-SAT model "
            "with the expanded pool; record makespan and procurement cost. "
            "Stage 3: choose the plan minimizing makespan; tie-break by "
            "procurement cost if requested. Discuss pruning techniques "
            "(symmetry between identical-cost plans, dominance: y' dominates "
            "y if it is component-wise >= and same cost, etc.) and provide an "
            "informal complexity estimate."
        ),
    },
    {
        "id": 8,
        "title": "Objective-Function Design: Makespan Primary, Optional Lexicographic Cost Tie-Break",
        "description": (
            "Make the objective hierarchy explicit. Primary objective: "
            "minimize C_max where C_max >= PCT_j for every terminal process "
            "(A3, B4, C5_3, D6, E3). State this as a linear minimization "
            "with C_max bounded below by the maxes. Optional secondary "
            "objective: among schedules with the same C_max, minimize "
            "procurement cost sum_{g,t} unit_price[t] * y[g, t]. Show two "
            "ways to encode the lexicographic objective in CP-SAT: (a) "
            "two-phase solve - first minimize C_max, then re-solve with "
            "C_max <= optimal_makespan and minimize cost; (b) a weighted "
            "scalarization Min(W * C_max + cost) with W chosen larger than "
            "the maximum possible cost (e.g., W >= 600000) so that any "
            "saved second of makespan dominates any procurement saving. "
            "Argue that approach (a) is preferable because it produces "
            "certifiably optimal lex pairs."
        ),
    },
    {
        "id": 9,
        "title": "Table 4 and Table 5 Output Format and Validation Rules",
        "description": (
            "Specify the exact format of both output tables. Table 4 columns: "
            "Number, Equipment ID, Start time (HH:MM:SS), End time "
            "(HH:MM:SS), Duration (s), Process ID, Crew (1 or 2). Each row is "
            "ONE equipment-operation; a two-equipment process yields two "
            "rows. Followed by 'Shortest duration to complete the task of "
            "question 4: <C_max> (s)'. Table 5 columns: Equipment Name, "
            "Number purchased by crew 1, Number purchased by crew 2, Total "
            "procurement Cost. Five rows: Automated Conveying Arm, Industrial "
            "Cleaning Machine, Precision Filling Machine, Automatic Sensing "
            "Multi-Function Machine, High-speed Polishing Machine. Validation "
            "rules: (1) every operation has exactly one Table 4 row; "
            "(2) async starts permitted; (3) per-row precedence "
            "row.Start >= PCT_pred; (4) PCT_j == max end over rows of j; "
            "(5) per-Equipment-ID non-overlap with transport gap; (6) initial "
            "transport from the correct crew's base for the FIRST row of each "
            "unit; (7) early-release endpoint verification "
            "End == s_{j,t} + p_{j,t}; (8) Table 5 sums match the integers "
            "y[g, t] used in Table 4; (9) total procurement cost <= 500000."
        ),
    },
    {
        "id": 10,
        "title": "Assumptions, Edge Cases, Bottleneck-Resource Interpretation, and Modeling Pitfalls",
        "description": (
            "Enumerate all modeling assumptions and possible ambiguities. "
            "(1) The budget is a hard constraint; partial dollars are not "
            "allowed (integer y). (2) The crew assignment of a purchased unit "
            "is a one-time decision at procurement and is fixed for the "
            "entire schedule. (3) Purchased units start at the assigned "
            "crew's base at time 0, identically to existing units of that "
            "crew. (4) Workshop C workloads are PER ROUND. (5) Asynchronous "
            "operation-level starts apply unchanged to the expanded pool. "
            "(6) Cross-crew sharing within a single process is permitted "
            "(existing or newly purchased; from either crew). (7) Bottleneck "
            "interpretation: ASM and HPM each have only 1 unit per crew "
            "before procurement, and ASM is required by 5+ operations "
            "(C5_1/2/3, A3, D4, D5, E3) while HPM by 4 (A2, B4, C4_1/2/3, "
            "D4, D6) - these are likely buy targets. (8) PITFALL: do NOT add "
            "a crew-wide simultaneity cap; the only crew-related modeling "
            "effect is initial-base distance. (9) PITFALL: do NOT couple the "
            "two equipment-type operations of the same process via a shared "
            "S_j; keep them per-operation. (10) PITFALL: when enumerating "
            "procurement plans in the two-stage approach, ensure the upper "
            "bound on each y[g, t] is derived from the budget, not from a "
            "guess."
        ),
    },
]

# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

call_log = []


def call_deepseek(messages, temperature=0.7, label=""):
    """Call DeepSeek chat completions API with retry and exponential backoff."""
    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY environment variable is not set.")
        sys.exit(1)

    for var in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
                "HTTPS_PROXY", "https_proxy"):
        val = os.environ.get(var, "")
        if val.startswith("socks://"):
            os.environ[var] = "socks5://" + val[len("socks://"):]

    proxy_url = (
        os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or None
    )
    http_client = (
        httpx.Client(proxy=proxy_url, timeout=REQUEST_TIMEOUT)
        if proxy_url
        else httpx.Client(timeout=REQUEST_TIMEOUT)
    )

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        http_client=http_client,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=32768,
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )
            content = response.choices[0].message.content
            log_entry = {
                "label": label,
                "timestamp": datetime.datetime.now().isoformat(),
                "request_messages": messages,
                "temperature": temperature,
                "response_content": content,
                "model": DEEPSEEK_MODEL,
            }
            call_log.append(log_entry)
            return content

        except Exception as e:
            print(f"  [{label}] Request error on attempt {attempt}/{MAX_RETRIES}: {e}")

        if attempt < MAX_RETRIES:
            wait = BASE_BACKOFF ** attempt
            print(f"  [{label}] Retrying in {wait:.0f}s ...")
            time.sleep(wait)

    print(f"ERROR: All {MAX_RETRIES} attempts failed for [{label}]. Exiting.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Workflow step 1: Design / confirm 10 angles
# ---------------------------------------------------------------------------


def design_angles():
    """Call 1/12: Ask DeepSeek to confirm and refine the ten modeling angles."""
    print("[1/12] Designing ten modeling angles ...")

    system_msg = (
        "You are a mathematical modeling expert specializing in industrial "
        "scheduling, operations research, joint procurement-and-scheduling "
        "optimization, and flexible job-shop scheduling problems (FJSSP). You "
        "will help formulate a rigorous mathematical model for a "
        "multi-workshop overhaul scheduling problem with TWO equipment crews "
        "jointly servicing five workshops, augmented by a $500,000 equipment "
        "procurement decision. The model must inherit the Q2/Q3 innovations: "
        "asynchronous operation-level start times within each process, and "
        "early equipment release. The procurement decision must be integrated "
        "with the scheduling decision under a hard budget constraint."
    )

    angle_list = ""
    for a in ANGLE_DEFINITIONS:
        angle_list += f"\n{a['id']}. **{a['title']}**: {a['description']}\n"

    user_msg = f"""
I am working on Question 4 of the 2026-51MCM Problem B competition.

{PROBLEM_DATA}

I plan to analyze this problem from ten distinct, complementary modeling
angles using ten parallel agents. Below are my proposed ten angles. Please
review, refine if needed, and output a final confirmed list of exactly ten
angles. For each angle, provide:
- Angle ID (1-10)
- Title
- A detailed description of what this angle should cover (3-5 sentences)

Proposed angles:
{angle_list}

Output your response as a structured numbered list. Keep each angle focused
and non-overlapping. Ensure that together, the ten angles cover the complete
mathematical formulation needed for Question 4, with special emphasis on:
- Procurement decision variables and the $500,000 hard budget constraint
- Crew-specific naming and initial location of newly purchased units
  (ACA1-5..., ACA2-5..., etc.)
- The expanded equipment pool used by the scheduling sub-model
- Asynchronous operation-level start times within each process (inherited)
- Early equipment release: each unit is freed at its own e_{{j,t}}, not at PCT_j
- Cross-crew sharing within the same process is permitted (existing or new)
- Workshop C's three-round expansion (C3-C5 repeated three times)
- Bottleneck analysis for single-unit-per-crew equipment types (ASM, HPM)
- Both an integrated CP-SAT model and a two-stage enumeration strategy
- Lexicographic objective: makespan primary, procurement cost optional
- Table 4 (per-equipment-operation) and Table 5 (procurement details) outputs
- The IMPORTANT clarification that crew affiliation is equipment-ownership
  and initial-location information ONLY - NO crew-wide labor cap
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    result = call_deepseek(messages, temperature=0.5, label="design_angles")
    print("  Done.\n")
    return result


# ---------------------------------------------------------------------------
# Workflow steps 2-11: Run each modeling angle
# ---------------------------------------------------------------------------


def run_angle(angle_id, angle_title, angle_description, design_output):
    """Call 2-11/12: One parallel agent for a specific modeling angle."""
    system_msg = (
        "You are a mathematical modeling expert. You are one of ten parallel "
        "agents, each tackling Question 4 of the 2026-51MCM Problem B from a "
        f"specific angle. Your assigned angle is Angle {angle_id}: "
        f"{angle_title}. The problem is a two-crew (Crew 1 and Crew 2) "
        "multi-workshop FJSSP with a $500,000 equipment procurement budget, "
        "asynchronous operation-level start times, and early equipment "
        "release. You must integrate procurement decisions with scheduling "
        "decisions while preserving every Q3 modeling primitive."
    )
    user_msg = f"""
## Your Task

You are Angle {angle_id} agent. Produce a detailed, rigorous mathematical
formulation for Question 4 from the following perspective:

**Angle {angle_id}: {angle_title}**
{angle_description}

## Problem Data

{PROBLEM_DATA}

## Design Phase Output (for context)

{design_output}

## Instructions

1. Write your analysis in well-structured Markdown.
2. Use proper LaTeX math notation ($ ... $ for inline, $$ ... $$ for display).
3. Be rigorous: define all variables, state all assumptions, derive results.
4. This is a multi-workshop problem with the COMBINED equipment pool of Crew 1
   and Crew 2 PLUS additional purchased units chosen under a $500,000 budget,
   shared across five workshops A, B, C, D, E.
5. CRITICAL: Each equipment unit's initial location depends on its crew - both
   for existing units AND for newly purchased units. Crew 1 units start at
   the Crew 1 base; Crew 2 units start at the Crew 2 base. Subsequent
   inter-workshop travel uses the shared, symmetric workshop distance matrix.
6. CRITICAL: Inherit the Q2/Q3 innovations:
   - Asynchronous starts: for a process j needing types t1, t2, use SEPARATE
     start variables s_{{j,t1}}, s_{{j,t2}}; do NOT introduce a single shared
     S_j.
   - Early release: equipment is released at its own operation end e_{{j,t}}
     = s_{{j,t}} + p_{{j,t}}, not at PCT_j.
7. Cross-crew sharing within a process is permitted: the two equipment types
   of one process may be served by units from different crews, including
   newly purchased units.
8. The procurement variables must be defined explicitly (either as integer
   counts y[g, t] or as candidate-unit binaries z[k]) and tied to the
   $500,000 budget.
9. Newly purchased units are named following ACA1-5/ACA2-5/.../HPM2-2 etc.
   with the crew label indicated by the digit before the dash.
10. Pay attention to Workshop C where processes C3->C4->C5 repeat three times.
11. Table 4 must include a "Crew" column derived from the unit's affiliation;
    Table 5 must list the five equipment categories with crew-1 and crew-2
    purchase counts and the total procurement cost.
12. IMPORTANT: do NOT introduce a crew-wide simultaneity cap. Crew affiliation
    is equipment ownership and initial-location information ONLY.
13. Your output will be combined with nine other angles into a final report.
14. Focus ONLY on your assigned angle - do not duplicate other angles' work.
15. Length: aim for 800-1200 words of substantive content.
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    return call_deepseek(messages, temperature=0.7, label=f"angle_{angle_id}")


# ---------------------------------------------------------------------------
# Workflow step 12: Aggregate results
# ---------------------------------------------------------------------------


def aggregate_results(design_output, angle_outputs):
    """Call 12/12: Synthesize all ten angle outputs into a final Markdown report."""
    print("[12/12] Aggregating final report ...")

    system_msg = (
        "You are a mathematical modeling expert and technical writer. Your "
        "task is to synthesize ten parallel modeling analyses into one "
        "coherent, publication-quality Markdown report for Question 4 of "
        "2026-51MCM Problem B. The report must be comprehensive, rigorous, "
        "and ready to guide a CP-SAT or MIP implementation. It must "
        "explicitly preserve and explain the two Q2/Q3 innovations "
        "(asynchronous operation-level starts and early equipment release) "
        "extended to the two-crew, procurement-augmented setting, and it "
        "must integrate the equipment procurement decision under the "
        "$500,000 hard budget with the scheduling decision."
    )

    combined = ""
    for i, output in enumerate(angle_outputs, 1):
        combined += f"\n\n---\n## Angle {i} Output\n\n{output}"

    user_msg = f"""
## Task

Synthesize the ten modeling angle outputs below into a single, coherent
Markdown report for Question 4. Remove duplications and contradictions,
standardize notation, and produce a document that is directly usable for
later coding (CP-SAT or MIP).

## Problem Data

{PROBLEM_DATA}

## Design Phase Output

{design_output}

## Ten Angle Outputs

{combined}

## Required Report Structure

The final report MUST include these sections in order, all with rigorous
LaTeX math notation:

1. **Q4 Problem Interpretation** - jointly determine the equipment procurement
   plan (under a $500,000 hard budget) and the scheduling strategy so that
   the makespan of all overhaul tasks across A, B, C, D, E is minimized.
   Frame Q4 as a strict generalization of Q3.

2. **Raw Data Extracted from the Word Document and Excel Workbook** - the
   Question 4 statement; the Table 4 and Table 5 field lists; the
   "Shortest duration to complete the task of question 4: (s)" line; the five
   Table-5 equipment-name rows; the Process Flow Table data for all five
   workshops with workloads and per-type efficiencies; the Crew Configuration
   Table data with existing equipment IDs by crew and unit prices; and all
   distance tables (Crew-1 base, Crew-2 base, inter-workshop).

3. **Data Inherited from Q3** - two-crew pool of 32 existing units; speed
   2 m/s; initial-distance tables per crew; symmetric inter-workshop
   distance matrix; Workshop C three-round expansion C1 -> C2 -> C3_1 ->
   C4_1 -> C5_1 -> C3_2 -> C4_2 -> C5_2 -> C3_3 -> C4_3 -> C5_3.

4. **Equipment Prices and Procurement Budget** - ACA $50000, ICM $40000,
   PFM $35000, ASM $80000, HPM $75000; total budget $500,000 (hard).

5. **Sets and Indices** - workshops, processes (with C unrolled), crews
   G = {{1, 2}}, equipment types T, existing-unit set U^{{exist}}_g, candidate
   purchased-unit set C_{{g,t}}, effective unit set
   U_t = U^{{exist}}_t cup U^{{new}}_t, type-of-unit map, crew-of-unit map.

6. **Parameters** - processing times p_{{j,t}}, crew-specific initial
   transport times tau_init(g, w), inter-workshop transport times
   tau(w, w'), workloads, efficiencies, existing-unit counts per type per
   crew, unit prices, the $500,000 budget.

7. **Procurement Decision Variables** - both representations:
   y[g, t] in Z_>=0, and z[k] in {{0, 1}} for k in C_{{g,t}}, with mapping
   y[g, t] = sum_{{k in C_{{g,t}}}} z[k]. State derived per-type upper bounds.

8. **Scheduling Decision Variables** - per-operation start s_{{j,t}}, end
   expression e_{{j,t}} = s_{{j,t}} + p_{{j,t}}, process completion PCT_j,
   assignment binaries x_{{j,t,k}} (over the EXPANDED pool), AddCircuit arc
   literals per unit (with z[k] guarding candidates), and makespan C_max.

9. **Objective Function** - primary: minimize C_max, with C_max >= PCT_j for
   every terminal process A3, B4, C5_3, D6, E3.

10. **Budget Constraint** -
    sum_{{g, t}} unit_price[t] * y[g, t] <= 500000.

11. **Equipment-Pool Expansion Constraints** - link z[k] to the actual use
    of candidate units; if z[k] = 0, candidate k must take its
    SOURCE_k -> SINK_k closing arc and contribute no operation.

12. **Assignment Constraints** - each operation (j, t) is served by exactly
    one unit drawn from the EFFECTIVE pool of type t (existing plus
    activated new units across both crews); cross-crew sharing within a
    process is allowed.

13. **Asynchronous Operation-Start Constraints** - per-operation
    s_{{j,t}} are independent for distinct t in E_j.

14. **Process Completion Constraints** -
    PCT_j = max_{{t in E_j}} e_{{j,t}}.

15. **Early Equipment Release Constraints** - the release time of unit k on
    operation (j, t) is e_{{j,t}}, NOT PCT_j.

16. **Equipment Sequencing and Travel Constraints** - if unit k serves both
    (i, t) and (j, t) in that order, then
    s_{{j,t}} >= e_{{i,t}} + tau(w(i), w(j)).

17. **Crew-Specific Initial Travel Constraints for Existing AND New
    Equipment** - the FIRST operation of each unit k satisfies
    s_{{first, t}} >= delta_{{g(k)}}(w) / speed; for candidate units,
    activate this only when z[k] = 1.

18. **Workshop Precedence Constraints** -
    s_{{succ, t}} >= PCT_pred for every (pred, succ) consecutive pair in
    the same workshop and every t in E_succ.

19. **Makespan Constraints** - C_max >= PCT_j for terminal processes.

20. **Optional Lexicographic Objective Explanation** - two-phase solve to
    minimize procurement cost subject to C_max == optimal_makespan.

21. **CP-SAT Implementation Guidance** - IntVar / linear expressions / max
    equality / BoolVar / AddCircuit per unit / OnlyEnforceIf / search
    strategy / symmetry breaking across identical units within the same
    crew, including identical CANDIDATE units.

22. **Two-Stage Enumeration + CP-SAT Solution Strategy** - enumerate
    feasible procurement plans under the budget; for each, solve the
    Q3-style scheduling sub-CP-SAT; choose the plan minimizing makespan;
    optionally tie-break on cost.

23. **Table 4 Output Format** - exact columns including "Crew", followed by
    "Shortest duration to complete the task of question 4: (s)".

24. **Table 5 Procurement Detail Format** - five rows, columns "Equipment
    Name", "Number purchased by crew 1", "Number purchased by crew 2",
    "Total procurement Cost".

25. **Validation Rules** - the nine rules covering both tables: assignment
    correctness, async starts allowed, per-row precedence, PCT consistency,
    per-equipment non-overlap with transport gap, crew-aware initial
    transport, early-release endpoint verification, Table 5 consistency
    with Table 4 crew labels, and total procurement cost <= 500000.

26. **Assumptions and Ambiguity Clarifications** - integer y; one-time crew
    assignment of purchased units; purchased units start at the assigned
    crew's base at time 0; Workshop C workloads PER ROUND; cross-crew
    sharing permitted; no preemption; no return-to-base; no workload
    splitting; integer-second durations.

27. **Important Pitfalls to Avoid** - do NOT add a crew-wide simultaneity
    cap; do NOT couple a process's two equipment-type operations via a
    shared S_j; ensure y[g, t] upper bounds are derived from the budget
    when sizing the candidate pool; remember the FIRST-operation initial
    transport constraint applies to BOTH existing and purchased units.

## Formatting Rules

- Use Markdown headers (## for sections, ### for subsections).
- Use LaTeX math notation for all formulas.
- Include complete data tables as Markdown tables.
- Be precise with all numerical values.
- The report should be self-contained and suitable for inclusion in a
  competition paper.
- Total length: 5500-7500 words.
- Do NOT include any solution numbers or final makespan - this is purely a
  problem formulation document.
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    result = call_deepseek(messages, temperature=0.3, label="aggregate")
    print("  Done.\n")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not DEEPSEEK_API_KEY:
        print("ERROR: Set the DEEPSEEK_API_KEY environment variable first.")
        print("  export DEEPSEEK_API_KEY='your-key-here'")
        sys.exit(1)

    print("=" * 70)
    print("  Question 4 - Two-Crew FJSSP with Equipment Procurement")
    print("  (Budget = $500,000) - Joint Procurement + Scheduling Model")
    print("  DeepSeek Multi-Agent Workflow (12 API calls)")
    print("=" * 70)
    print(f"  Model:       {DEEPSEEK_MODEL}")
    print(f"  Output MD:   {OUTPUT_MD}")
    print(f"  Output Log:  {OUTPUT_LOG}")
    print(f"  Angles JSON: {OUTPUT_ANGLES_JSON}")
    print("=" * 70)
    print()

    # ------------------------------------------------------------------
    # Step 1/12: Design angles
    # ------------------------------------------------------------------
    print("[INFO] Loading reference problem data ...")
    print(f"  - 5 workshops, {len(ANGLE_DEFINITIONS)} modeling angles")
    print(f"  - Existing pool: 2 crews x 16 units = 32 units")
    print(f"  - Procurement budget: $500,000 (hard constraint)")
    print()

    design_output = design_angles()

    # ------------------------------------------------------------------
    # Steps 2-11/12: Run 10 parallel modeling agents
    # ------------------------------------------------------------------
    print("[2-11/12] Running 10 parallel modeling agents ...")
    angle_outputs = [None] * 10

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for angle in ANGLE_DEFINITIONS:
            f = executor.submit(
                run_angle,
                angle["id"],
                angle["title"],
                angle["description"],
                design_output,
            )
            futures[f] = angle["id"]

        for future in as_completed(futures):
            aid = futures[future]
            try:
                result = future.result()
                angle_outputs[aid - 1] = result
                print(f"  Angle {aid:2d} completed.")
            except Exception as e:
                print(f"  Angle {aid:2d} FAILED: {e}")
                sys.exit(1)

    print("  All 10 angles done.\n")

    # Save intermediate angle outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    angle_data = []
    for i, (angle_def, output) in enumerate(
        zip(ANGLE_DEFINITIONS, angle_outputs), 1
    ):
        angle_data.append({
            "angle_id": i,
            "title": angle_def["title"],
            "output": output,
        })

    with open(OUTPUT_ANGLES_JSON, "w", encoding="utf-8") as f:
        json.dump(angle_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Angle outputs saved to: {OUTPUT_ANGLES_JSON}")

    # ------------------------------------------------------------------
    # Step 12/12: Aggregate
    # ------------------------------------------------------------------
    final_md = aggregate_results(design_output, angle_outputs)

    # Save final Markdown
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"[OK] Markdown report saved to: {OUTPUT_MD}")

    # Save full API call log
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(call_log, f, ensure_ascii=False, indent=2)
    print(f"[OK] API call log saved to: {OUTPUT_LOG}")

    print(f"\n[DONE] Total API calls logged: {len(call_log)}")
    print(f"[DONE] Final report: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
