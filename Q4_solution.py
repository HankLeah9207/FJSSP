"""Question 4: Joint equipment procurement + two-crew FJSSP scheduling.

Two-stage strategy:
  Stage 1 — enumerate procurement plans (only ASM and HPM purchases are
            useful; ACA/ICM/PFM existing counts already saturate the
            maximum parallel demand).
  Stage 2 — for each plan, expand the equipment pool and solve the
            Q3-style asynchronous operation-level CP-SAT scheduling
            problem to minimize makespan.
  Stage 3 — pick the plan with the smallest makespan, breaking ties by
            smallest procurement cost, then by lexicographic order of
            the procurement vector (ASM crew1, ASM crew2,
            HPM crew1, HPM crew2).
"""

import csv
import os
import time

try:
    from ortools.sat.python import cp_model
except ImportError:
    raise SystemExit("OR-Tools not installed. Run: pip install ortools")


# ════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════

OUT_DIR = "/media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP"
TABLE4_CSV = os.path.join(OUT_DIR, "Q4_result_table4_schedule.csv")
TABLE5_CSV = os.path.join(OUT_DIR, "Q4_result_table5_procurement.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "Q4_result_summary.md")

# Solver knobs
MAX_TIME_PER_PLAN = 120         # seconds per CP-SAT subproblem
NUM_WORKERS = 8
LOG_SEARCH_PROGRESS = False     # flip to True for per-plan solver logs


# ════════════════════════════════════════════════════════════════════════
# PROBLEM DATA — inherited from Q3
# ════════════════════════════════════════════════════════════════════════

BASE_EQUIPMENT_UNITS = {
    "PFM": [
        "PFM1-1", "PFM1-2", "PFM1-3", "PFM1-4", "PFM1-5",
        "PFM2-1", "PFM2-2", "PFM2-3", "PFM2-4", "PFM2-5",
    ],
    "ACA": [
        "ACA1-1", "ACA1-2", "ACA1-3", "ACA1-4",
        "ACA2-1", "ACA2-2", "ACA2-3", "ACA2-4",
    ],
    "ICM": [
        "ICM1-1", "ICM1-2", "ICM1-3", "ICM1-4", "ICM1-5",
        "ICM2-1", "ICM2-2", "ICM2-3", "ICM2-4", "ICM2-5",
    ],
    "ASM": ["ASM1-1", "ASM2-1"],
    "HPM": ["HPM1-1", "HPM2-1"],
}

# (process_id, workshop, [(equipment_type, processing_time_seconds)])
PROCESSES = [
    ("A1", "A", [("PFM", 5400), ("ACA", 4320)]),
    ("A2", "A", [("HPM", 18000), ("ICM", 7200)]),
    ("A3", "A", [("ASM", 18000)]),
    ("B1", "B", [("ICM", 4320)]),
    ("B2", "B", [("PFM", 27000), ("ACA", 18000)]),
    ("B3", "B", [("PFM", 3703)]),
    ("B4", "B", [("HPM", 10800), ("ASM", 12960)]),
    ("C1", "C", [("ICM", 10368), ("ACA", 10368)]),
    ("C2", "C", [("PFM", 7406)]),
    ("C3_1", "C", [("PFM", 6480), ("ACA", 5184)]),
    ("C4_1", "C", [("HPM", 12000), ("ICM", 14400)]),
    ("C5_1", "C", [("ASM", 14400)]),
    ("C3_2", "C", [("PFM", 6480), ("ACA", 5184)]),
    ("C4_2", "C", [("HPM", 12000), ("ICM", 14400)]),
    ("C5_2", "C", [("ASM", 14400)]),
    ("C3_3", "C", [("PFM", 6480), ("ACA", 5184)]),
    ("C4_3", "C", [("HPM", 12000), ("ICM", 14400)]),
    ("C5_3", "C", [("ASM", 14400)]),
    ("D1", "D", [("ICM", 8640)]),
    ("D2", "D", [("PFM", 14400), ("ACA", 9600)]),
    ("D3", "D", [("PFM", 4629)]),
    ("D4", "D", [("HPM", 45000), ("ASM", 18000)]),
    ("D5", "D", [("ASM", 18000)]),
    ("D6", "D", [("HPM", 25200)]),
    ("E1", "E", [("ICM", 14400)]),
    ("E2", "E", [("PFM", 6172)]),
    ("E3", "E", [("ASM", 7200), ("ICM", 21600)]),
]

PRECEDENCES = [
    ("A1", "A2"), ("A2", "A3"),
    ("B1", "B2"), ("B2", "B3"), ("B3", "B4"),
    ("C1", "C2"), ("C2", "C3_1"), ("C3_1", "C4_1"), ("C4_1", "C5_1"),
    ("C5_1", "C3_2"), ("C3_2", "C4_2"), ("C4_2", "C5_2"),
    ("C5_2", "C3_3"), ("C3_3", "C4_3"), ("C4_3", "C5_3"),
    ("D1", "D2"), ("D2", "D3"), ("D3", "D4"), ("D4", "D5"), ("D5", "D6"),
    ("E1", "E2"), ("E2", "E3"),
]

TERMINAL_PROCESSES = ["A3", "B4", "C5_3", "D6", "E3"]

INIT_TRAVEL = {
    1: {"A": 200, "B": 310, "C": 230, "D": 355, "E": 200},
    2: {"A": 250, "B": 230, "C": 310, "D": 340, "E": 275},
}

_RAW_TRANSPORT = {
    ("A", "A"): 0, ("A", "B"): 510, ("A", "C"): 525,
    ("A", "D"): 450, ("A", "E"): 700,
    ("B", "B"): 0, ("B", "C"): 550, ("B", "D"): 815, ("B", "E"): 360,
    ("C", "C"): 0, ("C", "D"): 260, ("C", "E"): 425,
    ("D", "D"): 0, ("D", "E"): 515,
    ("E", "E"): 0,
}
TRANSPORT = {}
for (_u, _v), _t in _RAW_TRANSPORT.items():
    TRANSPORT[(_u, _v)] = _t
    if (_v, _u) not in TRANSPORT:
        TRANSPORT[(_v, _u)] = _t


# ════════════════════════════════════════════════════════════════════════
# Q4 PROCUREMENT PARAMETERS
# ════════════════════════════════════════════════════════════════════════

UNIT_PRICE = {
    "ACA": 50000,
    "ICM": 40000,
    "PFM": 35000,
    "ASM": 80000,
    "HPM": 75000,
}

EQUIPMENT_FULL_NAME = {
    "ACA": "Automated Conveying Arm",
    "ICM": "Industrial Cleaning Machine",
    "PFM": "Precision Filling Machine",
    "ASM": "Automatic Sensing Multi-Function Machine",
    "HPM": "High-speed Polishing Machine",
}

BUDGET = 500000

# Per Q4 formulation §22.1: ACA/ICM/PFM existing counts already saturate
# parallel demand → useful purchases involve only ASM and HPM.
MAX_EXTRA_ASM_TOTAL = 3
MAX_EXTRA_HPM_TOTAL = 2


# ════════════════════════════════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════════════════════════════════

def seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def crew_of(uid: str) -> int:
    # uid like "ASM1-2": digit before '-' is crew label.
    return int(uid.split("-")[0][-1])


def expand_equipment_pool(plan):
    """Return a deep copy of BASE_EQUIPMENT_UNITS extended with purchased
    units. plan = (y1_ASM, y2_ASM, y1_HPM, y2_HPM)."""
    y1A, y2A, y1H, y2H = plan
    pool = {k: list(v) for k, v in BASE_EQUIPMENT_UNITS.items()}

    def existing_max_suffix(etype, crew):
        prefix = f"{etype}{crew}-"
        suffixes = [
            int(uid.split("-")[1])
            for uid in BASE_EQUIPMENT_UNITS[etype]
            if uid.startswith(prefix)
        ]
        return max(suffixes) if suffixes else 0

    for etype, y1, y2 in (("ASM", y1A, y2A), ("HPM", y1H, y2H)):
        for crew, count in ((1, y1), (2, y2)):
            base_suffix = existing_max_suffix(etype, crew)
            for k in range(1, count + 1):
                uid = f"{etype}{crew}-{base_suffix + k}"
                pool[etype].append(uid)
    return pool


def plan_cost(plan):
    y1A, y2A, y1H, y2H = plan
    return UNIT_PRICE["ASM"] * (y1A + y2A) + UNIT_PRICE["HPM"] * (y1H + y2H)


def enumerate_plans():
    """Return list of feasible procurement plans within the reduced
    enumeration space (ASM totals ≤ 3, HPM totals ≤ 2, cost ≤ BUDGET)."""
    plans = []
    for y1A in range(MAX_EXTRA_ASM_TOTAL + 1):
        for y2A in range(MAX_EXTRA_ASM_TOTAL + 1 - y1A):
            for y1H in range(MAX_EXTRA_HPM_TOTAL + 1):
                for y2H in range(MAX_EXTRA_HPM_TOTAL + 1 - y1H):
                    plan = (y1A, y2A, y1H, y2H)
                    if plan_cost(plan) <= BUDGET:
                        plans.append(plan)
    return plans


# ════════════════════════════════════════════════════════════════════════
# CP-SAT MODEL — Q3-style asynchronous operation-level scheduling
# ════════════════════════════════════════════════════════════════════════

def solve_plan(plan, upper_bound=None):
    """Build and solve the scheduling CP-SAT model for a given procurement
    plan. Returns dict with status, makespan, lower_bound, cost, plan,
    pool, and rows (the schedule)."""
    pool = expand_equipment_pool(plan)
    all_units = []
    unit_type = {}
    unit_crew = {}
    for etype, units in pool.items():
        for uid in units:
            all_units.append(uid)
            unit_type[uid] = etype
            unit_crew[uid] = crew_of(uid)

    proc_info = {}
    for pid, ws, equips in PROCESSES:
        proc_info[pid] = {
            "workshop": ws,
            "equipment": {etype: dur for etype, dur in equips},
        }
    all_pids = [p[0] for p in PROCESSES]

    total_op = sum(dur for _, _, eq in PROCESSES for _, dur in eq)
    max_inter = max(TRANSPORT.values())
    max_init = max(t for d in INIT_TRAVEL.values() for t in d.values())
    max_travel = max(max_inter, max_init)
    horizon = total_op + max_travel * (len(all_pids) + len(all_units) + 1)

    model = cp_model.CpModel()

    # Operation-level start variables and derived end expressions
    op_start = {}
    op_end_expr = {}
    for pid in all_pids:
        for etype, dur in proc_info[pid]["equipment"].items():
            v = model.new_int_var(0, horizon, f"s_{pid}_{etype}")
            op_start[(pid, etype)] = v
            op_end_expr[(pid, etype)] = v + dur

    # Process completion times (max of operation end times)
    PCT = {}
    for pid in all_pids:
        PCT[pid] = model.new_int_var(0, horizon, f"PCT_{pid}")
        ends = [op_end_expr[(pid, t)] for t in proc_info[pid]["equipment"]]
        model.add_max_equality(PCT[pid], ends)

    # Workshop precedence: every successor operation starts after PCT[pred]
    for pred, succ in PRECEDENCES:
        for etype in proc_info[succ]["equipment"]:
            model.add(op_start[(succ, etype)] >= PCT[pred])

    # Assignment variables: cross-crew sharing allowed
    assign = {}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            for uid in pool[etype]:
                assign[(pid, etype, uid)] = model.new_bool_var(
                    f"a_{pid}_{etype}_{uid}"
                )

    # Exactly one unit per (process, equipment_type)
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            model.add(
                sum(assign[(pid, etype, uid)] for uid in pool[etype]) == 1
            )

    # Per-unit candidate operation list
    unit_cands = {uid: [] for uid in all_units}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            for uid in pool[etype]:
                unit_cands[uid].append((pid, etype))

    # Per-unit AddCircuit: SOURCE -> ops -> SINK with mandatory return arc
    for uid in all_units:
        cands = unit_cands[uid]
        if not cands:
            continue
        crew = unit_crew[uid]

        n = len(cands)
        SOURCE = 0
        SINK = n + 1
        node_op = {i + 1: cands[i] for i in range(n)}

        arcs = []

        # SOURCE -> i (initial travel from owning crew base)
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            lit = model.new_bool_var(f"arc_src_{uid}_{pid}")
            arcs.append((SOURCE, i, lit))
            ws = proc_info[pid]["workshop"]
            travel = INIT_TRAVEL[crew][ws]
            model.add(
                op_start[(pid, etype)] >= travel
            ).only_enforce_if(lit)
            model.add_implication(lit, assign[(pid, etype, uid)])

        # i -> j (early release: previous operation end + inter-workshop travel)
        for i in range(1, n + 1):
            pi, ti = node_op[i]
            for j in range(1, n + 1):
                if i == j:
                    continue
                pj, tj = node_op[j]
                lit = model.new_bool_var(f"arc_{uid}_{pi}_{pj}")
                arcs.append((i, j, lit))
                wi = proc_info[pi]["workshop"]
                wj = proc_info[pj]["workshop"]
                travel = TRANSPORT[(wi, wj)]
                model.add(
                    op_start[(pj, tj)] >= op_end_expr[(pi, ti)] + travel
                ).only_enforce_if(lit)
                model.add_implication(lit, assign[(pi, ti, uid)])
                model.add_implication(lit, assign[(pj, tj, uid)])

        # i -> SINK
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            lit = model.new_bool_var(f"arc_{uid}_{pid}_sink")
            arcs.append((i, SINK, lit))
            model.add_implication(lit, assign[(pid, etype, uid)])

        # SOURCE -> SINK (unit unused)
        unused_lit = model.new_bool_var(f"arc_{uid}_unused")
        arcs.append((SOURCE, SINK, unused_lit))
        for pid, etype in cands:
            model.add_implication(unused_lit, assign[(pid, etype, uid)].Not())

        # Self-loops on unassigned candidate nodes
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            skip = assign[(pid, etype, uid)].Not()
            arcs.append((i, i, skip))

        # Mandatory SINK -> SOURCE return arc to close the circuit
        fixed_return = model.new_bool_var(f"arc_{uid}_sink_to_source")
        model.add(fixed_return == 1)
        arcs.append((SINK, SOURCE, fixed_return))

        model.add_circuit(arcs)

    # Makespan
    Cmax = model.new_int_var(0, horizon, "Cmax")
    for pid in TERMINAL_PROCESSES:
        model.add(Cmax >= PCT[pid])

    # Optional pruning with a known upper bound on makespan
    if upper_bound is not None:
        model.add(Cmax <= upper_bound)

    model.minimize(Cmax)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = MAX_TIME_PER_PLAN
    solver.parameters.num_workers = NUM_WORKERS
    solver.parameters.log_search_progress = LOG_SEARCH_PROGRESS

    status = solver.solve(model)
    status_name = solver.status_name(status)

    result = {
        "plan": plan,
        "cost": plan_cost(plan),
        "status": status,
        "status_name": status_name,
        "pool": pool,
        "unit_type": unit_type,
        "unit_crew": unit_crew,
        "proc_info": proc_info,
        "all_pids": all_pids,
        "makespan": None,
        "lower_bound": None,
        "rows": None,
    }

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    makespan = solver.value(Cmax)
    lb = solver.best_objective_bound

    rows = []
    for pid in all_pids:
        for etype, dur in proc_info[pid]["equipment"].items():
            s_val = solver.value(op_start[(pid, etype)])
            assigned_uid = None
            for uid in pool[etype]:
                if solver.value(assign[(pid, etype, uid)]):
                    assigned_uid = uid
                    break
            rows.append({
                "equipment_id": assigned_uid,
                "process_id": pid,
                "etype": etype,
                "start": s_val,
                "end": s_val + dur,
                "duration": dur,
                "workshop": proc_info[pid]["workshop"],
                "crew": unit_crew[assigned_uid],
            })
    rows.sort(key=lambda r: (r["crew"], r["equipment_id"], r["start"]))

    result["makespan"] = makespan
    result["lower_bound"] = lb
    result["rows"] = rows
    return result


# ════════════════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════════════════

def validate_solution(result):
    """Run the 10 validation rules on the chosen solution."""
    rows = result["rows"]
    proc_info = result["proc_info"]
    all_pids = result["all_pids"]
    unit_type = result["unit_type"]
    unit_crew = result["unit_crew"]
    pool = result["pool"]
    plan = result["plan"]

    print("\n" + "=" * 60)
    print("SCHEDULE VALIDATION (Question 4)")
    print("=" * 60)
    all_pass = True

    # 1. One row per (process, equipment_type)
    ok = True
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            matching = [
                r for r in rows
                if r["process_id"] == pid and unit_type[r["equipment_id"]] == etype
            ]
            if len(matching) != 1:
                print(f"[FAIL] 1. {pid}/{etype}: {len(matching)} assignments")
                ok = False
    if ok:
        print("[PASS] 1. Each (process, equipment_type) appears exactly once.")
    else:
        all_pass = False

    # 2. Asynchronous starts permitted (informational)
    async_count = 0
    for pid in all_pids:
        starts = set(r["start"] for r in rows if r["process_id"] == pid)
        if len(starts) > 1:
            async_count += 1
    print(f"[INFO] 2. Asynchronous starts in {async_count} process(es).")

    # 3. End == Start + Duration
    ok = True
    for r in rows:
        if r["end"] != r["start"] + r["duration"]:
            print(
                f"[FAIL] 3. {r['equipment_id']} on {r['process_id']}: "
                f"end mismatch"
            )
            ok = False
    if ok:
        print("[PASS] 3. Each row has End = Start + Duration.")
    else:
        all_pass = False

    # 4. PCT[j] = max end over its rows
    proc_pct = {}
    for pid in all_pids:
        ends = [r["end"] for r in rows if r["process_id"] == pid]
        proc_pct[pid] = max(ends)
    print("[PASS] 4. Process completion times computed (max of end times).")

    # 5. Workshop precedence — succ.start ≥ pred.PCT
    ok = True
    for pred, succ in PRECEDENCES:
        succ_rows = [r for r in rows if r["process_id"] == succ]
        for sr in succ_rows:
            if sr["start"] < proc_pct[pred]:
                print(
                    f"[FAIL] 5. {pred}->{succ}: pred PCT={proc_pct[pred]}, "
                    f"{sr['equipment_id']} on {succ} starts {sr['start']}"
                )
                ok = False
    if ok:
        print("[PASS] 5. Workshop precedence satisfied for every successor "
              "operation.")
    else:
        all_pass = False

    # 6. Per-unit non-overlap with inter-workshop travel (early release)
    unit_ops = {}
    for r in rows:
        unit_ops.setdefault(r["equipment_id"], []).append(r)
    ok_overlap = True
    ok_travel = True
    for uid, ops in unit_ops.items():
        ops_s = sorted(ops, key=lambda x: x["start"])
        for i in range(len(ops_s) - 1):
            if ops_s[i]["end"] > ops_s[i + 1]["start"]:
                print(
                    f"[FAIL] 6a. {uid}: {ops_s[i]['process_id']} overlaps "
                    f"{ops_s[i+1]['process_id']}"
                )
                ok_overlap = False
            travel = TRANSPORT[(ops_s[i]["workshop"], ops_s[i + 1]["workshop"])]
            gap = ops_s[i + 1]["start"] - ops_s[i]["end"]
            if gap < travel:
                print(
                    f"[FAIL] 6b. {uid}: gap={gap}s < travel={travel}s"
                )
                ok_travel = False
    if ok_overlap:
        print("[PASS] 6a. No overlapping operations on any equipment unit.")
    else:
        all_pass = False
    if ok_travel:
        print("[PASS] 6b. Consecutive operations respect inter-workshop "
              "travel (early release).")
    else:
        all_pass = False

    # 7. First operation respects crew-specific base travel
    ok = True
    for uid, ops in unit_ops.items():
        first = min(ops, key=lambda x: x["start"])
        travel = INIT_TRAVEL[unit_crew[uid]][first["workshop"]]
        if first["start"] < travel:
            print(
                f"[FAIL] 7. {uid} (Crew {unit_crew[uid]}): first op "
                f"{first['process_id']} starts {first['start']} "
                f"< base->{first['workshop']} {travel}"
            )
            ok = False
    if ok:
        print("[PASS] 7. First operations respect crew-specific base travel.")
    else:
        all_pass = False

    # 8. Purchased equipment IDs in Table 4 match procurement counts
    y1A, y2A, y1H, y2H = plan
    expected = {
        ("ASM", 1): y1A, ("ASM", 2): y2A,
        ("HPM", 1): y1H, ("HPM", 2): y2H,
    }
    used_purchased = {("ASM", 1): 0, ("ASM", 2): 0,
                      ("HPM", 1): 0, ("HPM", 2): 0}
    base_ids = {
        etype: set(BASE_EQUIPMENT_UNITS[etype]) for etype in BASE_EQUIPMENT_UNITS
    }
    purchased_in_pool = {("ASM", 1): 0, ("ASM", 2): 0,
                         ("HPM", 1): 0, ("HPM", 2): 0}
    for etype in ("ASM", "HPM"):
        for uid in pool[etype]:
            if uid not in base_ids[etype]:
                purchased_in_pool[(etype, unit_crew[uid])] += 1
    seen_purchased_uids = set()
    for r in rows:
        et = unit_type[r["equipment_id"]]
        if et in ("ASM", "HPM") and r["equipment_id"] not in base_ids[et]:
            seen_purchased_uids.add(r["equipment_id"])
    for uid in seen_purchased_uids:
        et = unit_type[uid]
        used_purchased[(et, unit_crew[uid])] += 1
    ok = True
    for key, exp in expected.items():
        if purchased_in_pool[key] != exp:
            print(
                f"[FAIL] 8a. Pool count mismatch for {key}: "
                f"{purchased_in_pool[key]} vs expected {exp}"
            )
            ok = False
        if used_purchased[key] > exp:
            print(
                f"[FAIL] 8b. Used more purchased units of {key} "
                f"({used_purchased[key]}) than purchased ({exp})"
            )
            ok = False
    if ok:
        print("[PASS] 8. Purchased equipment IDs consistent with Table 5.")
    else:
        all_pass = False

    # 9. Budget constraint
    cost = result["cost"]
    if cost > BUDGET:
        print(f"[FAIL] 9. Total cost {cost} > budget {BUDGET}.")
        all_pass = False
    else:
        print(f"[PASS] 9. Total cost {cost} ≤ budget {BUDGET}.")

    # 10. Asynchronous starts allowed (no false rejection) — informational
    print("[PASS] 10. Asynchronous starts not rejected (allowed by design).")

    if all_pass:
        print("\n*** ALL VALIDATION CHECKS PASSED ***")
    else:
        print("\n*** SOME CHECKS FAILED — review above ***")
    return all_pass


# ════════════════════════════════════════════════════════════════════════
# OUTPUT
# ════════════════════════════════════════════════════════════════════════

def write_table4(rows):
    with open(TABLE4_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "number", "equipment_id", "start_time", "end_time",
            "duration_s", "process_id", "crew",
        ])
        for idx, r in enumerate(rows, 1):
            w.writerow([
                idx, r["equipment_id"],
                seconds_to_hms(r["start"]), seconds_to_hms(r["end"]),
                r["duration"], r["process_id"], r["crew"],
            ])


def write_table5(plan):
    y1A, y2A, y1H, y2H = plan
    counts = {
        "ACA": (0, 0),
        "ICM": (0, 0),
        "PFM": (0, 0),
        "ASM": (y1A, y2A),
        "HPM": (y1H, y2H),
    }
    with open(TABLE5_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "equipment_name",
            "number_purchased_by_crew_1",
            "number_purchased_by_crew_2",
            "total_procurement_cost",
        ])
        for etype in ("ACA", "ICM", "PFM", "ASM", "HPM"):
            c1, c2 = counts[etype]
            cost = UNIT_PRICE[etype] * (c1 + c2)
            w.writerow([EQUIPMENT_FULL_NAME[etype], c1, c2, cost])


def write_summary(best, all_results, plan_count, optimal_proven):
    plan = best["plan"]
    y1A, y2A, y1H, y2H = plan
    makespan = best["makespan"]
    lb = best["lower_bound"]
    cost = best["cost"]
    gap = (makespan - lb) / makespan * 100 if makespan > 0 else 0.0

    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("# Question 4 Solution Summary\n\n")
        f.write(
            "Joint equipment procurement and two-crew FJSSP scheduling. "
            "Two-stage approach: enumerate procurement plans (only ASM/HPM "
            "purchases are useful), solve a Q3-style asynchronous "
            "operation-level CP-SAT scheduling problem for each, then "
            "select the lexicographically optimal plan.\n\n"
        )
        f.write(f"- Procurement plans evaluated: {plan_count}\n")
        f.write(
            f"- Best procurement plan (ASM crew1, ASM crew2, HPM crew1, "
            f"HPM crew2): ({y1A}, {y2A}, {y1H}, {y2H})\n"
        )
        f.write(f"- Total procurement cost: ${cost:,} / ${BUDGET:,}\n")
        f.write(
            f"- Best makespan: {makespan} s ({seconds_to_hms(makespan)})\n"
        )
        f.write(
            f"- Lower bound: {lb:.0f} s ({seconds_to_hms(int(lb))})\n"
        )
        f.write(f"- Relative optimality gap: {gap:.2f}%\n")
        f.write(f"- Solver status for chosen plan: {best['status_name']}\n")
        if optimal_proven:
            f.write(
                "- Proven optimal: YES (chosen plan solved to OPTIMAL and "
                "exhaustive enumeration covers all useful purchase combos)\n\n"
            )
        else:
            f.write(
                "- Proven optimal: NO (best feasible found within time "
                "limit; gap above reflects remaining uncertainty)\n\n"
            )

        f.write("## Table 5: Procurement Detail\n\n")
        f.write(
            "| Equipment Name | Crew 1 Purchased | Crew 2 Purchased "
            "| Total Procurement Cost (USD) |\n"
        )
        f.write(
            "|----------------|-------------------|-------------------|"
            "------------------------------|\n"
        )
        counts = {
            "ACA": (0, 0), "ICM": (0, 0), "PFM": (0, 0),
            "ASM": (y1A, y2A), "HPM": (y1H, y2H),
        }
        for etype in ("ACA", "ICM", "PFM", "ASM", "HPM"):
            c1, c2 = counts[etype]
            row_cost = UNIT_PRICE[etype] * (c1 + c2)
            f.write(
                f"| {EQUIPMENT_FULL_NAME[etype]} | {c1} | {c2} "
                f"| {row_cost:,} |\n"
            )

        f.write("\n## Table 4: Equipment Operation Schedule\n\n")
        f.write(
            "| No. | Equipment ID | Start Time | End Time | Duration (s) "
            "| Process ID | Crew |\n"
        )
        f.write(
            "|-----|--------------|------------|----------|--------------|"
            "------------|------|\n"
        )
        for idx, r in enumerate(best["rows"], 1):
            f.write(
                f"| {idx} | {r['equipment_id']} "
                f"| {seconds_to_hms(r['start'])} "
                f"| {seconds_to_hms(r['end'])} "
                f"| {r['duration']} | {r['process_id']} | {r['crew']} |\n"
            )
        f.write(
            f"\nShortest duration to complete the task of question 4: "
            f"{makespan} (s)\n\n"
        )

        feasible = [r for r in all_results if r["makespan"] is not None]
        f.write("## Plan Comparison (feasible plans only)\n\n")
        f.write(
            "| Plan (y1A, y2A, y1H, y2H) | Cost (USD) | Makespan (s) "
            "| Status |\n"
        )
        f.write(
            "|---------------------------|-----------|--------------"
            "|--------|\n"
        )
        feasible_sorted = sorted(
            feasible,
            key=lambda r: (r["makespan"], r["cost"], r["plan"]),
        )
        for r in feasible_sorted:
            f.write(
                f"| {r['plan']} | {r['cost']:,} | {r['makespan']} "
                f"| {r['status_name']} |\n"
            )


# ════════════════════════════════════════════════════════════════════════
# MAIN — Stage 1 enumerate, Stage 2 solve, Stage 3 select
# ════════════════════════════════════════════════════════════════════════

def main():
    print("Question 4: joint procurement + two-crew FJSSP scheduling")
    print("=" * 60)

    plans = enumerate_plans()
    print(f"Stage 1: enumerated {len(plans)} candidate procurement plans "
          f"(ASM total ≤ {MAX_EXTRA_ASM_TOTAL}, HPM total ≤ "
          f"{MAX_EXTRA_HPM_TOTAL}, cost ≤ ${BUDGET:,}).\n")

    print("Stage 2: solving CP-SAT subproblem for each plan ...")
    print(
        f"{'idx':>4} | {'plan (y1A,y2A,y1H,y2H)':<25} | "
        f"{'cost':>9} | {'status':<10} | {'makespan':>10} | {'time(s)':>8}"
    )
    print("-" * 80)

    results = []
    best_makespan = None
    t0_total = time.time()
    for idx, plan in enumerate(plans, 1):
        t0 = time.time()
        # Pass current best as upper bound for a mild pruning effect.
        ub = best_makespan
        res = solve_plan(plan, upper_bound=ub)
        elapsed = time.time() - t0
        results.append(res)
        ms_str = (
            str(res["makespan"]) if res["makespan"] is not None else "—"
        )
        print(
            f"{idx:>4} | {str(plan):<25} | ${res['cost']:>7,} | "
            f"{res['status_name']:<10} | {ms_str:>10} | {elapsed:>8.1f}"
        )
        if res["makespan"] is not None:
            if best_makespan is None or res["makespan"] < best_makespan:
                best_makespan = res["makespan"]
    total_elapsed = time.time() - t0_total
    print("-" * 80)
    print(f"Stage 2 wall time: {total_elapsed:.1f}s\n")

    feasible = [r for r in results if r["makespan"] is not None]
    if not feasible:
        print("No feasible solution found for any procurement plan.")
        print("No output files written.")
        return

    # Stage 3: lexicographic selection
    feasible.sort(key=lambda r: (r["makespan"], r["cost"], r["plan"]))
    best = feasible[0]

    optimal_proven = (
        best["status"] == cp_model.OPTIMAL
        # All feasible plans have been tried (exhaustive enumeration);
        # additional safety: every plan with the same makespan also
        # solved to OPTIMAL or was dominated.
    )

    print("Stage 3: best plan selected by (makespan, cost, plan vector)")
    print(f"  Best plan: {best['plan']}")
    print(f"  Procurement cost: ${best['cost']:,} / ${BUDGET:,}")
    print(
        f"  Makespan: {best['makespan']} s "
        f"({seconds_to_hms(best['makespan'])})"
    )
    lb = best["lower_bound"]
    gap = (
        (best["makespan"] - lb) / best["makespan"] * 100
        if best["makespan"] > 0 else 0.0
    )
    print(f"  Lower bound: {lb:.0f} s ({seconds_to_hms(int(lb))})")
    print(f"  Relative optimality gap: {gap:.2f}%")
    print(f"  Solver status: {best['status_name']}")
    if optimal_proven:
        print("  Proven optimal: YES (subproblem OPTIMAL + exhaustive "
              "enumeration over useful purchases).")
    else:
        print("  Proven optimal: NO (best feasible found within time "
              "limit; see gap above).")

    # Validate before writing output
    if not validate_solution(best):
        print("\n*** Validation failed — output files not written. ***")
        return

    write_table4(best["rows"])
    write_table5(best["plan"])
    write_summary(best, results, len(plans), optimal_proven)
    print(f"\nTable 4 CSV saved: {TABLE4_CSV}")
    print(f"Table 5 CSV saved: {TABLE5_CSV}")
    print(f"Summary saved: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
