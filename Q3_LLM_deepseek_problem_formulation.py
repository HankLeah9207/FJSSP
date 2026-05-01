#!/usr/bin/env python3
"""
Multi-agent DeepSeek API workflow for Question 3 of 2026-51MCM Problem B.

Generates a rigorous mathematical model for computing the minimum makespan
of Crew 1 AND Crew 2 jointly completing all overhaul tasks across five
workshops A, B, C, D, E. Inherits the Q2 modeling innovations: asynchronous
operation-level start times within a process, and early equipment release.

Workflow: 12 API calls total
  1. Design/confirm 10 distinct modeling angles
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
OUTPUT_MD = os.path.join(OUTPUT_DIR, "Q3_deepseek_problem_formulation.md")
OUTPUT_ANGLES_JSON = os.path.join(OUTPUT_DIR, "Q3_deepseek_angle_outputs.json")
OUTPUT_LOG = os.path.join(OUTPUT_DIR, "Q3_deepseek_problem_formulation_log.json")

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

MAX_RETRIES = 3
BASE_BACKOFF = 2.0
REQUEST_TIMEOUT = 180

# ---------------------------------------------------------------------------
# Problem data (extracted from attachments, Question 3)
# ---------------------------------------------------------------------------

PROBLEM_DATA = """
## Problem Statement (Question 3)

Using the equipment of BOTH Crew 1 AND Crew 2, complete the overhaul tasks for
all five workshops A, B, C, D, and E. Formulate a mathematical model to
compute the minimum time required to complete all tasks. Then, in Table 3,
record for each piece of equipment: the equipment ID, start time, end time,
continuous operation duration, process ID, and the crew to which it belongs.

This is a migration from Question 2 (single-crew) to a two-crew shared
equipment pool. The Q2 modeling innovations must be preserved:
- Asynchronous operation-level start times: when a process needs two equipment
  types, the two equipment operations may start at DIFFERENT times.
- Early equipment release: each equipment unit is released at its own
  operation-end time, NOT at the process completion time of its slowest
  co-worker.

Two-crew specifics:
- A process requiring two equipment types may use units from DIFFERENT crews.
- Each equipment unit's initial location depends on the crew it belongs to:
  Crew 1 units start at the Crew 1 base; Crew 2 units start at the Crew 2
  base. The two bases have different distances to each workshop.
- After leaving the base, all subsequent travel between workshops depends only
  on the inter-workshop distance, regardless of crew affiliation.

## Process Flow Data for All Five Workshops

### Workshop A (Process order: A1 -> A2 -> A3)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| A1 | Defect Filling | Precision Filling Machine 200 m³/h AND Automated Conveying Arm 250 m³/h | 300 m³ |
| A2 | Surface Leveling | High-speed Polishing Machine 100 m³/h AND Industrial Cleaning Machine 250 m³/h | 500 m³ |
| A3 | Strength Testing | Automatic Sensing Multi-Function Machine 100 m³/h | 500 m³ |

### Workshop B (Process order: B1 -> B2 -> B3 -> B4)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| B1 | Surface Cleaning | Industrial Cleaning Machine 100 m³/h | 120 m³ |
| B2 | Base Layer Construction | Precision Filling Machine 200 m³/h AND Automated Conveying Arm 300 m³/h | 1500 m³ |
| B3 | Surface Sealing | Precision Filling Machine 350 m³/h | 360 m³ |
| B4 | Surface Leveling | High-speed Polishing Machine 120 m³/h AND Automatic Sensing Multi-Function Machine 100 m³/h | 360 m³ |

### Workshop C (Process order: C1 -> C2 -> [C3 -> C4 -> C5] x 3)

Note: Processes C3, C4, C5 are repeated three times. Expand the chain as:
C1 -> C2 -> C3_1 -> C4_1 -> C5_1 -> C3_2 -> C4_2 -> C5_2 -> C3_3 -> C4_3 -> C5_3.

| Process | Name | Equipment Required (efficiency) | Workload (per round) |
|---------|------|--------------------------------|----------|
| C1 | Old Coating Removal | Industrial Cleaning Machine 250 m³/h AND Automated Conveying Arm 250 m³/h | 720 m³ |
| C2 | Base Filling | Precision Filling Machine 350 m³/h | 720 m³ |
| C3 | Sealing Coverage | Precision Filling Machine 200 m³/h AND Automated Conveying Arm 250 m³/h | 360 m³ |
| C4 | Surface Grinding | High-speed Polishing Machine 120 m³/h AND Industrial Cleaning Machine 100 m³/h | 400 m³ |
| C5 | Quality Inspection | Automatic Sensing Multi-Function Machine 100 m³/h | 400 m³ |

### Workshop D (Process order: D1 -> D2 -> D3 -> D4 -> D5 -> D6)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| D1 | Debris Removal | Industrial Cleaning Machine 250 m³/h | 600 m³ |
| D2 | Base Solidification | Precision Filling Machine 200 m³/h AND Automated Conveying Arm 300 m³/h | 800 m³ |
| D3 | Surface Sealing | Precision Filling Machine 350 m³/h | 450 m³ |
| D4 | Surface Leveling | High-speed Polishing Machine 120 m³/h AND Automatic Sensing Multi-Function Machine 300 m³/h | 1500 m³ |
| D5 | Load-bearing Inspection | Automatic Sensing Multi-Function Machine 300 m³/h | 1500 m³ |
| D6 | Edge Trimming | High-speed Polishing Machine 100 m³/h | 700 m³ |

### Workshop E (Process order: E1 -> E2 -> E3)

| Process | Name | Equipment Required (efficiency) | Workload |
|---------|------|--------------------------------|----------|
| E1 | Foundation Treatment | Industrial Cleaning Machine 250 m³/h | 1000 m³ |
| E2 | Surface Sealing | Precision Filling Machine 350 m³/h | 600 m³ |
| E3 | Stability Inspection | Automatic Sensing Multi-Function Machine 300 m³/h AND Industrial Cleaning Machine 100 m³/h | 600 m³ |

## Two-Crew Equipment Configuration (32 units total)

### Crew 1 Equipment (16 units)

| Equipment Type | Equipment IDs | Qty | Speed (m/s) |
|---|---|---|---|
| Automated Conveying Arm | Automated Conveying Arm1-1 ~ 1-4 | 4 | 2 |
| Industrial Cleaning Machine | Industrial Cleaning Machine1-1 ~ 1-5 | 5 | 2 |
| Precision Filling Machine | Precision Filling Machine1-1 ~ 1-5 | 5 | 2 |
| Automatic Sensing Multi-Function Machine | Automatic Sensing Multi-Function Machine1-1 | 1 | 2 |
| High-speed Polishing Machine | High-speed Polishing Machine1-1 | 1 | 2 |

### Crew 2 Equipment (16 units)

| Equipment Type | Equipment IDs | Qty | Speed (m/s) |
|---|---|---|---|
| Automated Conveying Arm | Automated Conveying Arm2-1 ~ 2-4 | 4 | 2 |
| Industrial Cleaning Machine | Industrial Cleaning Machine2-1 ~ 2-5 | 5 | 2 |
| Precision Filling Machine | Precision Filling Machine2-1 ~ 2-5 | 5 | 2 |
| Automatic Sensing Multi-Function Machine | Automatic Sensing Multi-Function Machine2-1 | 1 | 2 |
| High-speed Polishing Machine | High-speed Polishing Machine2-1 | 1 | 2 |

### Combined Equipment Pool (per equipment type)

| Equipment Type | Crew 1 Units | Crew 2 Units | Total |
|---|---|---|---|
| Automated Conveying Arm | 4 | 4 | 8 |
| Industrial Cleaning Machine | 5 | 5 | 10 |
| Precision Filling Machine | 5 | 5 | 10 |
| Automatic Sensing Multi-Function Machine | 1 | 1 | 2 |
| High-speed Polishing Machine | 1 | 1 | 2 |

All equipment travels at speed 2 m/s.

## Distance Table

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

Transport time = distance / speed, where speed = 2 m/s for all equipment.
Initial transport time uses the base-to-workshop distance specific to the
crew the equipment unit belongs to.

## Key Assumptions from Problem Statement

1. The sequence of processes within each workshop is fixed; processes must be
   executed strictly in the given order.
2. If a process requires two different types of equipment, both units must
   independently complete the full workload. The process is complete only
   after both have finished. The two units may belong to different crews and
   may start at DIFFERENT times (asynchronous operation-level start).
3. Equipment can be reused across different processes and workshops, but each
   piece of equipment can serve only one process at a time.
4. Equipment transfer within the same workshop has zero transport time.
   Equipment transfer between different workshops requires non-negligible
   transport time = distance / speed.
5. Start time is 00:00:00 (HH:MM:SS). Durations in seconds, rounded up
   (ceiling).
6. No return to base is required at the end.

## Critical Modeling Innovations Inherited from Question 2

### Innovation 1 — Asynchronous operation-level start times

For a process j requiring equipment types t1 and t2, do NOT introduce a
single shared start variable S_j. Instead, introduce one start variable per
operation:
  s_{j,t1}, s_{j,t2}
The two operations may start at different times. The process completion is
the maximum of the two operation ends:
  PCT_j = max(s_{j,t1} + p_{j,t1}, s_{j,t2} + p_{j,t2})

### Innovation 2 — Early equipment release

Each equipment unit is released at its own operation-end time, not at the
process completion time:
  - Operation Completion Time: e_{j,t} = s_{j,t} + p_{j,t}
  - Process Completion Time:   PCT_j   = max_{t in E_j} e_{j,t}
  - Equipment Release Time:    R_{j,k,t} = e_{j,t}  (NOT PCT_j)
  - Next-use constraint: s_{j',t} >= e_{j,t} + transport_time(w_j, w_{j'})
    when the same unit k serves both j and j'.

### Innovation 3 — Per-operation precedence (not per-process)

Workshop precedence is enforced per equipment-type operation of the
successor process:
  s_{succ, t} >= PCT_{pred}   for every t in E_{succ}.

The two innovations together allow a faster equipment unit to leave a process
early and travel to its next assignment without waiting for its slower
co-worker.
"""

# ---------------------------------------------------------------------------
# Predefined ten modeling angles (Question 3)
# ---------------------------------------------------------------------------

ANGLE_DEFINITIONS = [
    {
        "id": 1,
        "title": "Formal Sets, Indices, and Parameter Definitions for the Two-Crew FJSSP",
        "description": (
            "Provide rigorous mathematical definitions of all sets, indices, and "
            "parameters for Question 3. Define the set of workshops "
            "W = {A, B, C, D, E}; the expanded set of processes (with Workshop C's "
            "C3-C5 chain unrolled three times into C3_1..C5_3); the set of crews "
            "G = {1, 2}; the set of equipment types T (5 types); the set of "
            "individual equipment units U partitioned by crew "
            "U = U_1 ∪ U_2 (16 + 16 = 32 units); the equipment-to-process "
            "requirement mapping E_j ⊆ T for each process j; processing times "
            "p_{j,t} = ⌈workload_j / efficiency_{j,t} × 3600⌉; the workshop of "
            "each process w(j); the crew of each unit g(k); and two distance "
            "tables: initial distance δ_g(w) from each crew base g to each "
            "workshop w, and inter-workshop distance d(w, w'). Convert all "
            "distances to transport times using speed 2 m/s. Pay special "
            "attention to indexing conventions distinguishing units of the same "
            "type but from different crews."
        ),
    },
    {
        "id": 2,
        "title": "Operation-Level Asynchronous Scheduling Variables",
        "description": (
            "Formulate the operation-level asynchronous start variables that "
            "constitute one of the two key Q2 innovations carried into Q3. For "
            "each process j and each required equipment type t ∈ E_j, define a "
            "start variable s_{j,t} and an end expression e_{j,t} = s_{j,t} + "
            "p_{j,t}. Define the process completion time PCT_j = max_{t ∈ E_j} "
            "e_{j,t}. Show with a concrete example (e.g., process A1 needing "
            "Precision Filling Machine for 5400 s and Automated Conveying Arm "
            "for 4320 s) how the two operations may start at DIFFERENT times "
            "while still completing the process correctly. Explicitly reject the "
            "naive single shared start S_j formulation. Discuss why this "
            "asynchronous model is strictly more flexible than the synchronous "
            "one, and why the optimal makespan can only be smaller or equal."
        ),
    },
    {
        "id": 3,
        "title": "Two-Crew Equipment Assignment with Cross-Crew Sharing",
        "description": (
            "Model the equipment assignment decision for the combined pool of "
            "32 units (16 per crew). For each operation (j, t), define an "
            "assignment binary x_{j,t,k} = 1 if individual unit k ∈ U_t serves "
            "operation (j, t), where U_t is the set of all units of type t "
            "across BOTH crews. Enforce that exactly one unit is assigned per "
            "operation: ∑_{k ∈ U_t} x_{j,t,k} = 1. Critically, the two equipment "
            "types of the same process may be served by units from DIFFERENT "
            "crews — there is no constraint requiring same-crew co-workers. "
            "Discuss bottleneck types: with only 2 High-speed Polishing Machines "
            "(one per crew) and 2 Automatic Sensing Multi-Function Machines, "
            "these single-per-crew types remain critical resources even after "
            "the doubling. Analyze how the doubled pool of 8 Automated Conveying "
            "Arms and 10 Precision Filling Machines reduces resource contention "
            "compared to Q2."
        ),
    },
    {
        "id": 4,
        "title": "Equipment Path and Crew-Specific Transport-Time Modeling",
        "description": (
            "Formulate the routing of each equipment unit across workshops, "
            "with crew-specific initial positions. For each unit k ∈ U_g (where "
            "g = g(k) is the crew of k), the first workshop visit incurs the "
            "initial transport time τ_init(k, w) = δ_g(w) / speed. Between "
            "consecutive operations on the same unit, the transport time depends "
            "only on the workshop pair: τ(w, w') = d(w, w') / speed; if w = w' "
            "the transport time is zero. Adopt the path-style direct-successor "
            "arc formulation per equipment unit (CP-SAT AddCircuit) introduced "
            "in Q2: SOURCE_k → (j, t) arc carries s_{j,t} ≥ τ_init(k, w(j)); "
            "(i, t) → (j, t) arc carries s_{j,t} ≥ e_{i,t} + τ(w(i), w(j)); "
            "(i, t) → SINK_k arc terminates the path; SOURCE_k → SINK_k arc "
            "models an unused unit; self-loops at unassigned candidates allow "
            "AddCircuit to skip them. Provide the full distance/time table for "
            "BOTH bases and verify symmetry of the inter-workshop matrix."
        ),
    },
    {
        "id": 5,
        "title": "Early Equipment Release Mechanism for the Two-Crew Pool",
        "description": (
            "Provide the rigorous formalization of the early equipment release "
            "mechanism extended to the two-crew pool. For unit k assigned to "
            "operation (j, t), define the release time R_{j,k,t} = e_{j,t} = "
            "s_{j,t} + p_{j,t}, NOT PCT_j. The non-overlap and transport "
            "constraints between two consecutive operations (i, t) and (j, t) on "
            "the same unit k become:\n"
            "  s_{j,t} ≥ e_{i,t} + τ(w(i), w(j))\n"
            "Crucially, the release time of a faster unit is NOT held back by a "
            "slower co-worker in the same process — even when the two co-workers "
            "are from different crews. Provide a concrete example: in process "
            "A1, if a Precision Filling Machine from Crew 1 takes 5400 s while "
            "an Automated Conveying Arm from Crew 2 takes 4320 s, the Conveying "
            "Arm is freed at e_{A1, ACA} = 4320 s + (its own start), so it may "
            "depart for its next workshop while the Filling Machine is still "
            "working. Quantify the makespan reduction this delivers."
        ),
    },
    {
        "id": 6,
        "title": "Intra-Workshop Precedence and Workshop C Three-Round Expansion",
        "description": (
            "Formulate intra-workshop precedence using PER-OPERATION constraints "
            "(not per-process). For each ordered pair (pred, succ) of consecutive "
            "processes in the same workshop, and for each equipment type t ∈ "
            "E_succ, enforce:\n"
            "  s_{succ, t} ≥ PCT_pred\n"
            "where PCT_pred = max_{t' ∈ E_pred} e_{pred, t'}. This is stronger "
            "than enforcing only on the earliest-starting operation of succ. "
            "Carefully expand Workshop C's three-round repetition into 11 "
            "processes: C1 → C2 → C3_1 → C4_1 → C5_1 → C3_2 → C4_2 → C5_2 → "
            "C3_3 → C4_3 → C5_3, each carrying its own (s, e, PCT) variables. "
            "Confirm that the workload-per-round in Workshop C means the "
            "processing time of each round is identical (e.g., C3_1 = C3_2 = "
            "C3_3 in duration), but each round's operations have independent "
            "start variables and may use different equipment units."
        ),
    },
    {
        "id": 7,
        "title": "CP-SAT-Oriented Implementation Design",
        "description": (
            "Design the variable and constraint structure so the model can be "
            "implemented directly in Google OR-Tools CP-SAT. Specify: "
            "IntVar for each s_{j,t} with domain [0, H] where H is a horizon "
            "upper bound; the linear expression e_{j,t} = s_{j,t} + p_{j,t} "
            "without introducing a separate variable; AddMaxEquality to bind "
            "PCT_j; BoolVar for each x_{j,t,k}; arc literals for the path-style "
            "AddCircuit per unit. Detail the AddCircuit construction: for each "
            "unit k, build the candidate node set {SOURCE_k, SINK_k, "
            "(j, t) for every operation that requires type t(k)}, then build "
            "five arc categories (SOURCE → op, op → op, op → SINK, SOURCE → "
            "SINK, self-loops), each guarded by its own arc literal. Show "
            "OnlyEnforceIf bindings between arc literals and timing constraints. "
            "Discuss the makespan variable C_max = max over terminal processes "
            "and how to wire it via AddMaxEquality. Provide search-strategy "
            "hints (DecisionStrategy, num_search_workers, hinting, symmetry "
            "breaking across identical units within the same crew)."
        ),
    },
    {
        "id": 8,
        "title": "MIP / Big-M Alternative Formulation",
        "description": (
            "Provide a complete mixed-integer programming alternative for "
            "solvers that lack CP-SAT's AddCircuit primitive. Use big-M "
            "disjunctive sequencing variables y_{i,j,k} ∈ {0,1} for every "
            "ordered pair of operations of type t(k) sharing unit k:\n"
            "  s_{j,t} ≥ e_{i,t} + τ(w(i), w(j)) − M(1 − y_{i,j,k})\n"
            "  s_{i,t} ≥ e_{j,t} + τ(w(j), w(i)) − M·y_{i,j,k}\n"
            "These are activated only when both operations are assigned to k "
            "(i.e., x_{i,t,k} = x_{j,t,k} = 1). Express PCT_j = max_t e_{j,t} "
            "via PCT_j ≥ e_{j,t} for each t, and minimize C_max ≥ PCT_terminal. "
            "Linearize the conditional initial-transport via:\n"
            "  s_{j,t} ≥ τ_init(k, w(j)) · z_{j,t,k,first}\n"
            "where z is a 'first-on-unit' indicator; alternatively, model the "
            "initial transport via a single-commodity flow from a virtual "
            "depot. Discuss the tradeoffs: the number of big-M sequencing "
            "variables grows with the square of operations per type, which is "
            "manageable for the doubled but still moderate Q3 instance "
            "(≈40-50 operations per common type)."
        ),
    },
    {
        "id": 9,
        "title": "Table 3 Output Format and Validation Rules",
        "description": (
            "Define the exact format of Table 3 as required by the problem "
            "statement: columns are Equipment ID, Start Time (HH:MM:SS), End "
            "Time (HH:MM:SS), Continuous Operation Duration (seconds), Process "
            "ID, and Crew (1 or 2 — derived from the equipment unit's name "
            "suffix). Each row corresponds to a SINGLE equipment-operation, so "
            "a process j requiring two equipment types yields TWO rows in "
            "Table 3, possibly with different Start/End times. State the "
            "validation rules explicitly:\n"
            "1. Assignment correctness: every operation has exactly one row.\n"
            "2. Asynchronous starts allowed: rows of the same process need NOT "
            "share Start Time.\n"
            "3. Per-row precedence: every row of a successor process satisfies "
            "row.Start ≥ PCT_pred, where PCT_pred is the max end-time over the "
            "predecessor's rows.\n"
            "4. PCT consistency: PCT_j equals the max End Time over j's rows.\n"
            "5. Equipment non-overlap: per Equipment ID, rows do not overlap "
            "in time and the gap between consecutive rows is at least the "
            "transport time between their workshops.\n"
            "6. Initial-transport: the first row for each unit must have "
            "Start ≥ δ_{g(k)}(w) / speed, where g(k) is the unit's crew.\n"
            "7. Early-release verification: each row's End Time = s_{j,t} + "
            "p_{j,t}, independent of the process's PCT."
        ),
    },
    {
        "id": 10,
        "title": "Modeling Assumptions, Ambiguities, and Edge Cases",
        "description": (
            "Enumerate all modeling assumptions, identify ambiguities in the "
            "problem statement, and document edge cases:\n"
            "1. Initial transport: Crew 1 units depart from Crew 1 base; Crew 2 "
            "units depart from Crew 2 base. The 00:00:00 reference is the time "
            "at which both crews begin moving, not the time of first operation.\n"
            "2. Workshop C repetition: workloads listed are PER ROUND; processing "
            "times are repeated for each round but with independent start "
            "variables.\n"
            "3. Asynchronous starts: within-process operations of different "
            "types are independent; same-process co-workers may be from "
            "different crews and may begin at different times.\n"
            "4. No preemption: each operation runs without interruption; once "
            "started, it occupies its assigned unit for the full p_{j,t}.\n"
            "5. No splitting: workload per type is indivisible; a single process "
            "operation cannot be served by two units of the same type in "
            "parallel.\n"
            "6. No return-to-base: equipment does not need to return to its "
            "originating base after the schedule completes.\n"
            "7. Cross-crew interaction: the two crews' equipment pools are "
            "fully fungible; there is no penalty or restriction on assigning a "
            "Crew 2 unit to support a Crew 1 unit on the same process.\n"
            "8. Single-unit-per-crew bottlenecks: the Automatic Sensing "
            "Multi-Function Machine and High-speed Polishing Machine each have "
            "only one unit per crew (two total) — analyze whether this remains "
            "a binding constraint after the doubling.\n"
            "9. Distance symmetry: confirm that inter-workshop distances are "
            "symmetric; the base-to-workshop distances are NOT symmetric "
            "between the two crews (each crew has its own initial-distance "
            "table).\n"
            "10. Time integrality: all durations are integer seconds (ceiling "
            "of workload/efficiency × 3600)."
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
        "scheduling, operations research, and flexible job-shop scheduling "
        "problems (FJSSP). You will help formulate a rigorous mathematical "
        "model for a multi-workshop overhaul scheduling problem with TWO "
        "equipment crews jointly servicing five workshops, with inter-workshop "
        "transportation. The model must inherit two innovations from the "
        "single-crew predecessor (Question 2): asynchronous operation-level "
        "start times within each process, and early equipment release."
    )

    angle_list = ""
    for a in ANGLE_DEFINITIONS:
        angle_list += f"\n{a['id']}. **{a['title']}**: {a['description']}\n"

    user_msg = f"""
I am working on Question 3 of the 2026-51MCM Problem B competition.

{PROBLEM_DATA}

I plan to analyze this problem from ten distinct modeling angles using ten
parallel agents. Below are my proposed ten angles. Please review, refine if
needed, and output a final confirmed list of exactly ten angles. For each
angle, provide:
- Angle ID (1-10)
- Title
- A detailed description of what this angle should cover (3-5 sentences)

Proposed angles:
{angle_list}

Output your response as a structured numbered list. Keep each angle focused
and non-overlapping. Ensure that together, the ten angles cover the complete
mathematical formulation needed for Question 3, with special emphasis on:
- The two-crew equipment pool (32 units) and crew-specific initial positions
- Asynchronous operation-level start times within each process (Q2 innovation)
- Early equipment release: each unit is freed at its own e_{{j,t}}, not at PCT_j
- Cross-crew sharing within the same process is permitted
- Workshop C's three-round expansion (C3-C5 repeated three times)
- Bottleneck analysis for single-unit-per-crew equipment types
- Table 3 output requirements including the "Crew" column
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
        "agents, each tackling Question 3 of the 2026-51MCM Problem B from a "
        f"specific angle. Your assigned angle is Angle {angle_id}: "
        f"{angle_title}. The problem is a two-crew (Crew 1 and Crew 2) "
        "multi-workshop FJSSP with asynchronous operation-level start times "
        "and early equipment release."
    )
    user_msg = f"""
## Your Task

You are Angle {angle_id} agent. Produce a detailed, rigorous mathematical
formulation for Question 3 from the following perspective:

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
   and Crew 2 (32 units total) shared across five workshops A, B, C, D, E.
5. CRITICAL: Each equipment unit's initial location depends on its crew —
   Crew 1 units start at the Crew 1 base; Crew 2 units start at the Crew 2
   base. Subsequent inter-workshop travel uses the shared workshop distance
   matrix.
6. CRITICAL: Inherit the Q2 innovations:
   - Asynchronous starts: for a process j needing types t1, t2, use SEPARATE
     start variables s_{{j,t1}}, s_{{j,t2}}; do NOT introduce a single shared
     S_j.
   - Early release: equipment is released at its own operation end e_{{j,t}}
     = s_{{j,t}} + p_{{j,t}}, not at PCT_j.
7. Cross-crew sharing within a process is permitted: the two equipment types
   of one process may be served by units from different crews.
8. Pay attention to Workshop C where processes C3->C4->C5 repeat three times.
9. Table 3 must include a "Crew" column derived from the unit's affiliation.
10. Your output will be combined with nine other angles into a final report.
11. Focus ONLY on your assigned angle — do not duplicate other angles' work.
12. Length: aim for 800-1200 words of substantive content.
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
        "You are a mathematical modeling expert and technical writer. Your task "
        "is to synthesize ten parallel modeling analyses into one coherent, "
        "publication-quality Markdown report for Question 3 of 2026-51MCM "
        "Problem B. The report must be comprehensive, rigorous, and ready to "
        "guide a CP-SAT or MIP implementation. It must explicitly preserve and "
        "explain the two Q2 innovations (asynchronous operation-level starts "
        "and early equipment release) extended to the two-crew setting."
    )

    combined = ""
    for i, output in enumerate(angle_outputs, 1):
        combined += f"\n\n---\n## Angle {i} Output\n\n{output}"

    user_msg = f"""
## Task

Synthesize the ten modeling angle outputs below into a single, coherent
Markdown report for Question 3.

## Problem Data

{PROBLEM_DATA}

## Design Phase Output

{design_output}

## Ten Angle Outputs

{combined}

## Required Report Structure

The final report MUST include these sections in order:

1. **Problem Interpretation for Question 3** — What is being asked: Crew 1
   AND Crew 2 jointly complete all overhaul tasks in workshops A, B, C, D, E
   in minimum time. The combined equipment pool (32 units) is shared across
   workshops with transport delays. Crew 1 units start at Crew 1 base; Crew 2
   units start at Crew 2 base. Cross-crew sharing within a single process is
   allowed. Frame Q3 as a two-crew migration of Q2 that retains both Q2
   innovations.

2. **Extracted Data Structure from the Attachment** — Complete tables of all
   process data for all five workshops, equipment inventory for BOTH crews
   (32 units), TWO initial-distance tables (one per crew base), the
   inter-workshop distance matrix, and computed processing times
   p_{{j,t}} = ⌈workload / efficiency × 3600⌉.

3. **Sets and Indices** — Formal definitions: workshops, processes (with C3-C5
   three-round expansion), crews G = {{1, 2}}, equipment types, equipment units
   partitioned by crew U = U_1 ∪ U_2, type-of-unit map, crew-of-unit map.

4. **Parameters** — All numerical parameters: processing times p_{{j,t}},
   crew-specific initial transport times, inter-workshop transport times,
   workloads, efficiencies, equipment counts per type per crew.

5. **Decision Variables** — Per-operation start variables s_{{j,t}}, end
   expressions e_{{j,t}} = s_{{j,t}} + p_{{j,t}}, process completion variables
   PCT_j, assignment binaries x_{{j,t,k}}, sequencing literals (or AddCircuit
   arc literals), and the makespan variable C_max.

6. **Objective Function** — Minimize C_max with C_max ≥ PCT_j for each
   terminal process (A3, B4, C5_3, D6, E3).

7. **Constraints** — Each as a separate subsection:
   a. Per-operation precedence within each workshop: s_{{succ, t}} ≥ PCT_pred
      for every t ∈ E_succ.
   b. Equipment assignment: each operation receives exactly one unit of the
      required type, drawn from the COMBINED two-crew pool of that type.
   c. Operation timing: e_{{j,t}} = s_{{j,t}} + p_{{j,t}}.
   d. Process completion: PCT_j = max_{{t ∈ E_j}} e_{{j,t}} (asynchronous
      operations may begin at different times).
   e. Early equipment release: a unit k is freed at e_{{j,t}}, not at PCT_j.
   f. Equipment non-overlap with crew-aware transport: for two operations on
      the same unit k, s_{{j,t}} ≥ e_{{i,t}} + τ(w(i), w(j)).
   g. Crew-specific initial transport: the first operation of unit k satisfies
      s_{{first, t}} ≥ δ_{{g(k)}}(w) / speed, where g(k) is the unit's crew.
   h. Makespan: C_max ≥ PCT_j for every terminal process.

8. **Explicit Explanation of Asynchronous Same-Process Starts and Early
   Equipment Release** — With concrete examples drawn from the problem data,
   showing how a faster co-worker (possibly from the other crew) is freed
   early and how the two co-workers may begin at different times.

9. **Two-Crew Initial-Location Modeling** — Explain the per-crew base
   distances, how the model ties each unit to its crew via g(k), and how the
   path-style direct-successor arc model uses crew-specific SOURCE_k → op
   arcs.

10. **CP-SAT-Oriented Implementation Guidance** — How to translate the model
    into OR-Tools CP-SAT: AddMaxEquality for PCT, BoolVar assignment literals,
    path-style AddCircuit per unit (SOURCE → op, op → op, op → SINK,
    SOURCE → SINK, self-loops), OnlyEnforceIf bindings.

11. **Optional MIP / Big-M Alternative** — How to encode the same model as a
    MIP using big-M disjunctive sequencing and indicator-style first-on-unit
    constraints for solvers without AddCircuit.

12. **Table 3 Output Format and Validation Rules** — Columns: Equipment ID,
    Start Time (HH:MM:SS), End Time (HH:MM:SS), Continuous Operation Duration
    (s), Process ID, Crew (1 or 2). One row per equipment-operation. List the
    seven validation rules: assignment correctness, asynchronous starts
    permitted, per-row precedence, PCT consistency, equipment non-overlap with
    transport gap, crew-aware initial transport, early-release endpoint
    verification.

13. **Assumptions and Possible Ambiguities** — Enumerate all assumptions made
    (asynchronous starts within process, early release, cross-crew sharing,
    no preemption, no return-to-base, integer-second durations) and flag any
    ambiguities to be checked before solving.

## Formatting Rules

- Use Markdown headers (## for sections, ### for subsections).
- Use LaTeX math notation for all formulas.
- Include complete data tables as Markdown tables.
- Be precise with all numerical values.
- The report should be self-contained and suitable for inclusion in a
  competition paper.
- Total length: 4500-6500 words.
- Do NOT include any solution or algorithm — this is purely a problem
  formulation document.
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
    print("  Question 3 — Two-Crew Multi-Workshop FJSSP Problem Formulation")
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
    print(f"  - Combined pool: 2 crews x 16 units = 32 units total")
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
