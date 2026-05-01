import math

try:
    from ortools.sat.python import cp_model
except ImportError:
    raise SystemExit("OR-Tools not installed. Run: pip install ortools")


def seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


PROCESSES = [
    {
        "process_id": "A1",
        "workload": 300,
        "equipment": [
            {"equipment_id": "精密灌装机1-1", "equipment_type": "Precision filling machine", "rate": 200},
            {"equipment_id": "自动化输送臂1-1", "equipment_type": "Automated conveying arm", "rate": 250},
        ],
    },
    {
        "process_id": "A2",
        "workload": 500,
        "equipment": [
            {"equipment_id": "高速抛光机1-1", "equipment_type": "High-speed polishing machine", "rate": 100},
            {"equipment_id": "工业清洗机1-1", "equipment_type": "Industrial cleaning machine", "rate": 250},
        ],
    },
    {
        "process_id": "A3",
        "workload": 500,
        "equipment": [
            {"equipment_id": "自动传感多功能机1-1", "equipment_type": "Automatic sensing multi-function machine", "rate": 100},
        ],
    },
]

TRAVEL_TIME = 200  # seconds, Crew 1 base to Workshop A


def main(include_travel_time: bool = False):
    for proc in PROCESSES:
        for eq in proc["equipment"]:
            eq["duration"] = math.ceil(proc["workload"] / eq["rate"] * 3600)

    horizon = sum(max(eq["duration"] for eq in p["equipment"]) for p in PROCESSES)
    if include_travel_time:
        horizon += TRAVEL_TIME

    model = cp_model.CpModel()

    S = {}
    C = {}
    ops = []

    for proc in PROCESSES:
        pid = proc["process_id"]
        S[pid] = model.new_int_var(0, horizon, f"S_{pid}")
        C[pid] = model.new_int_var(0, horizon, f"C_{pid}")

        op_ends = []
        for eq in proc["equipment"]:
            dur = eq["duration"]
            op_start = model.new_int_var(0, horizon, f"start_{pid}_{eq['equipment_id']}")
            op_end = model.new_int_var(0, horizon, f"end_{pid}_{eq['equipment_id']}")

            model.add(op_start == S[pid])
            model.add(op_end == op_start + dur)

            op_ends.append(op_end)
            ops.append({
                "equipment_id": eq["equipment_id"],
                "equipment_type": eq["equipment_type"],
                "process_id": pid,
                "duration": dur,
                "start_var": op_start,
                "end_var": op_end,
            })

        model.add_max_equality(C[pid], op_ends)

    if include_travel_time:
        model.add(S["A1"] == TRAVEL_TIME)
    else:
        model.add(S["A1"] == 0)

    model.add(S["A2"] >= C["A1"])
    model.add(S["A3"] >= C["A2"])

    Cmax = model.new_int_var(0, horizon, "Cmax")
    model.add(Cmax == C["A3"])
    model.minimize(Cmax)

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    status_name = solver.status_name(status)

    print(f"Solver status: {status_name}")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No solution found.")
        return

    makespan = solver.value(Cmax)
    print(f"Minimum makespan: {makespan} seconds")
    print(f"Minimum makespan: {seconds_to_hms(makespan)}")
    print()

    rows = []
    for op in ops:
        start_val = solver.value(op["start_var"])
        end_val = solver.value(op["end_var"])
        rows.append({
            "equipment_id": op["equipment_id"],
            "process_id": op["process_id"],
            "start": start_val,
            "end": end_val,
            "duration": op["duration"],
            "equipment_type": op["equipment_type"],
        })

    rows.sort(key=lambda r: (r["start"], r["process_id"], r["equipment_id"]))

    print("Table 1: Equipment Operation Schedule")
    print("-" * 105)
    header = f"{'Equipment ID':<20} {'Process':<8} {'Start Time':<12} {'End Time':<12} {'Duration (s)':<14} {'Equipment Type'}"
    print(header)
    print("-" * 105)
    for r in rows:
        print(
            f"{r['equipment_id']:<20} {r['process_id']:<8} "
            f"{seconds_to_hms(r['start']):<12} {seconds_to_hms(r['end']):<12} "
            f"{r['duration']:<14} {r['equipment_type']}"
        )
    print("-" * 105)


if __name__ == "__main__":
    main()
