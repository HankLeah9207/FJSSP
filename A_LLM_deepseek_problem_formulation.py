#!/usr/bin/env python3
"""
Multi-agent DeepSeek API workflow for Question 1 of 2026-51MCM Problem B.

Generates a rigorous mathematical model for computing the minimum makespan
of Crew 1 completing all Workshop A processes (A1 -> A2 -> A3).

Workflow: 6 API calls total
  1. Design 4 distinct modeling angles
  2. Run 4 parallel modeling agents (one per angle)
  3. Aggregate into a final Markdown report
"""

import os
import sys
import json
import time
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = "/media/anomalymous/2C0A78860A784EB8/SWJTU/math"
INPUT_DOCX = os.path.join(PROJECT_ROOT, "2026-51MCM-Problem B.docx")
INPUT_XLSX = os.path.join(PROJECT_ROOT, "B-附件.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "FJSSP")
OUTPUT_MD = os.path.join(OUTPUT_DIR, "A_deepseek_problem_formulation.md")
OUTPUT_LOG = os.path.join(OUTPUT_DIR, "A_deepseek_problem_formulation_log.json")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

MAX_RETRIES = 3
BASE_BACKOFF = 2.0
REQUEST_TIMEOUT = 120

# ---------------------------------------------------------------------------
# Problem data (extracted from attachments, Question 1 only)
# ---------------------------------------------------------------------------

PROBLEM_DATA = """
## Problem Statement (Question 1)

Assume that Crew 1 independently undertakes all overhaul tasks in Workshop A.
Formulate a mathematical model to compute the minimum time required for Crew 1
to complete all processes in Workshop A. Then, in Table 1, record for each
piece of equipment: the equipment ID, start time, end time, continuous
operation duration, and the corresponding process ID.

## Workshop A Process Sequence (fixed order: A1 -> A2 -> A3)

### Process A1 — Defect Filling
- Equipment required:
  - Precision filling machine: efficiency = 200 m³/h
  - Automated conveying arm: efficiency = 250 m³/h
- Workload: 300 m³
- Both equipment must independently complete the full 300 m³ workload.
- Process A1 is complete only when BOTH equipment finish their 300 m³.

### Process A2 — Surface Leveling
- Equipment required:
  - High-speed polishing machine: efficiency = 100 m³/h
  - Industrial cleaning machine: efficiency = 250 m³/h
- Workload: 500 m³
- Both equipment must independently complete the full 500 m³ workload.
- Process A2 is complete only when BOTH equipment finish their 500 m³.

### Process A3 — Strength Testing
- Equipment required:
  - Automatic sensing multi-function machine: efficiency = 100 m³/h
- Workload: 500 m³

## Crew 1 Equipment Available (relevant to Workshop A)

| Equipment Type | Equipment ID | Qty | Move Speed |
|---|---|---|---|
| Precision filling machine | 精密灌装机1-1 ~ 1-5 | 5 | 2 m/s |
| Automated conveying arm | 自动化输送臂1-1 ~ 1-4 | 4 | 2 m/s |
| High-speed polishing machine | 高速抛光机1-1 | 1 | 2 m/s |
| Industrial cleaning machine | 工业清洗机1-1 ~ 1-5 | 5 | 2 m/s |
| Automatic sensing multi-function machine | 自动传感多功能机1-1 | 1 | 2 m/s |

## Distance: Crew 1 base to Workshop A = 400 m, move speed = 2 m/s

## Key Assumptions from Problem Statement
1. Processes must execute in strict order: A1 -> A2 -> A3.
2. If a process requires two equipment types, both must independently complete
   the full workload. No ordering or waiting between the two types within a
   process. The process finishes when the slower equipment finishes.
3. Each equipment unit can only serve one process at a time.
4. Equipment transfers within the same workshop have zero transport time.
5. Start time begins at 00:00:00 (HH:MM:SS). Durations are in seconds,
   rounded up (ceiling).

## Expected Numerical Results

- A1: Precision filling machine: ceil(300/200 * 3600) = 5400 s
       Automated conveying arm:   ceil(300/250 * 3600) = 4320 s
       Process A1 duration = max(5400, 4320) = 5400 s

- A2: High-speed polishing machine: ceil(500/100 * 3600) = 18000 s
       Industrial cleaning machine:  ceil(500/250 * 3600) = 7200 s
       Process A2 duration = max(18000, 7200) = 18000 s

- A3: Automatic sensing multi-function machine: ceil(500/100 * 3600) = 18000 s
       Process A3 duration = 18000 s

- Total makespan (no initial transport): 5400 + 18000 + 18000 = 41400 s = 11:30:00
- With initial transport (400m / 2 m/s = 200s): 41600 s = 11:33:20

## Expected Table 1

| # | Equipment ID | Start | End | Duration(s) | Process |
|---|---|---|---|---|---|
| 1 | 精密灌装机1-1 | 00:00:00 | 01:30:00 | 5400 | A1 |
| 2 | 自动化输送臂1-1 | 00:00:00 | 01:12:00 | 4320 | A1 |
| 3 | 高速抛光机1-1 | 01:30:00 | 06:30:00 | 18000 | A2 |
| 4 | 工业清洗机1-1 | 01:30:00 | 03:30:00 | 7200 | A2 |
| 5 | 自动传感多功能机1-1 | 06:30:00 | 11:30:00 | 18000 | A3 |

Total minimum completion time: 41400 s (11 hours 30 minutes)
"""

# ---------------------------------------------------------------------------
# Predefined four modeling angles
# ---------------------------------------------------------------------------

ANGLE_DEFINITIONS = [
    {
        "id": 1,
        "title": "Classical Deterministic Scheduling Formulation",
        "description": (
            "Formulate Question 1 as a classical deterministic scheduling problem "
            "with fixed process order (A1->A2->A3) and makespan minimization. "
            "Define the scheduling problem class (single-workshop flow-shop with "
            "multi-equipment processes). Clearly state decision variables (start/end "
            "times for each process), the objective function (minimize total "
            "completion time), and all constraints (sequential precedence, equipment "
            "availability). Prove that with fixed sequential ordering in a single "
            "workshop, the makespan is simply the sum of individual process durations, "
            "where each process duration is the max over its equipment operation times."
        ),
    },
    {
        "id": 2,
        "title": "Operation-Level Formulation with Early Equipment Release",
        "description": (
            "Formulate Question 1 at the operation level, treating each "
            "(process, equipment-type) pair as an independent operation unit. "
            "Model the early equipment release mechanism: each equipment unit is "
            "released immediately after finishing its assigned workload, even if the "
            "overall process has not yet completed (because another equipment type is "
            "still working). Formally define operation completion vs. process "
            "completion. Analyze why, for Question 1 with strictly sequential "
            "Workshop A processes, early release does not reduce the final makespan, "
            "but is a critical modeling refinement for multi-workshop scheduling in "
            "later questions (Q2-Q4) where released equipment can be reassigned to "
            "other workshops."
        ),
    },
    {
        "id": 3,
        "title": "Mixed-Integer Programming (MIP) Formulation",
        "description": (
            "Provide a rigorous Mixed-Integer Programming formulation for Question 1. "
            "Include: (a) binary assignment variables x_{i,k} indicating whether "
            "equipment k is assigned to process i; (b) continuous start time s_i and "
            "end time e_i variables for each process; (c) continuous start/end time "
            "variables for each equipment operation; (d) precedence constraints "
            "enforcing A1 before A2 before A3; (e) equipment non-overlap constraints "
            "ensuring each equipment serves at most one process at a time; "
            "(f) process completion constraints tying process end time to the maximum "
            "equipment finish time. Write the full objective function min C_max and "
            "all constraint sets with proper mathematical notation. Note that for "
            "Question 1, many binary variables become trivially fixed because each "
            "equipment type appears only in one process, but the MIP formulation "
            "generalizes to Questions 2-4."
        ),
    },
    {
        "id": 4,
        "title": "Computational Solution and Table 1 Construction",
        "description": (
            "Compute the exact numerical solution for Question 1. For each process "
            "(A1, A2, A3), calculate each equipment's processing time using "
            "ceil(workload / efficiency * 3600) in seconds. Determine each process "
            "duration as the max of its equipment times. Compute cumulative start and "
            "end times. Convert all times to HH:MM:SS format. Construct the final "
            "Table 1 with columns: equipment ID, start time, end time, duration (s), "
            "process ID. Also discuss the two interpretations of initial time: "
            "(a) default: first operation starts at 00:00:00, total = 41400 s; "
            "(b) alternative: include initial transport from Crew 1 to Workshop A "
            "(400m / 2 m/s = 200s), total = 41600 s, all times shifted by +200s. "
            "Justify why the default interpretation is preferred based on the "
            "template table showing A1 start = 00:00:00."
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

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
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

            print(
                f"  [{label}] HTTP {resp.status_code} on attempt {attempt}/{MAX_RETRIES}: "
                f"{resp.text[:200]}"
            )
        except requests.exceptions.RequestException as e:
            print(f"  [{label}] Request error on attempt {attempt}/{MAX_RETRIES}: {e}")

        if attempt < MAX_RETRIES:
            wait = BASE_BACKOFF ** attempt
            print(f"  [{label}] Retrying in {wait:.0f}s ...")
            time.sleep(wait)

    print(f"ERROR: All {MAX_RETRIES} attempts failed for [{label}]. Exiting.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Workflow step 1: Design angles
# ---------------------------------------------------------------------------


def design_angles():
    """Call 1/6: Ask DeepSeek to confirm and refine the four modeling angles."""
    system_msg = (
        "You are a mathematical modeling expert specializing in industrial "
        "scheduling and operations research. You will help formulate a rigorous "
        "mathematical model for an overhaul scheduling problem."
    )
    user_msg = f"""
I am working on Question 1 of the 2026-51MCM Problem B competition.

{PROBLEM_DATA}

I plan to analyze this problem from four distinct modeling angles using four
parallel agents. Below are my proposed four angles. Please review, refine if
needed, and output a final confirmed list of exactly four angles. For each
angle, provide:
- Angle ID (1-4)
- Title
- A detailed description of what this angle should cover (3-5 sentences)

Proposed angles:

1. {ANGLE_DEFINITIONS[0]['title']}: {ANGLE_DEFINITIONS[0]['description']}

2. {ANGLE_DEFINITIONS[1]['title']}: {ANGLE_DEFINITIONS[1]['description']}

3. {ANGLE_DEFINITIONS[2]['title']}: {ANGLE_DEFINITIONS[2]['description']}

4. {ANGLE_DEFINITIONS[3]['title']}: {ANGLE_DEFINITIONS[3]['description']}

Output your response as a structured list. Keep each angle focused and
non-overlapping.
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    return call_deepseek(messages, temperature=0.5, label="design_angles")


# ---------------------------------------------------------------------------
# Workflow steps 2-5: Run each modeling angle
# ---------------------------------------------------------------------------


def run_angle(angle_id, angle_title, angle_description, design_output):
    """Call 2-5/6: One parallel agent for a specific modeling angle."""
    system_msg = (
        "You are a mathematical modeling expert. You are one of four parallel "
        "agents, each tackling Question 1 of the 2026-51MCM Problem B from a "
        f"specific angle. Your assigned angle is Angle {angle_id}: "
        f"{angle_title}."
    )
    user_msg = f"""
## Your Task

You are Angle {angle_id} agent. Produce a detailed, rigorous mathematical
formulation for Question 1 from the following perspective:

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
4. Include the numerical computation where relevant to your angle.
5. Your output will be combined with three other angles into a final report.
6. Focus ONLY on your assigned angle — do not duplicate other angles' work.
7. Length: aim for 600-1000 words of substantive content.
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    return call_deepseek(messages, temperature=0.7, label=f"angle_{angle_id}")


# ---------------------------------------------------------------------------
# Workflow step 6: Aggregate results
# ---------------------------------------------------------------------------


def aggregate_results(design_output, angle_outputs):
    """Call 6/6: Synthesize the four angle outputs into a final Markdown report."""
    system_msg = (
        "You are a mathematical modeling expert and technical writer. Your task "
        "is to synthesize four parallel modeling analyses into one coherent, "
        "publication-quality Markdown report for Question 1 of 2026-51MCM "
        "Problem B."
    )

    combined = ""
    for i, output in enumerate(angle_outputs, 1):
        combined += f"\n\n---\n## Angle {i} Output\n\n{output}"

    user_msg = f"""
## Task

Synthesize the four modeling angle outputs below into a single, coherent
Markdown report for Question 1.

## Problem Data

{PROBLEM_DATA}

## Design Phase Output

{design_output}

## Four Angle Outputs

{combined}

## Required Report Structure

The final report MUST include these 12 sections in order:

1. **Problem Interpretation for Question 1** — What is being asked, scope.
2. **Extracted Data for Workshop A and Crew 1** — Tables of process data,
   equipment data, distances.
3. **Assumptions** — Including whether initial transportation from Crew 1 to
   Workshop A is counted. Default: not counted (first operation starts at
   00:00:00). Alternative: counted (adds 200s).
4. **Mathematical Notation** — Define all symbols, sets, indices, parameters.
5. **Objective Function** — Minimize makespan.
6. **Constraints** — Precedence, equipment, process completion.
7. **Early Equipment Release Modeling** — Formal definition and analysis.
8. **Solution Logic** — Step-by-step reasoning for the optimal schedule.
9. **Computed Processing Durations** — Detailed calculation for each process.
10. **Recommended Table 1 Result** — The final schedule table.
11. **Why Early Release Does Not Change Q1 Makespan** — Short explanation.
12. **Final Minimum Completion Time** — State the answer clearly.

## Formatting Rules

- Use Markdown headers (## for sections, ### for subsections).
- Use LaTeX math notation for all formulas.
- Include the Table 1 as a Markdown table.
- Include both the default (41400 s) and alternative (41600 s) interpretations.
- The recommended Table 1 should use the default interpretation (start at
  00:00:00, no initial transport).
- Be precise with numbers: all times in seconds and HH:MM:SS.
- The report should be self-contained and suitable for inclusion in a
  competition paper.
- Total length: 2000-3000 words.
"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    return call_deepseek(messages, temperature=0.3, label="aggregate")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not DEEPSEEK_API_KEY:
        print("ERROR: Set the DEEPSEEK_API_KEY environment variable first.")
        print("  export DEEPSEEK_API_KEY='your-key-here'")
        sys.exit(1)

    print(f"[INFO] Model: {DEEPSEEK_MODEL}")
    print(f"[INFO] Output Markdown: {OUTPUT_MD}")
    print(f"[INFO] Output Log: {OUTPUT_LOG}")
    print()

    # Step 1: Design angles
    print("[1/6] Designing four modeling angles ...")
    design_output = design_angles()
    print("  Done.\n")

    # Steps 2-5: Run 4 parallel modeling agents
    print("[2-5/6] Running 4 parallel modeling agents ...")
    angle_outputs = [None] * 4

    with ThreadPoolExecutor(max_workers=4) as executor:
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
                print(f"  Angle {aid} completed.")
            except Exception as e:
                print(f"  Angle {aid} FAILED: {e}")
                sys.exit(1)

    print("  All 4 angles done.\n")

    # Step 6: Aggregate
    print("[6/6] Aggregating final report ...")
    final_md = aggregate_results(design_output, angle_outputs)
    print("  Done.\n")

    # Save outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"[OK] Markdown report saved to: {OUTPUT_MD}")

    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(call_log, f, ensure_ascii=False, indent=2)
    print(f"[OK] API call log saved to: {OUTPUT_LOG}")

    print(f"\n[DONE] Total API calls logged: {len(call_log)}")


if __name__ == "__main__":
    main()
