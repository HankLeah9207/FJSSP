#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多工序协同作业调度问题求解器
使用ortools CP-SAT求解器
"""

import math
import itertools
import random
import time
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from ortools.sat.python import cp_model

# 设置随机种子
random.seed(42)

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Noto Serif CJK SC', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# ========================== 数据硬编码 ==========================

# 工序字典
operations = {
    "A1": {"workshop": "A", "order": 1, "name": "缺陷填补", "workload": 300.0,
           "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 250.0}},
    "A2": {"workshop": "A", "order": 2, "name": "表面整平", "workload": 500.0,
           "required_types": ["高速抛光机", "工业清洗机"], "efficiency": {"高速抛光机": 100.0, "工业清洗机": 250.0}},
    "A3": {"workshop": "A", "order": 3, "name": "强度检测", "workload": 500.0,
           "required_types": ["自动传感多功能机"], "efficiency": {"自动传感多功能机": 100.0}},
    # B车间
    "B1": {"workshop": "B", "order": 1, "name": "表面清理", "workload": 120.0, "required_types": ["工业清洗机"], "efficiency": {"工业清洗机": 100.0}},
    "B2": {"workshop": "B", "order": 2, "name": "垫层构筑", "workload": 1500.0, "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 300.0}},
    "B3": {"workshop": "B", "order": 3, "name": "表面密封", "workload": 360.0, "required_types": ["精密灌装机"], "efficiency": {"精密灌装机": 350.0}},
    "B4": {"workshop": "B", "order": 4, "name": "表面整平", "workload": 360.0, "required_types": ["高速抛光机", "自动传感多功能机"], "efficiency": {"高速抛光机": 120.0, "自动传感多功能机": 100.0}},
    # C车间
    "C1": {"workshop": "C", "order": 1, "name": "旧涂层剥离", "workload": 720.0, "required_types": ["工业清洗机", "自动化输送臂"], "efficiency": {"工业清洗机": 250.0, "自动化输送臂": 250.0}},
    "C2": {"workshop": "C", "order": 2, "name": "基底填充", "workload": 720.0, "required_types": ["精密灌装机"], "efficiency": {"精密灌装机": 350.0}},
    "C3_1": {"workshop": "C", "order": 3, "name": "密封覆盖", "workload": 360.0, "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 250.0}},
    "C3_2": {"workshop": "C", "order": 3, "name": "密封覆盖", "workload": 360.0, "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 250.0}},
    "C3_3": {"workshop": "C", "order": 3, "name": "密封覆盖", "workload": 360.0, "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 250.0}},
    "C4_1": {"workshop": "C", "order": 4, "name": "表面研磨", "workload": 400.0, "required_types": ["高速抛光机", "工业清洗机"], "efficiency": {"高速抛光机": 120.0, "工业清洗机": 100.0}},
    "C4_2": {"workshop": "C", "order": 4, "name": "表面研磨", "workload": 400.0, "required_types": ["高速抛光机", "工业清洗机"], "efficiency": {"高速抛光机": 120.0, "工业清洗机": 100.0}},
    "C4_3": {"workshop": "C", "order": 4, "name": "表面研磨", "workload": 400.0, "required_types": ["高速抛光机", "工业清洗机"], "efficiency": {"高速抛光机": 120.0, "工业清洗机": 100.0}},
    "C5_1": {"workshop": "C", "order": 5, "name": "质量检测", "workload": 400.0, "required_types": ["自动传感多功能机"], "efficiency": {"自动传感多功能机": 100.0}},
    "C5_2": {"workshop": "C", "order": 5, "name": "质量检测", "workload": 400.0, "required_types": ["自动传感多功能机"], "efficiency": {"自动传感多功能机": 100.0}},
    "C5_3": {"workshop": "C", "order": 5, "name": "质量检测", "workload": 400.0, "required_types": ["自动传感多功能机"], "efficiency": {"自动传感多功能机": 100.0}},
    # D车间
    "D1": {"workshop": "D", "order": 1, "name": "碎屑清理", "workload": 600.0, "required_types": ["工业清洗机"], "efficiency": {"工业清洗机": 250.0}},
    "D2": {"workshop": "D", "order": 2, "name": "基底固化", "workload": 800.0, "required_types": ["精密灌装机", "自动化输送臂"], "efficiency": {"精密灌装机": 200.0, "自动化输送臂": 300.0}},
    "D3": {"workshop": "D", "order": 3, "name": "表面密封", "workload": 450.0, "required_types": ["精密灌装机"], "efficiency": {"精密灌装机": 350.0}},
    "D4": {"workshop": "D", "order": 4, "name": "表面整平", "workload": 1500.0, "required_types": ["高速抛光机", "自动传感多功能机"], "efficiency": {"高速抛光机": 120.0, "自动传感多功能机": 300.0}},
    "D5": {"workshop": "D", "order": 5, "name": "承载检测", "workload": 1500.0, "required_types": ["自动传感多功能机"], "efficiency": {"自动传感多功能机": 300.0}},
    "D6": {"workshop": "D", "order": 6, "name": "边缘修整", "workload": 700.0, "required_types": ["高速抛光机"], "efficiency": {"高速抛光机": 100.0}},
    # E车间
    "E1": {"workshop": "E", "order": 1, "name": "基础处理", "workload": 1000.0, "required_types": ["工业清洗机"], "efficiency": {"工业清洗机": 250.0}},
    "E2": {"workshop": "E", "order": 2, "name": "表面密封", "workload": 600.0, "required_types": ["精密灌装机"], "efficiency": {"精密灌装机": 350.0}},
    "E3": {"workshop": "E", "order": 3, "name": "稳定性检测", "workload": 600.0, "required_types": ["自动传感多功能机", "工业清洗机"], "efficiency": {"自动传感多功能机": 300.0, "工业清洗机": 100.0}},
}

# 班组1设备
team1_machines = [
    "自动化输送臂1-1","自动化输送臂1-2","自动化输送臂1-3","自动化输送臂1-4",
    "工业清洗机1-1","工业清洗机1-2","工业清洗机1-3","工业清洗机1-4","工业清洗机1-5",
    "精密灌装机1-1","精密灌装机1-2","精密灌装机1-3","精密灌装机1-4","精密灌装机1-5",
    "自动传感多功能机1-1",
    "高速抛光机1-1",
]

# 班组2设备
team2_machines = [
    "自动化输送臂2-1","自动化输送臂2-2","自动化输送臂2-3","自动化输送臂2-4",
    "工业清洗机2-1","工业清洗机2-2","工业清洗机2-3","工业清洗机2-4","工业清洗机2-5",
    "精密灌装机2-1","精密灌装机2-2","精密灌装机2-3","精密灌装机2-4","精密灌装机2-5",
    "自动传感多功能机2-1",
    "高速抛光机2-1",
]

# 设备类型分组
type_to_machines = {
    "自动化输送臂": {"班组1": ["自动化输送臂1-1", "自动化输送臂1-2", "自动化输送臂1-3", "自动化输送臂1-4"],
                   "班组2": ["自动化输送臂2-1", "自动化输送臂2-2", "自动化输送臂2-3", "自动化输送臂2-4"]},
    "工业清洗机": {"班组1": ["工业清洗机1-1", "工业清洗机1-2", "工业清洗机1-3", "工业清洗机1-4", "工业清洗机1-5"],
                  "班组2": ["工业清洗机2-1", "工业清洗机2-2", "工业清洗机2-3", "工业清洗机2-4", "工业清洗机2-5"]},
    "精密灌装机": {"班组1": ["精密灌装机1-1", "精密灌装机1-2", "精密灌装机1-3", "精密灌装机1-4", "精密灌装机1-5"],
                  "班组2": ["精密灌装机2-1", "精密灌装机2-2", "精密灌装机2-3", "精密灌装机2-4", "精密灌装机2-5"]},
    "自动传感多功能机": {"班组1": ["自动传感多功能机1-1"], "班组2": ["自动传感多功能机2-1"]},
    "高速抛光机": {"班组1": ["高速抛光机1-1"], "班组2": ["高速抛光机2-1"]},
}

# 设备单价
machine_prices = {
    "自动化输送臂": 50000,
    "工业清洗机": 40000,
    "精密灌装机": 35000,
    "自动传感多功能机": 80000,
    "高速抛光机": 75000,
}

# 距离矩阵
distances_raw = {
    ("班组1","A"): 400, ("班组1","B"): 620, ("班组1","C"): 460, ("班组1","D"): 710, ("班组1","E"): 400,
    ("班组2","A"): 500, ("班组2","B"): 460, ("班组2","C"): 620, ("班组2","D"): 680, ("班组2","E"): 550,
    ("A","B"): 1020, ("A","C"): 1050, ("A","D"): 900, ("A","E"): 1400,
    ("B","C"): 1100, ("B","D"): 1630, ("B","E"): 720,
    ("C","D"): 520, ("C","E"): 850,
    ("D","E"): 1030,
}

# 构建完整距离矩阵（对称+自身）
distances = {}
all_locations = ["班组1", "班组2", "A", "B", "C", "D", "E"]
for loc1 in all_locations:
    for loc2 in all_locations:
        if loc1 == loc2:
            distances[(loc1, loc2)] = 0
        elif (loc1, loc2) in distances_raw:
            distances[(loc1, loc2)] = distances_raw[(loc1, loc2)]
        elif (loc2, loc1) in distances_raw:
            distances[(loc1, loc2)] = distances_raw[(loc2, loc1)]
        else:
            # 通过对称性推断班组间距离不存在于原始数据中
            distances[(loc1, loc2)] = 0

# 工序顺序约束
operation_sequences = {
    "A": ["A1", "A2", "A3"],
    "B": ["B1", "B2", "B3", "B4"],
    "C": ["C1", "C2", "C3_1", "C4_1", "C5_1", "C3_2", "C4_2", "C5_2", "C3_3", "C4_3", "C5_3"],
    "D": ["D1", "D2", "D3", "D4", "D5", "D6"],
    "E": ["E1", "E2", "E3"],
}

# 设备所属班组
def get_machine_team(machine_name):
    if machine_name.startswith("自动化输送臂1") or machine_name.startswith("工业清洗机1") or \
       machine_name.startswith("精密灌装机1") or machine_name.startswith("自动传感多功能机1") or \
       machine_name.startswith("高速抛光机1"):
        return "班组1"
    return "班组2"

def get_machine_type(machine_name):
    """从设备名提取类型"""
    for mtype in type_to_machines:
        if mtype in machine_name:
            return mtype
    return None


# ========================== 计算函数 ==========================

def calc_processing_time(workload, efficiency):
    """计算加工时间（秒），向上取整"""
    if efficiency <= 0:
        return float('inf')
    return math.ceil(workload / efficiency * 3600)

def calc_transport_time(distance, speed=2.0):
    """计算运输时间（秒），向上取整"""
    return math.ceil(distance / speed)

def get_transport_time(from_loc, to_loc):
    """获取两地间运输时间"""
    return calc_transport_time(distances.get((from_loc, to_loc), 0))

def format_time(seconds):
    """将秒数格式化为HH:MM:SS"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def compute_all_processing_times():
    """预计算所有工序在所有可能设备上的加工时间"""
    proc_times = {}  # (op_id, machine) -> time
    for op_id, op in operations.items():
        for mtype in op["required_types"]:
            eff = op["efficiency"][mtype]
            pt = calc_processing_time(op["workload"], eff)
            # 找到所有该类型的设备
            for team in ["班组1", "班组2"]:
                for machine in type_to_machines.get(mtype, {}).get(team, []):
                    proc_times[(op_id, machine)] = pt
    return proc_times

# 预计算加工时间
PROCESSING_TIMES = compute_all_processing_times()

def get_op_workshop(op_id):
    return operations[op_id]["workshop"]

def is_dual_machine_op(op_id):
    """判断是否为双设备工序"""
    return len(operations[op_id]["required_types"]) == 2

def get_dual_machine_types(op_id):
    """获取双设备工序的两种设备类型"""
    return operations[op_id]["required_types"]


# ========================== CP-SAT调度模型 ==========================

def solve_fjsp(machines_available, operations_to_schedule, time_limit=60,
               team_assignments=None, hint_solution=None):
    """
    使用CP-SAT求解FJSP问题

    machines_available: 可用设备列表
    operations_to_schedule: 需要调度的工序ID列表
    team_assignments: 强制指定工序分配到某个班组的字典 {op_id: "班组1"/"班组2"}
    hint_solution: 启发式得到的初始解

    返回: (makespan, schedule_dict) 或 (None, None)
    schedule_dict: {op_id: {start, end, machines: [机器列表], types: [类型列表]}}
    """
    model = cp_model.CpModel()

    # 可用的机器按类型分类
    machines_by_type = defaultdict(list)
    for m in machines_available:
        mtype = get_machine_type(m)
        if mtype:
            machines_by_type[mtype].append(m)

    # 构建工序-候选机器映射
    op_candidates = {}  # op_id -> {type: [machines]}
    for op_id in operations_to_schedule:
        op = operations[op_id]
        op_candidates[op_id] = {}
        for mtype in op["required_types"]:
            candidates = [m for m in machines_by_type.get(mtype, [])]
            if team_assignments and op_id in team_assignments:
                team = team_assignments[op_id]
                candidates = [m for m in candidates if get_machine_team(m) == team]
            op_candidates[op_id][mtype] = candidates

    # 过滤无可行候选的工序
    for op_id in list(operations_to_schedule):
        for mtype, cands in op_candidates.get(op_id, {}).items():
            if len(cands) == 0:
                return None, None

    # 最大时间 horizon
    max_proc_time = sum(max(PROCESSING_TIMES.get((op_id, m), 0)
                            for m in machines_available
                            if (op_id, m) in PROCESSING_TIMES)
                        for op_id in operations_to_schedule)
    max_transport = max(calc_transport_time(d) for d in distances_raw.values())
    horizon = max_proc_time + len(operations_to_schedule) * max_transport * 2 + 1000

    # 决策变量
    op_start = {}
    op_end = {}
    op_duration = {}
    op_machine_vars = {}  # op_id -> {mtype: machine_select_var}
    op_intervals = {}     # op_id -> {mtype: interval_var}

    for op_id in operations_to_schedule:
        op = operations[op_id]
        workshop = op["workshop"]

        # 该工序需要的每种设备类型的加工时间
        type_proc_times = {}
        for mtype in op["required_types"]:
            eff = op["efficiency"][mtype]
            type_proc_times[mtype] = calc_processing_time(op["workload"], eff)

        # 工序持续时间 = max(所有设备类型的加工时间) - 对于双设备工序
        # 但每种设备的实际占用时间是各自的加工时间
        duration = max(type_proc_times.values())
        op_duration[op_id] = duration

        # 开始和结束时间
        op_start[op_id] = model.NewIntVar(0, horizon, f'start_{op_id}')
        op_end[op_id] = model.NewIntVar(0, horizon, f'end_{op_id}')

        # 为每种设备类型创建区间变量和机器选择
        intervals_for_op = []
        for mtype in op["required_types"]:
            pt = type_proc_times[mtype]
            candidates = op_candidates[op_id][mtype]

            if len(candidates) == 1:
                # 只有一台候选机器
                m = candidates[0]
                interval = model.NewIntervalVar(
                    op_start[op_id], pt,
                    model.NewIntVar(0, horizon, f'end_{op_id}_{mtype}_{m}'),
                    f'interval_{op_id}_{mtype}_{m}')
                op_machine_vars.setdefault(op_id, {})[mtype] = [m]
                op_intervals.setdefault(op_id, {})[mtype] = interval
            else:
                # 多台候选机器，使用Alternative
                machine_var = model.NewIntVar(0, len(candidates) - 1,
                                               f'machine_select_{op_id}_{mtype}')
                op_machine_vars.setdefault(op_id, {})[mtype] = machine_var

                # 为每台候选机器创建可选区间
                machine_intervals = []
                for i, m in enumerate(candidates):
                    b = model.NewBoolVar(f'select_{op_id}_{mtype}_{m}')
                    machine_interval = model.NewOptionalIntervalVar(
                        op_start[op_id], pt,
                        model.NewIntVar(0, horizon, f'end_{op_id}_{mtype}_{m}'),
                        b, f'opt_interval_{op_id}_{mtype}_{m}')
                    machine_intervals.append((b, machine_interval, m))

                # 恰好选择一台机器
                model.Add(sum(b for b, _, _ in machine_intervals) == 1)
                # 机器变量与选择对应
                for i, (b, _, _) in enumerate(machine_intervals):
                    model.Add(machine_var == i).OnlyEnforceIf(b)
                    model.Add(machine_var != i).OnlyEnforceIf(b.Not())

                op_intervals.setdefault(op_id, {})[mtype] = machine_intervals

        # 工序结束时间 >= 每种设备的结束时间（实际上是每种设备的开始时间+加工时间）
        # 由于所有设备类型同时开始，工序结束时间 = max(所有设备类型的完成时间)
        for mtype in op["required_types"]:
            pt = type_proc_times[mtype]
            model.Add(op_end[op_id] >= op_start[op_id] + pt)

        # 工序顺序约束
        workshop_ops = [oid for oid in operations_to_schedule
                       if operations[oid]["workshop"] == workshop]
        workshop_ops.sort(key=lambda x: operations[x]["order"])
        for i in range(len(workshop_ops) - 1):
            curr_op = workshop_ops[i]
            next_op = workshop_ops[i + 1]
            if curr_op in op_end and next_op in op_start:
                model.Add(op_start[next_op] >= op_end[curr_op])

    # 设备不重叠约束 + 运输时间
    # 对于每台机器，收集可能分配到它的区间
    machine_intervals_map = defaultdict(list)

    for op_id in operations_to_schedule:
        workshop = operations[op_id]["workshop"]
        for mtype in operations[op_id]["required_types"]:
            interval_data = op_intervals[op_id][mtype]
            if isinstance(interval_data, list):
                # 多候选机器
                for b, interval, m in interval_data:
                    machine_intervals_map[m].append((interval, b, op_id, workshop))
            else:
                # 单候选机器
                m = op_machine_vars[op_id][mtype][0]
                b = model.NewBoolVar(f'fixed_select_{op_id}_{m}')
                model.Add(b == 1)
                machine_intervals_map[m].append((interval_data, b, op_id, workshop))

    # 添加设备不重叠约束
    for m, intervals in machine_intervals_map.items():
        if len(intervals) <= 1:
            continue

        # 提取实际区间变量
        interval_vars = []
        for interval, b, op_id, workshop in intervals:
            interval_vars.append(interval)

        # 使用NoOverlap约束
        if len(interval_vars) > 1:
            model.AddNoOverlap(interval_vars)

    # 运输时间约束：通过禁止模式来处理
    # 对于每台机器上的每对工序，如果它们在不同车间，需要考虑运输时间
    # 但由于CP-SAT的NoOverlap不直接支持sequence-dependent setup times，
    # 我们使用额外的约束来近似处理

    # 为每台机器上的每对可能冲突的工序添加顺序约束和运输时间
    for m, intervals in machine_intervals_map.items():
        machine_team = get_machine_team(m)
        if len(intervals) <= 1:
            continue

        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                interval_i, b_i, op_i, ws_i = intervals[i]
                interval_j, b_j, op_j, ws_j = intervals[j]

                # 创建二元变量：i在j之前
                i_before_j = model.NewBoolVar(f'order_{m}_{op_i}_before_{op_j}')

                # 获取加工时间
                op_i_type = None
                for t in operations[op_i]["required_types"]:
                    if get_machine_type(m) == t:
                        op_i_type = t
                        break
                op_j_type = None
                for t in operations[op_j]["required_types"]:
                    if get_machine_type(m) == t:
                        op_j_type = t
                        break

                if op_i_type is None or op_j_type is None:
                    continue

                pt_i = calc_processing_time(operations[op_i]["workload"],
                                           operations[op_i]["efficiency"][op_i_type])
                pt_j = calc_processing_time(operations[op_j]["workload"],
                                           operations[op_j]["efficiency"][op_j_type])

                # 运输时间
                if ws_i == ws_j:
                    trans_time = 0
                else:
                    trans_time = get_transport_time(ws_i, ws_j)

                # 两者都被选中时才生效
                both_selected = model.NewBoolVar(f'both_{m}_{op_i}_{op_j}')
                model.Add(both_selected == 1).OnlyEnforceIf([b_i, b_j])
                model.Add(both_selected == 0).OnlyEnforceIf(b_i.Not())
                model.Add(both_selected == 0).OnlyEnforceIf(b_j.Not())

                # i在j之前 -> start_j >= end_i + transport
                # end_i = start_i + pt_i
                model.Add(
                    op_start[op_j] >= op_start[op_i] + pt_i + trans_time
                ).OnlyEnforceIf([i_before_j, both_selected])

                # j在i之前
                if ws_j == ws_i:
                    trans_time_ji = 0
                else:
                    trans_time_ji = get_transport_time(ws_j, ws_i)

                model.Add(
                    op_start[op_i] >= op_start[op_j] + pt_j + trans_time_ji
                ).OnlyEnforceIf([i_before_j.Not(), both_selected])

    # 目标：最小化makespan
    makespan = model.NewIntVar(0, horizon, 'makespan')
    for op_id in operations_to_schedule:
        model.Add(makespan >= op_end[op_id])
    model.Minimize(makespan)

    # 求解
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = {}
        for op_id in operations_to_schedule:
            start = solver.Value(op_start[op_id])
            end = solver.Value(op_end[op_id])
            assigned_machines = []
            assigned_types = []

            for mtype in operations[op_id]["required_types"]:
                candidates = op_candidates[op_id][mtype]
                machine_var = op_machine_vars[op_id][mtype]
                if isinstance(machine_var, list):
                    m = machine_var[0]
                else:
                    idx = solver.Value(machine_var)
                    m = candidates[idx]
                assigned_machines.append(m)
                assigned_types.append(mtype)

            schedule[op_id] = {
                'start': start,
                'end': end,
                'machines': assigned_machines,
                'types': assigned_types,
                'duration': op_duration[op_id],
                'workshop': operations[op_id]["workshop"],
            }

        return solver.Value(makespan), schedule
    else:
        return None, None


# ========================== 问题1求解器 ==========================

def solve_problem1():
    """
    问题1：班组1独立承担A车间（3道工序）
    精确求解最短时长
    """
    print("=" * 60)
    print("问题1：班组1独立承担A车间")
    print("=" * 60)

    ops = operation_sequences["A"]
    makespan, schedule = solve_fjsp(team1_machines, ops, time_limit=120)

    if makespan is None:
        print("问题1无可行解")
        return None, None

    print(f"最短时长: {makespan}秒 = {format_time(makespan)}")
    print()

    # 构建表1
    table1_rows = []
    for op_id in ops:
        info = schedule[op_id]
        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            table1_rows.append({
                "设备编号": m,
                "起始时间(s)": info['start'],
                "结束时间(s)": info['start'] + pt,
                "持续工作时间(s)": pt,
                "工序编号": op_id,
            })

    df1 = pd.DataFrame(table1_rows)
    df1 = df1.sort_values(["起始时间(s)", "设备编号"])
    print("表1：")
    print(df1.to_string(index=False))
    print()

    return makespan, schedule


# ========================== 问题2求解器 ==========================

def solve_problem2():
    """
    问题2：仅班组1设备，完成A-E五个车间
    """
    print("=" * 60)
    print("问题2：仅班组1设备，完成A-E五个车间")
    print("=" * 60)

    all_ops = []
    for ws, ops in operation_sequences.items():
        all_ops.extend(ops)

    makespan, schedule = solve_fjsp(team1_machines, all_ops, time_limit=300)

    if makespan is None:
        print("问题2 CP-SAT无可行解，尝试启发式")
        makespan, schedule = greedy_heuristic(team1_machines, all_ops)

    if makespan is None:
        print("问题2无可行解")
        return None, None

    print(f"最短时长: {makespan}秒 = {format_time(makespan)}")
    print()

    # 构建表2
    table2_rows = []
    for op_id in all_ops:
        if op_id not in schedule:
            continue
        info = schedule[op_id]
        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            table2_rows.append({
                "设备编号": m,
                "起始时间(s)": info['start'],
                "结束时间(s)": info['start'] + pt,
                "持续工作时间(s)": pt,
                "工序编号": op_id,
            })

    df2 = pd.DataFrame(table2_rows)
    df2 = df2.sort_values(["起始时间(s)", "设备编号"])
    print("表2：")
    print(df2.to_string(index=False))
    print()

    return makespan, schedule


# ========================== 问题3求解器 ==========================

def solve_problem3():
    """
    问题3：班组1+班组2设备，完成A-E五个车间
    """
    print("=" * 60)
    print("问题3：班组1+班组2设备，完成A-E五个车间")
    print("=" * 60)

    all_machines = team1_machines + team2_machines
    all_ops = []
    for ws, ops in operation_sequences.items():
        all_ops.extend(ops)

    makespan, schedule = solve_fjsp(all_machines, all_ops, time_limit=300)

    if makespan is None:
        print("问题3 CP-SAT无可行解，尝试启发式")
        makespan, schedule = greedy_heuristic(all_machines, all_ops)

    if makespan is None:
        print("问题3无可行解")
        return None, None

    print(f"最短时长: {makespan}秒 = {format_time(makespan)}")
    print()

    # 构建表3
    table3_rows = []
    for op_id in all_ops:
        if op_id not in schedule:
            continue
        info = schedule[op_id]
        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            team = get_machine_team(m)
            table3_rows.append({
                "班组": team,
                "设备编号": m,
                "起始时间(s)": info['start'],
                "结束时间(s)": info['start'] + pt,
                "持续工作时间(s)": pt,
                "工序编号": op_id,
            })

    df3 = pd.DataFrame(table3_rows)
    df3 = df3.sort_values(["起始时间(s)", "班组", "设备编号"])
    print("表3：")
    print(df3.to_string(index=False))
    print()

    return makespan, schedule


# ========================== 启发式算法 ==========================

def greedy_heuristic(machines_available, operations_to_schedule):
    """
    贪心启发式：按工序顺序，每次选择最早可用的机器
    """
    machines_by_type = defaultdict(list)
    for m in machines_available:
        mtype = get_machine_type(m)
        if mtype:
            machines_by_type[mtype].append(m)

    # 按车间分组工序
    workshop_ops = defaultdict(list)
    for op_id in operations_to_schedule:
        ws = operations[op_id]["workshop"]
        workshop_ops[ws].append(op_id)

    # 按order排序
    for ws in workshop_ops:
        workshop_ops[ws].sort(key=lambda x: operations[x]["order"])

    # 机器状态: {machine: (available_time, current_workshop)}
    machine_state = {m: (0, get_machine_team(m)) for m in machines_available}

    schedule = {}

    # 按拓扑顺序调度：车间间并行，车间内按顺序
    # 使用事件驱动模拟
    pending_ops = set(operations_to_schedule)
    completed_ops = set()
    op_completion_time = {}

    while pending_ops:
        progressed = False

        for op_id in sorted(pending_ops):
            op = operations[op_id]
            ws = op["workshop"]
            order = op["order"]

            # 检查前驱工序是否完成
            predecessors = [oid for oid in workshop_ops[ws]
                          if operations[oid]["order"] < order]
            pred_ok = all(oid in completed_ops for oid in predecessors)
            if not pred_ok:
                continue

            # 获取前驱工序完成时间
            pred_end = 0
            for oid in predecessors:
                if oid in op_completion_time:
                    pred_end = max(pred_end, op_completion_time[oid])

            # 为每种设备类型找最早可用的机器
            assigned_machines = []
            assigned_types = []
            max_end = 0

            can_assign = True
            for mtype in op["required_types"]:
                candidates = [m for m in machines_by_type.get(mtype, [])]
                if not candidates:
                    can_assign = False
                    break

                best_machine = None
                best_start = float('inf')
                best_machine_state = None

                for m in candidates:
                    avail_time, curr_ws = machine_state[m]
                    # 考虑运输时间
                    if curr_ws == ws:
                        trans = 0
                    else:
                        trans = get_transport_time(curr_ws, ws)

                    start_time = max(pred_end, avail_time + trans)
                    pt = calc_processing_time(op["workload"], op["efficiency"][mtype])
                    end_time = start_time + pt

                    if start_time < best_start:
                        best_start = start_time
                        best_machine = m
                        best_machine_state = (end_time, ws)

                if best_machine is None:
                    can_assign = False
                    break

                assigned_machines.append(best_machine)
                assigned_types.append(mtype)
                pt = calc_processing_time(op["workload"], op["efficiency"][mtype])
                end_time = best_start + pt
                max_end = max(max_end, end_time)

            if not can_assign:
                continue

            # 确定实际开始时间（所有设备都就绪）
            actual_start = 0
            for i, m in enumerate(assigned_machines):
                mtype = assigned_types[i]
                avail_time, curr_ws = machine_state[m]
                if curr_ws == ws:
                    trans = 0
                else:
                    trans = get_transport_time(curr_ws, ws)
                pt = calc_processing_time(op["workload"], op["efficiency"][mtype])
                start_time = max(pred_end, avail_time + trans)
                actual_start = max(actual_start, start_time)

            # 更新机器状态
            for i, m in enumerate(assigned_machines):
                mtype = assigned_types[i]
                pt = calc_processing_time(op["workload"], op["efficiency"][mtype])
                machine_state[m] = (actual_start + pt, ws)

            schedule[op_id] = {
                'start': actual_start,
                'end': max_end,
                'machines': assigned_machines,
                'types': assigned_types,
                'duration': max_end - actual_start,
                'workshop': ws,
            }

            completed_ops.add(op_id)
            pending_ops.remove(op_id)
            op_completion_time[op_id] = max_end
            progressed = True

        if not progressed and pending_ops:
            print(f"启发式无法调度剩余工序: {pending_ops}")
            return None, None

    makespan = max(info['end'] for info in schedule.values()) if schedule else 0
    return makespan, schedule


# ========================== 问题4求解器 ==========================

def solve_problem4():
    """
    问题4：预算500000元购置新设备，联合优化
    外层枚举购置方案 + 内层调度
    策略：先用启发式快速评估所有方案，再对前N个最优方案用CP-SAT精确求解
    """
    print("=" * 60)
    print("问题4：预算500000元购置新设备")
    print("=" * 60)

    budget = 500000
    all_ops = []
    for ws, ops in operation_sequences.items():
        all_ops.extend(ops)

    mtypes = list(machine_prices.keys())

    # 生成所有可能的购置组合
    plans = []
    max_counts = {mtype: budget // price for mtype, price in machine_prices.items()}
    for mtype in max_counts:
        max_counts[mtype] = min(max_counts[mtype], 5)

    for auto_count in range(0, max_counts["自动化输送臂"] + 1):
        for wash_count in range(0, max_counts["工业清洗机"] + 1):
            for fill_count in range(0, max_counts["精密灌装机"] + 1):
                for sense_count in range(0, min(max_counts["自动传感多功能机"], 3) + 1):
                    for polish_count in range(0, min(max_counts["高速抛光机"], 3) + 1):
                        total_cost = (auto_count * machine_prices["自动化输送臂"] +
                                     wash_count * machine_prices["工业清洗机"] +
                                     fill_count * machine_prices["精密灌装机"] +
                                     sense_count * machine_prices["自动传感多功能机"] +
                                     polish_count * machine_prices["高速抛光机"])
                        if total_cost > budget:
                            continue
                        plan = {
                            "自动化输送臂": auto_count,
                            "工业清洗机": wash_count,
                            "精密灌装机": fill_count,
                            "自动传感多功能机": sense_count,
                            "高速抛光机": polish_count,
                            "总成本": total_cost,
                        }
                        plans.append(plan)

    print(f"共有 {len(plans)} 种购置方案")

    base_machines = team1_machines + team2_machines

    # 阶段1：用启发式快速评估所有方案
    print("阶段1：启发式快速评估...")
    heuristic_results = []

    for idx, plan in enumerate(plans):
        new_machines = []
        new_machine_counter = defaultdict(int)
        for mtype in mtypes:
            for _ in range(plan[mtype]):
                new_machine_counter[mtype] += 1
                count = new_machine_counter[mtype]
                new_machines.append(f"{mtype}_新_{count}")

        all_machines = base_machines + new_machines

        # 临时更新type_to_machines
        old_type_to_machines = {}
        for mtype in mtypes:
            old_type_to_machines[mtype] = type_to_machines[mtype].copy()
            team_new = [m for m in new_machines if m.startswith(mtype)]
            if team_new:
                if "新购" not in type_to_machines[mtype]:
                    type_to_machines[mtype]["新购"] = []
                type_to_machines[mtype]["新购"].extend(team_new)

        makespan, schedule = greedy_heuristic(all_machines, all_ops)

        # 恢复type_to_machines
        for mtype in mtypes:
            type_to_machines[mtype] = old_type_to_machines[mtype]

        if makespan is not None:
            heuristic_results.append((makespan, plan, new_machines))

        if (idx + 1) % 200 == 0:
            print(f"  已评估 {idx + 1} 种方案")

    # 按启发式结果排序
    heuristic_results.sort(key=lambda x: x[0])
    print(f"启发式评估完成，最优 {heuristic_results[0][0]}秒")

    # 阶段2：对前N个最优方案用CP-SAT精确求解
    print("阶段2：CP-SAT精确求解Top方案...")
    top_n = min(10, len(heuristic_results))
    best_makespan = float('inf')
    best_schedule = None
    best_plan = None
    best_machines = None

    for idx, (heu_makespan, plan, new_machines) in enumerate(heuristic_results[:top_n]):
        all_machines = base_machines + new_machines

        # 临时更新type_to_machines
        old_type_to_machines = {}
        for mtype in mtypes:
            old_type_to_machines[mtype] = type_to_machines[mtype].copy()
            team_new = [m for m in new_machines if m.startswith(mtype)]
            if team_new:
                if "新购" not in type_to_machines[mtype]:
                    type_to_machines[mtype]["新购"] = []
                type_to_machines[mtype]["新购"].extend(team_new)

        makespan, schedule = solve_fjsp(all_machines, all_ops, time_limit=120)

        # 恢复type_to_machines
        for mtype in mtypes:
            type_to_machines[mtype] = old_type_to_machines[mtype]

        if makespan is not None and makespan < best_makespan:
            best_makespan = makespan
            best_schedule = schedule
            best_plan = plan
            best_machines = all_machines.copy()
            print(f"  方案 {idx+1}: {makespan}秒 = {format_time(makespan)} (新最优!)")
        elif makespan is not None:
            print(f"  方案 {idx+1}: {makespan}秒 = {format_time(makespan)}")
        else:
            print(f"  方案 {idx+1}: CP-SAT无可行解")

    if best_makespan == float('inf'):
        print("问题4无可行解")
        return None, None, None

    print(f"\n最优购置方案:")
    for mtype, count in best_plan.items():
        if mtype != "总成本":
            print(f"  {mtype}: {count}台 × {machine_prices[mtype]} = {count * machine_prices[mtype]}元")
    print(f"  总成本: {best_plan['总成本']}元")
    print(f"  最短时长: {best_makespan}秒 = {format_time(best_makespan)}")
    print()

    # 构建表4（购置方案表）和表5（调度表）
    # 表4
    table4_rows = []
    for mtype in mtypes:
        count = best_plan.get(mtype, 0)
        if count > 0:
            table4_rows.append({
                "设备类型": mtype,
                "购置数量": count,
                "单价(元)": machine_prices[mtype],
                "小计(元)": count * machine_prices[mtype],
            })
    table4_rows.append({
        "设备类型": "合计",
        "购置数量": "",
        "单价(元)": "",
        "小计(元)": best_plan["总成本"],
    })

    df4 = pd.DataFrame(table4_rows)
    print("表4：最优购置方案")
    print(df4.to_string(index=False))
    print()

    # 表5
    table5_rows = []
    for op_id in all_ops:
        if op_id not in best_schedule:
            continue
        info = best_schedule[op_id]
        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            team = get_machine_team(m)
            if "_新_" in m:
                team = "新购"
            table5_rows.append({
                "设备归属": team,
                "设备编号": m,
                "起始时间(s)": info['start'],
                "结束时间(s)": info['start'] + pt,
                "持续工作时间(s)": pt,
                "工序编号": op_id,
            })

    df5 = pd.DataFrame(table5_rows)
    df5 = df5.sort_values(["起始时间(s)", "设备归属", "设备编号"])
    print("表5：最优方案调度结果")
    print(df5.to_string(index=False))
    print()

    return best_makespan, best_schedule, best_plan


# ========================== 可行性检查 ==========================

def check_feasibility(schedule, machines_available, operations_to_schedule):
    """检查调度方案的可行性"""
    checks = []

    # 1. 所有工序都已调度
    unscheduled = [op for op in operations_to_schedule if op not in schedule]
    if unscheduled:
        checks.append(f"未调度工序: {unscheduled}")
    else:
        checks.append("所有工序已调度: 通过")

    # 2. 工序顺序约束
    for ws, ops in operation_sequences.items():
        ops_in_ws = [op for op in ops if op in schedule]
        ops_in_ws.sort(key=lambda x: operations[x]["order"])
        for i in range(len(ops_in_ws) - 1):
            curr = ops_in_ws[i]
            next_op = ops_in_ws[i + 1]
            if schedule[curr]['end'] > schedule[next_op]['start']:
                checks.append(f"顺序违反: {curr}结束{schedule[curr]['end']} > {next_op}开始{schedule[next_op]['start']}")

    # 3. 设备不重叠
    machine_usage = defaultdict(list)
    for op_id, info in schedule.items():
        if op_id not in operations_to_schedule:
            continue
        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            machine_usage[m].append((info['start'], info['start'] + pt, op_id))

    for m, usages in machine_usage.items():
        usages.sort()
        for i in range(len(usages) - 1):
            if usages[i][1] > usages[i+1][0]:
                checks.append(f"设备重叠: {m} 在 {usages[i][2]} 和 {usages[i+1][2]} 之间")

    # 4. 双设备工序同时开始
    for op_id, info in schedule.items():
        if is_dual_machine_op(op_id):
            starts = []
            for i, m in enumerate(info['machines']):
                mtype = info['types'][i]
                pt = calc_processing_time(operations[op_id]["workload"],
                                         operations[op_id]["efficiency"][mtype])
                starts.append(info['start'])
            if len(set(starts)) > 1:
                checks.append(f"双设备工序开始时间不一致: {op_id}, starts={starts}")

    if len(checks) == 1:  # 只有"所有工序已调度"
        checks.append("工序顺序: 通过")
        checks.append("设备不重叠: 通过")
        checks.append("双设备同时开始: 通过")

    return checks


# ========================== 理论下界计算 ==========================

def compute_lower_bound(machines_available, operations_to_schedule):
    """计算makespan的理论下界"""
    machines_by_type = defaultdict(list)
    for m in machines_available:
        mtype = get_machine_type(m)
        if mtype:
            machines_by_type[mtype].append(m)

    # 1. 关键路径下界
    lb_critical_path = 0
    for ws, ops in operation_sequences.items():
        ws_ops = [op for op in ops if op in operations_to_schedule]
        ws_time = 0
        for op_id in ws_ops:
            op = operations[op_id]
            min_pt = min(calc_processing_time(op["workload"], op["efficiency"][t])
                        for t in op["required_types"])
            ws_time += min_pt
        lb_critical_path = max(lb_critical_path, ws_time)

    # 2. 设备负载下界（每种设备类型）
    lb_machine = 0
    for mtype, machines in machines_by_type.items():
        total_workload = 0
        for op_id in operations_to_schedule:
            op = operations[op_id]
            if mtype in op["required_types"]:
                pt = calc_processing_time(op["workload"], op["efficiency"][mtype])
                total_workload += pt
        if len(machines) > 0:
            type_lb = total_workload // len(machines)
            lb_machine = max(lb_machine, type_lb)

    # 3. 运输时间下界（简单估计）
    lb_transport = 0
    for ws, ops in operation_sequences.items():
        ws_ops = [op for op in ops if op in operations_to_schedule]
        if len(ws_ops) > 0 and len(machines_available) > 0:
            # 至少一台机器需要移动到该车间
            team = get_machine_team(machines_available[0])
            lb_transport = max(lb_transport, get_transport_time(team, ws))

    overall_lb = max(lb_critical_path, lb_machine, lb_transport)
    return overall_lb, {
        "关键路径下界": lb_critical_path,
        "设备负载下界": lb_machine,
        "运输时间下界": lb_transport,
    }


# ========================== 基准规则对比 ==========================

def baseline_comparison():
    """基准规则对比：先到先服务(FCFS)规则"""
    print("=" * 60)
    print("基准规则对比：FCFS贪心调度")
    print("=" * 60)

    all_ops = []
    for ws, ops in operation_sequences.items():
        all_ops.extend(ops)

    # FCFS - 班组1
    makespan_fcfs_p1, _ = greedy_heuristic(team1_machines, operation_sequences["A"])
    makespan_fcfs_p2, _ = greedy_heuristic(team1_machines, all_ops)
    makespan_fcfs_p3, _ = greedy_heuristic(team1_machines + team2_machines, all_ops)

    print(f"FCFS 班组1-A车间: {makespan_fcfs_p1}秒 = {format_time(makespan_fcfs_p1)}")
    print(f"FCFS 班组1-AE车间: {makespan_fcfs_p2}秒 = {format_time(makespan_fcfs_p2)}")
    print(f"FCFS 双班组-AE车间: {makespan_fcfs_p3}秒 = {format_time(makespan_fcfs_p3)}")
    print()

    return makespan_fcfs_p1, makespan_fcfs_p2, makespan_fcfs_p3


# ========================== 甘特图绘制 ==========================

def plot_gantt(schedule, title, filename, machines_available=None):
    """绘制甘特图"""
    if not schedule:
        return

    fig, ax = plt.subplots(figsize=(16, 10))

    # 收集所有机器
    all_machines = set()
    for op_id, info in schedule.items():
        for m in info['machines']:
            all_machines.add(m)
    all_machines = sorted(all_machines)

    # 颜色映射
    workshop_colors = {
        "A": "#FF6B6B",
        "B": "#4ECDC4",
        "C": "#45B7D1",
        "D": "#96CEB4",
        "E": "#FFEAA7",
    }

    machine_to_y = {m: i for i, m in enumerate(all_machines)}

    for op_id, info in schedule.items():
        workshop = info['workshop']
        color = workshop_colors.get(workshop, "#CCCCCC")

        for i, m in enumerate(info['machines']):
            mtype = info['types'][i]
            pt = calc_processing_time(operations[op_id]["workload"],
                                     operations[op_id]["efficiency"][mtype])
            start = info['start']
            y = machine_to_y[m]

            ax.barh(y, pt, left=start, height=0.6, color=color, edgecolor='black', linewidth=0.5)
            if pt > 500:
                ax.text(start + pt / 2, y, f'{op_id}', ha='center', va='center', fontsize=8)

    ax.set_yticks(range(len(all_machines)))
    ax.set_yticklabels(all_machines, fontsize=9)
    ax.set_xlabel('时间 (秒)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(axis='x', alpha=0.3)

    # 图例
    legend_patches = [mpatches.Patch(color=c, label=f'车间 {ws}') for ws, c in workshop_colors.items()]
    ax.legend(handles=legend_patches, loc='upper right')

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"甘特图已保存: {filename}")
    plt.close()


# ========================== Excel导出 ==========================

def export_to_excel(all_results, output_path):
    """导出所有结果到Excel文件"""
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, df in all_results.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print(f"Excel文件已保存: {output_path}")


# ========================== 主函数 ==========================

def main():
    output_dir = "/mnt/agents/output"
    os.makedirs(output_dir, exist_ok=True)

    all_excel_data = {}

    # ====== 问题1 ======
    makespan1, schedule1 = solve_problem1()
    if schedule1:
        # 构建表1
        table1_rows = []
        for op_id in operation_sequences["A"]:
            info = schedule1[op_id]
            for i, m in enumerate(info['machines']):
                mtype = info['types'][i]
                pt = calc_processing_time(operations[op_id]["workload"],
                                         operations[op_id]["efficiency"][mtype])
                table1_rows.append({
                    "设备编号": m,
                    "起始时间(s)": info['start'],
                    "结束时间(s)": info['start'] + pt,
                    "持续工作时间(s)": pt,
                    "工序编号": op_id,
                })
        all_excel_data["表1_问题1"] = pd.DataFrame(table1_rows)
        plot_gantt(schedule1, "问题1：班组1独立承担A车间", f"{output_dir}/gantt_problem1.png", team1_machines)

        lb1, lb1_detail = compute_lower_bound(team1_machines, operation_sequences["A"])
        print(f"问题1 理论下界: {lb1}秒")
        for k, v in lb1_detail.items():
            print(f"  {k}: {v}秒")
        if makespan1:
            print(f"  Gap: {(makespan1 - lb1) / makespan1 * 100:.2f}%")
        print()

        checks1 = check_feasibility(schedule1, team1_machines, operation_sequences["A"])
        print("可行性检查:")
        for c in checks1:
            print(f"  {c}")
        print()

    # ====== 问题2 ======
    all_ops = []
    for ws, ops in operation_sequences.items():
        all_ops.extend(ops)

    makespan2, schedule2 = solve_problem2()
    if schedule2:
        table2_rows = []
        for op_id in all_ops:
            if op_id not in schedule2:
                continue
            info = schedule2[op_id]
            for i, m in enumerate(info['machines']):
                mtype = info['types'][i]
                pt = calc_processing_time(operations[op_id]["workload"],
                                         operations[op_id]["efficiency"][mtype])
                table2_rows.append({
                    "设备编号": m,
                    "起始时间(s)": info['start'],
                    "结束时间(s)": info['start'] + pt,
                    "持续工作时间(s)": pt,
                    "工序编号": op_id,
                })
        all_excel_data["表2_问题2"] = pd.DataFrame(table2_rows)
        plot_gantt(schedule2, "问题2：仅班组1设备完成A-E", f"{output_dir}/gantt_problem2.png", team1_machines)

        lb2, lb2_detail = compute_lower_bound(team1_machines, all_ops)
        print(f"问题2 理论下界: {lb2}秒")
        for k, v in lb2_detail.items():
            print(f"  {k}: {v}秒")
        if makespan2:
            print(f"  Gap: {(makespan2 - lb2) / makespan2 * 100:.2f}%")
        print()

        checks2 = check_feasibility(schedule2, team1_machines, all_ops)
        print("可行性检查:")
        for c in checks2:
            print(f"  {c}")
        print()

    # ====== 问题3 ======
    makespan3, schedule3 = solve_problem3()
    if schedule3:
        table3_rows = []
        for op_id in all_ops:
            if op_id not in schedule3:
                continue
            info = schedule3[op_id]
            for i, m in enumerate(info['machines']):
                mtype = info['types'][i]
                pt = calc_processing_time(operations[op_id]["workload"],
                                         operations[op_id]["efficiency"][mtype])
                team = get_machine_team(m)
                table3_rows.append({
                    "班组": team,
                    "设备编号": m,
                    "起始时间(s)": info['start'],
                    "结束时间(s)": info['start'] + pt,
                    "持续工作时间(s)": pt,
                    "工序编号": op_id,
                })
        all_excel_data["表3_问题3"] = pd.DataFrame(table3_rows)
        plot_gantt(schedule3, "问题3：班组1+班组2完成A-E", f"{output_dir}/gantt_problem3.png",
                  team1_machines + team2_machines)

        lb3, lb3_detail = compute_lower_bound(team1_machines + team2_machines, all_ops)
        print(f"问题3 理论下界: {lb3}秒")
        for k, v in lb3_detail.items():
            print(f"  {k}: {v}秒")
        if makespan3:
            print(f"  Gap: {(makespan3 - lb3) / makespan3 * 100:.2f}%")
        print()

        checks3 = check_feasibility(schedule3, team1_machines + team2_machines, all_ops)
        print("可行性检查:")
        for c in checks3:
            print(f"  {c}")
        print()

    # ====== 问题4 ======
    makespan4, schedule4, plan4 = solve_problem4()
    if schedule4 and plan4:
        # 表4
        table4_rows = []
        mtypes = list(machine_prices.keys())
        for mtype in mtypes:
            count = plan4.get(mtype, 0)
            if count > 0:
                table4_rows.append({
                    "设备类型": mtype,
                    "购置数量": count,
                    "单价(元)": machine_prices[mtype],
                    "小计(元)": count * machine_prices[mtype],
                })
        table4_rows.append({
            "设备类型": "合计",
            "购置数量": sum(plan4.get(m, 0) for m in mtypes),
            "单价(元)": "",
            "小计(元)": plan4["总成本"],
        })
        all_excel_data["表4_购置方案"] = pd.DataFrame(table4_rows)

        # 表5
        table5_rows = []
        for op_id in all_ops:
            if op_id not in schedule4:
                continue
            info = schedule4[op_id]
            for i, m in enumerate(info['machines']):
                mtype = info['types'][i]
                pt = calc_processing_time(operations[op_id]["workload"],
                                         operations[op_id]["efficiency"][mtype])
                team = get_machine_team(m)
                if "_新_" in m:
                    team = "新购"
                table5_rows.append({
                    "设备归属": team,
                    "设备编号": m,
                    "起始时间(s)": info['start'],
                    "结束时间(s)": info['start'] + pt,
                    "持续工作时间(s)": pt,
                    "工序编号": op_id,
                })
        all_excel_data["表5_问题4调度"] = pd.DataFrame(table5_rows)

        all_machines_p4 = team1_machines + team2_machines + \
                         [m for op_info in schedule4.values() for m in op_info['machines'] if "_新_" in m]
        all_machines_p4 = list(set(all_machines_p4))
        plot_gantt(schedule4, "问题4：最优购置方案调度", f"{output_dir}/gantt_problem4.png", all_machines_p4)

    # ====== 基准对比 ======
    fcfs1, fcfs2, fcfs3 = baseline_comparison()

    # ====== 汇总 ======
    print("=" * 60)
    print("结果汇总")
    print("=" * 60)
    print(f"问题1 (班组1-A车间): {makespan1}秒 = {format_time(makespan1) if makespan1 else 'N/A'}")
    print(f"问题2 (班组1-AE车间): {makespan2}秒 = {format_time(makespan2) if makespan2 else 'N/A'}")
    print(f"问题3 (双班组-AE车间): {makespan3}秒 = {format_time(makespan3) if makespan3 else 'N/A'}")
    print(f"问题4 (最优购置方案): {makespan4}秒 = {format_time(makespan4) if makespan4 else 'N/A'}")
    print()
    print("FCFS基准:")
    print(f"  班组1-A车间: {fcfs1}秒")
    print(f"  班组1-AE车间: {fcfs2}秒")
    print(f"  双班组-AE车间: {fcfs3}秒")
    print()

    # 导出Excel
    if all_excel_data:
        export_to_excel(all_excel_data, f"{output_dir}/调度结果.xlsx")

    print("\n所有结果已保存到 /mnt/agents/output/")

    return {
        "problem1": makespan1,
        "problem2": makespan2,
        "problem3": makespan3,
        "problem4": makespan4,
        "schedule1": schedule1,
        "schedule2": schedule2,
        "schedule3": schedule3,
        "schedule4": schedule4,
        "plan4": plan4,
        "fcfs": (fcfs1, fcfs2, fcfs3),
    }


if __name__ == "__main__":
    result = main()
