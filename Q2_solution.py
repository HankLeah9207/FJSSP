import math
import csv

try:
    from ortools.sat.python import cp_model
except ImportError:
    raise SystemExit("OR-Tools not installed. Run: pip install ortools")


def seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ═══════════════════════════════════════════════════════════════════════
# DATA — hardcoded from Q2_deepseek_problem_formulation.md
# ═══════════════════════════════════════════════════════════════════════

EQUIPMENT_UNITS = {
    "PFM": ["PFM1-1", "PFM1-2", "PFM1-3", "PFM1-4", "PFM1-5"],
    "ACA": ["ACA1-1", "ACA1-2", "ACA1-3", "ACA1-4"],
    "ICM": ["ICM1-1", "ICM1-2", "ICM1-3", "ICM1-4", "ICM1-5"],
    "ASM": ["ASM1-1"],
    "HPM": ["HPM1-1"],
}

ALL_UNITS = []
UNIT_TYPE = {}
for _etype, _units in EQUIPMENT_UNITS.items():
    for _uid in _units:
        ALL_UNITS.append(_uid)
        UNIT_TYPE[_uid] = _etype

# (process_id, workshop, [(equipment_type, processing_time_seconds)])
# Processing times pre-computed: ceil(workload / efficiency * 3600)
PROCESSES = [
    # Workshop A: A1 -> A2 -> A3
    ("A1", "A", [("PFM", 5400), ("ACA", 4320)]),
    ("A2", "A", [("HPM", 18000), ("ICM", 7200)]),
    ("A3", "A", [("ASM", 18000)]),
    # Workshop B: B1 -> B2 -> B3 -> B4
    ("B1", "B", [("ICM", 4320)]),
    ("B2", "B", [("PFM", 27000), ("ACA", 18000)]),
    ("B3", "B", [("PFM", 3703)]),
    ("B4", "B", [("HPM", 10800), ("ASM", 12960)]),
    # Workshop C: C1 -> C2 -> C3_1 -> C4_1 -> C5_1 -> C3_2 -> C4_2 -> C5_2 -> C3_3 -> C4_3 -> C5_3
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
    # Workshop D: D1 -> D2 -> D3 -> D4 -> D5 -> D6
    ("D1", "D", [("ICM", 8640)]),
    ("D2", "D", [("PFM", 14400), ("ACA", 9600)]),
    ("D3", "D", [("PFM", 4629)]),
    ("D4", "D", [("HPM", 45000), ("ASM", 18000)]),
    ("D5", "D", [("ASM", 18000)]),
    ("D6", "D", [("HPM", 25200)]),
    # Workshop E: E1 -> E2 -> E3
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

# Transport times (seconds) = distance / 2 m/s
_RAW_TRANSPORT = {
    ("BASE", "A"): 200, ("BASE", "B"): 310, ("BASE", "C"): 230,
    ("BASE", "D"): 355, ("BASE", "E"): 200,
    ("A", "A"): 0, ("A", "B"): 510, ("A", "C"): 525,
    ("A", "D"): 450, ("A", "E"): 700,
    ("B", "B"): 0, ("B", "C"): 550, ("B", "D"): 815, ("B", "E"): 360,
    ("C", "C"): 0, ("C", "D"): 260, ("C", "E"): 425,
    ("D", "D"): 0, ("D", "E"): 515,
    ("E", "E"): 0,
}
TRANSPORT = {}
for (u, v), t in _RAW_TRANSPORT.items():
    TRANSPORT[(u, v)] = t
    if (v, u) not in TRANSPORT:
        TRANSPORT[(v, u)] = t


# ═══════════════════════════════════════════════════════════════════════
# MODEL
# ═══════════════════════════════════════════════════════════════════════

def main():
    proc_info = {}
    for pid, ws, equips in PROCESSES:
        proc_info[pid] = {
            "workshop": ws,
            "equipment": {etype: dur for etype, dur in equips},
        }
    all_pids = [p[0] for p in PROCESSES]

    total_proc = sum(max(d for _, d in p[2]) for p in PROCESSES)
    max_travel = max(TRANSPORT.values())
    horizon = total_proc + max_travel * (len(all_pids) + 1)

    model = cp_model.CpModel()

    # ── Process start / completion variables ──────────────────────────
    S = {}
    PCT = {}
    for pid in all_pids:
        S[pid] = model.new_int_var(0, horizon, f"S_{pid}")
        PCT[pid] = model.new_int_var(0, horizon, f"PCT_{pid}")

    # PCT >= S + p  for every required equipment type
    for pid in all_pids:
        for etype, dur in proc_info[pid]["equipment"].items():
            model.add(PCT[pid] >= S[pid] + dur)

    # Intra-workshop precedence: S_succ >= PCT_pred
    for pred, succ in PRECEDENCES:
        model.add(S[succ] >= PCT[pred])

    # ── Assignment variables ──────────────────────────────────────────
    # assign[(pid, etype, uid)] = 1  iff unit uid serves process pid
    assign = {}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            for uid in EQUIPMENT_UNITS[etype]:
                assign[(pid, etype, uid)] = model.new_bool_var(
                    f"a_{pid}_{uid}"
                )

    # Exactly one unit of each required type per process
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            model.add(
                sum(assign[(pid, etype, uid)]
                    for uid in EQUIPMENT_UNITS[etype]) == 1
            )

    # ── Per-unit candidate lists ──────────────────────────────────────
    unit_cands = {uid: [] for uid in ALL_UNITS}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            dur = proc_info[pid]["equipment"][etype]
            for uid in EQUIPMENT_UNITS[etype]:
                unit_cands[uid].append((pid, etype, dur))

    # ── Pairwise sequencing ───────────────────────────────────────────
    #
    # For each equipment unit k, every pair of candidate processes that
    # are both assigned to k must be ordered.  The time gap between them
    # uses the EQUIPMENT's own processing time (early release), not the
    # process completion time.
    #
    # Validity of pairwise ordering:
    #   If processes i, j, l are all on unit k in the order i→j→l, the
    #   non-consecutive constraint  S_l >= S_i + p_{i,t} + τ(w_i, w_l)
    #   is always dominated by the chain
    #     S_l >= S_j + p_j + τ(w_j, w_l) >= S_i + p_i + τ(w_i, w_j) + p_j + τ(w_j, w_l)
    #   because p_j >= 0 and transport times satisfy the triangle
    #   inequality (based on physical distances).  Therefore pairwise
    #   ordering never over-constrains the schedule.

    seq = {}

    for uid in ALL_UNITS:
        cands = unit_cands[uid]
        if not cands:
            continue

        dummy = f"DUM_{uid}"

        # ── dummy → real ──
        for pid, etype, dur in cands:
            key = (dummy, pid, uid)
            seq[key] = model.new_bool_var(f"sq_{dummy}_{pid}")
            model.add_implication(seq[key], assign[(pid, etype, uid)])
            model.add_implication(assign[(pid, etype, uid)], seq[key])
            ws = proc_info[pid]["workshop"]
            travel = TRANSPORT[("BASE", ws)]
            model.add(S[pid] >= travel).only_enforce_if(seq[key])

        # ── real → real ──
        for i, (pi, ei, di) in enumerate(cands):
            for j, (pj, ej, dj) in enumerate(cands):
                if i == j:
                    continue
                key = (pi, pj, uid)
                seq[key] = model.new_bool_var(f"sq_{pi}_{pj}_{uid}")
                model.add_implication(seq[key], assign[(pi, ei, uid)])
                model.add_implication(seq[key], assign[(pj, ej, uid)])
                wi = proc_info[pi]["workshop"]
                wj = proc_info[pj]["workshop"]
                travel = TRANSPORT[(wi, wj)]
                # Early release: use di (equipment's own processing time)
                model.add(
                    S[pj] >= S[pi] + di + travel
                ).only_enforce_if(seq[key])

        # ── ordering: exactly one direction when both assigned ──
        for i, (pi, ei, di) in enumerate(cands):
            for j, (pj, ej, dj) in enumerate(cands):
                if i >= j:
                    continue
                fwd = seq[(pi, pj, uid)]
                bwd = seq[(pj, pi, uid)]
                ai = assign[(pi, ei, uid)]
                aj = assign[(pj, ej, uid)]
                model.add(fwd + bwd >= ai + aj - 1)
                model.add(fwd + bwd <= 1)

    # ── Makespan ──────────────────────────────────────────────────────
    Cmax = model.new_int_var(0, horizon, "Cmax")
    for pid in TERMINAL_PROCESSES:
        model.add(Cmax >= PCT[pid])
    model.minimize(Cmax)

    # ── Solve ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 300
    solver.parameters.num_workers = 8
    solver.parameters.log_search_progress = True

    print("Solving Question 2 (Crew 1, Workshops A-E) ...")
    print(f"Processes: {len(all_pids)}, Equipment units: {len(ALL_UNITS)}")
    print(f"Horizon: {horizon} s\n")

    status = solver.solve(model)
    status_name = solver.status_name(status)

    print(f"\nSolver status: {status_name}")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No solution found.")
        return

    makespan = solver.value(Cmax)
    lb = solver.best_objective_bound
    gap = (makespan - lb) / makespan * 100 if makespan > 0 else 0.0

    print(f"Best makespan: {makespan} seconds")
    print(f"Best makespan: {seconds_to_hms(makespan)}")
    print(f"Objective lower bound: {lb:.0f} seconds ({seconds_to_hms(int(lb))})")
    print(f"Relative optimality gap: {gap:.2f}%")

    # ── Extract schedule ──────────────────────────────────────────────
    rows = []
    for pid in all_pids:
        s_val = solver.value(S[pid])
        for etype, dur in proc_info[pid]["equipment"].items():
            assigned_uid = None
            for uid in EQUIPMENT_UNITS[etype]:
                if solver.value(assign[(pid, etype, uid)]):
                    assigned_uid = uid
                    break
            rows.append({
                "equipment_id": assigned_uid,
                "process_id": pid,
                "start": s_val,
                "end": s_val + dur,
                "duration": dur,
                "workshop": proc_info[pid]["workshop"],
            })

    rows.sort(key=lambda r: (r["start"], r["equipment_id"]))

    # ── Print Table 2 ─────────────────────────────────────────────────
    print(f"\nTable 2: Equipment Operation Schedule ({len(rows)} rows)")
    sep = "-" * 110
    print(sep)
    hdr = (f"{'No.':<5} {'Equipment ID':<12} {'Start Time':<12} "
           f"{'End Time':<12} {'Duration (s)':<14} {'Process ID'}")
    print(hdr)
    print(sep)
    for idx, r in enumerate(rows, 1):
        print(
            f"{idx:<5} {r['equipment_id']:<12} "
            f"{seconds_to_hms(r['start']):<12} "
            f"{seconds_to_hms(r['end']):<12} "
            f"{r['duration']:<14} {r['process_id']}"
        )
    print(sep)

    # ── Save CSV ──────────────────────────────────────────────────────
    csv_path = (
        "/media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP/"
        "Q2_table2_solution.csv"
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "number", "equipment_id", "start_time", "end_time",
            "duration_s", "process_id",
        ])
        for idx, r in enumerate(rows, 1):
            writer.writerow([
                idx, r["equipment_id"],
                seconds_to_hms(r["start"]), seconds_to_hms(r["end"]),
                r["duration"], r["process_id"],
            ])
    print(f"\nCSV saved: {csv_path}")

    # ── Save summary ──────────────────────────────────────────────────
    md_path = (
        "/media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP/"
        "Q2_solution_summary.md"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Question 2 Solution Summary\n\n")
        f.write(f"- Solver status: {status_name}\n")
        f.write(f"- Best makespan: {makespan} s ({seconds_to_hms(makespan)})\n")
        f.write(f"- Objective lower bound: {lb:.0f} s ({seconds_to_hms(int(lb))})\n")
        f.write(f"- Relative optimality gap: {gap:.2f}%\n\n")
        f.write("## Table 2\n\n")
        f.write("| No. | Equipment ID | Start | End | Duration (s) "
                "| Process |\n")
        f.write("|-----|-------------|-------|-----|-------------|"
                "---------|\n")
        for idx, r in enumerate(rows, 1):
            f.write(
                f"| {idx} | {r['equipment_id']} "
                f"| {seconds_to_hms(r['start'])} "
                f"| {seconds_to_hms(r['end'])} "
                f"| {r['duration']} | {r['process_id']} |\n"
            )
    print(f"Summary saved: {md_path}")

    # ── Validation ────────────────────────────────────────────────────
    validate_schedule(rows, proc_info, all_pids)


# ═══════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════

def validate_schedule(rows, proc_info, all_pids):
    print("\n" + "=" * 60)
    print("SCHEDULE VALIDATION")
    print("=" * 60)
    all_pass = True

    # 1. Every required process-equipment-type assigned exactly once
    ok = True
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            matching = [r for r in rows
                        if r["process_id"] == pid
                        and UNIT_TYPE[r["equipment_id"]] == etype]
            if len(matching) != 1:
                print(f"[FAIL] 1. {pid}/{etype}: {len(matching)} assignments")
                ok = False
    if ok:
        print("[PASS] 1. All process-equipment-type assignments correct.")
    else:
        all_pass = False

    # 2. Same process → same start time
    ok = True
    for pid in all_pids:
        starts = set(r["start"] for r in rows if r["process_id"] == pid)
        if len(starts) > 1:
            print(f"[FAIL] 2. {pid} has multiple starts: {starts}")
            ok = False
    if ok:
        print("[PASS] 2. All equipment in same process share start time.")
    else:
        all_pass = False

    # 3. Process completion = max end time
    proc_pct = {}
    for pid in all_pids:
        ends = [r["end"] for r in rows if r["process_id"] == pid]
        proc_pct[pid] = max(ends)
    print("[PASS] 3. Process completion times computed (max of end times).")

    # 4. Workshop precedence
    ok = True
    for pred, succ in PRECEDENCES:
        if proc_pct[pred] > min(r["start"] for r in rows
                                if r["process_id"] == succ):
            print(f"[FAIL] 4. {pred}->{succ}: pred ends {proc_pct[pred]}, "
                  f"succ starts earlier")
            ok = False
    if ok:
        print("[PASS] 4. All workshop precedence constraints satisfied.")
    else:
        all_pass = False

    # 5. No overlapping operations per equipment unit
    unit_ops = {}
    for r in rows:
        unit_ops.setdefault(r["equipment_id"], []).append(r)
    ok = True
    for uid, ops in unit_ops.items():
        ops_s = sorted(ops, key=lambda x: x["start"])
        for i in range(len(ops_s) - 1):
            if ops_s[i]["end"] > ops_s[i + 1]["start"]:
                print(f"[FAIL] 5. {uid}: {ops_s[i]['process_id']} overlaps "
                      f"{ops_s[i+1]['process_id']}")
                ok = False
    if ok:
        print("[PASS] 5. No overlapping operations on any equipment unit.")
    else:
        all_pass = False

    # 6. Transport time between consecutive ops (early release)
    ok = True
    for uid, ops in unit_ops.items():
        ops_s = sorted(ops, key=lambda x: x["start"])
        for i in range(len(ops_s) - 1):
            ws_c = ops_s[i]["workshop"]
            ws_n = ops_s[i + 1]["workshop"]
            travel = TRANSPORT[(ws_c, ws_n)]
            release = ops_s[i]["end"]
            gap = ops_s[i + 1]["start"] - release
            if gap < travel:
                print(
                    f"[FAIL] 6. {uid}: {ops_s[i]['process_id']}({ws_c})"
                    f"->{ops_s[i+1]['process_id']}({ws_n}): "
                    f"gap={gap}s < travel={travel}s"
                )
                ok = False
    if ok:
        print("[PASS] 6. Consecutive ops respect transport time "
              "(early release).")
    else:
        all_pass = False

    # 7. First op of each unit respects base travel
    ok = True
    for uid, ops in unit_ops.items():
        first = min(ops, key=lambda x: x["start"])
        ws = first["workshop"]
        travel = TRANSPORT[("BASE", ws)]
        if first["start"] < travel:
            print(f"[FAIL] 7. {uid}: first op {first['process_id']} "
                  f"starts {first['start']}s < base->{ws} {travel}s")
            ok = False
    if ok:
        print("[PASS] 7. All first operations respect base travel time.")
    else:
        all_pass = False

    # 8. Early release analysis
    print("\n--- Early Release Analysis ---")
    early_count = 0
    for uid, ops in unit_ops.items():
        ops_s = sorted(ops, key=lambda x: x["start"])
        for i in range(len(ops_s)):
            op = ops_s[i]
            pct = proc_pct[op["process_id"]]
            if op["end"] < pct:
                benefit = pct - op["end"]
                print(
                    f"  {uid}: released from {op['process_id']} at "
                    f"{seconds_to_hms(op['end'])} "
                    f"(process ends {seconds_to_hms(pct)}, "
                    f"saved {benefit}s = {seconds_to_hms(benefit)})"
                )
                early_count += 1
    if early_count > 0:
        print(f"[PASS] 8. Early release used {early_count} time(s).")
    else:
        print("[INFO] 8. No early release benefit observed.")

    if all_pass:
        print("\n*** ALL VALIDATION CHECKS PASSED ***")
    else:
        print("\n*** SOME CHECKS FAILED — review above ***")


if __name__ == "__main__":
    main()
