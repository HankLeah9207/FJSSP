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
# MODEL — asynchronous operation-level CP-SAT formulation
# ═══════════════════════════════════════════════════════════════════════

def main():
    proc_info = {}
    for pid, ws, equips in PROCESSES:
        proc_info[pid] = {
            "workshop": ws,
            "equipment": {etype: dur for etype, dur in equips},
        }
    all_pids = [p[0] for p in PROCESSES]

    # Horizon: sum of all operation durations + transport buffer
    total_op = sum(dur for _, _, eq in PROCESSES for _, dur in eq)
    max_travel = max(TRANSPORT.values())
    horizon = total_op + max_travel * (len(all_pids) + len(ALL_UNITS) + 1)

    model = cp_model.CpModel()

    # ── Operation-level start variables ───────────────────────────────
    # op_start[(pid, etype)] is the start time of the operation that
    # equipment of type `etype` performs on process `pid`. Multiple
    # operations of the same process may start asynchronously.
    op_start = {}
    op_end_expr = {}  # linear expression: op_start + duration
    for pid in all_pids:
        for etype, dur in proc_info[pid]["equipment"].items():
            v = model.new_int_var(0, horizon, f"s_{pid}_{etype}")
            op_start[(pid, etype)] = v
            op_end_expr[(pid, etype)] = v + dur

    # Process completion = max over operation end times
    PCT = {}
    for pid in all_pids:
        PCT[pid] = model.new_int_var(0, horizon, f"PCT_{pid}")
        ends = [op_end_expr[(pid, t)] for t in proc_info[pid]["equipment"]]
        model.add_max_equality(PCT[pid], ends)

    # Intra-workshop precedence: every operation of succ starts after PCT[pred]
    for pred, succ in PRECEDENCES:
        for etype in proc_info[succ]["equipment"]:
            model.add(op_start[(succ, etype)] >= PCT[pred])

    # ── Assignment variables ──────────────────────────────────────────
    # assign[(pid, etype, uid)] = 1 iff unit uid serves process pid
    assign = {}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            for uid in EQUIPMENT_UNITS[etype]:
                assign[(pid, etype, uid)] = model.new_bool_var(
                    f"a_{pid}_{etype}_{uid}"
                )

    # Exactly one unit of each required type per process
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            model.add(
                sum(assign[(pid, etype, uid)]
                    for uid in EQUIPMENT_UNITS[etype]) == 1
            )

    # ── Per-unit candidate node lists ─────────────────────────────────
    # Each unit's candidate nodes are operations whose required type
    # matches the unit's type.
    unit_cands = {uid: [] for uid in ALL_UNITS}
    for pid in all_pids:
        for etype in proc_info[pid]["equipment"]:
            for uid in EQUIPMENT_UNITS[etype]:
                unit_cands[uid].append((pid, etype))

    # ── Path-style direct-successor arc model per equipment unit ──────
    #
    # For each equipment unit `uid` we build a directed graph whose
    # nodes are SOURCE, all candidate operations of `uid`, and SINK.
    # CP-SAT's AddCircuit constraint enforces that the selected arcs
    # form a single Hamiltonian circuit on the present nodes. To allow
    # candidate nodes to be skipped (when the unit is not assigned to
    # that operation), each candidate has a self-loop arc whose literal
    # equals NOT(assign[node]).
    #
    # Selected real arcs carry travel-time constraints between the
    # connected operations' start/end times. The SOURCE→node arc
    # enforces base→workshop travel; node→node enforces inter-workshop
    # travel using early equipment release (operation end, not PCT).

    for uid in ALL_UNITS:
        cands = unit_cands[uid]
        if not cands:
            continue
        etype_uid = UNIT_TYPE[uid]

        # Index nodes: 0 = SOURCE, 1..N = candidates, N+1 = SINK
        n = len(cands)
        SOURCE = 0
        SINK = n + 1
        node_op = {i + 1: cands[i] for i in range(n)}

        arcs = []

        # SOURCE -> node i
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            lit = model.new_bool_var(f"arc_src_{uid}_{pid}")
            arcs.append((SOURCE, i, lit))
            ws = proc_info[pid]["workshop"]
            travel = TRANSPORT[("BASE", ws)]
            model.add(
                op_start[(pid, etype)] >= travel
            ).only_enforce_if(lit)
            # If this arc is taken, the unit must be assigned to this op
            model.add_implication(lit, assign[(pid, etype, uid)])

        # node i -> node j  (i != j)
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
                # Early release: use the operation's own end time
                model.add(
                    op_start[(pj, tj)] >= op_end_expr[(pi, ti)] + travel
                ).only_enforce_if(lit)
                model.add_implication(lit, assign[(pi, ti, uid)])
                model.add_implication(lit, assign[(pj, tj, uid)])

        # node i -> SINK
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            lit = model.new_bool_var(f"arc_{uid}_{pid}_sink")
            arcs.append((i, SINK, lit))
            model.add_implication(lit, assign[(pid, etype, uid)])

        # SOURCE -> SINK (unit unused)
        unused_lit = model.new_bool_var(f"arc_{uid}_unused")
        arcs.append((SOURCE, SINK, unused_lit))
        # If unused, no candidate may be assigned to this unit
        for pid, etype in cands:
            model.add_implication(unused_lit, assign[(pid, etype, uid)].Not())

        # Self-loops: candidate i NOT assigned ⇔ self-loop selected
        for i in range(1, n + 1):
            pid, etype = node_op[i]
            skip = assign[(pid, etype, uid)].Not()
            arcs.append((i, i, skip))

        # AddCircuit 要求闭合回路，此人工弧将设备路径 SOURCE→...→SINK 闭合为回路
        fixed_return = model.new_bool_var(f"arc_{uid}_sink_to_source")
        model.add(fixed_return == 1)
        arcs.append((SINK, SOURCE, fixed_return))

        model.add_circuit(arcs)

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
    print("Asynchronous operation-level model with early equipment release.")
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
        for etype, dur in proc_info[pid]["equipment"].items():
            s_val = solver.value(op_start[(pid, etype)])
            assigned_uid = None
            for uid in EQUIPMENT_UNITS[etype]:
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
        f.write("Asynchronous operation-level model with early equipment "
                "release.\n\n")
        f.write(f"- Solver status: {status_name}\n")
        f.write(f"- Best makespan: {makespan} s ({seconds_to_hms(makespan)})\n")
        f.write(f"- Objective lower bound: {lb:.0f} s ({seconds_to_hms(int(lb))})\n")
        f.write(f"- Relative optimality gap: {gap:.2f}%\n\n")
        f.write("## Table 2\n\n")
        f.write("Rows belonging to the same process may have different "
                "Start Times; the process completion time is the maximum "
                "of their End Times.\n\n")
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
# VALIDATION — asynchronous operation-level
# ═══════════════════════════════════════════════════════════════════════

def validate_schedule(rows, proc_info, all_pids):
    print("\n" + "=" * 60)
    print("SCHEDULE VALIDATION (asynchronous operation-level)")
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

    # 2. Asynchronous starts within a process are ALLOWED — informational only
    async_count = 0
    for pid in all_pids:
        starts = set(r["start"] for r in rows if r["process_id"] == pid)
        if len(starts) > 1:
            async_count += 1
    print(f"[INFO] 2. Asynchronous operation starts allowed; "
          f"{async_count} process(es) exhibit asynchronous starts.")

    # 3. Process completion = max end time over its operations
    proc_pct = {}
    for pid in all_pids:
        ends = [r["end"] for r in rows if r["process_id"] == pid]
        proc_pct[pid] = max(ends)
    print("[PASS] 3. Process completion times computed (max of end times).")

    # 4. Workshop precedence — every row of succ starts at/after PCT[pred]
    ok = True
    for pred, succ in PRECEDENCES:
        succ_rows = [r for r in rows if r["process_id"] == succ]
        for sr in succ_rows:
            if sr["start"] < proc_pct[pred]:
                print(f"[FAIL] 4. {pred}->{succ}: pred PCT={proc_pct[pred]}, "
                      f"{sr['equipment_id']} on {succ} starts {sr['start']}")
                ok = False
    if ok:
        print("[PASS] 4. All workshop precedence constraints satisfied "
              "for every successor operation.")
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

    # 6. Transport time between consecutive ops uses operation end (early release)
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
              "(based on operation end, i.e. early release).")
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

    # 8. Early release benefit analysis (per row vs PCT of its process)
    print("\n--- Early Release Analysis ---")
    early_count = 0
    for uid, ops in unit_ops.items():
        ops_s = sorted(ops, key=lambda x: x["start"])
        for op in ops_s:
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
