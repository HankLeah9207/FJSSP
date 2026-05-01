import itertools
import math
import os
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "PingFang HK",
    "Hiragino Sans GB",
    "Songti SC",
    "STHeiti",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


RANDOM_SEED = 2026
BUDGET = 500000
WORKSHOPS = list("ABCDE")

DEVICE_TYPES = [
    "Automated Conveying Arm",
    "Industrial Cleaning Machine",
    "Precision Filling Machine",
    "Automatic Sensing Multi-Function Machine",
    "High-speed Polishing Machine",
]

TYPE_CN = {
    "Automated Conveying Arm": "自动化输送臂",
    "Industrial Cleaning Machine": "工业清洗机",
    "Precision Filling Machine": "精密灌装机",
    "Automatic Sensing Multi-Function Machine": "自动传感多功能机",
    "High-speed Polishing Machine": "高速抛光机",
}
CN_TYPE = {v: k for k, v in TYPE_CN.items()}

PROCESS_SHEET_CANDIDATES = ["工序流程表", "Process Flow Table", "process flow table"]
CREW_SHEET_CANDIDATES = ["班组配置表", "Crew Configuration Table", "crew configuration table"]
DISTANCE_SHEET_CANDIDATES = ["车间距离表", "Workshop Distance Table", "workshop distance table"]


PROCESS_COLUMN_CANDIDATES = {
    "workshop": ["Workshop", "workshop", "车间", "作业车间"],
    "process_id": ["Process ID", "ProcessID", "process id", "工序编号", "工序号"],
    "workload": ["Workload", "workload", "工程量", "作业量", "工作量"],
    "efficiency": ["Operational efficiency", "Operation efficiency", "作业效率", "设备作业效率", "效率"],
}
CREW_COLUMN_CANDIDATES = {
    "equipment_type": ["Equipment type", "Equipment Type", "设备类型", "设备名称"],
    "price": ["Unit Price(per unit)", "Unit Price", "Price", "单价", "设备单价", "购置单价"],
    "speed": ["Speed(m/s)", "Speed", "移动速度", "速度(m/s)", "速度"],
    "crew1": ["Equipment ID of Crew 1", "Crew 1 Equipment ID", "班组1设备编号", "班组1设备ID", "班组1"],
    "crew2": ["Equipment ID of Crew 2", "Crew 2 Equipment ID", "班组2设备编号", "班组2设备ID", "班组2"],
}
DISTANCE_COLUMN_CANDIDATES = {
    "origin": ["Origin", "origin", "起点", "出发地", "始发位置"],
    "destination": ["Destination", "destination", "终点", "目的地", "到达位置"],
    "distance": ["Distance", "distance", "距离", "距离(m)", "运输距离"],
}


@dataclass(frozen=True)
class Operation:
    expanded_op_id: str
    base_op_id: str
    workshop: str
    order: int
    workload: float
    required_types: tuple
    efficiency: dict
    expansion_note: str = ""

    @property
    def op_id(self):
        return self.expanded_op_id

    @property
    def display_op_id(self):
        return self.base_op_id


@dataclass
class Machine:
    machine_id: str
    team: int
    type: str
    speed: float
    price: int
    initial_location: str
    purchased: bool = False


def seconds_to_hhmmss(seconds):
    seconds = int(math.ceil(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_number(x):
    if pd.isna(x):
        return None
    m = re.search(r"-?[\d.]+", str(x).replace(",", ""))
    return float(m.group()) if m else None


def normalize_location(x):
    s = str(x).strip()
    s = s.replace("班组 1", "班组1").replace("班组 2", "班组2")
    if s.lower() in {"crew 1", "crew1"}:
        return "Crew 1"
    if s.lower() in {"crew 2", "crew2"}:
        return "Crew 2"
    if s == "班组1":
        return "Crew 1"
    if s == "班组2":
        return "Crew 2"
    return s


def normalize_type_name(s):
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("Industrial Cleaning Machine250", "Industrial Cleaning Machine 250")
    s = s.replace("Machine250", "Machine 250")
    for cn, en in CN_TYPE.items():
        if s == cn:
            return en
    return s


def canonical_type_from_text(text):
    text = normalize_type_name(text)
    if text in DEVICE_TYPES:
        return text
    for en, cn in TYPE_CN.items():
        if en in text or cn in text:
            return en
    raise ValueError(f"无法识别设备类型: {text}")


def parse_efficiency(text):
    text = str(text)
    compact = normalize_type_name(text)
    result = {}
    for en in DEVICE_TYPES:
        labels = [re.escape(en), re.escape(TYPE_CN[en])]
        for label in labels:
            # 兼容 “设备名 200 m³/h” 和 “设备名：200” 两类写法。
            m = re.search(label + r"\s*[:：]?\s*([\d.]+)", compact)
            if m:
                value_per_hour = float(m.group(1))
                if value_per_hour <= 0:
                    raise ValueError(f"设备 {en} 的效率必须为正数: {text}")
                result[en] = value_per_hour / 3600.0
                break
    if not result:
        raise ValueError(f"无法解析作业效率: {text}")
    return result


def split_machine_ids(text):
    if pd.isna(text):
        return []
    raw = str(text)
    raw = raw.replace("\n", "|").replace("，", "|").replace(",", "|")
    raw = raw.replace("；", "|").replace(";", "|").replace("。", "")
    return [x.strip() for x in raw.split("|") if x.strip() and x.strip().lower() != "nan"]


def find_sheet_name(dfs_or_excel, candidates: list[str]) -> str:
    if isinstance(dfs_or_excel, pd.ExcelFile):
        sheet_names = list(dfs_or_excel.sheet_names)
    elif isinstance(dfs_or_excel, dict):
        sheet_names = list(dfs_or_excel.keys())
    else:
        raise TypeError("find_sheet_name 需要 pd.ExcelFile 或 dict[str, DataFrame]")
    exact = {s: s for s in sheet_names}
    lower = {s.lower(): s for s in sheet_names}
    for name in candidates:
        if name in exact:
            return exact[name]
        if name.lower() in lower:
            return lower[name.lower()]
    raise KeyError(f"找不到候选 sheet {candidates}；Excel 实际包含: {sheet_names}")


def find_column(df, candidates, table_name):
    exact = {str(c).strip(): c for c in df.columns}
    lower = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        if name in exact:
            return exact[name]
        if name.lower() in lower:
            return lower[name.lower()]
    raise KeyError(f"{table_name} 缺少必要列 {candidates}；实际列名: {list(df.columns)}")


def load_data(file_path):
    xl = pd.ExcelFile(file_path)
    return {s: pd.read_excel(file_path, sheet_name=s) for s in xl.sheet_names}


def add_distance(distance, a, b, d):
    a = normalize_location(a)
    b = normalize_location(b)
    if d is None or d < 0:
        raise ValueError(f"距离必须为非负数: {a}->{b}={d}")
    distance[(a, b)] = float(d)
    distance[(b, a)] = float(d)


def preprocess_data(dfs):
    process_sheet = find_sheet_name(dfs, PROCESS_SHEET_CANDIDATES)
    crew_sheet = find_sheet_name(dfs, CREW_SHEET_CANDIDATES)
    distance_sheet = find_sheet_name(dfs, DISTANCE_SHEET_CANDIDATES)
    pf = dfs[process_sheet].copy()
    cf = dfs[crew_sheet].copy()
    df_dist = dfs[distance_sheet].copy()

    print("数据读取摘要:")
    print(f"  工序表 sheet: {process_sheet}, 列名: {list(pf.columns)}")
    print(f"  班组表 sheet: {crew_sheet}, 列名: {list(cf.columns)}")
    print(f"  距离表 sheet: {distance_sheet}, 列名: {list(df_dist.columns)}")

    pcols = {k: find_column(pf, v, "工序流程表") for k, v in PROCESS_COLUMN_CANDIDATES.items()}
    ccols = {k: find_column(cf, v, "班组配置表") for k, v in CREW_COLUMN_CANDIDATES.items()}
    dcols = {k: find_column(df_dist, v, "车间距离表") for k, v in DISTANCE_COLUMN_CANDIDATES.items()}

    pf[pcols["workshop"]] = pf[pcols["workshop"]].ffill()
    operations, workshop_ops = {}, defaultdict(list)
    expansion_rows = []
    warnings = []

    for _, row in pf.iterrows():
        if pd.isna(row[pcols["process_id"]]):
            continue
        base = str(row[pcols["process_id"]]).split(".")[0].strip()
        workshop = str(row[pcols["workshop"]]).strip()
        if not base or workshop.lower() == "nan":
            continue
        order_match = re.search(r"\d+", base)
        if not order_match:
            raise ValueError(f"无法从工序编号中识别顺序: {base}")
        order = int(order_match.group())
        workload = parse_number(row[pcols["workload"]])
        if workload is None or workload <= 0:
            raise ValueError(f"工序 {base} 的工程量必须为正数: {row[pcols['workload']]}")
        eff = parse_efficiency(row[pcols["efficiency"]])

        # C3、C4、C5 在附件中对应重复工程段/重复作业记录。这里将其展开为
        # C3-1/C4-1/C5-1, C3-2/C4-2/C5-2, C3-3/C4-3/C5-3 三轮内部工序，
        # 题目回填表仍显示原始工序编号，完整排程表保留内部展开编号。
        repeat = 3 if base in {"C3", "C4", "C5"} else 1
        if repeat > 1:
            warnings.append(
                "WARNING: C3-C5 are internally expanded into repeated sub-operations. "
                "Please verify this interpretation against the original process table."
            )
        for r in range(1, repeat + 1):
            expanded = f"{base}-{r}" if repeat > 1 else base
            expanded_order = order + (r - 1) * 100 if repeat > 1 else order
            note = "C3-C5重复工程段/重复作业记录的内部展开" if repeat > 1 else ""
            op = Operation(
                expanded_op_id=expanded,
                base_op_id=base,
                workshop=workshop,
                order=expanded_order,
                workload=float(workload),
                required_types=tuple(eff.keys()),
                efficiency=eff,
                expansion_note=note,
            )
            operations[expanded] = op
            workshop_ops[workshop].append(expanded)
            if repeat > 1:
                expansion_rows.append(
                    {
                        "原始工序编号": base,
                        "内部展开编号": expanded,
                        "车间": workshop,
                        "工程量": workload,
                        "所需设备类型": " + ".join(TYPE_CN.get(t, t) for t in eff.keys()),
                        "展开原因说明": note,
                    }
                )

    for w in list(workshop_ops):
        workshop_ops[w] = sorted(workshop_ops[w], key=lambda x: operations[x].order)

    machines, prices = {}, {}
    for _, row in cf.iterrows():
        if pd.isna(row[ccols["equipment_type"]]):
            continue
        t = canonical_type_from_text(row[ccols["equipment_type"]])
        price = parse_number(row[ccols["price"]])
        speed = parse_number(row[ccols["speed"]])
        if price is None or price <= 0:
            raise ValueError(f"设备 {t} 的单价必须为正数")
        if speed is None or speed <= 0:
            raise ValueError(f"设备 {t} 的移动速度必须为正数")
        prices[t] = int(price)
        for team in [1, 2]:
            for mid in split_machine_ids(row[ccols[f"crew{team}"]]):
                machines[mid] = Machine(mid, team, t, float(speed), int(price), f"Crew {team}")

    distance = {}
    for _, row in df_dist.iterrows():
        if pd.isna(row[dcols["origin"]]) or pd.isna(row[dcols["destination"]]):
            continue
        d = parse_number(row[dcols["distance"]])
        add_distance(distance, row[dcols["origin"]], row[dcols["destination"]], d)
    for x in ["Crew 1", "Crew 2", "班组1", "班组2"] + WORKSHOPS:
        add_distance(distance, x, x, 0.0)

    errors = []
    for op in operations.values():
        for t in op.required_types:
            if not any(m.type == t for m in machines.values()):
                errors.append(f"{op.expanded_op_id} 缺少设备类型 {t}")
    if errors:
        raise ValueError("数据可行性错误:\n" + "\n".join(errors))

    expansion_df = pd.DataFrame(expansion_rows)
    return operations, dict(workshop_ops), machines, distance, prices, expansion_df, sorted(set(warnings))


def calc_processing_time(operation: Operation, machine: Machine) -> int:
    if machine.type not in operation.required_types:
        raise ValueError(f"设备 {machine.machine_id} 类型 {machine.type} 不满足工序 {operation.expanded_op_id}")
    eff = operation.efficiency.get(machine.type)
    if eff is None or pd.isna(eff) or eff <= 0:
        raise ValueError(f"工序 {operation.expanded_op_id} 在设备类型 {machine.type} 上的效率无效: {eff}")
    return int(math.ceil(operation.workload / eff))


def calc_transport_time(machine: Machine, from_location, to_location, distance: dict) -> int:
    start = normalize_location(from_location)
    end = normalize_location(to_location)
    if start == end:
        return 0
    if (start, end) not in distance:
        raise KeyError(f"距离矩阵缺少 {start} -> {end}")
    if machine.speed is None or machine.speed <= 0:
        raise ValueError(f"设备 {machine.machine_id} 移动速度无效: {machine.speed}")
    return int(math.ceil(distance[(start, end)] / machine.speed))


def workshop_ops_from_operations(operations):
    result = defaultdict(list)
    for op_id, op in operations.items():
        result[op.workshop].append(op_id)
    return {w: sorted(seq, key=lambda x: operations[x].order) for w, seq in result.items()}


def subset_operations(operations, selected_workshops):
    selected = set(selected_workshops)
    return {op_id: op for op_id, op in operations.items() if op.workshop in selected}


def theoretical_min_processing_time(op, machines):
    values = []
    for t in op.required_types:
        candidates = [m for m in machines.values() if m.type == t]
        if not candidates:
            return math.inf
        values.append(min(calc_processing_time(op, m) for m in candidates))
    return max(values)


def remaining_chain_lengths(operations, workshop_ops, machines):
    chain = {}
    for _, seq in workshop_ops.items():
        suffix = 0
        for op_id in reversed(seq):
            suffix += theoretical_min_processing_time(operations[op_id], machines)
            chain[op_id] = suffix
    return chain


def predecessors_done(op_id, operations, workshop_ops, op_complete):
    seq = workshop_ops[operations[op_id].workshop]
    idx = seq.index(op_id)
    return 0 if idx == 0 else op_complete.get(seq[idx - 1])


def candidate_machine_lists(op, machines):
    lists = []
    for t in op.required_types:
        cands = [m for m in machines.values() if m.type == t]
        if not cands:
            raise RuntimeError(f"工序 {op.expanded_op_id} 缺少候选设备类型 {t}")
        lists.append(cands)
    return lists


def score_assignment(trial, rule):
    max_end = max(x["end"] for x in trial)
    sum_end = sum(x["end"] for x in trial)
    if rule == "fastest_machine_first":
        return (sum(x["duration"] for x in trial), max_end, sum_end)
    if rule == "nearest_available_machine_first":
        return (sum(x["transport"] for x in trial), max_end, sum_end)
    if rule == "earliest_available_machine_first":
        return (sum(x["available"] for x in trial), max_end, sum_end)
    return (max_end, sum_end, sum(x["transport"] for x in trial))


def choose_assignment(op, machines, distance, m_avail, m_loc, pred_done, machine_rule="earliest_completion_time"):
    best = None
    for combo in itertools.product(*candidate_machine_lists(op, machines)):
        if len({m.machine_id for m in combo}) < len(combo):
            continue
        trial = []
        for m in combo:
            trans = calc_transport_time(m, m_loc[m.machine_id], op.workshop, distance)
            start = max(pred_done, m_avail[m.machine_id] + trans)
            dur = calc_processing_time(op, m)
            trial.append(
                {
                    "machine": m,
                    "start": int(start),
                    "end": int(start + dur),
                    "duration": int(dur),
                    "transport": int(trans),
                    "available": int(m_avail[m.machine_id]),
                }
            )
        score = score_assignment(trial, machine_rule)
        if best is None or score < best[0]:
            best = (score, trial)
    if best is None:
        raise RuntimeError(f"工序 {op.expanded_op_id} 没有可行设备组合")
    return best[1]


def records_from_trial(op, trial):
    records = []
    for x in trial:
        m = x["machine"]
        records.append(
            {
                "设备编号": m.machine_id,
                "设备类型": m.type,
                "班组": m.team,
                "是否新购": bool(m.purchased),
                "车间": op.workshop,
                "原始工序编号": op.base_op_id,
                "内部工序编号": op.expanded_op_id,
                "工序编号": op.base_op_id,
                "起始秒": int(x["start"]),
                "结束秒": int(x["end"]),
                "起始时间": seconds_to_hhmmss(x["start"]),
                "结束时间": seconds_to_hhmmss(x["end"]),
                "持续工作时间(s)": int(x["duration"]),
                "运输时间(s)": int(x["transport"]),
            }
        )
    return records


def finalize_schedule(records, problem_name=None):
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values(["起始秒", "结束秒", "班组", "设备类型", "设备编号"]).reset_index(drop=True)
    if "序号" in df.columns:
        df = df.drop(columns=["序号"])
    df.insert(0, "序号", range(1, len(df) + 1))
    if problem_name is not None:
        df.insert(0, "问题", problem_name)
    return df


def build_topological_order(operations, workshop_ops, mode="round_robin", rng=None, machines=None):
    rng = rng or random.Random(RANDOM_SEED)
    machines = machines or {}
    pos, order = {w: 0 for w in workshop_ops}, []
    total = sum(len(v) for v in workshop_ops.values())
    critical = remaining_chain_lengths(operations, workshop_ops, machines) if machines else {}
    while len(order) < total:
        eligible = [workshop_ops[w][i] for w, i in pos.items() if i < len(workshop_ops[w])]
        if mode == "alphabetical":
            chosen = min(eligible, key=lambda op_id: (operations[op_id].workshop, operations[op_id].order))
        elif mode in {"shortest_processing_time", "spt"}:
            chosen = min(eligible, key=lambda op_id: (theoretical_min_processing_time(operations[op_id], machines), op_id))
        elif mode == "critical_path_first":
            chosen = max(eligible, key=lambda op_id: (critical.get(op_id, 0), -operations[op_id].order))
        elif mode == "random_weighted":
            weights = []
            for op_id in eligible:
                op = operations[op_id]
                proc = max(1, theoretical_min_processing_time(op, machines))
                rem = critical.get(op_id, proc)
                weights.append(max(1e-6, rem / proc))
            chosen = rng.choices(eligible, weights=weights, k=1)[0]
        elif mode == "random":
            chosen = rng.choice(eligible)
        else:
            chosen = min(eligible, key=lambda op_id: (pos[operations[op_id].workshop], operations[op_id].workshop))
        order.append(chosen)
        pos[operations[chosen].workshop] += 1
    return order


def schedule_by_order(
    operations,
    workshop_ops,
    machines,
    distance,
    allowed_teams=None,
    selected_workshops=None,
    priority_order=None,
    machine_rule="earliest_completion_time",
    problem_name=None,
):
    if allowed_teams is not None:
        machines = {k: v for k, v in machines.items() if v.team in set(allowed_teams)}
    if selected_workshops is not None:
        selected = set(selected_workshops)
        workshop_ops = {w: ops for w, ops in workshop_ops.items() if w in selected}
    op_set = set(itertools.chain.from_iterable(workshop_ops.values()))
    if priority_order is None:
        priority_order = build_topological_order(operations, workshop_ops, machines=machines)
    priority_order = [op for op in priority_order if op in op_set]
    missing = [op for op in op_set if op not in priority_order]
    priority_order += sorted(missing, key=lambda x: (operations[x].workshop, operations[x].order))

    m_avail = {mid: 0 for mid in machines}
    m_loc = {mid: machines[mid].initial_location for mid in machines}
    op_complete, records, unscheduled = {}, [], set(op_set)
    while unscheduled:
        progress = False
        for op_id in priority_order:
            if op_id not in unscheduled:
                continue
            pred_done = predecessors_done(op_id, operations, workshop_ops, op_complete)
            if pred_done is None:
                continue
            op = operations[op_id]
            trial = choose_assignment(op, machines, distance, m_avail, m_loc, pred_done, machine_rule)
            for x in trial:
                m = x["machine"]
                m_avail[m.machine_id] = x["end"]
                m_loc[m.machine_id] = op.workshop
            op_complete[op_id] = max(x["end"] for x in trial)
            records.extend(records_from_trial(op, trial))
            unscheduled.remove(op_id)
            progress = True
        if not progress:
            raise RuntimeError("调度解码失败：存在无法满足的前序关系")
    return finalize_schedule(records, problem_name), int(max(op_complete.values()) if op_complete else 0)


def dispatch_schedule(
    operations,
    workshop_ops,
    machines,
    distance,
    allowed_teams=None,
    operation_rule="earliest_completion_time",
    machine_rule="earliest_completion_time",
    rng=None,
    problem_name=None,
):
    rng = rng or random.Random(RANDOM_SEED)
    if allowed_teams is not None:
        machines = {k: v for k, v in machines.items() if v.team in set(allowed_teams)}
    m_avail = {mid: 0 for mid in machines}
    m_loc = {mid: machines[mid].initial_location for mid in machines}
    op_set = set(itertools.chain.from_iterable(workshop_ops.values()))
    op_complete, records, order, unscheduled = {}, [], [], set(op_set)
    critical = remaining_chain_lengths(operations, workshop_ops, machines)

    while unscheduled:
        eligible = []
        for op_id in sorted(unscheduled):
            pred_done = predecessors_done(op_id, operations, workshop_ops, op_complete)
            if pred_done is not None:
                eligible.append((op_id, pred_done))
        if not eligible:
            raise RuntimeError("调度派工失败：没有可调度工序")

        scored = []
        for op_id, pred_done in eligible:
            op = operations[op_id]
            trial = choose_assignment(op, machines, distance, m_avail, m_loc, pred_done, machine_rule)
            if operation_rule == "alphabetical":
                score = (op.workshop, op.order)
            elif operation_rule in {"shortest_processing_time", "spt"}:
                score = (theoretical_min_processing_time(op, machines), op.workshop, op.order)
            elif operation_rule == "critical_path_first":
                score = (-critical.get(op_id, 0), op.workshop, op.order)
            elif operation_rule == "random_weighted":
                proc = max(1, theoretical_min_processing_time(op, machines))
                score = (-(critical.get(op_id, proc) / proc + rng.random()), rng.random())
            elif operation_rule == "random":
                score = (rng.random(),)
            else:
                score = (max(x["end"] for x in trial), sum(x["end"] for x in trial))
            scored.append((score, op_id, trial))
        _, op_id, trial = min(scored, key=lambda x: x[0])
        op = operations[op_id]
        for x in trial:
            m = x["machine"]
            m_avail[m.machine_id] = x["end"]
            m_loc[m.machine_id] = op.workshop
        op_complete[op_id] = max(x["end"] for x in trial)
        records.extend(records_from_trial(op, trial))
        order.append(op_id)
        unscheduled.remove(op_id)
    return finalize_schedule(records, problem_name), int(max(op_complete.values()) if op_complete else 0), order


def is_valid_topological_order(order, operations, workshop_ops):
    pos = {op_id: i for i, op_id in enumerate(order)}
    if len(pos) != len(order):
        return False
    for _, seq in workshop_ops.items():
        for a, b in zip(seq, seq[1:]):
            if pos.get(a, -1) >= pos.get(b, -1):
                return False
    return True


def local_search_order(operations, workshop_ops, machines, distance, allowed_teams, start_order, start_cmax, rng, attempts):
    best_order = list(start_order)
    best_cmax = start_cmax
    best_df = None
    improvements = 0
    if len(best_order) < 2:
        return best_df, best_cmax, best_order, improvements
    for _ in range(attempts):
        i, j = sorted(rng.sample(range(len(best_order)), 2))
        candidate = list(best_order)
        candidate[i], candidate[j] = candidate[j], candidate[i]
        if not is_valid_topological_order(candidate, operations, workshop_ops):
            continue
        df, cmax = schedule_by_order(
            operations, workshop_ops, machines, distance, allowed_teams=allowed_teams, priority_order=candidate
        )
        if cmax < best_cmax:
            best_order, best_cmax, best_df = candidate, cmax, df
            improvements += 1
    return best_df, best_cmax, best_order, improvements


def schedule_problem_1(operations, workshop_ops, machines, distance):
    ops = workshop_ops["A"]
    m1 = {k: v for k, v in machines.items() if v.team == 1}
    choices = []
    for op_id in ops:
        op = operations[op_id]
        choices.append(list(itertools.product(*candidate_machine_lists(op, m1))))
    best = None
    for combo_per_op in itertools.product(*choices):
        m_avail = {mid: 0 for mid in m1}
        m_loc = {mid: m.initial_location for mid, m in m1.items()}
        op_complete, records, feasible = {}, [], True
        for op_id, combo in zip(ops, combo_per_op):
            if len({m.machine_id for m in combo}) < len(combo):
                feasible = False
                break
            pred = predecessors_done(op_id, operations, {"A": ops}, op_complete) or 0
            op = operations[op_id]
            trial = []
            for m in combo:
                trans = calc_transport_time(m, m_loc[m.machine_id], op.workshop, distance)
                start = max(pred, m_avail[m.machine_id] + trans)
                dur = calc_processing_time(op, m)
                trial.append(
                    {
                        "machine": m,
                        "start": int(start),
                        "end": int(start + dur),
                        "duration": int(dur),
                        "transport": int(trans),
                        "available": int(m_avail[m.machine_id]),
                    }
                )
            for x in trial:
                m = x["machine"]
                m_avail[m.machine_id] = x["end"]
                m_loc[m.machine_id] = op.workshop
            op_complete[op_id] = max(x["end"] for x in trial)
            records.extend(records_from_trial(op, trial))
        if feasible:
            cmax = max(op_complete.values())
            if best is None or cmax < best[0]:
                best = (cmax, records)
    if best is None:
        raise RuntimeError("问题1精确枚举未找到可行排程")
    return finalize_schedule(best[1]), int(best[0])


def optimize_schedule(
    operations,
    workshop_ops,
    machines,
    distance,
    allowed_teams,
    iterations=1000,
    strategies=None,
    local_search=True,
    random_seed=RANDOM_SEED,
):
    rng = random.Random(random_seed)
    strategies = strategies or [
        "round_robin",
        "alphabetical",
        "shortest_processing_time",
        "earliest_completion_time",
        "critical_path_first",
        "random_weighted",
    ]
    candidates = []
    strategy_best = {}
    metric_machines = machines if allowed_teams is None else {k: v for k, v in machines.items() if v.team in set(allowed_teams)}

    for strategy in strategies:
        if strategy == "earliest_completion_time":
            df, cmax, order = dispatch_schedule(
                operations, workshop_ops, machines, distance, allowed_teams, strategy, "earliest_completion_time", rng
            )
        else:
            order = build_topological_order(operations, workshop_ops, mode=strategy, rng=rng, machines=metric_machines)
            df, cmax = schedule_by_order(
                operations, workshop_ops, machines, distance, allowed_teams=allowed_teams, priority_order=order
            )
        candidates.append((cmax, order, df, strategy))
        strategy_best[strategy] = min(strategy_best.get(strategy, cmax), cmax)

    random_modes = ["random", "random_weighted", "critical_path_first", "shortest_processing_time"]
    for i in range(iterations):
        strategy = random_modes[i % len(random_modes)]
        if strategy in {"random", "random_weighted"} and i % 3 == 0:
            df, cmax, order = dispatch_schedule(
                operations, workshop_ops, machines, distance, allowed_teams, strategy, "earliest_completion_time", rng
            )
        else:
            order = build_topological_order(operations, workshop_ops, mode=strategy, rng=rng, machines=metric_machines)
            df, cmax = schedule_by_order(
                operations, workshop_ops, machines, distance, allowed_teams=allowed_teams, priority_order=order
            )
        candidates.append((cmax, order, df, strategy))
        strategy_best[strategy] = min(strategy_best.get(strategy, cmax), cmax)

    best_cmax, best_order, best_df, _ = min(candidates, key=lambda x: x[0])
    improvements = 0
    if local_search:
        ls_df, ls_cmax, ls_order, improvements = local_search_order(
            operations,
            workshop_ops,
            machines,
            distance,
            allowed_teams,
            best_order,
            best_cmax,
            rng,
            attempts=max(50, min(500, iterations // 2)),
        )
        if ls_df is not None and ls_cmax < best_cmax:
            best_df, best_cmax, best_order = ls_df, ls_cmax, ls_order

    values = [x[0] for x in candidates]
    stats = {
        "iterations": len(candidates),
        "best": int(best_cmax),
        "mean": float(statistics.mean(values)),
        "std": float(statistics.pstdev(values)) if len(values) > 1 else 0.0,
        "worst": int(max(values)),
        "strategy_best": strategy_best,
        "local_search_improvements": improvements,
    }
    return best_df, int(best_cmax), stats, best_order


def clone_with_purchases(machines, prices, scheme):
    new = {mid: Machine(m.machine_id, m.team, m.type, m.speed, m.price, m.initial_location, m.purchased) for mid, m in machines.items()}
    type_speed = {}
    for m in machines.values():
        type_speed.setdefault(m.type, m.speed)
    for (team, t), cnt in sorted(scheme.items()):
        if cnt <= 0:
            continue
        if t not in prices:
            raise KeyError(f"购置方案包含未知设备类型: {t}")
        if t not in type_speed:
            raise KeyError(f"没有设备类型 {t} 的速度信息，无法克隆新购设备")
        for i in range(1, cnt + 1):
            mid = f"{TYPE_CN.get(t, t)}-T{team}-P{i}"
            new[mid] = Machine(mid, team, t, type_speed[t], prices[t], f"Crew {team}", True)
    return new


def purchase_cost(scheme, prices):
    cost = 0
    for (_, t), cnt in scheme.items():
        if t not in prices:
            raise KeyError(f"购置方案包含未知设备类型: {t}")
        cost += prices[t] * cnt
    return int(cost)


def generate_purchase_candidates(
    prices: dict,
    budget: int,
    teams: list[int],
    max_total_new_machines: int | None = None,
    max_per_type_team: int | None = None,
) -> list[dict]:
    if not prices:
        return [{}]
    min_price = min(prices.values())
    theoretical_max = budget // min_price
    if max_total_new_machines is None:
        max_total_new_machines = max(1, int(math.floor(math.sqrt(max(1, theoretical_max)))))
    if max_per_type_team is None:
        max_per_type_team = max(1, int(math.ceil(max_total_new_machines / max(1, len(prices)))))

    keys = [(team, t) for team in teams for t in prices]
    candidates = [{}]

    def rec(idx, remaining_budget, remaining_count, scheme):
        if idx == len(keys):
            if scheme:
                candidates.append(dict(scheme))
            return
        team, t = keys[idx]
        max_cnt = min(max_per_type_team, remaining_count, remaining_budget // prices[t])
        for cnt in range(max_cnt + 1):
            if cnt:
                scheme[(team, t)] = cnt
            else:
                scheme.pop((team, t), None)
            rec(idx + 1, remaining_budget - cnt * prices[t], remaining_count - cnt, scheme)
        scheme.pop((team, t), None)

    rec(0, budget, max_total_new_machines, {})
    unique = {}
    for scheme in candidates:
        key = tuple(sorted(scheme.items()))
        unique[key] = scheme
    return list(unique.values())


def scheme_to_text(scheme, team):
    parts = []
    for (tm, t), cnt in sorted(scheme.items(), key=lambda x: (x[0][1], x[0][0])):
        if tm == team and cnt:
            parts.append(f"{TYPE_CN.get(t, t)}x{cnt}")
    return "；".join(parts) if parts else "不购买"


def purchased_utilization(schedule_df, makespan):
    if makespan <= 0 or schedule_df.empty or "是否新购" not in schedule_df:
        return 0.0
    new_rows = schedule_df[schedule_df["是否新购"].astype(bool)]
    if new_rows.empty:
        return 0.0
    new_machine_count = new_rows["设备编号"].nunique()
    return float(new_rows["持续工作时间(s)"].sum() / (makespan * new_machine_count))


def schedule_problem_4(
    operations,
    workshop_ops,
    machines,
    distance,
    prices,
    budget=BUDGET,
    quick_iterations=100,
    refine_iterations=800,
    top_k=10,
    random_seed=RANDOM_SEED,
):
    candidates = generate_purchase_candidates(prices, budget, teams=[1, 2])
    cap_note = (
        f"候选生成默认上限由预算/最低单价自动推导；候选数={len(candidates)}，"
        f"quick_iterations={quick_iterations}, refine_iterations={refine_iterations}, top_k={top_k}"
    )
    quick_rows = []
    for idx, scheme in enumerate(candidates):
        nm = clone_with_purchases(machines, prices, scheme)
        seed = random_seed + idx * 17
        df, cmax, _, _ = optimize_schedule(
            operations,
            workshop_ops,
            nm,
            distance,
            [1, 2],
            iterations=max(100, quick_iterations),
            local_search=False,
            random_seed=seed,
        )
        feasible, _ = check_feasibility(
            df,
            operations,
            nm,
            distance,
            budget=budget,
            purchase_scheme=scheme,
            prices=prices,
            verbose=False,
        )
        quick_rows.append(
            {
                "scheme": scheme,
                "df": df,
                "makespan": cmax,
                "cost": purchase_cost(scheme, prices),
                "util": purchased_utilization(df, cmax),
                "feasible": feasible,
            }
        )

    quick_rows.sort(key=lambda x: (not x["feasible"], x["makespan"], x["cost"]))
    refine_pool = quick_rows[: max(1, top_k)]
    refined_rows = []
    for idx, item in enumerate(refine_pool):
        scheme = item["scheme"]
        nm = clone_with_purchases(machines, prices, scheme)
        df, cmax, stats, _ = optimize_schedule(
            operations,
            workshop_ops,
            nm,
            distance,
            [1, 2],
            iterations=max(100, refine_iterations),
            local_search=True,
            random_seed=random_seed + 10000 + idx * 31,
        )
        feasible, _ = check_feasibility(
            df,
            operations,
            nm,
            distance,
            budget=budget,
            purchase_scheme=scheme,
            prices=prices,
            verbose=False,
        )
        refined_rows.append(
            {
                "scheme": scheme,
                "df": df,
                "makespan": cmax,
                "cost": purchase_cost(scheme, prices),
                "util": purchased_utilization(df, cmax),
                "feasible": feasible,
                "stats": stats,
            }
        )
    refined_rows.sort(key=lambda x: (not x["feasible"], x["makespan"], x["cost"]))
    best = refined_rows[0]
    best_scheme = best["scheme"]
    machines_with_purchases = clone_with_purchases(machines, prices, best_scheme)
    p5 = pd.DataFrame(
        [
            {
                "设备名称": TYPE_CN.get(t, t),
                "班组1购买台数": best_scheme.get((1, t), 0),
                "班组2购买台数": best_scheme.get((2, t), 0),
            }
            for t in prices
        ]
    )

    candidate_rows = []
    for rank, item in enumerate(quick_rows, 1):
        candidate_rows.append(
            {
                "排名": rank,
                "购买总费用": item["cost"],
                "当前搜索最优可行时长(s)": item["makespan"],
                "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(item["makespan"]),
                "班组1购买方案": scheme_to_text(item["scheme"], 1),
                "班组2购买方案": scheme_to_text(item["scheme"], 2),
                "新购设备利用率": item["util"],
                "是否通过可行性检查": item["feasible"],
            }
        )
    p4_stats = {
        "purchase_candidate_note": cap_note,
        "candidate_count": len(candidates),
        "quick_candidates": pd.DataFrame(candidate_rows),
        "refined_count": len(refined_rows),
        "best_cost": best["cost"],
        "best_stats": best.get("stats", {}),
    }
    return best["df"], int(best["makespan"]), p5, best_scheme, machines_with_purchases, p4_stats


def check_feasibility(
    schedule_df: pd.DataFrame,
    operations: dict,
    machines: dict,
    distance: dict,
    budget: int | None = None,
    purchase_scheme: dict | None = None,
    prices: dict | None = None,
    verbose: bool = True,
) -> tuple[bool, pd.DataFrame]:
    rows = []

    def add(name, ok, violations, note):
        rows.append({"检查项": name, "是否通过": bool(ok), "违规数量": int(violations), "说明": note})

    if schedule_df is None or schedule_df.empty:
        add("排程非空", False, 1, "schedule_df 为空")
        result = pd.DataFrame(rows)
        return False, result

    op_col = "内部工序编号" if "内部工序编号" in schedule_df.columns else "工序编号"
    required_cols = {"设备编号", "设备类型", "车间", "起始秒", "结束秒", "持续工作时间(s)", op_col}
    missing_cols = required_cols - set(schedule_df.columns)
    add("排程字段完整性", not missing_cols, len(missing_cols), f"缺失字段: {sorted(missing_cols)}" if missing_cols else "字段完整")
    if missing_cols:
        result = pd.DataFrame(rows)
        return False, result

    grouped = schedule_df.groupby(op_col)
    completeness_violations = 0
    type_violations = 0
    for op_id, op in operations.items():
        if op_id not in grouped.groups:
            completeness_violations += 1
            continue
        g = grouped.get_group(op_id)
        expected_n = len(op.required_types)
        if len(g) != expected_n:
            completeness_violations += 1
        if Counter(g["设备类型"]) != Counter(op.required_types):
            type_violations += 1
    extra_ops = set(schedule_df[op_col]) - set(operations)
    completeness_violations += len(extra_ops)
    add(
        "工序完整性",
        completeness_violations == 0,
        completeness_violations,
        "每个工序出现次数与所需设备数一致，且无多余内部工序",
    )
    add("设备类型 multiset 匹配", type_violations == 0, type_violations, "使用 Counter 检查 required_types")

    row_type_violations = 0
    duration_violations = 0
    for _, r in schedule_df.iterrows():
        op_id = r[op_col]
        if op_id not in operations or r["设备编号"] not in machines:
            row_type_violations += 1
            continue
        op = operations[op_id]
        m = machines[r["设备编号"]]
        if m.type != r["设备类型"] or m.type not in op.required_types:
            row_type_violations += 1
        expected = calc_processing_time(op, m)
        actual = int(r["持续工作时间(s)"])
        if actual != expected or int(r["结束秒"]) - int(r["起始秒"]) != expected:
            duration_violations += 1
    add("设备类型逐行匹配", row_type_violations == 0, row_type_violations, "每条记录设备类型满足该工序")
    add("加工时长正确性", duration_violations == 0, duration_violations, "持续工作时间=ceil(workload/efficiency)")

    workshop_ops = workshop_ops_from_operations(operations)
    op_end = grouped["结束秒"].max().to_dict()
    order_violations = 0
    for _, seq in workshop_ops.items():
        for a, b in zip(seq, seq[1:]):
            if b not in grouped.groups or a not in op_end:
                order_violations += 1
                continue
            b_start = grouped.get_group(b)["起始秒"].min()
            if int(b_start) < int(op_end[a]):
                order_violations += 1
    add("工序顺序约束", order_violations == 0, order_violations, "同一车间按内部展开顺序执行，后续等待前序整体完成")

    overlap_violations = 0
    transport_violations = 0
    first_transport_violations = 0
    for mid, g in schedule_df.sort_values(["起始秒", "结束秒"]).groupby("设备编号"):
        if mid not in machines:
            overlap_violations += len(g)
            continue
        m = machines[mid]
        records = g.sort_values(["起始秒", "结束秒"]).to_dict("records")
        first = records[0]
        need_first = calc_transport_time(m, m.initial_location, first["车间"], distance)
        if int(first["起始秒"]) < need_first:
            first_transport_violations += 1
        for r1, r2 in zip(records, records[1:]):
            if int(r2["起始秒"]) < int(r1["结束秒"]):
                overlap_violations += 1
            need = calc_transport_time(m, r1["车间"], r2["车间"], distance)
            if int(r2["起始秒"]) < int(r1["结束秒"]) + need:
                transport_violations += 1
    add("设备不可重叠", overlap_violations == 0, overlap_violations, "同一设备任意相邻作业不重叠")
    add("首次运输时间", first_transport_violations == 0, first_transport_violations, "首任务从设备所属班组初始位置出发")
    add("跨车间运输时间", transport_violations == 0, transport_violations, "后续任务从上一车间出发并留足运输")

    dual_violations = 0
    for op_id, op in operations.items():
        if len(op.required_types) <= 1 or op_id not in grouped.groups:
            continue
        g = grouped.get_group(op_id)
        if len(g) != len(op.required_types):
            dual_violations += 1
            continue
        if Counter(g["设备类型"]) != Counter(op.required_types):
            dual_violations += 1
        if any(int(x) != calc_processing_time(op, machines[mid]) for x, mid in zip(g["持续工作时间(s)"], g["设备编号"])):
            dual_violations += 1
    add("双设备工序完成规则", dual_violations == 0, dual_violations, "双设备均完成完整工程量，工序完成取两条记录最大结束")

    budget_violations = 0
    budget_note = "非问题4或未传入购置方案"
    if purchase_scheme is not None and prices is not None:
        try:
            cost = purchase_cost(purchase_scheme, prices)
            missing_price = [(team, t) for (team, t), cnt in purchase_scheme.items() if cnt and t not in prices]
            budget_violations += len(missing_price)
            if budget is not None and cost > budget:
                budget_violations += 1
            for (team, t), cnt in purchase_scheme.items():
                actual = sum(1 for m in machines.values() if m.purchased and m.team == team and m.type == t)
                if actual < cnt:
                    budget_violations += 1
            budget_note = f"购买费用={cost}，预算={budget}，已检查新购设备加入 machines"
        except Exception as exc:
            budget_violations += 1
            budget_note = str(exc)
    add("问题4预算约束", budget_violations == 0, budget_violations, budget_note)

    result = pd.DataFrame(rows, columns=["检查项", "是否通过", "违规数量", "说明"])
    ok = bool(result["是否通过"].all())
    if verbose:
        print(result.to_string(index=False))
    return ok, result


def lower_bounds(operations, workshop_ops, machines, allowed_teams=None):
    if allowed_teams is not None:
        machines = {k: v for k, v in machines.items() if v.team in set(allowed_teams)}
    cp = 0
    for _, seq in workshop_ops.items():
        total = 0
        for op_id in seq:
            op = operations[op_id]
            per_type = []
            for t in op.required_types:
                cands = [m for m in machines.values() if m.type == t]
                if not cands:
                    per_type.append(math.inf)
                else:
                    per_type.append(min(calc_processing_time(op, m) for m in cands))
            total += max(per_type)
        cp = max(cp, total)

    load_by_type = defaultdict(int)
    count_by_type = Counter(m.type for m in machines.values())
    for seq in workshop_ops.values():
        for op_id in seq:
            op = operations[op_id]
            for t in op.required_types:
                cands = [m for m in machines.values() if m.type == t]
                if cands:
                    load_by_type[t] += min(calc_processing_time(op, m) for m in cands)
                else:
                    load_by_type[t] += math.inf
    load_lb = 0
    for t, load in load_by_type.items():
        cnt = count_by_type.get(t, 0)
        load_lb = max(load_lb, math.inf if cnt == 0 else math.ceil(load / cnt))

    transport_note = "综合下界未计入运输时间，为乐观下界"
    combined = max(cp, load_lb)
    return {
        "关键路径下界(s)": int(cp),
        "设备负载下界(s)": int(load_lb),
        "综合下界(s)": int(combined),
        "运输下界说明": transport_note,
    }


def run_baselines(operations, workshop_ops, machines, distance, problem_specs):
    rows = []
    for problem_name, allowed_teams, heuristic_cmax, check_operations, check_machines in problem_specs:
        base_workshop_ops = workshop_ops_from_operations(check_operations)
        ae_order = list(itertools.chain.from_iterable(base_workshop_ops[w] for w in WORKSHOPS if w in base_workshop_ops))
        baseline_values = {}
        baseline_defs = [
            ("A→E串行(s)", "serial", "earliest_completion_time"),
            ("最快设备优先(s)", "round_robin", "fastest_machine_first"),
            ("最近可用设备优先(s)", "round_robin", "nearest_available_machine_first"),
            ("最早可用设备优先(s)", "round_robin", "earliest_available_machine_first"),
            ("最早完成优先(s)", "earliest_completion_time", "earliest_completion_time"),
        ]
        for col, op_rule, machine_rule in baseline_defs:
            if op_rule == "serial":
                df, cmax = schedule_by_order(
                    check_operations,
                    base_workshop_ops,
                    check_machines,
                    distance,
                    allowed_teams=allowed_teams,
                    priority_order=ae_order,
                    machine_rule=machine_rule,
                )
            elif op_rule == "earliest_completion_time":
                df, cmax, _ = dispatch_schedule(
                    check_operations,
                    base_workshop_ops,
                    check_machines,
                    distance,
                    allowed_teams=allowed_teams,
                    operation_rule=op_rule,
                    machine_rule=machine_rule,
                )
            else:
                order = build_topological_order(check_operations, base_workshop_ops, op_rule, machines=check_machines)
                df, cmax = schedule_by_order(
                    check_operations,
                    base_workshop_ops,
                    check_machines,
                    distance,
                    allowed_teams=allowed_teams,
                    priority_order=order,
                    machine_rule=machine_rule,
                )
            feasible, _ = check_feasibility(df, check_operations, check_machines, distance, verbose=False)
            baseline_values[col] = cmax if feasible else np.nan
        rows.append({"问题": problem_name, "本文启发式搜索(s)": heuristic_cmax, **baseline_values})
    return pd.DataFrame(rows)


def make_fill_table(schedule_df, include_team=False):
    cols = ["序号", "设备编号", "起始时间", "结束时间", "持续工作时间(s)", "工序编号"]
    if include_team:
        cols.append("班组")
    result = schedule_df[cols].copy()
    result["序号"] = range(1, len(result) + 1)
    return result


def make_full_table(schedule_df, problem_name):
    cols = [
        "问题",
        "序号",
        "设备编号",
        "设备类型",
        "班组",
        "是否新购",
        "车间",
        "原始工序编号",
        "内部工序编号",
        "起始秒",
        "结束秒",
        "起始时间",
        "结束时间",
        "持续工作时间(s)",
        "运输时间(s)",
    ]
    df = schedule_df.copy()
    if "问题" not in df.columns:
        df.insert(0, "问题", problem_name)
    return df[cols]


def export_results(output_path, tables):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            safe_name = name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)


def plot_gantt(schedule, title, output_prefix):
    if schedule.empty:
        return []
    os.makedirs(os.path.dirname(output_prefix) or ".", exist_ok=True)
    df = schedule.copy()
    df["sort_key"] = list(zip(df["班组"], df["设备类型"], df["设备编号"]))
    machines = (
        df.sort_values(["班组", "设备类型", "设备编号"])["设备编号"]
        .drop_duplicates()
        .tolist()
    )
    ypos = {m: i for i, m in enumerate(machines)}
    colors = dict(zip(WORKSHOPS, plt.cm.Set2.colors[: len(WORKSHOPS)]))

    fig_h = max(4.5, 0.36 * len(machines) + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    for _, r in df.iterrows():
        left = r["起始秒"] / 3600.0
        width = (r["结束秒"] - r["起始秒"]) / 3600.0
        hatch = "//" if bool(r.get("是否新购", False)) else None
        ax.barh(
            ypos[r["设备编号"]],
            width,
            left=left,
            color=colors.get(r["车间"], "lightgray"),
            edgecolor="black",
            linewidth=0.6 if hatch else 0.4,
            hatch=hatch,
        )
        if width > 0.03:
            ax.text(left + width / 2, ypos[r["设备编号"]], str(r["工序编号"]), va="center", ha="center", fontsize=7)
    labels = []
    machine_info = df.drop_duplicates("设备编号").set_index("设备编号")
    for mid in machines:
        r = machine_info.loc[mid]
        labels.append(f"T{int(r['班组'])} | {TYPE_CN.get(r['设备类型'], r['设备类型'])} | {mid}")
    ax.set_yticks(range(len(machines)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Time / hour")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25, linestyle="--", linewidth=0.5)
    handles = [Patch(facecolor=colors[w], edgecolor="black", label=w) for w in WORKSHOPS]
    if df["是否新购"].astype(bool).any():
        handles.append(Patch(facecolor="white", edgecolor="black", hatch="//", label="Purchased"))
    ax.legend(handles=handles, title="Workshop", loc="upper right", fontsize=8)
    fig.tight_layout()
    paths = []
    for ext in ["png", "pdf"]:
        path = f"{output_prefix}.{ext}"
        fig.savefig(path, dpi=240)
        paths.append(path)
    plt.close(fig)
    return paths


def main(file_path="B-attachment.xlsx", output_xlsx=None, output_dir="outputs", make_plots=True):
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到输入文件: {file_path}。请将附件 Excel 放到当前目录，或调用 main(file_path=...) 指定路径。")
    os.makedirs(output_dir, exist_ok=True)
    if output_xlsx is None:
        output_xlsx = os.path.join(output_dir, "fjsp_results.xlsx")

    dfs = load_data(file_path)
    operations, workshop_ops, machines, distance, prices, expansion_df, warnings = preprocess_data(dfs)
    p1_operations = subset_operations(operations, ["A"])
    p1_workshop_ops = workshop_ops_from_operations(p1_operations)

    print(f"工序数量: {len(operations)}，设备数量: {len(machines)}，设备类型数量: {len(set(m.type for m in machines.values()))}")

    p1_df, p1_c = schedule_problem_1(operations, workshop_ops, machines, distance)
    p2_df, p2_c, p2_stats, _ = optimize_schedule(operations, workshop_ops, machines, distance, [1], iterations=1000)
    p3_df, p3_c, p3_stats, _ = optimize_schedule(operations, workshop_ops, machines, distance, [1, 2], iterations=1000)
    p4_df, p4_c, p5_df, best_purchase_scheme, machines_with_purchases, p4_stats = schedule_problem_4(
        operations, workshop_ops, machines, distance, prices
    )

    p1_df = finalize_schedule(p1_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题1")
    p2_df = finalize_schedule(p2_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题2")
    p3_df = finalize_schedule(p3_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题3")
    p4_df = finalize_schedule(p4_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题4")

    checks = []
    ok1, c1 = check_feasibility(p1_df, p1_operations, machines, distance, verbose=False)
    ok2, c2 = check_feasibility(p2_df, operations, machines, distance, verbose=False)
    ok3, c3 = check_feasibility(p3_df, operations, machines, distance, verbose=False)
    ok4, c4 = check_feasibility(
        p4_df,
        operations,
        machines_with_purchases,
        distance,
        budget=BUDGET,
        purchase_scheme=best_purchase_scheme,
        prices=prices,
        verbose=False,
    )
    for name, df in [("问题1", c1), ("问题2", c2), ("问题3", c3), ("问题4", c4)]:
        checks.append(df.assign(问题=name))
    checks_df = pd.concat(checks, ignore_index=True)[["问题", "检查项", "是否通过", "违规数量", "说明"]]

    lb_rows = []
    lb_specs = [
        ("问题1", p1_workshop_ops, p1_operations, machines, [1], p1_c),
        ("问题2", workshop_ops, operations, machines, [1], p2_c),
        ("问题3", workshop_ops, operations, machines, [1, 2], p3_c),
        ("问题4", workshop_ops, operations, machines_with_purchases, [1, 2], p4_c),
    ]
    for name, wops, ops, mach, teams, cmax in lb_specs:
        lb = lower_bounds(ops, wops, mach, teams)
        combined = lb["综合下界(s)"]
        lb_rows.append(
            {
                "问题": name,
                "关键路径下界(s)": lb["关键路径下界(s)"],
                "设备负载下界(s)": lb["设备负载下界(s)"],
                "综合下界(s)": combined,
                "本文可行解(s)": cmax,
                "gap": (cmax - combined) / combined if combined else np.nan,
                "说明": lb["运输下界说明"],
            }
        )
    lbs_df = pd.DataFrame(lb_rows)

    baselines_df = run_baselines(
        operations,
        workshop_ops,
        machines,
        distance,
        [
            ("问题2", [1], p2_c, operations, machines),
            ("问题3", [1, 2], p3_c, operations, machines),
            ("问题4", [1, 2], p4_c, operations, machines_with_purchases),
        ],
    )

    summary_rows = [
        {
            "问题": "问题1",
            "精确最短时长(s)": p1_c,
            "精确最短时长(HH:MM:SS)": seconds_to_hhmmss(p1_c),
            "备注": "由于 A 车间工序严格串行，枚举设备组合覆盖全部可行方案",
        },
        {
            "问题": "问题2",
            "当前搜索最优可行时长(s)": p2_c,
            "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p2_c),
            "备注": f"best feasible schedule found; 多策略启发式+局部扰动，搜索次数={p2_stats['iterations']}",
        },
        {
            "问题": "问题3",
            "当前搜索最优可行时长(s)": p3_c,
            "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p3_c),
            "备注": f"best feasible schedule found; 双班组联合调度，搜索次数={p3_stats['iterations']}",
        },
        {
            "问题": "问题4",
            "当前搜索最优可行时长(s)": p4_c,
            "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p4_c),
            "备注": f"best feasible schedule found; 购置费用={purchase_cost(best_purchase_scheme, prices)}; {p4_stats['purchase_candidate_note']}",
        },
    ]
    for warning in warnings:
        summary_rows.append({"问题": "C工序展开", "备注": warning})
    summary_df = pd.DataFrame(summary_rows).fillna("")

    full_tables = {
        "表1": make_fill_table(p1_df, include_team=False),
        "表2": make_fill_table(p2_df, include_team=False),
        "表3": make_fill_table(p3_df, include_team=True),
        "表4": make_fill_table(p4_df, include_team=True),
        "表5": p5_df,
        "问题1完整排程": make_full_table(p1_df, "问题1"),
        "问题2完整排程": make_full_table(p2_df, "问题2"),
        "问题3完整排程": make_full_table(p3_df, "问题3"),
        "问题4完整排程": make_full_table(p4_df, "问题4"),
        "Summary": summary_df,
        "Feasibility": checks_df,
        "理论下界对比": lbs_df,
        "基准规则对比": baselines_df,
        "问题4候选购置方案对比": p4_stats["quick_candidates"],
        "C工序展开说明": expansion_df
        if not expansion_df.empty
        else pd.DataFrame(columns=["原始工序编号", "内部展开编号", "车间", "工程量", "所需设备类型", "展开原因说明"]),
    }
    export_results(output_xlsx, full_tables)

    gantt_paths = []
    if make_plots:
        gantt_paths.extend(plot_gantt(p1_df, "问题1 当前搜索最优可行排程", os.path.join(output_dir, "problem1_gantt")))
        gantt_paths.extend(plot_gantt(p2_df, "问题2 当前搜索最优可行排程", os.path.join(output_dir, "problem2_gantt")))
        gantt_paths.extend(plot_gantt(p3_df, "问题3 当前搜索最优可行排程", os.path.join(output_dir, "problem3_gantt")))
        gantt_paths.extend(plot_gantt(p4_df, "问题4 当前搜索最优可行排程", os.path.join(output_dir, "problem4_gantt")))

    print("\n主流程输出摘要:")
    print(summary_df.to_string(index=False))
    print("\n问题4购买方案:")
    print(p5_df.to_string(index=False))
    print("\n各问题可行性检查结果:")
    print(checks_df.groupby("问题")["是否通过"].all().to_string())
    print("\n理论下界 gap:")
    print(lbs_df[["问题", "综合下界(s)", "本文可行解(s)", "gap"]].to_string(index=False))
    print("\nBaseline 对比:")
    print(baselines_df.to_string(index=False))
    print(f"\nExcel 输出路径: {output_xlsx}")
    if gantt_paths:
        print("甘特图输出路径:")
        for path in gantt_paths:
            print(f"  {path}")

    return {
        "summaries": summary_rows,
        "tables": full_tables,
        "checks": checks_df,
        "lbs": lbs_df,
        "baselines": baselines_df,
        "p4_candidates": p4_stats["quick_candidates"],
        "p4_purchase_scheme": best_purchase_scheme,
        "machines_with_purchases": machines_with_purchases,
        "stats": {"p2": p2_stats, "p3": p3_stats, "p4": p4_stats},
        "output_xlsx": output_xlsx,
        "gantt_paths": gantt_paths,
    }


if __name__ == "__main__":
    result = main(file_path="B-attachment.xlsx", output_xlsx=os.path.join("outputs", "fjsp_results.xlsx"), make_plots=True)
