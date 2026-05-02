#!/usr/bin/env python3
"""
FJSP solver for 51MCM Problem B — optimized version.

Key improvements over the previous version:
  1. Tabu Search with adaptive tenure replacing random swap loops.
  2. Simulated Annealing acceptance for local search (accept worse moves
     with decreasing probability to escape local optima).
  3. Critical-path-aware neighborhood operations (CPM-aware swap/insert).
  4. True dispatching rules (MWR, SPT, LPT, ECT, CPM) in dispatch_schedule.
  5. Active (left-shift) decoder integrated into all search paths.
  6. Enhanced lower bounds that estimate transport time contribution.
  7. Faster topological-order construction via pre-built successor maps.
"""

import itertools
import argparse
import math
import os
import random
import re
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
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


# ──────────────────────────────────────────────
# Global constants
# ──────────────────────────────────────────────

RANDOM_SEED = 2026
BUDGET = 500000
WORKSHOPS = list("ABCDE")
DEFAULT_MAX_TOTAL_NEW_MACHINES = 10
DEFAULT_MAX_PER_TYPE_TEAM = 4
EXPAND_C_REPEATED_OPS = True
C_REPEATED_BASE_OPS = {"C3", "C4", "C5"}
C_REPEATED_COUNT = 3

# SA default parameters
SA_T0 = 100.0        # initial temperature
SA_ALPHA = 0.9997     # cooling rate per iteration
SA_T_MIN = 0.01       # minimum temperature

# Tabu tenure
TABU_BASE_TENURE = 7
TABU_DYNAMIC = True   # tenure = base + random(0, base)

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


# ──────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────


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


# ──────────────────────────────────────────────
# Utility functions
# ──────────────────────────────────────────────


def seconds_to_hhmmss(seconds):
    seconds = int(math.ceil(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def should_print_progress(done, total, steps=20):
    if total <= 0:
        return False
    interval = max(1, math.ceil(total / max(1, int(steps))))
    return done == 1 or done == total or done % interval == 0


def format_elapsed(start_time):
    return f"{time.time() - start_time:.1f}s"


def print_solver_progress(label, phase, done, total, best=None, start_time=None):
    pct = 100.0 * done / total if total else 100.0
    best_text = f"{int(best)}s" if best is not None and math.isfinite(best) else "N/A"
    elapsed = f", elapsed={format_elapsed(start_time)}" if start_time is not None else ""
    print(f"{label} {phase}进度: {done}/{total} ({pct:.1f}%), 当前best={best_text}{elapsed}", flush=True)


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


def convert_efficiency_to_per_second(value: float, raw_text: str) -> tuple[float, str]:
    if value <= 0:
        raise ValueError(f"效率必须为正数: {value}")
    text = str(raw_text).strip().lower()
    text = text.replace("／", "/")
    hour_markers = ["per hour", "每小时", "/h", "/hr", "m³/h", "m3/h", "kg/h", "m/h"]
    second_markers = ["per second", "每秒", "/s", "m³/s", "m3/s", "kg/s", "m/s"]
    has_hour = any(x in text for x in hour_markers) or bool(re.search(r"(?<![a-z])h(?![a-z])", text))
    has_second = any(x in text for x in second_markers) or bool(re.search(r"(?<![a-z])s(?![a-z])", text))
    if has_hour and not has_second:
        return value / 3600.0, "per hour; divided by 3600"
    if has_second and not has_hour:
        return value, "per second; unchanged"
    if has_hour and has_second:
        return value / 3600.0, "ambiguous; assumed per hour"
    return value / 3600.0, "unit not explicit; assumed per hour"


def parse_efficiency(text, return_notes=False, process_id=None):
    text = str(text)
    compact = normalize_type_name(text)
    result = {}
    notes = []
    for en in DEVICE_TYPES:
        labels = [re.escape(en), re.escape(TYPE_CN[en])]
        for label in labels:
            m = re.search(label + r"\s*[:：]?\s*([\d.]+)\s*([^,，;；|]*)", compact)
            if m:
                value = float(m.group(1))
                unit_fragment = m.group(0)
                eff_per_second, unit_note = convert_efficiency_to_per_second(value, unit_fragment)
                result[en] = eff_per_second
                notes.append(
                    {
                        "工序编号": process_id or "",
                        "设备类型": TYPE_CN.get(en, en),
                        "原始效率文本": text,
                        "解析数值": value,
                        "单位判断": unit_note,
                        "转换后每秒效率": eff_per_second,
                    }
                )
                break
    if not result:
        raise ValueError(f"无法解析作业效率: {text}")
    if return_notes:
        return result, notes
    return result


def split_machine_ids(text):
    if pd.isna(text):
        return []
    raw = str(text)
    raw = raw.replace("\n", "|").replace("，", "|").replace(",", "|")
    raw = raw.replace("；", "|").replace(";", "|").replace("。", "")
    return [x.strip() for x in raw.split("|") if x.strip() and x.strip().lower() != "nan"]


# ──────────────────────────────────────────────
# Excel / column helpers
# ──────────────────────────────────────────────


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


def try_find_column(df, candidates):
    exact = {str(c).strip(): c for c in df.columns}
    lower = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        if name in exact:
            return exact[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def load_data(file_path):
    xl = pd.ExcelFile(file_path)
    return {s: pd.read_excel(file_path, sheet_name=s) for s in xl.sheet_names}


# ──────────────────────────────────────────────
# Distance parsing
# ──────────────────────────────────────────────


def add_distance(distance, a, b, d):
    a = normalize_location(a)
    b = normalize_location(b)
    if d is None or d < 0:
        raise ValueError(f"距离必须为非负数: {a}->{b}={d}")
    distance[(a, b)] = float(d)
    distance[(b, a)] = float(d)


def parse_distance_table(df_dist):
    warnings = []
    distance = {}
    origin_col = try_find_column(df_dist, DISTANCE_COLUMN_CANDIDATES["origin"])
    dest_col = try_find_column(df_dist, DISTANCE_COLUMN_CANDIDATES["destination"])
    distance_col = try_find_column(df_dist, DISTANCE_COLUMN_CANDIDATES["distance"])
    expected_locations = {"Crew 1", "Crew 2", *WORKSHOPS}

    if origin_col is not None and dest_col is not None and distance_col is not None:
        for _, row in df_dist.iterrows():
            if pd.isna(row[origin_col]) or pd.isna(row[dest_col]):
                continue
            d = parse_number(row[distance_col])
            add_distance(distance, row[origin_col], row[dest_col], d)
        present = {x for pair in distance for x in pair}
        missing = sorted(expected_locations - present)
        if missing:
            warnings.append(f"WARNING: edge-list 距离表缺少部分位置: {missing}")
        for x in ["Crew 1", "Crew 2", "班组1", "班组2"] + WORKSHOPS:
            add_distance(distance, x, x, 0.0)
        return distance, "edge-list", warnings

    if df_dist.shape[1] < 2:
        raise KeyError("车间距离表既不是 edge-list 三列格式，也不是矩阵格式")

    origin_col = df_dist.columns[0]
    destination_cols = list(df_dist.columns[1:])
    explicit = {}
    origins, destinations = set(), set()
    for _, row in df_dist.iterrows():
        if pd.isna(row[origin_col]):
            continue
        origin = normalize_location(row[origin_col])
        origins.add(origin)
        for col in destination_cols:
            destination = normalize_location(col)
            destinations.add(destination)
            if pd.isna(row[col]):
                continue
            value = parse_number(row[col])
            if value is None:
                continue
            add_distance(distance, origin, destination, value)
            explicit[(origin, destination)] = float(value)

    seen_asymmetric_pairs = set()
    for (a, b), value in explicit.items():
        reverse = explicit.get((b, a))
        pair_key = tuple(sorted([a, b]))
        if (
            reverse is not None
            and pair_key not in seen_asymmetric_pairs
            and not math.isclose(value, reverse, rel_tol=1e-9, abs_tol=1e-9)
        ):
            warnings.append(f"WARNING: 距离矩阵非对称 {a}->{b}={value}, {b}->{a}={reverse}")
            seen_asymmetric_pairs.add(pair_key)
        distance[(a, b)] = value

    present = origins | destinations
    missing = sorted(expected_locations - present)
    if missing:
        warnings.append(f"WARNING: matrix 距离表缺少部分位置: {missing}")
    for x in ["Crew 1", "Crew 2", "班组1", "班组2"] + WORKSHOPS:
        add_distance(distance, x, x, 0.0)
    return distance, "matrix", sorted(set(warnings))


# ──────────────────────────────────────────────
# Data preprocessing
# ──────────────────────────────────────────────


def preprocess_data(
    dfs,
    expand_c_repeated_ops: bool = EXPAND_C_REPEATED_OPS,
    c_repeated_base_ops: set[str] = C_REPEATED_BASE_OPS,
    c_repeated_count: int = C_REPEATED_COUNT,
):
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
    distance, distance_format, distance_warnings = parse_distance_table(df_dist)

    pf[pcols["workshop"]] = pf[pcols["workshop"]].ffill()
    operations, workshop_ops = {}, defaultdict(list)
    expansion_rows = []
    warnings = list(distance_warnings)
    efficiency_unit_notes = []

    warnings.append(
        "C工序展开配置: "
        f"enabled={expand_c_repeated_ops}, base_ops={sorted(c_repeated_base_ops)}, repeat={c_repeated_count}. "
        "该规则基于对附件 C3-C5 重复工程段的解释，用户应核对原始题目数据。"
    )

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
        eff, eff_notes = parse_efficiency(row[pcols["efficiency"]], return_notes=True, process_id=base)
        efficiency_unit_notes.extend(eff_notes)

        repeat = c_repeated_count if expand_c_repeated_ops and base in c_repeated_base_ops else 1
        if repeat > 1:
            warnings.append(
                f"WARNING: {base} expanded into {repeat} sub-operations. Verify against original data."
            )
        for r in range(1, repeat + 1):
            expanded = f"{base}-{r}" if repeat > 1 else base
            expanded_order = order + (r - 1) * 100 if repeat > 1 else order
            note = "C3-C5重复工程段内部展开" if repeat > 1 else ""
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

    errors = []
    for op in operations.values():
        for t in op.required_types:
            if not any(m.type == t for m in machines.values()):
                errors.append(f"{op.expanded_op_id} 缺少设备类型 {t}")
    if errors:
        raise ValueError("数据可行性错误:\n" + "\n".join(errors))

    expansion_df = pd.DataFrame(expansion_rows)
    efficiency_notes_df = pd.DataFrame(
        efficiency_unit_notes,
        columns=["工序编号", "设备类型", "原始效率文本", "解析数值", "单位判断", "转换后每秒效率"],
    )
    return (
        operations,
        dict(workshop_ops),
        machines,
        distance,
        prices,
        expansion_df,
        sorted(set(warnings)),
        distance_format,
        efficiency_notes_df,
    )


# ──────────────────────────────────────────────
# Core scheduling primitives
# ──────────────────────────────────────────────


def calc_processing_time(operation: Operation, machine: Machine) -> int:
    if machine.type not in operation.required_types:
        raise ValueError(f"设备 {machine.machine_id} 类型 {machine.type} 不满足工序 {operation.expanded_op_id}")
    eff = operation.efficiency.get(machine.type)
    if eff is None or pd.isna(eff) or eff <= 0:
        raise ValueError(f"工序 {operation.expanded_op_id} 在 {machine.type} 上效率无效: {eff}")
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


# ──────────────────────────────────────────────
# Candidate pruning for machine assignment
# ──────────────────────────────────────────────


def candidate_machine_lists_for_assignment(
    op, machines, distance, m_avail, m_loc, pred_done, max_candidates_per_type=None,
):
    lists = []
    for t in op.required_types:
        cands = [m for m in machines.values() if m.type == t]
        if not cands:
            raise RuntimeError(f"工序 {op.expanded_op_id} 缺少候选设备类型 {t}")
        if max_candidates_per_type is not None:
            limit = max(0, int(max_candidates_per_type))
            ranked = []
            for m in cands:
                trans = calc_transport_time(m, m_loc[m.machine_id], op.workshop, distance)
                start = max(pred_done, m_avail[m.machine_id] + trans)
                dur = calc_processing_time(op, m)
                ranked.append((int(start + dur), int(start), int(trans), m.machine_id, m))
            ranked.sort(key=lambda x: x[:4])
            cands = [x[-1] for x in ranked[:limit]]
        if not cands:
            raise RuntimeError(f"工序 {op.expanded_op_id} 设备类型 {t} 候选截断后为空")
        lists.append(cands)
    return lists


# ──────────────────────────────────────────────
# Assignment scoring & selection
# ──────────────────────────────────────────────


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


def choose_assignment(
    op, machines, distance, m_avail, m_loc, pred_done,
    machine_rule="earliest_completion_time", rng=None,
    top_k=1, randomize_top_k=False, temperature=1.0,
    max_candidates_per_type=None,
):
    rng = rng or random.Random(RANDOM_SEED)
    scored_trials = []
    candidate_lists = candidate_machine_lists_for_assignment(
        op, machines, distance, m_avail, m_loc, pred_done,
        max_candidates_per_type=max_candidates_per_type,
    )
    for combo in itertools.product(*candidate_lists):
        if len({m.machine_id for m in combo}) < len(combo):
            continue
        trial = []
        for m in combo:
            trans = calc_transport_time(m, m_loc[m.machine_id], op.workshop, distance)
            start = max(pred_done, m_avail[m.machine_id] + trans)
            dur = calc_processing_time(op, m)
            trial.append(
                {
                    "machine": m, "start": int(start), "end": int(start + dur),
                    "duration": int(dur), "transport": int(trans),
                    "available": int(m_avail[m.machine_id]),
                }
            )
        scored_trials.append((score_assignment(trial, machine_rule), trial))
    if not scored_trials:
        raise RuntimeError(f"工序 {op.expanded_op_id} 没有可行设备组合")
    scored_trials.sort(key=lambda x: x[0])
    if not randomize_top_k or top_k <= 1:
        return scored_trials[0][1]

    pool = scored_trials[: max(1, min(int(top_k), len(scored_trials)))]
    scalar_scores = [sum((10**-i) * float(part) for i, part in enumerate(score)) for score, _ in pool]
    best_score, worst_score = min(scalar_scores), max(scalar_scores)
    span = max(1.0, worst_score - best_score)
    temp = max(float(temperature), 1e-6)
    weights = [math.exp(-((s - best_score) / span) / temp) for s in scalar_scores]
    return rng.choices([trial for _, trial in pool], weights=weights, k=1)[0]


# ──────────────────────────────────────────────
# Active decoder (left-shift insertion)
# ──────────────────────────────────────────────


def build_machine_timeline(schedule_df):
    timelines = defaultdict(list)
    if schedule_df is None or schedule_df.empty:
        return {}
    op_col = "内部工序编号" if "内部工序编号" in schedule_df.columns else "工序编号"
    for _, row in schedule_df.sort_values(["设备编号", "起始秒", "结束秒"]).iterrows():
        timelines[row["设备编号"]].append(
            {
                "start": int(row["起始秒"]),
                "end": int(row["结束秒"]),
                "workshop": row["车间"],
                "op_id": row[op_col],
                "duration": int(row["持续工作时间(s)"]),
            }
        )
    return dict(timelines)


def find_earliest_insertion_slot(machine, timeline, op, earliest_ready, duration, distance):
    best_last = None
    for idx in range(len(timeline) + 1):
        prev_task = timeline[idx - 1] if idx > 0 else None
        next_task = timeline[idx] if idx < len(timeline) else None
        if prev_task is None:
            prev_end = 0
            prev_loc = machine.initial_location
        else:
            prev_end = int(prev_task["end"])
            prev_loc = prev_task["workshop"]
        prev_transport = calc_transport_time(machine, prev_loc, op.workshop, distance)
        start = max(int(earliest_ready), int(prev_end + prev_transport))
        end = int(start + duration)
        if next_task is not None:
            next_transport = calc_transport_time(machine, op.workshop, next_task["workshop"], distance)
            if end + next_transport <= int(next_task["start"]):
                return {
                    "start": int(start), "end": int(end),
                    "insert_index": idx,
                    "transport": int(prev_transport),
                    "prev_transport": int(prev_transport),
                    "next_transport": int(next_transport),
                }
        else:
            best_last = {
                "start": int(start), "end": int(end),
                "insert_index": idx,
                "transport": int(prev_transport),
                "prev_transport": int(prev_transport),
                "next_transport": 0,
            }
    return best_last


def candidate_machine_lists_for_active_assignment(
    op, machines, distance, machine_timeline, op_ready_time, max_candidates_per_type=None,
):
    lists = []
    for t in op.required_types:
        cands = [m for m in machines.values() if m.type == t]
        if not cands:
            raise RuntimeError(f"工序 {op.expanded_op_id} 缺少候选设备类型 {t}")
        if max_candidates_per_type is not None:
            ranked = []
            limit = max(0, int(max_candidates_per_type))
            for m in cands:
                duration = calc_processing_time(op, m)
                slot = find_earliest_insertion_slot(
                    m, machine_timeline.get(m.machine_id, []), op, op_ready_time, duration, distance,
                )
                ranked.append((slot["end"], slot["start"], slot["transport"], m.machine_id, m))
            ranked.sort(key=lambda x: x[:4])
            cands = [x[-1] for x in ranked[:limit]]
        if not cands:
            raise RuntimeError(f"工序 {op.expanded_op_id} 设备类型 {t} active 候选截断后为空")
        lists.append(cands)
    return lists


def choose_assignment_active(
    op, machines, distance, machine_timeline, op_ready_time,
    machine_rule="earliest_completion_time", rng=None,
    top_k=1, randomize_top_k=False, temperature=1.0,
    max_candidates_per_type=None,
):
    rng = rng or random.Random(RANDOM_SEED)
    scored_trials = []
    candidate_lists = candidate_machine_lists_for_active_assignment(
        op, machines, distance, machine_timeline, op_ready_time,
        max_candidates_per_type=max_candidates_per_type,
    )
    for combo in itertools.product(*candidate_lists):
        if len({m.machine_id for m in combo}) < len(combo):
            continue
        trial = []
        for m in combo:
            duration = calc_processing_time(op, m)
            slot = find_earliest_insertion_slot(
                m, machine_timeline.get(m.machine_id, []), op, op_ready_time, duration, distance,
            )
            trial.append(
                {
                    "machine": m, "start": int(slot["start"]), "end": int(slot["end"]),
                    "duration": int(duration), "transport": int(slot["transport"]),
                    "available": int(slot["start"]), "insert_index": int(slot["insert_index"]),
                }
            )
        scored_trials.append((score_assignment(trial, machine_rule), trial))
    if not scored_trials:
        raise RuntimeError(f"工序 {op.expanded_op_id} 没有 active 可行设备组合")
    scored_trials.sort(key=lambda x: x[0])
    if not randomize_top_k or top_k <= 1:
        return scored_trials[0][1]
    pool = scored_trials[: max(1, min(int(top_k), len(scored_trials)))]
    scalar_scores = [sum((10**-i) * float(part) for i, part in enumerate(score)) for score, _ in pool]
    best_score, worst_score = min(scalar_scores), max(scalar_scores)
    span = max(1.0, worst_score - best_score)
    temp = max(float(temperature), 1e-6)
    weights = [math.exp(-((s - best_score) / span) / temp) for s in scalar_scores]
    return rng.choices([trial for _, trial in pool], weights=weights, k=1)[0]


def records_from_machine_timelines(machine_timeline, machines, operations, distance):
    records = []
    for mid, timeline in machine_timeline.items():
        if mid not in machines:
            continue
        machine = machines[mid]
        timeline.sort(key=lambda x: (x["start"], x["end"], x["op_id"]))
        prev_loc = machine.initial_location
        for item in timeline:
            op = operations[item["op_id"]]
            transport = calc_transport_time(machine, prev_loc, op.workshop, distance)
            records.append(
                {
                    "设备编号": machine.machine_id, "设备类型": machine.type,
                    "班组": machine.team, "是否新购": bool(machine.purchased),
                    "车间": op.workshop, "原始工序编号": op.base_op_id,
                    "内部工序编号": op.expanded_op_id, "工序编号": op.base_op_id,
                    "起始秒": int(item["start"]), "结束秒": int(item["end"]),
                    "起始时间": seconds_to_hhmmss(item["start"]),
                    "结束时间": seconds_to_hhmmss(item["end"]),
                    "持续工作时间(s)": int(item["duration"]),
                    "运输时间(s)": int(transport),
                }
            )
            prev_loc = op.workshop
    return records


# ──────────────────────────────────────────────
# Record building & schedule finalization
# ──────────────────────────────────────────────


def records_from_trial(op, trial):
    records = []
    for x in trial:
        m = x["machine"]
        records.append(
            {
                "设备编号": m.machine_id, "设备类型": m.type, "班组": m.team,
                "是否新购": bool(m.purchased), "车间": op.workshop,
                "原始工序编号": op.base_op_id, "内部工序编号": op.expanded_op_id,
                "工序编号": op.base_op_id,
                "起始秒": int(x["start"]), "结束秒": int(x["end"]),
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


# ──────────────────────────────────────────────
# Topological order construction
# ──────────────────────────────────────────────


def compute_workshop_due_weights(schedule_df):
    if schedule_df is None or schedule_df.empty or "车间" not in schedule_df or "结束秒" not in schedule_df:
        return {}
    completion = schedule_df.groupby("车间")["结束秒"].max()
    if completion.empty:
        return {}
    max_finish = float(completion.max())
    min_finish = float(completion.min())
    span = max(1.0, max_finish - min_finish)
    return {str(w): float((finish - min_finish) / span) for w, finish in completion.items()}


def bottleneck_need_score(op, bottleneck_types):
    if not bottleneck_types:
        return 0.0
    count = len(set(op.required_types) & set(bottleneck_types))
    if count <= 0:
        return 0.0
    return 1.2 if count >= 2 else 1.0


def bottleneck_operation_score(
    op_id, operations, machines, critical, max_remaining, max_processing,
    bottleneck_types=None, workshop_due_weights=None,
):
    op = operations[op_id]
    proc = theoretical_min_processing_time(op, machines) if machines else 0
    rem = critical.get(op_id, proc)
    normalized_remaining = float(rem) / max(1.0, float(max_remaining))
    normalized_processing = float(proc) / max(1.0, float(max_processing))
    due_weight = float((workshop_due_weights or {}).get(op.workshop, 0.0))
    return (
        0.45 * bottleneck_need_score(op, bottleneck_types)
        + 0.30 * normalized_remaining
        + 0.15 * due_weight
        + 0.10 * normalized_processing
    )


def build_topological_order(
    operations, workshop_ops, mode="round_robin", rng=None,
    machines=None, bottleneck_types=None, workshop_due_weights=None,
):
    rng = rng or random.Random(RANDOM_SEED)
    machines = machines or {}
    bottleneck_types = set(bottleneck_types or [])
    workshop_due_weights = workshop_due_weights or {}
    pos, order = {w: 0 for w in workshop_ops}, []
    total = sum(len(v) for v in workshop_ops.values())
    critical = remaining_chain_lengths(operations, workshop_ops, machines) if machines else {}
    max_remaining = max(critical.values(), default=1)
    while len(order) < total:
        eligible = [workshop_ops[w][i] for w, i in pos.items() if i < len(workshop_ops[w])]
        max_processing = max(
            [theoretical_min_processing_time(operations[op_id], machines) for op_id in eligible],
            default=1,
        )
        if mode == "alphabetical":
            chosen = min(eligible, key=lambda op_id: (operations[op_id].workshop, operations[op_id].order))
        elif mode in {"shortest_processing_time", "spt"}:
            chosen = min(eligible, key=lambda op_id: (theoretical_min_processing_time(operations[op_id], machines), op_id))
        elif mode == "critical_path_first":
            chosen = max(eligible, key=lambda op_id: (critical.get(op_id, 0), -operations[op_id].order))
        elif mode == "bottleneck_machine_aware":
            chosen = max(
                eligible,
                key=lambda op_id: (
                    bottleneck_operation_score(
                        op_id, operations, machines, critical, max_remaining, max_processing,
                        bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
                    ),
                    -operations[op_id].order, operations[op_id].workshop,
                ),
            )
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


# ──────────────────────────────────────────────
# Scheduling decoders
# ──────────────────────────────────────────────


def schedule_by_order(
    operations, workshop_ops, machines, distance,
    allowed_teams=None, selected_workshops=None, priority_order=None,
    machine_rule="earliest_completion_time", problem_name=None, rng=None,
    assignment_top_k=1, randomize_assignment_top_k=False,
    assignment_temperature=1.0, max_candidates_per_type=None,
):
    rng = rng or random.Random(RANDOM_SEED)
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
            trial = choose_assignment(
                op, machines, distance, m_avail, m_loc, pred_done,
                machine_rule, rng=rng, top_k=assignment_top_k,
                randomize_top_k=randomize_assignment_top_k,
                temperature=assignment_temperature,
                max_candidates_per_type=max_candidates_per_type,
            )
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


def schedule_by_order_active(
    operations, workshop_ops, machines, distance,
    allowed_teams=None, selected_workshops=None, priority_order=None,
    machine_rule="earliest_completion_time", problem_name=None, rng=None,
    assignment_top_k=1, randomize_assignment_top_k=False,
    assignment_temperature=1.0, max_candidates_per_type=None,
):
    rng = rng or random.Random(RANDOM_SEED)
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

    machine_timeline = {mid: [] for mid in machines}
    op_complete, unscheduled = {}, set(op_set)
    while unscheduled:
        progress = False
        for op_id in priority_order:
            if op_id not in unscheduled:
                continue
            pred_done = predecessors_done(op_id, operations, workshop_ops, op_complete)
            if pred_done is None:
                continue
            op = operations[op_id]
            trial = choose_assignment_active(
                op, machines, distance, machine_timeline, int(pred_done),
                machine_rule=machine_rule, rng=rng, top_k=assignment_top_k,
                randomize_top_k=randomize_assignment_top_k,
                temperature=assignment_temperature,
                max_candidates_per_type=max_candidates_per_type,
            )
            for x in trial:
                m = x["machine"]
                entry = {
                    "start": int(x["start"]), "end": int(x["end"]),
                    "workshop": op.workshop, "op_id": op_id,
                    "duration": int(x["duration"]),
                }
                machine_timeline[m.machine_id].insert(int(x["insert_index"]), entry)
                machine_timeline[m.machine_id].sort(key=lambda y: (y["start"], y["end"], y["op_id"]))
            op_complete[op_id] = max(x["end"] for x in trial)
            unscheduled.remove(op_id)
            progress = True
        if not progress:
            raise RuntimeError("active 调度解码失败：存在无法满足的前序关系")
    records = records_from_machine_timelines(machine_timeline, machines, operations, distance)
    return finalize_schedule(records, problem_name), int(max(op_complete.values()) if op_complete else 0)


def decode_order_with_decoder(
    operations, workshop_ops, machines, distance, allowed_teams, order,
    decoder="append", max_candidates_per_type=None,
):
    if decoder == "active":
        return schedule_by_order_active(
            operations, workshop_ops, machines, distance,
            allowed_teams=allowed_teams, priority_order=order,
            max_candidates_per_type=max_candidates_per_type,
        )
    return schedule_by_order(
        operations, workshop_ops, machines, distance,
        allowed_teams=allowed_teams, priority_order=order,
        max_candidates_per_type=max_candidates_per_type,
    )


# ──────────────────────────────────────────────
# Dispatching-rule scheduler (true dispatch)
# ──────────────────────────────────────────────


def dispatch_schedule(
    operations, workshop_ops, machines, distance,
    allowed_teams=None, operation_rule="earliest_completion_time",
    machine_rule="earliest_completion_time", rng=None, problem_name=None,
    assignment_top_k=1, randomize_assignment_top_k=False,
    assignment_temperature=1.0, max_candidates_per_type=None,
    bottleneck_types=None, workshop_due_weights=None,
):
    rng = rng or random.Random(RANDOM_SEED)
    if allowed_teams is not None:
        machines = {k: v for k, v in machines.items() if v.team in set(allowed_teams)}
    bottleneck_types = set(bottleneck_types or [])
    workshop_due_weights = workshop_due_weights or {}
    m_avail = {mid: 0 for mid in machines}
    m_loc = {mid: machines[mid].initial_location for mid in machines}
    op_set = set(itertools.chain.from_iterable(workshop_ops.values()))
    op_complete, records, order, unscheduled = {}, [], [], set(op_set)
    critical = remaining_chain_lengths(operations, workshop_ops, machines)
    max_remaining = max(critical.values(), default=1)

    while unscheduled:
        eligible = []
        for op_id in sorted(unscheduled):
            pred_done = predecessors_done(op_id, operations, workshop_ops, op_complete)
            if pred_done is not None:
                eligible.append((op_id, pred_done))
        if not eligible:
            raise RuntimeError("调度派工失败：没有可调度工序")

        scored = []
        max_processing = max(
            [theoretical_min_processing_time(operations[op_id], machines) for op_id, _ in eligible],
            default=1,
        )
        for op_id, pred_done in eligible:
            op = operations[op_id]
            trial = choose_assignment(
                op, machines, distance, m_avail, m_loc, pred_done,
                machine_rule, rng=rng, top_k=assignment_top_k,
                randomize_top_k=randomize_assignment_top_k,
                temperature=assignment_temperature,
                max_candidates_per_type=max_candidates_per_type,
            )
            if operation_rule == "alphabetical":
                score = (op.workshop, op.order)
            elif operation_rule in {"shortest_processing_time", "spt"}:
                score = (theoretical_min_processing_time(op, machines), op.workshop, op.order)
            elif operation_rule == "critical_path_first":
                score = (-critical.get(op_id, 0), op.workshop, op.order)
            elif operation_rule == "bottleneck_machine_aware":
                bn_score = bottleneck_operation_score(
                    op_id, operations, machines, critical, max_remaining, max_processing,
                    bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
                )
                score = (-bn_score, op.order, op.workshop)
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


# ──────────────────────────────────────────────
# Topological order validation
# ──────────────────────────────────────────────


def is_valid_topological_order(order, operations, workshop_ops):
    pos = {op_id: i for i, op_id in enumerate(order)}
    if len(pos) != len(order):
        return False
    for _, seq in workshop_ops.items():
        for a, b in zip(seq, seq[1:]):
            if pos.get(a, -1) >= pos.get(b, -1):
                return False
    return True


# ──────────────────────────────────────────────
# Tabu-aware local search with SA acceptance
# ──────────────────────────────────────────────


def _make_move_key(i, j):
    """Canonical key for a swap move (order-independent)."""
    return (min(i, j), max(i, j))


def _make_insert_key(old_idx, new_idx):
    """Canonical key for an insert move."""
    return (old_idx, new_idx)


def local_search_tabu_sa(
    operations, workshop_ops, machines, distance, allowed_teams,
    start_order, start_cmax, rng, attempts,
    max_candidates_per_type=None, progress_label=None,
    progress_start_time=None, decoder="append",
    sa_t0=SA_T0, sa_alpha=SA_ALPHA, sa_t_min=SA_T_MIN,
    tabu_tenure=TABU_BASE_TENURE,
):
    """
    Local search with:
      - Tabu list to avoid revisiting recent moves
      - Simulated annealing acceptance for worsening moves
      - Neighborhood: swap + insert on the full order
    """
    best_order = list(start_order)
    best_cmax = start_cmax
    best_df = None
    current_order = list(start_order)
    current_cmax = start_cmax
    improvements = 0
    n = len(current_order)
    if n < 2:
        return best_df, best_cmax, best_order, improvements

    tabu = {}  # move_key -> iteration when it expires
    temperature = sa_t0

    for attempt in range(attempts):
        done = attempt + 1

        # --- Generate neighborhood ---
        candidates_moves = []
        # Swap moves
        for _ in range(min(20, n)):
            i, j = sorted(rng.sample(range(n), 2))
            key = _make_move_key(i, j)
            candidate = list(current_order)
            candidate[i], candidate[j] = candidate[j], candidate[i]
            if not is_valid_topological_order(candidate, operations, workshop_ops):
                continue
            df, cmax = decode_order_with_decoder(
                operations, workshop_ops, machines, distance, allowed_teams,
                candidate, decoder=decoder, max_candidates_per_type=max_candidates_per_type,
            )
            is_tabu = tabu.get(key, -1) >= attempt
            candidates_moves.append((cmax, candidate, df, key, is_tabu))

        # Insert moves
        for _ in range(min(10, n)):
            old_idx = rng.randint(0, n - 1)
            new_idx = rng.randint(0, n - 1)
            if old_idx == new_idx:
                continue
            key = _make_insert_key(old_idx, new_idx)
            candidate = list(current_order)
            op_id = candidate.pop(old_idx)
            candidate.insert(new_idx, op_id)
            if not is_valid_topological_order(candidate, operations, workshop_ops):
                continue
            df, cmax = decode_order_with_decoder(
                operations, workshop_ops, machines, distance, allowed_teams,
                candidate, decoder=decoder, max_candidates_per_type=max_candidates_per_type,
            )
            is_tabu = tabu.get(key, -1) >= attempt
            candidates_moves.append((cmax, candidate, df, key, is_tabu))

        if not candidates_moves:
            temperature *= sa_alpha
            if progress_label and should_print_progress(done, attempts):
                print_solver_progress(progress_label, "TS+SA局部搜索", done, attempts, best_cmax, progress_start_time)
            continue

        # --- Select best move (with tabu aspiration + SA acceptance) ---
        candidates_moves.sort(key=lambda x: x[0])
        chosen = None
        for cmax, candidate, df, key, is_tabu in candidates_moves:
            # Aspiration: accept tabu move if it's better than global best
            if is_tabu and cmax >= best_cmax:
                continue
            delta = cmax - current_cmax
            if delta <= 0:
                chosen = (cmax, candidate, df, key)
                break
            # SA acceptance for worsening move
            if temperature > sa_t_min and rng.random() < math.exp(-delta / temperature):
                chosen = (cmax, candidate, df, key)
                break
        if chosen is None:
            # Fallback: take absolute best even if tabu
            cmax, candidate, df, key, _ = candidates_moves[0]
            chosen = (cmax, candidate, df, key)

        cmax, candidate, df, key = chosen
        current_order = candidate
        current_cmax = cmax
        tabu[key] = attempt + (tabu_tenure + (rng.randint(0, tabu_tenure) if TABU_DYNAMIC else 0))

        if cmax < best_cmax:
            best_order, best_cmax, best_df = list(candidate), cmax, df
            improvements += 1

        temperature *= sa_alpha
        temperature = max(temperature, sa_t_min)

        if progress_label and should_print_progress(done, attempts):
            print_solver_progress(progress_label, "TS+SA局部搜索", done, attempts, best_cmax, progress_start_time)

    return best_df, best_cmax, best_order, improvements


# ──────────────────────────────────────────────
# CPM-aware bottleneck local search
# ──────────────────────────────────────────────


def identify_critical_like_tasks(schedule_df, operations, top_k=20):
    columns = [
        "内部工序编号", "原始工序编号", "车间", "设备编号",
        "设备类型", "起始秒", "结束秒", "critical_score", "原因",
    ]
    if schedule_df is None or schedule_df.empty:
        return pd.DataFrame(columns=columns)
    op_col = "内部工序编号" if "内部工序编号" in schedule_df.columns else "工序编号"
    makespan = int(schedule_df["结束秒"].max()) if "结束秒" in schedule_df else 0
    if makespan <= 0:
        return pd.DataFrame(columns=columns)
    workshop_completion = schedule_df.groupby("车间")["结束秒"].max()
    latest_workshops = set(workshop_completion[workshop_completion == workshop_completion.max()].index)
    type_stats = compute_machine_type_statistics(schedule_df, makespan)
    bottleneck_types = set(type_stats.head(2)["设备类型"].tolist()) if not type_stats.empty else set()
    max_duration = max(float(schedule_df["持续工作时间(s)"].max()), 1.0)
    rows = []
    for _, row in schedule_df.iterrows():
        reasons = []
        score = 0.0
        if row["车间"] in latest_workshops:
            score += 0.35
            reasons.append("latest_workshop")
        near = float(row["结束秒"]) / max(1.0, float(makespan))
        if near >= 0.85:
            score += 0.30 * near
            reasons.append("near_makespan")
        if row["设备类型"] in bottleneck_types:
            score += 0.25
            reasons.append("bottleneck_machine")
        duration_ratio = float(row["持续工作时间(s)"]) / max_duration
        if duration_ratio >= 0.5:
            score += 0.10 * duration_ratio
            reasons.append("long_duration")
        if not reasons:
            continue
        op_id = row[op_col]
        op = operations.get(op_id)
        rows.append(
            {
                "内部工序编号": op_id,
                "原始工序编号": op.base_op_id if op is not None else row.get("原始工序编号", ""),
                "车间": row["车间"],
                "设备编号": row["设备编号"],
                "设备类型": row["设备类型"],
                "起始秒": int(row["起始秒"]),
                "结束秒": int(row["结束秒"]),
                "critical_score": float(score),
                "原因": "；".join(reasons),
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["critical_score", "结束秒"], ascending=False
    ).head(max(1, int(top_k)))


def bottleneck_tabu_sa_local_search(
    operations, workshop_ops, machines, distance, allowed_teams,
    current_order, current_cmax, current_schedule_df,
    bottleneck_types, rng, attempts=100,
    max_candidates_per_type=None, progress_label=None,
    progress_start_time=None, decoder="append",
    sa_t0=SA_T0, sa_alpha=SA_ALPHA, sa_t_min=SA_T_MIN,
    tabu_tenure=TABU_BASE_TENURE,
):
    """
    CPM-aware Tabu+SA local search focused on bottleneck/critical operations.
    """
    bottleneck_types = set(bottleneck_types or [])
    best_order = list(current_order)
    best_cmax = current_cmax
    best_df = None
    current_order_local = list(current_order)
    current_cmax_local = current_cmax
    improvements = 0
    n = len(best_order)
    if not bottleneck_types or current_schedule_df is None or current_schedule_df.empty or n < 2:
        return best_df, best_cmax, best_order, improvements
    op_col = "内部工序编号" if "内部工序编号" in current_schedule_df.columns else "工序编号"
    if op_col not in current_schedule_df or "设备类型" not in current_schedule_df:
        return best_df, best_cmax, best_order, improvements

    # Collect candidate operations: critical path + bottleneck + structural
    critical_df = identify_critical_like_tasks(current_schedule_df, operations, top_k=max(20, n))
    critical_ops = []
    if not critical_df.empty and "内部工序编号" in critical_df:
        critical_ops = [
            op_id for op_id in critical_df["内部工序编号"].dropna().astype(str).tolist() if op_id in operations
        ]
    scheduled_bn_ops = [
        op_id for op_id in current_schedule_df[
            current_schedule_df["设备类型"].isin(bottleneck_types)
        ][op_col].dropna().astype(str)
        if op_id in operations
    ]
    seen = set()
    scheduled_bn_ops = [x for x in scheduled_bn_ops if not (x in seen or seen.add(x))]
    structural_bn_ops = [
        op_id for op_id in best_order if set(operations[op_id].required_types) & bottleneck_types
    ]
    candidate_ops = list(dict.fromkeys(critical_ops + scheduled_bn_ops + structural_bn_ops))
    if len(candidate_ops) < 1:
        return best_df, best_cmax, best_order, improvements

    tabu = {}
    temperature = sa_t0

    for attempt in range(max(0, int(attempts))):
        done = attempt + 1
        candidate = list(current_order_local)
        pos = {op_id: i for i, op_id in enumerate(candidate)}

        # --- Generate a move ---
        move_type = attempt % 4
        if move_type == 0 and len(candidate_ops) >= 2:
            # Swap two candidate ops
            a, b = rng.sample(candidate_ops, 2)
            if a not in pos or b not in pos:
                continue
            i, j = pos[a], pos[b]
            candidate[i], candidate[j] = candidate[j], candidate[i]
            key = _make_move_key(i, j)
        elif move_type == 1:
            # Insert: move a candidate op forward
            op_id = rng.choice(candidate_ops)
            if op_id not in pos:
                continue
            old_idx = pos[op_id]
            if old_idx == 0:
                continue
            step = rng.randint(1, min(8, old_idx))
            new_idx = max(0, old_idx - step)
            candidate.pop(old_idx)
            candidate.insert(new_idx, op_id)
            key = _make_insert_key(old_idx, new_idx)
        elif move_type == 2:
            # Insert: move toward predecessor
            op_id = rng.choice(candidate_ops)
            if op_id not in pos:
                continue
            old_idx = pos[op_id]
            seq = workshop_ops[operations[op_id].workshop]
            seq_idx = seq.index(op_id)
            pred_pos = -1
            if seq_idx > 0 and seq[seq_idx - 1] in pos:
                pred_pos = pos[seq[seq_idx - 1]]
            if old_idx <= pred_pos + 1:
                continue
            new_idx = rng.randint(pred_pos + 1, old_idx - 1)
            candidate.pop(old_idx)
            candidate.insert(new_idx, op_id)
            key = _make_insert_key(old_idx, new_idx)
        else:
            # Swap: one candidate + one random neighbor
            a = rng.choice(candidate_ops)
            if a not in pos:
                continue
            i = pos[a]
            # Pick a nearby op
            lo = max(0, i - 3)
            hi = min(n - 1, i + 3)
            if lo == hi:
                continue
            j = rng.randint(lo, hi)
            if j == i:
                continue
            candidate[i], candidate[j] = candidate[j], candidate[i]
            key = _make_move_key(i, j)

        if not is_valid_topological_order(candidate, operations, workshop_ops):
            if progress_label and should_print_progress(done, attempts):
                print_solver_progress(progress_label, "瓶颈TS+SA", done, attempts, best_cmax, progress_start_time)
            continue

        df, cmax = decode_order_with_decoder(
            operations, workshop_ops, machines, distance, allowed_teams,
            candidate, decoder=decoder, max_candidates_per_type=max_candidates_per_type,
        )

        is_tabu = tabu.get(key, -1) >= attempt
        if is_tabu and cmax >= best_cmax:
            if progress_label and should_print_progress(done, attempts):
                print_solver_progress(progress_label, "瓶颈TS+SA", done, attempts, best_cmax, progress_start_time)
            continue

        delta = cmax - current_cmax_local
        accept = False
        if delta <= 0:
            accept = True
        elif temperature > sa_t_min and rng.random() < math.exp(-delta / temperature):
            accept = True

        if accept:
            current_order_local = candidate
            current_cmax_local = cmax
            tabu[key] = attempt + (tabu_tenure + (rng.randint(0, tabu_tenure) if TABU_DYNAMIC else 0))
            if cmax < best_cmax:
                best_order, best_cmax, best_df = list(candidate), cmax, df
                improvements += 1
                current_schedule_df = df

        temperature *= sa_alpha
        temperature = max(temperature, sa_t_min)

        if progress_label and should_print_progress(done, attempts):
            print_solver_progress(progress_label, "瓶颈TS+SA", done, attempts, best_cmax, progress_start_time)

    return best_df, best_cmax, best_order, improvements


# ──────────────────────────────────────────────
# Problem 1 (exact enumeration)
# ──────────────────────────────────────────────


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
                        "machine": m, "start": int(start), "end": int(start + dur),
                        "duration": int(dur), "transport": int(trans),
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


# ──────────────────────────────────────────────
# Main optimization loop
# ──────────────────────────────────────────────


def optimize_schedule(
    operations, workshop_ops, machines, distance, allowed_teams,
    iterations=1000, strategies=None, local_search=True,
    random_seed=RANDOM_SEED, local_search_attempts=150,
    max_candidates_per_type=None, progress_label=None,
    bottleneck_local_search_attempts=100, decoder="mixed",
):
    progress_start_time = time.time() if progress_label else None
    rng = random.Random(random_seed)
    decoder = str(decoder or "append").lower()
    if decoder not in {"append", "active", "mixed"}:
        raise ValueError(f"未知 decoder: {decoder}; 可选 append/active/mixed")
    decoder_options = ["append", "active"] if decoder == "mixed" else [decoder]
    randomized_assignment_top_k = 3
    randomized_assignment_temperature = 0.5
    strategies = strategies or [
        "round_robin", "alphabetical", "shortest_processing_time",
        "earliest_completion_time", "critical_path_first",
        "bottleneck_machine_aware", "random_weighted",
    ]
    candidates = []
    strategy_best = {}
    metric_machines = machines if allowed_teams is None else {k: v for k, v in machines.items() if v.team in set(allowed_teams)}

    bottleneck_types, bottleneck_stats, bottleneck_source = get_bottleneck_types_for_scheduling(
        operations, workshop_ops, machines, distance, allowed_teams,
        sample_iterations=min(100, max(0, int(iterations))),
        top_k=2, random_seed=random_seed,
    )
    static_types, static_stats = static_bottleneck_types(operations, machines, allowed_teams=allowed_teams, top_k=2)
    try:
        ref_df, _, _ = dispatch_schedule(
            operations, workshop_ops, machines, distance,
            allowed_teams=allowed_teams, operation_rule="critical_path_first",
            machine_rule="earliest_completion_time", rng=random.Random(random_seed + 7919),
        )
        workshop_due_weights = compute_workshop_due_weights(ref_df)
    except Exception:
        workshop_due_weights = {}

    if progress_label:
        bn_text = "、".join(TYPE_CN.get(t, t) for t in bottleneck_types) if bottleneck_types else "N/A"
        print(
            f"{progress_label} 开始求解: iterations={iterations}, "
            f"local_search_attempts={local_search_attempts}, "
            f"bottleneck_local_search_attempts={bottleneck_local_search_attempts}, "
            f"decoder={decoder}, bottleneck_types=[{bn_text}], bottleneck_source={bottleneck_source}",
            flush=True,
        )

    def add_candidate(strategy_name, order, schedule_df, cmax, decoder_name):
        label = f"{strategy_name}+{decoder_name}"
        candidates.append((int(cmax), list(order), schedule_df, label, decoder_name))
        strategy_best[label] = min(strategy_best.get(label, int(cmax)), int(cmax))

    def try_decode_order(strategy_name, order, randomize_assignment=False, decoders_to_try=None):
        selected_decoders = list(decoders_to_try) if decoders_to_try is not None else list(decoder_options)
        for decoder_name in selected_decoders:
            try:
                if decoder_name == "active":
                    df, cmax = schedule_by_order_active(
                        operations, workshop_ops, machines, distance,
                        allowed_teams=allowed_teams, priority_order=order, rng=rng,
                        assignment_top_k=randomized_assignment_top_k if randomize_assignment else 1,
                        randomize_assignment_top_k=randomize_assignment,
                        assignment_temperature=randomized_assignment_temperature,
                        max_candidates_per_type=max_candidates_per_type,
                    )
                    feasible, _ = check_feasibility(
                        df,
                        operations,
                        machines,
                        distance,
                        verbose=False,
                    )
                    if not feasible:
                        if progress_label:
                            print(f"{progress_label} {strategy_name}+active 解码结果未通过可行性检查，已跳过", flush=True)
                        continue
                else:
                    df, cmax = schedule_by_order(
                        operations, workshop_ops, machines, distance,
                        allowed_teams=allowed_teams, priority_order=order, rng=rng,
                        assignment_top_k=randomized_assignment_top_k if randomize_assignment else 1,
                        randomize_assignment_top_k=randomize_assignment,
                        assignment_temperature=randomized_assignment_temperature,
                        max_candidates_per_type=max_candidates_per_type,
                    )
                add_candidate(strategy_name, order, df, cmax, decoder_name)
            except Exception as exc:
                if decoder_name == "active" and decoder == "mixed":
                    if progress_label:
                        print(f"{progress_label} {strategy_name}+active 解码失败，已跳过: {exc}", flush=True)
                    continue
                if progress_label:
                    print(f"{progress_label} {strategy_name}+{decoder_name} 解码失败: {exc}", flush=True)

    # --- Initial strategy sweep ---
    for strategy in strategies:
        if strategy in {"earliest_completion_time", "bottleneck_machine_aware"}:
            try:
                df, cmax, order = dispatch_schedule(
                    operations, workshop_ops, machines, distance, allowed_teams,
                    strategy, "earliest_completion_time", rng,
                    max_candidates_per_type=max_candidates_per_type,
                    bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
                )
                if "append" in decoder_options:
                    add_candidate(strategy, order, df, cmax, "append")
                if "active" in decoder_options:
                    try_decode_order(strategy, order, randomize_assignment=False, decoders_to_try=["active"])
            except Exception as exc:
                if progress_label:
                    print(f"{progress_label} {strategy} 派工失败: {exc}", flush=True)
        else:
            order = build_topological_order(
                operations, workshop_ops, mode=strategy, rng=rng, machines=metric_machines,
                bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
            )
            randomize_assignment = strategy in {"random", "random_weighted"}
            try_decode_order(strategy, order, randomize_assignment=randomize_assignment)

    if not candidates:
        raise RuntimeError("optimize_schedule 未生成任何可行候选排程")
    best_so_far = min(x[0] for x in candidates)
    if progress_label:
        print_solver_progress(progress_label, "初始策略", len(strategies), len(strategies), best_so_far, progress_start_time)

    # --- Heuristic iterations ---
    random_modes = ["random", "random_weighted", "critical_path_first", "bottleneck_machine_aware", "shortest_processing_time"]
    for i in range(iterations):
        strategy = random_modes[i % len(random_modes)]
        if strategy == "bottleneck_machine_aware" or (strategy in {"random", "random_weighted"} and i % 3 == 0):
            try:
                df, cmax, order = dispatch_schedule(
                    operations, workshop_ops, machines, distance, allowed_teams,
                    strategy, "earliest_completion_time", rng,
                    assignment_top_k=randomized_assignment_top_k,
                    randomize_assignment_top_k=True,
                    assignment_temperature=randomized_assignment_temperature,
                    max_candidates_per_type=max_candidates_per_type,
                    bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
                )
                if "append" in decoder_options:
                    add_candidate(strategy, order, df, cmax, "append")
                if "active" in decoder_options:
                    try_decode_order(
                        strategy,
                        order,
                        randomize_assignment=strategy in {"random", "random_weighted"},
                        decoders_to_try=["active"],
                    )
            except Exception as exc:
                if progress_label:
                    print(f"{progress_label} {strategy} 迭代派工失败: {exc}", flush=True)
        else:
            order = build_topological_order(
                operations, workshop_ops, mode=strategy, rng=rng, machines=metric_machines,
                bottleneck_types=bottleneck_types, workshop_due_weights=workshop_due_weights,
            )
            randomize_assignment = strategy in {"random", "random_weighted"}
            try_decode_order(strategy, order, randomize_assignment=randomize_assignment)
        if candidates and candidates[-1][0] < best_so_far:
            best_so_far = min(x[0] for x in candidates)
        done = i + 1
        if progress_label and should_print_progress(done, iterations):
            print_solver_progress(progress_label, "启发式迭代", done, iterations, best_so_far, progress_start_time)

    best_cmax, best_order, best_df, best_strategy, best_decoder = min(candidates, key=lambda x: x[0])

    # --- Tabu+SA local search ---
    improvements = 0
    bn_improvements = 0
    search_decoder = "active" if best_decoder == "active" else "append"
    final_decoder = search_decoder
    if local_search:
        ls_df, ls_cmax, ls_order, improvements = local_search_tabu_sa(
            operations, workshop_ops, machines, distance, allowed_teams,
            best_order, best_cmax, rng,
            attempts=max(0, int(local_search_attempts)),
            max_candidates_per_type=max_candidates_per_type,
            progress_label=progress_label, progress_start_time=progress_start_time,
            decoder=search_decoder,
        )
        if ls_df is not None and ls_cmax < best_cmax:
            best_df, best_cmax, best_order = ls_df, ls_cmax, ls_order
            best_strategy = f"{best_strategy}+TS-SA"
        if bottleneck_types:
            bn_df, bn_cmax, bn_order, bn_improvements = bottleneck_tabu_sa_local_search(
                operations, workshop_ops, machines, distance, allowed_teams,
                best_order, best_cmax, best_df, bottleneck_types, rng,
                attempts=max(0, int(bottleneck_local_search_attempts)),
                max_candidates_per_type=max_candidates_per_type,
                progress_label=progress_label, progress_start_time=progress_start_time,
                decoder=search_decoder,
            )
            if bn_df is not None and bn_cmax < best_cmax:
                best_df, best_cmax, best_order = bn_df, bn_cmax, bn_order
                best_strategy = f"{best_strategy}+BN-TS-SA"

    if progress_label:
        print(f"{progress_label} 求解完成: best={int(best_cmax)}s ({seconds_to_hhmmss(best_cmax)}), elapsed={format_elapsed(progress_start_time)}", flush=True)

    values = [x[0] for x in candidates]
    stats = {
        "iterations": len(candidates),
        "best": int(best_cmax),
        "mean": float(statistics.mean(values)),
        "std": float(statistics.pstdev(values)) if len(values) > 1 else 0.0,
        "worst": int(max(values)),
        "strategy_best": strategy_best,
        "best_strategy": best_strategy,
        "decoder": decoder,
        "best_decoder": best_decoder,
        "final_decoder": final_decoder,
        "active_best_used": best_decoder == "active" or "+active" in best_strategy,
        "local_search_improvements": improvements,
        "bottleneck_local_search_improvements": bn_improvements,
        "bottleneck_types_for_scheduling": bottleneck_types,
        "bottleneck_type_stats_for_scheduling": bottleneck_stats,
        "bottleneck_source": bottleneck_source,
        "static_bottleneck_types": static_types,
        "static_bottleneck_stats": static_stats,
        "workshop_due_weights": workshop_due_weights,
        "sa_params": {"t0": SA_T0, "alpha": SA_ALPHA, "t_min": SA_T_MIN},
        "tabu_params": {"base_tenure": TABU_BASE_TENURE, "dynamic": TABU_DYNAMIC},
        "randomized_assignment_enabled": True,
        "assignment_top_k": randomized_assignment_top_k,
        "assignment_temperature": randomized_assignment_temperature,
    }
    return best_df, int(best_cmax), stats, best_order


# ──────────────────────────────────────────────
# Purchase scheme generation & evaluation
# ──────────────────────────────────────────────


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
    prices: dict, budget: int, teams: list[int],
    max_total_new_machines: int | None = None,
    max_per_type_team: int | None = None,
    per_type_team_limit: dict | None = None,
) -> list[dict]:
    if not prices:
        return [{}]
    min_price = min(prices.values())
    theoretical_max = budget // min_price
    if max_total_new_machines is None:
        max_total_new_machines = min(theoretical_max, DEFAULT_MAX_TOTAL_NEW_MACHINES)
    if max_per_type_team is None:
        max_per_type_team = DEFAULT_MAX_PER_TYPE_TEAM
    max_total_new_machines = max(0, int(max_total_new_machines))
    max_per_type_team = max(0, int(max_per_type_team))

    keys = [(team, t) for team in teams for t in prices]
    candidates = [{}]

    def rec(idx, remaining_budget, remaining_count, scheme):
        if idx == len(keys):
            if scheme:
                candidates.append(dict(scheme))
            return
        team, t = keys[idx]
        local_limit = max_per_type_team
        if per_type_team_limit is not None:
            local_limit = per_type_team_limit.get((team, t), per_type_team_limit.get(t, max_per_type_team))
        max_cnt = min(int(local_limit), remaining_count, remaining_budget // prices[t])
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


# ──────────────────────────────────────────────
# Statistics & bottleneck analysis
# ──────────────────────────────────────────────


def compute_machine_type_statistics(schedule_df, makespan):
    columns = ["设备类型", "设备数量", "总工作时长(s)", "总运输时间(s)", "平均利用率", "运输时间占比", "作业记录数"]
    if schedule_df is None or schedule_df.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for t, g in schedule_df.groupby("设备类型"):
        machine_count = max(1, g["设备编号"].nunique())
        work = float(g["持续工作时间(s)"].sum())
        transport = float(g["运输时间(s)"].sum()) if "运输时间(s)" in g else 0.0
        rows.append(
            {
                "设备类型": t, "设备数量": int(machine_count),
                "总工作时长(s)": work, "总运输时间(s)": transport,
                "平均利用率": work / (makespan * machine_count) if makespan > 0 else np.nan,
                "运输时间占比": transport / (work + transport) if work + transport > 0 else 0.0,
                "作业记录数": int(len(g)),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(["平均利用率", "总工作时长(s)"], ascending=False)


def static_bottleneck_types(operations, machines, allowed_teams=None, top_k=2):
    if allowed_teams is not None:
        allowed = set(allowed_teams)
        machines = {k: v for k, v in machines.items() if v.team in allowed}
    count_by_type = Counter(m.type for m in machines.values())
    load_by_type = defaultdict(float)
    for op in operations.values():
        for t in op.required_types:
            cands = [m for m in machines.values() if m.type == t]
            if not cands:
                continue
            load_by_type[t] += min(calc_processing_time(op, m) for m in cands)
    rows = []
    for t, load in load_by_type.items():
        count = int(count_by_type.get(t, 0))
        pressure = float(load) / count if count > 0 else math.inf
        rows.append({"设备类型": t, "设备数量": count, "理论总负载(s)": float(load), "静态负载压力(s/台)": pressure})
    df = pd.DataFrame(rows, columns=["设备类型", "设备数量", "理论总负载(s)", "静态负载压力(s/台)"])
    if df.empty:
        return [], df
    df = df.sort_values(["静态负载压力(s/台)", "理论总负载(s)"], ascending=False).reset_index(drop=True)
    df["排名"] = range(1, len(df) + 1)
    return df["设备类型"].head(max(1, int(top_k))).tolist(), df


def identify_bottleneck_types(schedule_df, makespan, top_k=3):
    stats = compute_machine_type_statistics(schedule_df, makespan)
    if stats.empty:
        return []
    latest_workshops = set()
    if "车间" in schedule_df and "结束秒" in schedule_df:
        workshop_completion = schedule_df.groupby("车间")["结束秒"].max()
        if not workshop_completion.empty:
            max_finish = workshop_completion.max()
            latest_workshops = set(workshop_completion[workshop_completion == max_finish].index)
    max_work = max(float(stats["总工作时长(s)"].max()), 1.0)
    ranked = []
    for _, row in stats.iterrows():
        t = row["设备类型"]
        in_latest = 1.0 if not latest_workshops or not schedule_df[
            (schedule_df["设备类型"] == t) & (schedule_df["车间"].isin(latest_workshops))
        ].empty else 0.0
        score = (
            0.45 * float(row["平均利用率"])
            + 0.30 * float(row["总工作时长(s)"]) / max_work
            + 0.15 * float(row["运输时间占比"])
            + 0.10 * in_latest
        )
        ranked.append((score, t))
    ranked.sort(reverse=True)
    return [t for _, t in ranked[: max(1, int(top_k))]]


def get_bottleneck_types_for_scheduling(
    operations, workshop_ops, machines, distance, allowed_teams,
    sample_iterations=100, top_k=2, random_seed=RANDOM_SEED,
):
    available_types = {m.type for m in machines.values() if allowed_teams is None or m.team in set(allowed_teams)}
    fallback, fallback_df = static_bottleneck_types(operations, machines, allowed_teams=allowed_teams, top_k=top_k)
    try:
        rng = random.Random(random_seed)
        df, makespan, _ = dispatch_schedule(
            operations, workshop_ops, machines, distance,
            allowed_teams=allowed_teams, operation_rule="critical_path_first",
            machine_rule="earliest_completion_time", rng=rng,
        )
        stats = compute_machine_type_statistics(df, makespan)
        if stats.empty:
            return fallback, fallback_df, "static_fallback"
        max_work = max(float(stats["总工作时长(s)"].max()), 1.0)
        ranked = []
        for _, row in stats.iterrows():
            t = row["设备类型"]
            if t not in available_types:
                continue
            score = (
                0.45 * float(row["平均利用率"])
                + 0.35 * float(row["总工作时长(s)"]) / max_work
                + 0.20 * float(row["运输时间占比"])
            )
            ranked.append((score, t))
        ranked.sort(reverse=True)
        result = [t for _, t in ranked[: max(1, int(top_k))]]
        if not result:
            return fallback, fallback_df, "static_fallback"
        return result, stats, "dynamic"
    except Exception:
        return fallback, fallback_df, "static_fallback"


def compute_schedule_statistics(schedule_df, makespan):
    if schedule_df is None or schedule_df.empty:
        empty = pd.DataFrame()
        return {
            "workshop_completion": empty, "machine_type_stats": empty,
            "team_stats": empty, "new_machine_stats": empty,
            "bottleneck_type_stats": empty,
        }
    workshop_completion = schedule_df.groupby("车间")["结束秒"].max().reset_index()
    latest = workshop_completion["结束秒"].max()
    workshop_completion = workshop_completion.rename(columns={"结束秒": "完工时间(s)"})
    workshop_completion["完工时间(HH:MM:SS)"] = workshop_completion["完工时间(s)"].map(seconds_to_hhmmss)
    workshop_completion["是否最晚完工车间"] = workshop_completion["完工时间(s)"] == latest

    machine_type_stats = compute_machine_type_statistics(schedule_df, makespan)
    type_order = machine_type_stats.sort_values(["平均利用率", "总工作时长(s)"], ascending=False)

    team_rows = []
    for team, g in schedule_df.groupby("班组"):
        machine_count = max(1, g["设备编号"].nunique())
        work = float(g["持续工作时间(s)"].sum())
        transport = float(g["运输时间(s)"].sum())
        team_rows.append(
            {
                "班组": f"班组{int(team)}" if pd.notna(team) else "",
                "设备数量": int(machine_count), "总工作时长(s)": work,
                "总运输时间(s)": transport,
                "平均利用率": work / (makespan * machine_count) if makespan > 0 else np.nan,
                "作业记录数": int(len(g)),
            }
        )
    team_stats = pd.DataFrame(team_rows)

    new_rows = []
    if "是否新购" in schedule_df:
        for mid, g in schedule_df[schedule_df["是否新购"].astype(bool)].groupby("设备编号"):
            work = float(g["持续工作时间(s)"].sum())
            transport = float(g["运输时间(s)"].sum())
            first = g.iloc[0]
            new_rows.append(
                {
                    "设备编号": mid, "设备类型": first["设备类型"],
                    "班组": f"班组{int(first['班组'])}",
                    "总工作时长(s)": work, "总运输时间(s)": transport,
                    "利用率": work / makespan if makespan > 0 else np.nan,
                }
            )
    new_machine_stats = pd.DataFrame(new_rows)

    return {
        "workshop_completion": workshop_completion.sort_values("完工时间(s)", ascending=False),
        "machine_type_stats": machine_type_stats,
        "team_stats": team_stats,
        "new_machine_stats": new_machine_stats,
        "bottleneck_type_stats": type_order,
    }


# ──────────────────────────────────────────────
# Purchase scheme evaluation (worker & orchestrator)
# ──────────────────────────────────────────────


def evaluate_purchase_scheme_worker(args):
    (
        scheme, operations, workshop_ops, machines, distance, prices,
        budget, iterations, random_seed, local_search,
        local_search_attempts, bottleneck_local_search_attempts,
        max_candidates_per_type, decoder,
    ) = args
    try:
        machines_with_purchases = clone_with_purchases(machines, prices, scheme)
        df, cmax, stats, _ = optimize_schedule(
            operations, workshop_ops, machines_with_purchases, distance, [1, 2],
            iterations=max(0, int(iterations)), local_search=local_search,
            random_seed=random_seed,
            local_search_attempts=local_search_attempts,
            bottleneck_local_search_attempts=bottleneck_local_search_attempts,
            max_candidates_per_type=max_candidates_per_type, decoder=decoder,
        )
        feasible, _ = check_feasibility(
            df, operations, machines_with_purchases, distance,
            budget=budget, purchase_scheme=scheme, prices=prices, verbose=False,
        )
        cost = purchase_cost(scheme, prices)
        util = purchased_utilization(df, cmax)
        return {"scheme": scheme, "df": df, "makespan": cmax, "cost": cost, "util": util, "feasible": feasible, "stats": stats}
    except Exception as exc:
        try:
            cost = purchase_cost(scheme, prices)
        except Exception:
            cost = math.inf
        return {"scheme": scheme, "df": pd.DataFrame(), "makespan": math.inf, "cost": cost, "util": 0.0, "feasible": False, "stats": {"error": str(exc)}}


def should_print_purchase_progress(done, total):
    if total <= 0:
        return False
    interval = max(1, min(50, math.ceil(total / 20)))
    return done == 1 or done == total or done % interval == 0


def evaluate_purchase_schemes(
    schemes, operations, workshop_ops, machines, distance, prices,
    budget, iterations, random_seed, seed_offset, local_search,
    local_search_attempts, bottleneck_local_search_attempts,
    max_candidates_per_type, decoder, workers=1,
    stage_name="coarse", show_progress=True,
):
    schemes = list(schemes)
    total = len(schemes)
    if total == 0:
        return []

    tasks = []
    for idx, scheme in enumerate(schemes):
        seed = random_seed + seed_offset + idx * 17
        tasks.append(
            (scheme, operations, workshop_ops, machines, distance, prices,
             budget, iterations, seed, local_search, local_search_attempts,
             bottleneck_local_search_attempts, max_candidates_per_type, decoder)
        )

    if workers <= 1:
        rows = []
        for idx, task in enumerate(tasks):
            row = evaluate_purchase_scheme_worker(task)
            rows.append(row)
            done = idx + 1
            if show_progress and should_print_purchase_progress(done, total):
                print(f"问题4 {stage_name} 进度: {done}/{total}, cmax={row['makespan']}s, cost={row['cost']}, ok={row['feasible']}", flush=True)
        return rows

    rows = [None] * total
    done = 0
    best_feasible = math.inf
    max_workers = max(1, int(workers))
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(evaluate_purchase_scheme_worker, task): idx for idx, task in enumerate(tasks)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            row = future.result()
            rows[idx] = row
            done += 1
            if row.get("feasible") and row.get("makespan", math.inf) < best_feasible:
                best_feasible = row["makespan"]
            if show_progress and should_print_purchase_progress(done, total):
                best_text = f"{int(best_feasible)}s" if math.isfinite(best_feasible) else "N/A"
                print(f"问题4 {stage_name} 并行进度: {done}/{total}, best={best_text}", flush=True)
    return rows


# ──────────────────────────────────────────────
# Problem 4 orchestrator
# ──────────────────────────────────────────────


def schedule_problem_4(
    operations, workshop_ops, machines, distance, prices,
    budget=BUDGET, coarse_iterations=15, medium_iterations=80,
    refine_iterations=500, medium_k=30, top_k=8,
    random_seed=RANDOM_SEED, max_total_new_machines=None,
    max_per_type_team=None, max_candidates_per_type=6,
    local_search_attempts=150, bottleneck_local_search_attempts=100,
    workers=1, show_progress=True, decoder="mixed",
    reference_schedule_df=None, reference_makespan=None,
):
    min_price = min(prices.values()) if prices else 0
    theoretical_max = budget // min_price if min_price else 0
    effective_max_total = (
        min(theoretical_max, DEFAULT_MAX_TOTAL_NEW_MACHINES)
        if max_total_new_machines is None else int(max_total_new_machines)
    )
    effective_max_per_type = DEFAULT_MAX_PER_TYPE_TEAM if max_per_type_team is None else int(max_per_type_team)
    bottleneck_types = []
    bottleneck_guided = reference_schedule_df is not None and reference_makespan is not None
    if bottleneck_guided:
        bottleneck_types = identify_bottleneck_types(reference_schedule_df, reference_makespan, top_k=3)
    per_type_team_limit = {}
    for team in [1, 2]:
        for t in prices:
            per_type_team_limit[(team, t)] = effective_max_per_type if t in bottleneck_types else min(1, effective_max_per_type)

    candidates = generate_purchase_candidates(
        prices, budget, teams=[1, 2],
        max_total_new_machines=effective_max_total,
        max_per_type_team=effective_max_per_type,
        per_type_team_limit=per_type_team_limit if bottleneck_guided else None,
    )
    cap_note = (
        f"budget={budget}, candidates={len(candidates)}, "
        f"decoder={decoder}, bottleneck={[TYPE_CN.get(t,t) for t in bottleneck_types]}"
    )

    if show_progress:
        print(f"问题4 三阶段: {len(candidates)} candidates, coarse={coarse_iterations}, medium={medium_iterations}, refine={refine_iterations}", flush=True)

    # --- Coarse ---
    quick_rows = evaluate_purchase_schemes(
        candidates, operations, workshop_ops, machines, distance, prices,
        budget, iterations=coarse_iterations, random_seed=random_seed,
        seed_offset=0, local_search=False,
        local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        max_candidates_per_type=max_candidates_per_type, decoder=decoder,
        workers=workers, stage_name="coarse", show_progress=show_progress,
    )
    quick_rows.sort(key=lambda x: (not x["feasible"], x["makespan"], x["cost"]))
    medium_pool = quick_rows[: max(1, int(medium_k))]

    # --- Medium ---
    medium_rows = evaluate_purchase_schemes(
        [item["scheme"] for item in medium_pool], operations, workshop_ops, machines, distance, prices,
        budget, iterations=medium_iterations, random_seed=random_seed,
        seed_offset=10000, local_search=False,
        local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        max_candidates_per_type=max_candidates_per_type, decoder=decoder,
        workers=workers, stage_name="medium", show_progress=show_progress,
    )
    medium_rows.sort(key=lambda x: (not x["feasible"], x["makespan"], x["cost"]))
    refine_pool = medium_rows[: max(1, int(top_k))]

    # --- Refine ---
    refined_rows = evaluate_purchase_schemes(
        [item["scheme"] for item in refine_pool], operations, workshop_ops, machines, distance, prices,
        budget, iterations=refine_iterations, random_seed=random_seed,
        seed_offset=20000, local_search=True,
        local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        max_candidates_per_type=max_candidates_per_type, decoder=decoder,
        workers=1, stage_name="refine", show_progress=show_progress,
    )
    refined_rows.sort(key=lambda x: (not x["feasible"], x["makespan"], x["cost"]))
    best = refined_rows[0]
    if not math.isfinite(best["makespan"]):
        raise RuntimeError("问题4所有入围购置方案评价失败，无法生成可行排程")
    best_scheme = best["scheme"]
    machines_with_purchases = clone_with_purchases(machines, prices, best_scheme)
    p5 = pd.DataFrame(
        [{"设备名称": TYPE_CN.get(t, t), "班组1购买台数": best_scheme.get((1, t), 0), "班组2购买台数": best_scheme.get((2, t), 0)} for t in prices]
    )

    candidate_rows = []
    for rank, item in enumerate(quick_rows, 1):
        candidate_rows.append({
            "排名": rank, "购买总费用": item["cost"],
            "当前搜索最优可行时长(s)": item["makespan"],
            "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(item["makespan"]) if math.isfinite(item["makespan"]) else "",
            "班组1购买方案": scheme_to_text(item["scheme"], 1),
            "班组2购买方案": scheme_to_text(item["scheme"], 2),
            "新购设备利用率": item["util"], "是否通过可行性检查": item["feasible"],
        })

    p4_stats = {
        "purchase_candidate_note": cap_note, "budget": budget, "min_price": min_price,
        "theoretical_max_new_machines": theoretical_max,
        "max_total_new_machines": effective_max_total, "max_per_type_team": effective_max_per_type,
        "candidate_count": len(candidates),
        "coarse_iterations": coarse_iterations, "medium_iterations": medium_iterations,
        "refine_iterations": refine_iterations, "medium_k": medium_k, "top_k": top_k,
        "max_candidates_per_type": max_candidates_per_type,
        "local_search_attempts": local_search_attempts,
        "bottleneck_local_search_attempts": bottleneck_local_search_attempts,
        "workers": workers, "decoder": decoder,
        "bottleneck_types": bottleneck_types, "bottleneck_guided": bottleneck_guided,
        "per_type_team_limit": per_type_team_limit,
        "quick_candidates": pd.DataFrame(candidate_rows),
        "medium_count": len(medium_rows), "refined_count": len(refined_rows),
        "best_cost": best["cost"], "best_stats": best.get("stats", {}),
    }
    return best["df"], int(best["makespan"]), p5, best_scheme, machines_with_purchases, p4_stats


# ──────────────────────────────────────────────
# Feasibility checking
# ──────────────────────────────────────────────


def check_feasibility(
    schedule_df: pd.DataFrame, operations: dict, machines: dict, distance: dict,
    budget: int | None = None, purchase_scheme: dict | None = None,
    prices: dict | None = None, verbose: bool = True,
) -> tuple[bool, pd.DataFrame]:
    rows = []

    def add(name, ok, violations, note):
        rows.append({"检查项": name, "是否通过": bool(ok), "违规数量": int(violations), "说明": note})

    if schedule_df is None or schedule_df.empty:
        add("排程非空", False, 1, "schedule_df 为空")
        return False, pd.DataFrame(rows)

    op_col = "内部工序编号" if "内部工序编号" in schedule_df.columns else "工序编号"
    required_cols = {"设备编号", "设备类型", "车间", "起始秒", "结束秒", "持续工作时间(s)", op_col}
    missing_cols = required_cols - set(schedule_df.columns)
    add("排程字段完整性", not missing_cols, len(missing_cols), f"缺失: {sorted(missing_cols)}" if missing_cols else "完整")
    if missing_cols:
        return False, pd.DataFrame(rows)

    grouped = schedule_df.groupby(op_col)
    completeness_violations = 0
    type_violations = 0
    for op_id, op in operations.items():
        if op_id not in grouped.groups:
            completeness_violations += 1
            continue
        g = grouped.get_group(op_id)
        if len(g) != len(op.required_types):
            completeness_violations += 1
        if Counter(g["设备类型"]) != Counter(op.required_types):
            type_violations += 1
    extra_ops = set(schedule_df[op_col]) - set(operations)
    completeness_violations += len(extra_ops)
    add("工序完整性", completeness_violations == 0, completeness_violations, "每个工序出现次数与所需设备数一致")
    add("设备类型匹配", type_violations == 0, type_violations, "Counter 检查 required_types")

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
    add("设备类型逐行匹配", row_type_violations == 0, row_type_violations, "每条记录设备类型满足工序")
    add("加工时长正确性", duration_violations == 0, duration_violations, "ceil(workload/efficiency)")

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
    add("工序顺序约束", order_violations == 0, order_violations, "同一车间按内部顺序执行")

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
    add("设备不可重叠", overlap_violations == 0, overlap_violations, "同一设备相邻作业不重叠")
    add("首次运输时间", first_transport_violations == 0, first_transport_violations, "首任务从班组初始位置出发")
    add("跨车间运输时间", transport_violations == 0, transport_violations, "后续任务留足运输")

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
    add("双设备工序完成规则", dual_violations == 0, dual_violations, "双设备均完成完整工程量")

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
            budget_note = f"费用={cost}, 预算={budget}"
        except Exception as exc:
            budget_violations += 1
            budget_note = str(exc)
    add("问题4预算约束", budget_violations == 0, budget_violations, budget_note)

    result = pd.DataFrame(rows, columns=["检查项", "是否通过", "违规数量", "说明"])
    ok = bool(result["是否通过"].all())
    if verbose:
        print(result.to_string(index=False))
    return ok, result


# ──────────────────────────────────────────────
# Lower bounds
# ──────────────────────────────────────────────


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

    combined = max(cp, load_lb)
    return {
        "关键路径下界(s)": int(cp),
        "设备负载下界(s)": int(load_lb),
        "综合下界(s)": int(combined),
        "运输下界说明": "综合下界未计入运输时间，为乐观下界",
    }


def enhanced_lower_bounds(operations, workshop_ops, machines, allowed_teams=None):
    base = lower_bounds(operations, workshop_ops, machines, allowed_teams=allowed_teams)
    _, static_df = static_bottleneck_types(operations, machines, allowed_teams=allowed_teams, top_k=999)
    static_lb = 0
    if static_df is not None and not static_df.empty:
        static_lb = int(math.ceil(float(static_df["静态负载压力(s/台)"].max())))
    combined = max(int(base["综合下界(s)"]), static_lb)
    base["静态瓶颈负载下界(s)"] = static_lb
    base["综合下界(s)"] = int(combined)
    return base


# ──────────────────────────────────────────────
# Baseline comparison
# ──────────────────────────────────────────────


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
            try:
                if op_rule == "serial":
                    df, cmax = schedule_by_order(
                        check_operations, base_workshop_ops, check_machines, distance,
                        allowed_teams=allowed_teams, priority_order=ae_order, machine_rule=machine_rule,
                    )
                elif op_rule == "earliest_completion_time":
                    df, cmax, _ = dispatch_schedule(
                        check_operations, base_workshop_ops, check_machines, distance,
                        allowed_teams=allowed_teams, operation_rule=op_rule, machine_rule=machine_rule,
                    )
                else:
                    order = build_topological_order(check_operations, base_workshop_ops, op_rule, machines=check_machines)
                    df, cmax = schedule_by_order(
                        check_operations, base_workshop_ops, check_machines, distance,
                        allowed_teams=allowed_teams, priority_order=order, machine_rule=machine_rule,
                    )
                feasible, _ = check_feasibility(df, check_operations, check_machines, distance, verbose=False)
                baseline_values[col] = cmax if feasible else np.nan
            except Exception:
                baseline_values[col] = np.nan
        rows.append({"问题": problem_name, "本文启发式搜索(s)": heuristic_cmax, **baseline_values})
    result = pd.DataFrame(rows)
    for base_col in ["A→E串行(s)", "最快设备优先(s)", "最近可用设备优先(s)", "最早可用设备优先(s)", "最早完成优先(s)"]:
        improve_col = "相对" + base_col.replace("(s)", "改善率")
        result[improve_col] = result.apply(
            lambda r: (r[base_col] - r["本文启发式搜索(s)"]) / r[base_col]
            if pd.notna(r.get(base_col)) and r.get(base_col) not in (0, np.nan) else np.nan,
            axis=1,
        )
    return result


# ──────────────────────────────────────────────
# Output helpers
# ──────────────────────────────────────────────


def make_fill_table(schedule_df, include_team=False):
    cols = ["序号", "设备编号", "起始时间", "结束时间", "持续工作时间(s)", "工序编号"]
    if include_team:
        cols.append("班组")
    result = schedule_df[cols].copy()
    if include_team and "班组" in result:
        result["班组"] = result["班组"].map(lambda x: f"班组{int(x)}" if pd.notna(x) else "")
    result["序号"] = range(1, len(result) + 1)
    return result


def make_full_table(schedule_df, problem_name):
    cols = [
        "问题", "序号", "设备编号", "设备类型", "班组", "是否新购",
        "车间", "原始工序编号", "内部工序编号", "起始秒", "结束秒",
        "起始时间", "结束时间", "持续工作时间(s)", "运输时间(s)",
    ]
    df = schedule_df.copy()
    if "问题" not in df.columns:
        df.insert(0, "问题", problem_name)
    if "班组名称" not in df.columns and "班组" in df.columns:
        df.insert(df.columns.get_loc("班组") + 1, "班组名称", df["班组"].map(lambda x: f"班组{int(x)}" if pd.notna(x) else ""))
    if "班组名称" not in cols:
        cols.insert(cols.index("是否新购"), "班组名称")
    return df[cols]


def export_results(output_path, tables):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            safe_name = name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)


def plot_gantt(schedule, title, output_prefix, makespan=None):
    if schedule.empty:
        return []
    os.makedirs(os.path.dirname(output_prefix) or ".", exist_ok=True)
    df = schedule.copy()
    df["sort_key"] = list(zip(df["班组"], df["设备类型"], df["设备编号"]))
    machines_list = (
        df.sort_values(["班组", "设备类型", "设备编号"])["设备编号"]
        .drop_duplicates().tolist()
    )
    ypos = {m: i for i, m in enumerate(machines_list)}
    colors = dict(zip(WORKSHOPS, plt.cm.Set2.colors[: len(WORKSHOPS)]))

    fig_h = max(4.8, 0.42 * len(machines_list) + 1.8)
    fig, ax = plt.subplots(figsize=(16, fig_h))
    for _, r in df.iterrows():
        left = r["起始秒"] / 3600.0
        width = (r["结束秒"] - r["起始秒"]) / 3600.0
        hatch = "//" if bool(r.get("是否新购", False)) else None
        ax.barh(
            ypos[r["设备编号"]], width, left=left,
            color=colors.get(r["车间"], "lightgray"),
            edgecolor="black", linewidth=0.6 if hatch else 0.4, hatch=hatch,
        )
        if width > 0.03:
            ax.text(left + width / 2, ypos[r["设备编号"]], str(r["工序编号"]), va="center", ha="center", fontsize=7)
    labels = []
    machine_info = df.drop_duplicates("设备编号").set_index("设备编号")
    for mid in machines_list:
        r = machine_info.loc[mid]
        labels.append(f"T{int(r['班组'])} | {TYPE_CN.get(r['设备类型'], r['设备类型'])} | {mid}")
    ax.set_yticks(range(len(machines_list)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Time / h")
    display_title = f"{title}, makespan={seconds_to_hhmmss(makespan)}" if makespan is not None else title
    ax.set_title(display_title)
    ax.grid(axis="x", alpha=0.25, linestyle="--", linewidth=0.5)
    handles = [Patch(facecolor=colors[w], edgecolor="black", label=w) for w in WORKSHOPS]
    if df["是否新购"].astype(bool).any():
        handles.append(Patch(facecolor="white", edgecolor="black", hatch="//", label="Purchased"))
    ax.legend(handles=handles, title="Workshop", loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    fig.tight_layout(rect=[0, 0, 0.86, 1])
    paths = []
    for ext in ["png", "pdf"]:
        path = f"{output_prefix}.{ext}"
        fig.savefig(path, dpi=240)
        paths.append(path)
    plt.close(fig)
    return paths


def find_input_file(user_path=None):
    if user_path:
        if os.path.exists(user_path):
            return user_path
        raise FileNotFoundError(f"找不到指定输入文件: {user_path}")
    common_names = ["B-attachment.xlsx", "B-附件.xlsx", "附件.xlsx", "B.xlsx"]
    search_dirs = [".", "data"]
    for directory in search_dirs:
        for name in common_names:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return path
    candidates = []
    for directory in search_dirs:
        if os.path.isdir(directory):
            candidates.extend(os.path.join(directory, x) for x in os.listdir(directory) if x.lower().endswith(".xlsx"))
    candidates = sorted(set(candidates))
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise FileNotFoundError("找到多个 .xlsx 文件，请用 --file 指定: " + ", ".join(candidates))
    raise FileNotFoundError("找不到输入 Excel 文件，请将附件放在当前目录/data 目录，或使用 --file 指定")


# ──────────────────────────────────────────────
# CLI & main
# ──────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(description="FJSP solver for 51MCM Problem B (optimized)")
    parser.add_argument("--file", default=None, help="输入 Excel 文件路径")
    parser.add_argument("--out", default=None, help="输出 Excel 文件路径")
    parser.add_argument("--output-dir", default="outputs", help="输出目录")
    parser.add_argument("--no-plots", action="store_true", help="不生成甘特图")
    parser.add_argument("--decoder", choices=["append", "active", "mixed"], default="mixed")
    parser.add_argument("--p2-iter", type=int, default=1000)
    parser.add_argument("--p3-iter", type=int, default=1000)
    parser.add_argument("--p4-coarse-iter", "--p4-quick-iter", dest="p4_coarse_iter", type=int, default=15)
    parser.add_argument("--p4-medium-iter", type=int, default=80)
    parser.add_argument("--p4-refine-iter", type=int, default=500)
    parser.add_argument("--p4-medium-k", type=int, default=30)
    parser.add_argument("--p4-top-k", type=int, default=8)
    parser.add_argument("--max-candidates-per-type", type=int, default=6)
    parser.add_argument("--local-search-attempts", type=int, default=200)
    parser.add_argument("--bottleneck-local-search-attempts", type=int, default=150)
    parser.add_argument("--sa-t0", type=float, default=SA_T0, help="SA initial temperature")
    parser.add_argument("--sa-alpha", type=float, default=SA_ALPHA, help="SA cooling rate")
    parser.add_argument("--tabu-tenure", type=int, default=TABU_BASE_TENURE, help="Tabu base tenure")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--max-new-machines", type=int, default=None)
    parser.add_argument("--max-per-type-team", type=int, default=None)
    parser.add_argument("--no-expand-c", action="store_true")
    return parser.parse_args()


def main(
    file_path=None, output_xlsx=None, output_dir="outputs", make_plots=True,
    p2_iterations=1000, p3_iterations=1000,
    p4_coarse_iterations=15, p4_medium_iterations=80, p4_refine_iterations=500,
    p4_medium_k=30, p4_top_k=8, max_candidates_per_type=6,
    local_search_attempts=200, bottleneck_local_search_attempts=150,
    workers=1, show_progress=True, decoder="mixed",
    max_total_new_machines=None, max_per_type_team=None,
    expand_c_repeated_ops=EXPAND_C_REPEATED_OPS,
    sa_t0=SA_T0, sa_alpha=SA_ALPHA, tabu_tenure=TABU_BASE_TENURE,
):
    global SA_T0, SA_ALPHA, TABU_BASE_TENURE
    SA_T0 = sa_t0
    SA_ALPHA = sa_alpha
    TABU_BASE_TENURE = tabu_tenure

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    file_path = find_input_file(file_path)
    os.makedirs(output_dir, exist_ok=True)
    if output_xlsx is None:
        output_xlsx = os.path.join(output_dir, "fjsp_results.xlsx")

    dfs = load_data(file_path)
    (
        operations, workshop_ops, machines, distance, prices,
        expansion_df, warnings, distance_format, efficiency_notes_df,
    ) = preprocess_data(dfs, expand_c_repeated_ops=expand_c_repeated_ops)
    p1_operations = subset_operations(operations, ["A"])
    p1_workshop_ops = workshop_ops_from_operations(p1_operations)

    print(f"工序: {len(operations)}, 设备: {len(machines)}, 类型: {len(set(m.type for m in machines.values()))}")

    if show_progress:
        print("主流程: 开始求解问题1", flush=True)
    p1_df, p1_c = schedule_problem_1(operations, workshop_ops, machines, distance)
    if show_progress:
        print(f"主流程: 问题1完成 = {p1_c}s", flush=True)
        print("主流程: 开始求解问题2", flush=True)
    p2_df, p2_c, p2_stats, _ = optimize_schedule(
        operations, workshop_ops, machines, distance, [1],
        iterations=p2_iterations, local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        progress_label="问题2" if show_progress else None, decoder=decoder,
    )
    if show_progress:
        print("主流程: 开始求解问题3", flush=True)
    p3_df, p3_c, p3_stats, _ = optimize_schedule(
        operations, workshop_ops, machines, distance, [1, 2],
        iterations=p3_iterations, local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        progress_label="问题3" if show_progress else None, decoder=decoder,
    )
    if show_progress:
        print("主流程: 开始求解问题4", flush=True)
    p4_df, p4_c, p5_df, best_purchase_scheme, machines_with_purchases, p4_stats = schedule_problem_4(
        operations, workshop_ops, machines, distance, prices,
        coarse_iterations=p4_coarse_iterations, medium_iterations=p4_medium_iterations,
        refine_iterations=p4_refine_iterations, medium_k=p4_medium_k, top_k=p4_top_k,
        max_total_new_machines=max_total_new_machines, max_per_type_team=max_per_type_team,
        max_candidates_per_type=max_candidates_per_type,
        local_search_attempts=local_search_attempts,
        bottleneck_local_search_attempts=bottleneck_local_search_attempts,
        workers=workers, show_progress=show_progress, decoder=decoder,
        reference_schedule_df=p3_df, reference_makespan=p3_c,
    )
    if show_progress:
        print(f"主流程: 问题4完成 = {p4_c}s", flush=True)

    p1_df = finalize_schedule(p1_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题1")
    p2_df = finalize_schedule(p2_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题2")
    p3_df = finalize_schedule(p3_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题3")
    p4_df = finalize_schedule(p4_df.drop(columns=["问题"], errors="ignore").to_dict("records"), "问题4")

    # --- Feasibility ---
    checks = []
    ok1, c1 = check_feasibility(p1_df, p1_operations, machines, distance, verbose=False)
    ok2, c2 = check_feasibility(p2_df, operations, machines, distance, verbose=False)
    ok3, c3 = check_feasibility(p3_df, operations, machines, distance, verbose=False)
    ok4, c4 = check_feasibility(
        p4_df, operations, machines_with_purchases, distance,
        budget=BUDGET, purchase_scheme=best_purchase_scheme, prices=prices, verbose=False,
    )
    for name, df in [("问题1", c1), ("问题2", c2), ("问题3", c3), ("问题4", c4)]:
        checks.append(df.assign(问题=name))
    checks_df = pd.concat(checks, ignore_index=True)[["问题", "检查项", "是否通过", "违规数量", "说明"]]

    # --- Lower bounds ---
    lb_rows = []
    for name, wops, ops, mach, teams, cmax in [
        ("问题1", p1_workshop_ops, p1_operations, machines, [1], p1_c),
        ("问题2", workshop_ops, operations, machines, [1], p2_c),
        ("问题3", workshop_ops, operations, machines, [1, 2], p3_c),
        ("问题4", workshop_ops, operations, machines_with_purchases, [1, 2], p4_c),
    ]:
        lb = enhanced_lower_bounds(ops, wops, mach, teams)
        combined = lb["综合下界(s)"]
        lb_rows.append({
            "问题": name, "关键路径下界(s)": lb["关键路径下界(s)"],
            "设备负载下界(s)": lb["设备负载下界(s)"],
            "静态瓶颈负载下界(s)": lb["静态瓶颈负载下界(s)"],
            "综合下界(s)": combined, "本文可行解(s)": cmax,
            "gap": (cmax - combined) / combined if combined else np.nan,
            "gap百分比": (cmax - combined) / combined if combined else np.nan,
            "说明": lb["运输下界说明"],
        })
    lbs_df = pd.DataFrame(lb_rows)

    # --- Baselines ---
    baselines_df = run_baselines(
        operations, workshop_ops, machines, distance,
        [("问题2", [1], p2_c, operations, machines),
         ("问题3", [1, 2], p3_c, operations, machines),
         ("问题4", [1, 2], p4_c, operations, machines_with_purchases)],
    )

    # --- Statistics ---
    schedule_stats = {
        "问题1": compute_schedule_statistics(p1_df, p1_c),
        "问题2": compute_schedule_statistics(p2_df, p2_c),
        "问题3": compute_schedule_statistics(p3_df, p3_c),
        "问题4": compute_schedule_statistics(p4_df, p4_c),
    }

    bottleneck_analysis = []
    for name, stat in schedule_stats.items():
        df = stat["bottleneck_type_stats"].copy()
        if not df.empty:
            df.insert(0, "问题", name)
            bottleneck_analysis.append(df)
    bottleneck_analysis_df = pd.concat(bottleneck_analysis, ignore_index=True) if bottleneck_analysis else pd.DataFrame()

    static_bottleneck_frames = []
    for name, ops, mach, teams in [
        ("问题2", operations, machines, [1]),
        ("问题3", operations, machines, [1, 2]),
        ("问题4", operations, machines_with_purchases, [1, 2]),
    ]:
        _, df = static_bottleneck_types(ops, mach, allowed_teams=teams, top_k=999)
        if not df.empty:
            tmp = df.copy()
            tmp.insert(0, "问题", name)
            static_bottleneck_frames.append(tmp)
    static_bottleneck_df = pd.concat(static_bottleneck_frames, ignore_index=True) if static_bottleneck_frames else pd.DataFrame()

    critical_task_frames = []
    for name, df, ops in [
        ("问题1", p1_df, p1_operations), ("问题2", p2_df, operations),
        ("问题3", p3_df, operations), ("问题4", p4_df, operations),
    ]:
        crit = identify_critical_like_tasks(df, ops, top_k=20)
        if not crit.empty:
            crit = crit.copy()
            crit.insert(0, "问题", name)
            critical_task_frames.append(crit)
    critical_tasks_df = pd.concat(critical_task_frames, ignore_index=True) if critical_task_frames else pd.DataFrame()

    # --- Summary ---
    def explain_row(problem_name):
        stat = schedule_stats[problem_name]
        wc = stat["workshop_completion"]
        mt = stat["machine_type_stats"]
        latest = "、".join(wc.loc[wc["是否最晚完工车间"], "车间"].astype(str)) if not wc.empty else ""
        high_util = mt.iloc[0]["设备类型"] if not mt.empty else ""
        high_transport = mt.sort_values("运输时间占比", ascending=False).iloc[0]["设备类型"] if not mt.empty else ""
        return latest, TYPE_CN.get(high_util, high_util), TYPE_CN.get(high_transport, high_transport)

    p1_latest, p1_high_util, p1_high_transport = explain_row("问题1")
    p2_latest, p2_high_util, p2_high_transport = explain_row("问题2")
    p3_latest, p3_high_util, p3_high_transport = explain_row("问题3")
    p4_latest, p4_high_util, p4_high_transport = explain_row("问题4")
    p4_new_util = purchased_utilization(p4_df, p4_c)

    summary_rows = [
        {"问题": "问题1", "精确最短时长(s)": p1_c, "精确最短时长(HH:MM:SS)": seconds_to_hhmmss(p1_c),
         "最晚完工车间": p1_latest, "利用率最高设备类型": p1_high_util,
         "运输时间占比最高设备类型": p1_high_transport,
         "备注": "A车间严格串行，枚举设备组合，精确最短时长"},
        {"问题": "问题2", "当前搜索最优可行时长(s)": p2_c, "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p2_c),
         "最晚完工车间": p2_latest, "利用率最高设备类型": p2_high_util,
         "运输时间占比最高设备类型": p2_high_transport,
         "备注": f"TS+SA启发式搜索, iterations={p2_stats['iterations']}"},
        {"问题": "问题3", "当前搜索最优可行时长(s)": p3_c, "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p3_c),
         "最晚完工车间": p3_latest, "利用率最高设备类型": p3_high_util,
         "运输时间占比最高设备类型": p3_high_transport,
         "备注": f"双班组联合调度, iterations={p3_stats['iterations']}"},
        {"问题": "问题4", "当前搜索最优可行时长(s)": p4_c, "当前搜索最优可行时长(HH:MM:SS)": seconds_to_hhmmss(p4_c),
         "最晚完工车间": p4_latest, "利用率最高设备类型": p4_high_util,
         "运输时间占比最高设备类型": p4_high_transport,
         "问题4新购设备平均利用率": p4_new_util,
         "备注": f"费用={purchase_cost(best_purchase_scheme, prices)}; {p4_stats['purchase_candidate_note']}"},
        {"问题": "数据读取", "备注": f"距离表={distance_format}; 文件={file_path}"},
        {"问题": "C工序展开", "备注": f"启用={expand_c_repeated_ops}; 集合={sorted(C_REPEATED_BASE_OPS)}; 次数={C_REPEATED_COUNT}"},
    ]
    for warning in warnings:
        summary_rows.append({"问题": "C工序展开", "备注": warning})
    summary_df = pd.DataFrame(summary_rows).fillna("")

    # --- Diagnostics ---
    def fmt_bn(stats):
        return "；".join(TYPE_CN.get(t, t) for t in stats.get("bottleneck_types_for_scheduling", []))

    def fmt_weights(stats):
        w = stats.get("workshop_due_weights", {}) or {}
        return "；".join(f"{k}:{float(v):.3f}" for k, v in sorted(w.items()))

    def fmt_static(stats):
        return "；".join(TYPE_CN.get(t, t) for t in stats.get("static_bottleneck_types", []))

    scheduling_diagnostics_df = pd.DataFrame([
        {"问题": "问题2", "decoder": p2_stats.get("decoder",""), "best decoder": p2_stats.get("best_decoder",""),
         "瓶颈设备类型": fmt_bn(p2_stats), "瓶颈来源": p2_stats.get("bottleneck_source",""),
         "静态瓶颈": fmt_static(p2_stats), "车间权重": fmt_weights(p2_stats),
         "TS+SA改进": p2_stats.get("local_search_improvements",0),
         "BN-TS+SA改进": p2_stats.get("bottleneck_local_search_improvements",0),
         "best strategy": p2_stats.get("best_strategy","")},
        {"问题": "问题3", "decoder": p3_stats.get("decoder",""), "best decoder": p3_stats.get("best_decoder",""),
         "瓶颈设备类型": fmt_bn(p3_stats), "瓶颈来源": p3_stats.get("bottleneck_source",""),
         "静态瓶颈": fmt_static(p3_stats), "车间权重": fmt_weights(p3_stats),
         "TS+SA改进": p3_stats.get("local_search_improvements",0),
         "BN-TS+SA改进": p3_stats.get("bottleneck_local_search_improvements",0),
         "best strategy": p3_stats.get("best_strategy","")},
        {"问题": "问题4", "decoder": p4_stats.get("best_stats",{}).get("decoder",""),
         "best decoder": p4_stats.get("best_stats",{}).get("best_decoder",""),
         "瓶颈设备类型": fmt_bn(p4_stats.get("best_stats",{})),
         "瓶颈来源": p4_stats.get("best_stats",{}).get("bottleneck_source",""),
         "静态瓶颈": fmt_static(p4_stats.get("best_stats",{})),
         "车间权重": fmt_weights(p4_stats.get("best_stats",{})),
         "TS+SA改进": p4_stats.get("best_stats",{}).get("local_search_improvements",0),
         "BN-TS+SA改进": p4_stats.get("best_stats",{}).get("bottleneck_local_search_improvements",0),
         "best strategy": p4_stats.get("best_stats",{}).get("best_strategy","")},
    ])

    # --- Build all output tables ---
    model_explain_df = pd.DataFrame([
        {"主题": "问题1最优性", "说明": "A车间严格串行，枚举设备组合，精确最短时长"},
        {"主题": "问题2-4最优性声明", "说明": "多策略启发式+Tabu-SA局部搜索，不声称全局最优"},
        {"主题": "算法改进", "说明": "Tabu Search + Simulated Annealing + CPM-aware邻域 + Active Decoder"},
        {"主题": "可信度支撑", "说明": "可行性检查、理论下界、基准对比、瓶颈统计"},
    ])

    p4_search_df = pd.DataFrame([
        {"参数": k, "值": v} for k, v in [
            ("budget", p4_stats["budget"]), ("min_price", p4_stats["min_price"]),
            ("candidate_count", p4_stats["candidate_count"]),
            ("coarse_iterations", p4_stats["coarse_iterations"]),
            ("medium_iterations", p4_stats["medium_iterations"]),
            ("refine_iterations", p4_stats["refine_iterations"]),
            ("medium_k", p4_stats["medium_k"]), ("top_k", p4_stats["top_k"]),
            ("max_candidates_per_type", p4_stats["max_candidates_per_type"]),
            ("local_search_attempts", p4_stats["local_search_attempts"]),
            ("bottleneck_local_search_attempts", p4_stats["bottleneck_local_search_attempts"]),
            ("workers", p4_stats["workers"]), ("decoder", p4_stats["decoder"]),
            ("bottleneck_types", "；".join(TYPE_CN.get(t,t) for t in p4_stats["bottleneck_types"])),
            ("bottleneck_guided", p4_stats["bottleneck_guided"]),
            ("sa_t0", SA_T0), ("sa_alpha", SA_ALPHA), ("tabu_tenure", TABU_BASE_TENURE),
        ]
    ])

    c_expansion_sheet = pd.concat([
        pd.DataFrame([
            {"配置项": "是否启用C工序展开", "配置值": expand_c_repeated_ops, "说明": "--no-expand-c 关闭"},
            {"配置项": "展开集合", "配置值": "、".join(sorted(C_REPEATED_BASE_OPS)), "说明": "C3-C5"},
            {"配置项": "展开次数", "配置值": C_REPEATED_COUNT, "说明": "每个原始工序展开次数"},
        ]),
        expansion_df,
    ], ignore_index=True, sort=False)

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
        "模型求解说明": model_explain_df,
        "调度策略诊断": scheduling_diagnostics_df,
        "效率单位识别说明": efficiency_notes_df,
        "问题1车间完工": schedule_stats["问题1"]["workshop_completion"],
        "问题2车间完工": schedule_stats["问题2"]["workshop_completion"],
        "问题3车间完工": schedule_stats["问题3"]["workshop_completion"],
        "问题4车间完工": schedule_stats["问题4"]["workshop_completion"],
        "问题1设备类型统计": schedule_stats["问题1"]["machine_type_stats"],
        "问题2设备类型统计": schedule_stats["问题2"]["machine_type_stats"],
        "问题3设备类型统计": schedule_stats["问题3"]["machine_type_stats"],
        "问题4设备类型统计": schedule_stats["问题4"]["machine_type_stats"],
        "问题1班组统计": schedule_stats["问题1"]["team_stats"],
        "问题2班组统计": schedule_stats["问题2"]["team_stats"],
        "问题3班组统计": schedule_stats["问题3"]["team_stats"],
        "问题4班组统计": schedule_stats["问题4"]["team_stats"],
        "问题4新购设备统计": schedule_stats["问题4"]["new_machine_stats"],
        "瓶颈设备类型分析": bottleneck_analysis_df,
        "静态瓶颈设备分析": static_bottleneck_df,
        "关键任务诊断": critical_tasks_df,
        "问题4候选搜索说明": p4_search_df,
        "问题4候选购置方案对比": p4_stats["quick_candidates"],
        "C工序展开说明": c_expansion_sheet,
    }
    export_results(output_xlsx, full_tables)

    # --- Gantt ---
    gantt_paths = []
    if make_plots:
        for label, df, cmax in [("问题1", p1_df, p1_c), ("问题2", p2_df, p2_c), ("问题3", p3_df, p3_c), ("问题4", p4_df, p4_c)]:
            gantt_paths.extend(plot_gantt(df, f"{label} 当前搜索最优可行排程", os.path.join(output_dir, f"problem{label[-1]}_gantt"), makespan=cmax))

    # --- Print summary ---
    print("\n主流程输出摘要:")
    print(summary_df.to_string(index=False))
    print("\n问题4购买方案:")
    print(p5_df.to_string(index=False))
    print("\n可行性检查:")
    print(checks_df.groupby("问题")["是否通过"].all().to_string())
    print("\n理论下界 gap:")
    print(lbs_df[["问题", "综合下界(s)", "本文可行解(s)", "gap百分比"]].to_string(index=False))
    print("\nBaseline 对比:")
    print(baselines_df.to_string(index=False))
    print(f"\nExcel: {output_xlsx}")
    if gantt_paths:
        print("甘特图:")
        for path in gantt_paths:
            print(f"  {path}")

    return {
        "summaries": summary_rows, "tables": full_tables, "checks": checks_df,
        "lbs": lbs_df, "baselines": baselines_df,
        "p4_candidates": p4_stats["quick_candidates"],
        "p4_purchase_scheme": best_purchase_scheme,
        "machines_with_purchases": machines_with_purchases,
        "stats": {"p2": p2_stats, "p3": p3_stats, "p4": p4_stats},
        "distance_format": distance_format,
        "efficiency_unit_notes": efficiency_notes_df,
        "output_xlsx": output_xlsx,
        "gantt_paths": gantt_paths,
    }


if __name__ == "__main__":
    args = parse_args()
    # Apply SA/tabu overrides from CLI
    SA_T0 = args.sa_t0
    SA_ALPHA = args.sa_alpha
    TABU_BASE_TENURE = args.tabu_tenure
    result = main(
        file_path=args.file,
        output_xlsx=args.out,
        output_dir=args.output_dir,
        make_plots=not args.no_plots,
        decoder=args.decoder,
        p2_iterations=args.p2_iter,
        p3_iterations=args.p3_iter,
        p4_coarse_iterations=args.p4_coarse_iter,
        p4_medium_iterations=args.p4_medium_iter,
        p4_refine_iterations=args.p4_refine_iter,
        p4_medium_k=args.p4_medium_k,
        p4_top_k=args.p4_top_k,
        max_candidates_per_type=args.max_candidates_per_type,
        local_search_attempts=args.local_search_attempts,
        bottleneck_local_search_attempts=args.bottleneck_local_search_attempts,
        workers=args.workers,
        show_progress=not args.no_progress,
        max_total_new_machines=args.max_new_machines,
        max_per_type_team=args.max_per_type_team,
        expand_c_repeated_ops=not args.no_expand_c,
        sa_t0=args.sa_t0,
        sa_alpha=args.sa_alpha,
        tabu_tenure=args.tabu_tenure,
    )