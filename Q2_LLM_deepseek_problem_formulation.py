#!/usr/bin/env python3
"""
Multi-agent DeepSeek API workflow for Question 2 of 2026-51MCM Problem B.

Generates a rigorous mathematical model for computing the minimum makespan
of Crew 1 completing all overhaul tasks across five workshops A, B, C, D, E,
with early equipment release modeling.

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
OUTPUT_MD = os.path.join(OUTPUT_DIR, "Q2_deepseek_problem_formulation.md")
OUTPUT_ANGLES_JSON = os.path.join(OUTPUT_DIR, "Q2_deepseek_angle_outputs.json")
OUTPUT_LOG = os.path.join(OUTPUT_DIR, "Q2_deepseek_problem_formulation_log.json")

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

MAX_RETRIES = 3
BASE_BACKOFF = 2.0
REQUEST_TIMEOUT = 180

# ---------------------------------------------------------------------------
# Problem data (extracted from attachments, Question 2)
# ---------------------------------------------------------------------------

PROBLEM_DATA = """
## Problem Statement (Question 2)

Using only the equipment of Crew 1, complete the overhaul tasks for all five
workshops A, B, C, D, and E. Formulate a mathematical model to compute the
minimum time required to complete all tasks. Then, in Table 2, record for each
piece of equipment: the equipment ID, start time, end time, continuous
operation duration, and the corresponding process ID.

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

Note: Processes C3, C4, C5 are repeated three times. After completing one
round of C3->C4->C5, another two rounds must be carried out.

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

## Crew 1 Equipment Configuration

| Equipment Type | Equipment IDs | Qty | Speed (m/s) |
|---|---|---|---|
| Automated Conveying Arm | Automated Conveying Arm1-1 ~ 1-4 | 4 | 2 |
| Industrial Cleaning Machine | Industrial Cleaning Machine1-1 ~ 1-5 | 5 | 2 |
| Precision Filling Machine | Precision Filling Machine1-1 ~ 1-5 | 5 | 2 |
| Automatic Sensing Multi-Function Machine | Automatic Sensing Multi-Function Machine1-1 | 1 | 2 |
| High-speed Polishing Machine | High-speed Polishing Machine1-1 | 1 | 2 |

## Workshop Distance Table

| Origin | Destination | Distance (m) |
|--------|-------------|---------------|
| Crew 1 | A | 400 |
| Crew 1 | B | 620 |
| Crew 1 | C | 460 |
| Crew 1 | D | 710 |
| Crew 1 | E | 400 |
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

## Key Assumptions from Problem Statement

1. The sequence of processes within each workshop is fixed; processes must be
   executed strictly in the given order.
2. If a process requires two different types of equipment, both must
   independently complete the full workload. The process is complete only after
   both have finished.
3. Equipment can be reused across different processes and workshops, but each
   piece of equipment can serve only one process at a time.
4. Equipment transfer within the same workshop has zero transport time.
   Equipment transfer between different workshops requires non-negligible
   transport time = distance / speed.
5. Start time is 00:00:00 (HH:MM:SS). Durations in seconds, rounded up
   (ceiling).

## Critical Modeling Innovation: Early Equipment Release

For Question 2, equipment is shared across five workshops. A key optimization
is early equipment release:

- Operation Completion Time: OCT_{j,k} = s_{j,k} + p_{j,k}
  (when equipment k finishes its part of process j)
- Process Completion Time: PCT_j = max_{k in required equipment} OCT_{j,k}
  (when all equipment finish for process j)
- Equipment Release Time: R_{j,k} = OCT_{j,k}
  (equipment k is free immediately after its own operation, NOT after the
   entire process finishes)
- Next use constraint: s_{j',k} >= OCT_{j,k} + transport_time(workshop_j, workshop_j')
  (depends on OCT, not PCT)

This distinction is essential because equipment can be reused across workshops.
A faster equipment unit should not be forced to wait for a slower co-worker in
the same process before being transported to another workshop.
"""

# ---------------------------------------------------------------------------
# Predefined ten modeling angles
# ---------------------------------------------------------------------------

ANGLE_DEFINITIONS = [
    {
        "id": 1,
        "title": "Full Mathematical Formulation of the Multi-Workshop Flexible Job-Shop Scheduling Problem",
        "description": (
            "Provide the complete mathematical formulation of Question 2 as a "
            "multi-workshop flexible job-shop scheduling problem (FJSSP). Define "
            "the problem class precisely. State the overall structure: five "
            "workshops with fixed intra-workshop process sequences, a single crew "
            "with shared equipment, inter-workshop transportation times, and "
            "makespan minimization. Identify why this is harder than Q1: equipment "
            "must be scheduled across workshops, creating resource contention and "
            "transportation delays. Provide the full optimization model skeleton "
            "with sets, parameters, variables, objective, and constraint categories."
        ),
    },
    {
        "id": 2,
        "title": "Data Extraction and Definition of Sets, Indices, Parameters, and Processing Times",
        "description": (
            "Extract all numerical data from the problem attachments and organize "
            "them into formal mathematical notation. Define: the set of workshops "
            "W = {A,B,C,D,E}; the set of processes for each workshop; the set of "
            "equipment types and individual units in Crew 1; the equipment-to-process "
            "requirement mapping; processing times p_{j,k} = ceil(workload_j / "
            "efficiency_{j,k} * 3600) for every (process, equipment-type) pair; "
            "the distance matrix and transport times between all workshop pairs and "
            "from Crew 1 base. Pay special attention to Workshop C where processes "
            "C3-C5 repeat three times — define how to index repeated rounds."
        ),
    },
    {
        "id": 3,
        "title": "Crew 1 Equipment Assignment and Identical-Machine Resource Constraints",
        "description": (
            "Model the equipment assignment problem for Crew 1. For equipment types "
            "with multiple identical units (e.g., 5 Precision Filling Machines, 4 "
            "Automated Conveying Arms, 5 Industrial Cleaning Machines), formulate "
            "the assignment decision: which specific unit serves which process. "
            "Define binary assignment variables. Formulate the constraint that each "
            "unit can serve at most one process at a time (non-overlap). Discuss the "
            "key insight that for bottleneck equipment types with only 1 unit "
            "(High-speed Polishing Machine, Automatic Sensing Multi-Function Machine), "
            "all processes requiring that type must be sequenced, creating critical "
            "path bottlenecks. Analyze the resource contention across workshops."
        ),
    },
    {
        "id": 4,
        "title": "Early Equipment Release Mechanism and Operation-Level Resource Occupation",
        "description": (
            "Provide the rigorous mathematical formulation of the early equipment "
            "release mechanism. Define:\n"
            "- Operation Completion Time: OCT_{j,k} = s_{j,k} + p_{j,k}\n"
            "- Process Completion Time: PCT_j = max_{k} OCT_{j,k}\n"
            "- Equipment Release Time: R_{j,k} = OCT_{j,k} (NOT PCT_j)\n"
            "Show that equipment k is occupied during [s_{j,k}, OCT_{j,k}] only, "
            "not during [s_{j,k}, PCT_j]. The non-overlap constraint for equipment "
            "unit k between processes j and j' should be:\n"
            "  s_{j',k} >= OCT_{j,k} + transport_time  OR  s_{j,k} >= OCT_{j',k} + transport_time\n"
            "NOT based on PCT. Provide a concrete example showing how early release "
            "reduces makespan compared to the naive model where equipment waits for "
            "the full process to finish. Explain why this is the key modeling "
            "innovation for Question 2."
        ),
    },
    {
        "id": 5,
        "title": "Workshop Precedence Constraints and Process Completion Logic",
        "description": (
            "Formulate all intra-workshop precedence constraints. For each workshop, "
            "the next process can only start after the current process is fully "
            "completed (PCT). Write:\n"
            "  S_{j+1} >= PCT_j  for consecutive processes within the same workshop.\n"
            "Carefully handle Workshop C where C3->C4->C5 repeat three times. Define "
            "the expanded process sequence: C1, C2, C3_r1, C4_r1, C5_r1, C3_r2, "
            "C4_r2, C5_r2, C3_r3, C4_r3, C5_r3 with precedence constraints between "
            "consecutive elements. Also define the process completion constraint:\n"
            "  PCT_j = max_{k in E_j} (s_{j,k} + p_{j,k})\n"
            "where E_j is the set of equipment types required by process j. Discuss "
            "how within a process, all equipment starts at the process start time "
            "S_j (simultaneous start) but may finish at different times."
        ),
    },
    {
        "id": 6,
        "title": "Inter-Workshop Transportation Time Modeling for Equipment Reuse",
        "description": (
            "Model equipment transportation between workshops. When equipment unit k "
            "finishes process j in workshop w and is next assigned to process j' in "
            "workshop w', the constraint is:\n"
            "  s_{j',k} >= OCT_{j,k} + dist(w, w') / speed_k\n"
            "Note: the transport starts at OCT_{j,k} (early release), not PCT_j. "
            "Also model the initial movement: at time 0, all equipment is at Crew 1 "
            "base. The first process using equipment k in workshop w requires:\n"
            "  s_{first,k} >= dist(Crew1, w) / speed_k\n"
            "Provide the full distance matrix and compute all transport times. "
            "Discuss the scheduling implication: equipment routing across workshops "
            "creates a traveling-salesman-like sub-problem embedded in the scheduling."
        ),
    },
    {
        "id": 7,
        "title": "CP-SAT/MIP-Compatible Variable and Constraint Design",
        "description": (
            "Design the variable and constraint structure so that the model can be "
            "directly implemented in Google OR-Tools CP-SAT solver or a MIP solver. "
            "For CP-SAT: use IntervalVar for each (process, equipment) operation; "
            "use NoOverlap constraints for each equipment unit; use precedence "
            "constraints via AddLinearConstraint. For MIP: use big-M or indicator "
            "constraints for disjunctive scheduling. Define:\n"
            "- Binary sequencing variables y_{j,j',k} = 1 if equipment k serves "
            "process j before j'\n"
            "- Big-M disjunctive constraints for equipment non-overlap\n"
            "- How to linearize the max in PCT_j = max_k OCT_{j,k}\n"
            "Discuss the tradeoff between CP-SAT and MIP formulations for this "
            "problem size."
        ),
    },
    {
        "id": 8,
        "title": "Objective Function, Makespan Minimization, and Lower-Bound Reasoning",
        "description": (
            "Define the objective function precisely:\n"
            "  min C_max where C_max >= PCT_j for all terminal processes "
            "(A3, B4, C5_r3, D6, E3).\n"
            "Derive lower bounds on the optimal makespan:\n"
            "1. Machine-based lower bound: for each equipment type, sum all "
            "processing times across all workshops that need it, plus minimum "
            "transport times between workshops.\n"
            "2. Workshop-based lower bound: for each workshop, sum all process "
            "durations plus initial transport time.\n"
            "3. Critical-path lower bound: identify the longest chain considering "
            "both precedence and resource constraints.\n"
            "Analyze which equipment types are likely bottlenecks (especially the "
            "single-unit types: High-speed Polishing Machine and Automatic Sensing "
            "Multi-Function Machine)."
        ),
    },
    {
        "id": 9,
        "title": "Table 2 Output Structure and Schedule Interpretation",
        "description": (
            "Define exactly what Table 2 should contain based on the problem "
            "statement. Columns: Equipment ID, Start Time, End Time, Duration (s), "
            "Process ID. For each equipment unit, there may be multiple rows (one "
            "per process it serves). Times in HH:MM:SS format. Duration = operation "
            "time p_{j,k}, not process duration. Start/End times are for the "
            "equipment's actual operation, not for the process.\n"
            "Discuss: should transport time be reflected in the table? The equipment "
            "is not 'operating' during transport, so transport gaps appear as idle "
            "time between rows for the same equipment. Verify that for each "
            "equipment unit, its rows do not overlap in time and respect transport "
            "time gaps. Provide the table format template and explain how to "
            "validate the schedule."
        ),
    },
    {
        "id": 10,
        "title": "Modeling Assumptions, Edge Cases, and Consistency Checks",
        "description": (
            "Enumerate all modeling assumptions and identify potential ambiguities:\n"
            "1. Does the initial transport from Crew 1 base count? (Table shows "
            "start at 00:00:00 — clarify whether this means operations or transport.)\n"
            "2. Workshop C repetition: are the workloads for C3-C5 per round or "
            "total? (Per round, based on the problem statement.)\n"
            "3. Can equipment from different workshops start their first process at "
            "different times? (Yes, as long as transport time is respected.)\n"
            "4. Is preemption allowed? (No — each operation runs without interruption.)\n"
            "5. Can multiple units of the same equipment type work on the same "
            "process simultaneously? (No — the workload is indivisible per type.)\n"
            "6. Are there any equipment types that appear in processes across all "
            "five workshops? (Analyze the equipment-process mapping.)\n"
            "7. Consistency check: verify that all equipment types required by all "
            "processes are available in Crew 1.\n"
            "8. Edge case: what if a workshop has no processes that need a certain "
            "equipment type? That equipment need not visit that workshop.\n"
            "9. Validate that early release does not violate any problem constraints."
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
        "model for a multi-workshop overhaul scheduling problem with shared "
        "equipment and inter-workshop transportation."
    )

    angle_list = ""
    for a in ANGLE_DEFINITIONS:
        angle_list += f"\n{a['id']}. **{a['title']}**: {a['description']}\n"

    user_msg = f"""
I am working on Question 2 of the 2026-51MCM Problem B competition.

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
mathematical formulation needed for Question 2, with special emphasis on:
- The early equipment release mechanism (OCT vs PCT distinction)
- Multi-workshop scheduling with transportation
- The Workshop C repetition structure (C3-C5 repeated three times)
- Bottleneck analysis for single-unit equipment types
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
        "agents, each tackling Question 2 of the 2026-51MCM Problem B from a "
        f"specific angle. Your assigned angle is Angle {angle_id}: "
        f"{angle_title}."
    )
    user_msg = f"""
## Your Task

You are Angle {angle_id} agent. Produce a detailed, rigorous mathematical
formulation for Question 2 from the following perspective:

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
4. This is a multi-workshop problem with Crew 1 equipment shared across five
   workshops A, B, C, D, E. Equipment must be transported between workshops.
5. CRITICAL: Model early equipment release correctly. Equipment k is released
   at OCT_{{j,k}} = s_{{j,k}} + p_{{j,k}}, NOT at PCT_j. The next use of
   equipment k depends on OCT_{{j,k}}, not on when the entire process j
   finishes.
6. Pay attention to Workshop C where processes C3->C4->C5 repeat three times.
7. Your output will be combined with nine other angles into a final report.
8. Focus ONLY on your assigned angle — do not duplicate other angles' work.
9. Length: aim for 800-1200 words of substantive content.
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
        "publication-quality Markdown report for Question 2 of 2026-51MCM "
        "Problem B. The report must be comprehensive, rigorous, and ready to "
        "guide a CP-SAT or MIP implementation."
    )

    combined = ""
    for i, output in enumerate(angle_outputs, 1):
        combined += f"\n\n---\n## Angle {i} Output\n\n{output}"

    user_msg = f"""
## Task

Synthesize the ten modeling angle outputs below into a single, coherent
Markdown report for Question 2.

## Problem Data

{PROBLEM_DATA}

## Design Phase Output

{design_output}

## Ten Angle Outputs

{combined}

## Required Report Structure

The final report MUST include these sections in order:

1. **Problem Interpretation for Question 2** — What is being asked: Crew 1
   alone must complete all overhaul tasks in workshops A, B, C, D, E in
   minimum time. Equipment is shared across workshops with transport delays.

2. **Extracted Data Structure from the Attachment** — Complete tables of all
   process data for all five workshops, equipment inventory, distance matrix,
   and computed processing times p_{{j,k}} = ceil(workload / efficiency * 3600).

3. **Sets and Indices** — Formal definitions of all sets: workshops, processes
   (including C3-C5 repetition expansion), equipment types, equipment units.

4. **Parameters** — All numerical parameters: processing times, distances,
   transport times, workloads, efficiencies.

5. **Decision Variables** — Start times, assignment variables, sequencing
   variables, makespan variable.

6. **Objective Function** — Minimize C_max with proper definition.

7. **Constraints** — Each as a separate subsection:
   a. Process precedence within each workshop
   b. Equipment assignment (which unit serves which process)
   c. Operation start and completion times
   d. Process completion as max of required equipment operations:
      PCT_j = max_{{k in E_j}} OCT_{{j,k}}
   e. Early equipment release: R_{{j,k}} = OCT_{{j,k}}, not PCT_j
   f. Equipment non-overlap with early release:
      s_{{j',k}} >= OCT_{{j,k}} + transport_time OR vice versa
   g. Inter-workshop transportation time constraints
   h. Initial movement from Crew 1 base to first assigned workshop
   i. Makespan definition: C_max >= PCT_j for all terminal processes

8. **Explanation of Why Early Release Is Valid and Useful for Question 2** —
   With concrete examples from the problem data.

9. **CP-SAT-Oriented Implementation Notes** — How to translate the model into
   OR-Tools CP-SAT: IntervalVar, NoOverlap, optional intervals, etc.

10. **Table 2 Output Requirements** — Format, columns, interpretation of
    start/end times, how transport gaps appear.

11. **Assumptions and Possible Ambiguities** — List all assumptions made and
    flag any ambiguities that should be checked before solving.

## Formatting Rules

- Use Markdown headers (## for sections, ### for subsections).
- Use LaTeX math notation for all formulas.
- Include complete data tables as Markdown tables.
- Be precise with all numerical values.
- The report should be self-contained and suitable for inclusion in a
  competition paper.
- Total length: 4000-6000 words.
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
    print("  Question 2 — Multi-Workshop FJSSP Problem Formulation")
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
    print(f"  - 5 workshops, {sum(1 for a in ANGLE_DEFINITIONS)} modeling angles")
    print(f"  - Crew 1 equipment: 5 types, 16 units total")
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
