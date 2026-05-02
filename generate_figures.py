import csv
import io
import os
from collections import OrderedDict

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager, patches, rcParams


FONT_CANDIDATES = [
    "SimSun",
    "AR PL UMing CN",
    "Songti SC",
    "STSong",
    "Noto Serif CJK SC",
    "Noto Serif CJK JP",
    "Source Han Serif SC",
    "WenQuanYi Zen Hei",
]
AVAILABLE_FONT_NAMES = {font.name for font in font_manager.fontManager.ttflist}
SELECTED_CHINESE_FONT = next(
    (font_name for font_name in FONT_CANDIDATES if font_name in AVAILABLE_FONT_NAMES),
    "DejaVu Sans",
)
CHINESE_FONT = font_manager.FontProperties(family=SELECTED_CHINESE_FONT)
rcParams["font.family"] = [SELECTED_CHINESE_FONT, "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

WORKSHOP_COLORS = {
    "A": "#4C78A8",
    "B": "#F58518",
    "C": "#54A24B",
    "D": "#E45756",
    "E": "#72B7B2",
}

EQUIPMENT_TYPE_LABELS = OrderedDict(
    [
        ("ACA", "ACA类设备"),
        ("ICM", "ICM类设备"),
        ("PFM", "PFM类设备"),
        ("ASM", "ASM类设备"),
        ("HPM", "HPM类设备"),
    ]
)

WORKSHOP_LABELS = {
    "A": "A车间",
    "B": "B车间",
    "C": "C车间",
    "D": "D车间",
    "E": "E车间",
}

MAKESPAN = {
    "问题1": 41600,
    "问题2": 151604,
    "问题3": 123844,
    "问题4": 123844,
}

LOWER_BOUND_DATA = {
    "问题1": {
        "critical_path_lb": 41400,
        "resource_lb": 18000,
        "combined_lb": 41400,
        "solution": 41600,
    },
    "问题2": {
        "critical_path_lb": 123614,
        "resource_lb": 135000,
        "combined_lb": 135000,
        "solution": 151604,
    },
    "问题3": {
        "critical_path_lb": 123614,
        "resource_lb": 67500,
        "combined_lb": 123614,
        "solution": 123844,
    },
    "问题4": {
        "critical_path_lb": 123614,
        "resource_lb": 67500,
        "combined_lb": 123614,
        "solution": 123844,
    },
}

BASELINE_COMPARISON = {
    "问题2": {
        "ours": 151604,
        "A到E串行": 215303,
        "最快设备优先": 209083,
        "最近可用设备优先": 209083,
        "最早可用设备优先": 209083,
        "最早完成优先": 165890,
    },
    "问题3": {
        "ours": 123844,
        "A到E串行": 135068,
        "最快设备优先": 143684,
        "最近可用设备优先": 188667,
        "最早可用设备优先": 143684,
        "最早完成优先": 135068,
    },
    "问题4": {
        "ours": 123844,
        "A到E串行": 135068,
        "最快设备优先": 143684,
        "最近可用设备优先": 188667,
        "最早可用设备优先": 143684,
        "最早完成优先": 135068,
    },
}

Q4_PROCUREMENT_CANDIDATES = [
    (0, 123844),
    (35000, 123844),
    (35000, 123844),
    (40000, 123844),
    (40000, 123844),
    (50000, 123844),
    (50000, 123844),
    (70000, 123844),
    (75000, 123844),
    (75000, 123844),
    (80000, 123844),
    (80000, 123844),
    (115000, 123844),
    (120000, 123844),
    (125000, 123844),
    (150000, 123844),
    (150000, 123844),
    (155000, 123844),
    (155000, 123844),
    (160000, 123844),
    (230000, 123844),
    (235000, 123844),
    (240000, 123844),
    (310000, 123844),
    (315000, 123844),
    (390000, 123844),
]

Q2_AVAILABLE_COUNTS = {"ACA": 4, "ICM": 5, "PFM": 5, "ASM": 1, "HPM": 1}
Q3_AVAILABLE_COUNTS = {"ACA": 8, "ICM": 10, "PFM": 10, "ASM": 2, "HPM": 2}

Q2_SCHEDULE_TEXT = """equipment_id,start,end,duration,process
ACA1-4,200,4520,4320,A1
ICM1-1,200,14600,14400,E1
PFM1-1,200,5600,5400,A1
ACA1-2,230,10598,10368,C1
ICM1-2,230,10598,10368,C1
ICM1-3,310,4630,4320,B1
ICM1-5,355,8995,8640,D1
ACA1-3,4630,22630,18000,B2
PFM1-5,4630,31630,27000,B2
HPM1-1,5600,23600,18000,A2
ICM1-4,5600,12800,7200,A2
ACA1-1,8995,18595,9600,D2
PFM1-2,8995,23395,14400,D2
PFM1-3,10598,18004,7406,C2
PFM1-1,14600,20772,6172,E2
PFM1-3,18004,24484,6480,C3_1
ACA1-1,18855,24039,5184,C3_1
ASM1-1,20772,27972,7200,E3
PFM1-2,23395,28024,4629,D3
HPM1-1,24484,36484,12000,C4_1
ICM1-1,24484,38884,14400,C4_1
ASM1-1,28672,46672,18000,A3
PFM1-4,31630,35333,3703,B3
HPM1-1,36744,81744,45000,D4
ASM1-1,47122,65122,18000,D4
ICM1-1,53625,75225,21600,E3
ASM1-1,65382,79782,14400,C5_1
ACA1-1,79782,84966,5184,C3_2
PFM1-1,79782,86262,6480,C3_2
ASM1-1,81744,99744,18000,D5
HPM1-1,86262,98262,12000,C4_2
ICM1-1,86262,100662,14400,C4_2
HPM1-1,99744,124944,25200,D6
ASM1-1,100662,115062,14400,C5_2
ACA1-1,115062,120246,5184,C3_3
PFM1-2,115062,121542,6480,C3_3
ASM1-1,115612,128572,12960,B4
ICM1-1,121542,135942,14400,C4_3
HPM1-1,125204,137204,12000,C4_3
ASM1-1,137204,151604,14400,C5_3
HPM1-1,137754,148554,10800,B4
"""

Q3_SCHEDULE_TEXT = """equipment_id,start,end,duration,process,crew
ACA1-2,8980,18580,9600,D2,1
ACA1-3,230,10598,10368,C1,1
ACA1-4,200,4520,4320,A1,1
ASM1-1,38884,53284,14400,C5_1,1
ASM1-1,53834,66794,12960,B4,1
ASM1-1,74164,88564,14400,C5_2,1
ASM1-1,109444,123844,14400,C5_3,1
HPM1-1,28009,73009,45000,D4,1
HPM1-1,97435,122635,25200,D6,1
ICM1-3,20772,42372,21600,E3,1
ICM1-4,200,14600,14400,E1,1
ICM1-5,230,10598,10368,C1,1
PFM1-1,14600,20772,6172,E2,1
PFM1-2,23380,28009,4629,D3,1
PFM1-3,8980,23380,14400,D2,1
PFM1-4,88564,95044,6480,C3_3,1
PFM1-5,200,5600,5400,A1,1
ACA2-1,88564,93748,5184,C3_3,2
ACA2-2,53284,58468,5184,C3_2,2
ACA2-3,18004,23188,5184,C3_1,2
ACA2-4,4550,22550,18000,B2,2
ASM2-1,23600,41600,18000,A3,2
ASM2-1,42300,49500,7200,E3,2
ASM2-1,50015,68015,18000,D4,2
ASM2-1,73009,91009,18000,D5,2
HPM2-1,24484,36484,12000,C4_1,2
HPM2-1,37034,47834,10800,B4,2
HPM2-1,59764,71764,12000,C4_2,2
HPM2-1,95044,107044,12000,C4_3,2
ICM2-1,340,8980,8640,D1,2
ICM2-1,95044,109444,14400,C4_3,2
ICM2-2,59764,74164,14400,C4_2,2
ICM2-3,24484,38884,14400,C4_1,2
ICM2-4,230,4550,4320,B1,2
ICM2-5,5600,12800,7200,A2,2
PFM2-1,18004,24484,6480,C3_1,2
PFM2-2,10598,18004,7406,C2,2
PFM2-3,31550,35253,3703,B3,2
PFM2-4,4550,31550,27000,B2,2
PFM2-5,53284,59764,6480,C3_2,2
"""


def seconds_to_hms(seconds):
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def seconds_to_hours(seconds):
    return seconds / 3600.0


def equipment_type_from_id(equipment_id):
    prefix = []
    for char in equipment_id:
        if char.isalpha():
            prefix.append(char)
        else:
            break
    return "".join(prefix)


def workshop_from_process(process):
    return process[0]


def parse_embedded_schedule(schedule_text):
    reader = csv.DictReader(io.StringIO(schedule_text.strip()))
    rows = []
    for row in reader:
        parsed = {
            "equipment_id": row["equipment_id"],
            "start": int(row["start"]),
            "end": int(row["end"]),
            "duration": int(row["duration"]),
            "process": row["process"],
        }
        if "crew" in row and row["crew"]:
            parsed["crew"] = int(row["crew"])
        rows.append(parsed)
    return rows


def ensure_output_dir():
    output_dir = os.path.join(os.getcwd(), "Fig")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def apply_common_axis_style(ax):
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(CHINESE_FONT)


def save_figure(fig, output_dir, filename):
    fig.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
    plt.close(fig)


def total_duration_by_type(schedule_rows):
    totals = {equipment_type: 0 for equipment_type in EQUIPMENT_TYPE_LABELS}
    for row in schedule_rows:
        equipment_type = equipment_type_from_id(row["equipment_id"])
        totals[equipment_type] += row["duration"]
    return totals


def utilization_by_type(schedule_rows, available_counts, makespan):
    totals = total_duration_by_type(schedule_rows)
    return {
        equipment_type: totals[equipment_type] / (makespan * available_counts[equipment_type]) * 100
        for equipment_type in EQUIPMENT_TYPE_LABELS
    }


def workshop_completion_hours(schedule_rows):
    completion = {workshop: 0 for workshop in WORKSHOP_COLORS}
    for row in schedule_rows:
        workshop = workshop_from_process(row["process"])
        completion[workshop] = max(completion[workshop], row["end"])
    return {workshop: seconds_to_hours(value) for workshop, value in completion.items()}


def annotate_bar_values(ax, bars, value_format):
    for bar in bars:
        value = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            value_format(value),
            ha="center",
            va="bottom",
            fontsize=9,
            fontproperties=CHINESE_FONT,
        )


def create_figure_8(output_dir, q2_rows):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)

    utilization = utilization_by_type(q2_rows, Q2_AVAILABLE_COUNTS, MAKESPAN["问题2"])
    type_keys = list(EQUIPMENT_TYPE_LABELS.keys())
    x_labels = [EQUIPMENT_TYPE_LABELS[key] for key in type_keys]
    colors = ["#7C6A0A", "#4C78A8", "#54A24B", "#E45756", "#F58518"]
    bars = axes[0].bar(x_labels, [utilization[key] for key in type_keys], color=colors, width=0.65)
    annotate_bar_values(axes[0], bars, lambda value: f"{value:.1f}%")
    axes[0].set_title("问题2瓶颈设备利用率分析", fontproperties=CHINESE_FONT, fontsize=13)
    axes[0].set_ylabel("利用率（%）", fontproperties=CHINESE_FONT)
    apply_common_axis_style(axes[0])

    completion = workshop_completion_hours(q2_rows)
    workshop_keys = list(WORKSHOP_COLORS.keys())
    workshop_labels = [WORKSHOP_LABELS[key] for key in workshop_keys]
    bars = axes[1].bar(
        workshop_labels,
        [completion[key] for key in workshop_keys],
        color=[WORKSHOP_COLORS[key] for key in workshop_keys],
        width=0.65,
    )
    annotate_bar_values(axes[1], bars, lambda value: f"{value:.1f}")
    axes[1].set_title("问题2关键车间完工时间", fontproperties=CHINESE_FONT, fontsize=13)
    axes[1].set_ylabel("完工时间（小时）", fontproperties=CHINESE_FONT)
    apply_common_axis_style(axes[1])

    save_figure(fig, output_dir, "图8问题2瓶颈设备利用率与关键车间分析图.png")


def create_figure_9(output_dir, q2_rows, q3_rows):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)

    problems = ["问题2", "问题3"]
    makespan_hours = [seconds_to_hours(MAKESPAN[problem]) for problem in problems]
    bars = axes[0].bar(
        problems,
        makespan_hours,
        color=["#E45756", "#54A24B"],
        width=0.55,
    )
    for bar, problem in zip(bars, problems):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            seconds_to_hms(MAKESPAN[problem]),
            ha="center",
            va="bottom",
            fontsize=9,
            fontproperties=CHINESE_FONT,
        )
    axes[0].set_title("双班组协同前后工期对比", fontproperties=CHINESE_FONT, fontsize=13)
    axes[0].set_ylabel("工期（小时）", fontproperties=CHINESE_FONT)
    apply_common_axis_style(axes[0])

    q2_utilization = utilization_by_type(q2_rows, Q2_AVAILABLE_COUNTS, MAKESPAN["问题2"])
    q3_utilization = utilization_by_type(q3_rows, Q3_AVAILABLE_COUNTS, MAKESPAN["问题3"])
    type_keys = list(EQUIPMENT_TYPE_LABELS.keys())
    positions = range(len(type_keys))
    width = 0.36
    q2_bars = axes[1].bar(
        [position - width / 2 for position in positions],
        [q2_utilization[key] for key in type_keys],
        width=width,
        color="#E45756",
        label="问题2单班组",
    )
    q3_bars = axes[1].bar(
        [position + width / 2 for position in positions],
        [q3_utilization[key] for key in type_keys],
        width=width,
        color="#4C78A8",
        label="问题3双班组",
    )
    axes[1].set_xticks(list(positions))
    axes[1].set_xticklabels([EQUIPMENT_TYPE_LABELS[key] for key in type_keys])
    axes[1].set_title("双班组协同下设备瓶颈缓解", fontproperties=CHINESE_FONT, fontsize=13)
    axes[1].set_ylabel("利用率（%）", fontproperties=CHINESE_FONT)
    axes[1].legend(prop=CHINESE_FONT, frameon=False)
    apply_common_axis_style(axes[1])
    annotate_bar_values(axes[1], q2_bars, lambda value: f"{value:.1f}%")
    annotate_bar_values(axes[1], q3_bars, lambda value: f"{value:.1f}%")

    for bottleneck in ["ASM", "HPM"]:
        idx = type_keys.index(bottleneck)
        drop = q2_utilization[bottleneck] - q3_utilization[bottleneck]
        axes[1].text(
            idx,
            max(q2_utilization[bottleneck], q3_utilization[bottleneck]) + 5,
            f"下降{drop:.1f}个百分点",
            ha="center",
            va="bottom",
            color=WORKSHOP_COLORS["D"],
            fontsize=9,
            fontproperties=CHINESE_FONT,
        )

    save_figure(fig, output_dir, "图9问题2-问题3双班组协同效果图.png")


def create_figure_10(output_dir):
    fig, ax = plt.subplots(figsize=(8.5, 5.5), constrained_layout=True)

    all_costs = [cost / 10000 for cost, _ in Q4_PROCUREMENT_CANDIDATES]
    all_makespans = [seconds_to_hours(makespan) for _, makespan in Q4_PROCUREMENT_CANDIDATES]
    ax.scatter(all_costs, all_makespans, s=55, color="#4C78A8", alpha=0.75)

    best_cost, best_makespan = Q4_PROCUREMENT_CANDIDATES[0]
    ax.scatter(
        [best_cost / 10000],
        [seconds_to_hours(best_makespan)],
        s=140,
        color="#E45756",
        marker="*",
        label="最优方案：不购买",
        zorder=3,
    )
    ax.annotate(
        "最优方案：不购买",
        (best_cost / 10000, seconds_to_hours(best_makespan)),
        xytext=(1.5, seconds_to_hours(best_makespan) + 1.5),
        textcoords="data",
        arrowprops={"arrowstyle": "->", "color": "#444444", "lw": 1.0},
        fontproperties=CHINESE_FONT,
    )

    ax.set_title("问题4购买方案成本-收益图", fontproperties=CHINESE_FONT, fontsize=13)
    ax.set_xlabel("采购成本（万元）", fontproperties=CHINESE_FONT)
    ax.set_ylabel("工期（小时）", fontproperties=CHINESE_FONT)
    ax.legend(prop=CHINESE_FONT, frameon=False, loc="upper left")
    apply_common_axis_style(ax)

    save_figure(fig, output_dir, "图10问题4购买方案成本-收益图.png")


def create_figure_11(output_dir):
    fig, ax = plt.subplots(figsize=(8.5, 5.2), constrained_layout=True)

    problems = list(MAKESPAN.keys())
    hours = [seconds_to_hours(MAKESPAN[problem]) for problem in problems]
    bars = ax.bar(problems, hours, color=["#9C755F", "#E45756", "#4C78A8", "#54A24B"], width=0.58)
    for bar, problem in zip(bars, problems):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            seconds_to_hms(MAKESPAN[problem]),
            ha="center",
            va="bottom",
            fontsize=9,
            fontproperties=CHINESE_FONT,
        )

    ax.plot(problems, hours, color="#444444", linewidth=1.3, marker="o", markersize=5)
    ax.set_title("四问工期递进对比", fontproperties=CHINESE_FONT, fontsize=13)
    ax.set_ylabel("工期（小时）", fontproperties=CHINESE_FONT)
    apply_common_axis_style(ax)

    save_figure(fig, output_dir, "图11四问makespan递进对比图.png")


def create_figure_12(output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)

    problems = list(LOWER_BOUND_DATA.keys())
    gaps = [
        (LOWER_BOUND_DATA[problem]["solution"] - LOWER_BOUND_DATA[problem]["combined_lb"])
        / LOWER_BOUND_DATA[problem]["combined_lb"]
        * 100
        for problem in problems
    ]
    bars = axes[0].bar(problems, gaps, color=["#4C78A8", "#F58518", "#54A24B", "#72B7B2"], width=0.58)
    annotate_bar_values(axes[0], bars, lambda value: f"{value:.2f}%")
    axes[0].set_title("下界与最终解的相对差距", fontproperties=CHINESE_FONT, fontsize=13)
    axes[0].set_ylabel("Gap（%）", fontproperties=CHINESE_FONT)
    apply_common_axis_style(axes[0])

    baseline_rules = [rule for rule in next(iter(BASELINE_COMPARISON.values())) if rule != "ours"]
    question_labels = list(BASELINE_COMPARISON.keys())
    positions = range(len(question_labels))
    width = 0.14
    palette = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]
    for idx, rule in enumerate(baseline_rules):
        improvement = [
            (BASELINE_COMPARISON[question][rule] - BASELINE_COMPARISON[question]["ours"])
            / BASELINE_COMPARISON[question][rule]
            * 100
            for question in question_labels
        ]
        axes[1].bar(
            [position + (idx - 2) * width for position in positions],
            improvement,
            width=width,
            color=palette[idx],
            label=rule,
        )

    axes[1].set_xticks(list(positions))
    axes[1].set_xticklabels(question_labels)
    axes[1].set_title("相对基线规则改善率", fontproperties=CHINESE_FONT, fontsize=13)
    axes[1].set_ylabel("改善率（%）", fontproperties=CHINESE_FONT)
    axes[1].legend(prop=CHINESE_FONT, frameon=False, loc="upper left")
    apply_common_axis_style(axes[1])

    save_figure(fig, output_dir, "图12下界gap与baseline改善率图.png")


def equipment_order(schedule_rows):
    ordered = []
    seen = set()
    for row in schedule_rows:
        equipment_id = row["equipment_id"]
        if equipment_id not in seen:
            seen.add(equipment_id)
            ordered.append(equipment_id)
    return ordered


def draw_gantt(ax, schedule_rows, title):
    order = equipment_order(schedule_rows)
    y_positions = {equipment_id: idx for idx, equipment_id in enumerate(order)}

    for row in schedule_rows:
        workshop = workshop_from_process(row["process"])
        ax.barh(
            y_positions[row["equipment_id"]],
            seconds_to_hours(row["duration"]),
            left=seconds_to_hours(row["start"]),
            height=0.72,
            color=WORKSHOP_COLORS[workshop],
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_title(title, fontproperties=CHINESE_FONT, fontsize=13)
    ax.set_ylabel("设备编号", fontproperties=CHINESE_FONT)
    apply_common_axis_style(ax)


def create_figure_13(output_dir, q2_rows, q3_rows, q4_rows):
    fig, axes = plt.subplots(3, 1, figsize=(14, 16), sharex=False, constrained_layout=True)

    draw_gantt(axes[0], q2_rows, "问题2调度甘特图")
    draw_gantt(axes[1], q3_rows, "问题3调度甘特图")
    draw_gantt(axes[2], q4_rows, "问题4调度甘特图")
    axes[2].set_xlabel("时间（小时）", fontproperties=CHINESE_FONT)

    legend_handles = [
        patches.Patch(color=color, label=WORKSHOP_LABELS[workshop])
        for workshop, color in WORKSHOP_COLORS.items()
    ]
    axes[0].legend(handles=legend_handles, prop=CHINESE_FONT, frameon=False, ncol=5, loc="upper right")

    save_figure(fig, output_dir, "图13问题2-3-4调度甘特图.png")


def main():
    output_dir = ensure_output_dir()
    q2_rows = parse_embedded_schedule(Q2_SCHEDULE_TEXT)
    q3_rows = parse_embedded_schedule(Q3_SCHEDULE_TEXT)
    q4_rows = parse_embedded_schedule(Q3_SCHEDULE_TEXT)

    create_figure_8(output_dir, q2_rows)
    create_figure_9(output_dir, q2_rows, q3_rows)
    create_figure_10(output_dir)
    create_figure_11(output_dir)
    create_figure_12(output_dir)
    create_figure_13(output_dir, q2_rows, q3_rows, q4_rows)


if __name__ == "__main__":
    main()