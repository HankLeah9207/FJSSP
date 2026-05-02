"""
Generate Figures 4, 5, 6, 8, 9a, 9b for the FJSSP paper.
Output directory: /media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP/
"""

import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties

matplotlib.use("Agg")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE = "/media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP"

FONT_PATHS = [
    "/usr/share/fonts/truetype/arphic/SimSun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
]

# ── Font setup ─────────────────────────────────────────────────────────────────
_font_path = None
for _fp in FONT_PATHS:
    if os.path.exists(_fp):
        _font_path = _fp
        break
if _font_path is None:
    raise FileNotFoundError(
        "Neither SimSun.ttf nor NotoSerifCJK-Regular.ttc was found. "
        "Please install a CJK font at one of:\n" + "\n".join(FONT_PATHS)
    )

from matplotlib import font_manager as _fm
_fm.fontManager.addfont(_font_path)
_fp_obj = FontProperties(fname=_font_path)
_FONT_NAME = _fp_obj.get_name()

plt.rcParams.update({
    "font.family": _FONT_NAME,
    "axes.unicode_minus": False,
})

def fp(size=10):
    """Return a FontProperties object at the given size."""
    return FontProperties(fname=_font_path, size=size)


def save(fig, stem):
    """Save figure as PNG (300 dpi) and SVG."""
    png = os.path.join(BASE, stem + ".png")
    svg = os.path.join(BASE, stem + ".svg")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    print(f"  saved {stem}.png  {stem}.svg")


# ── Helper: draw a Gantt bar and optionally label it ──────────────────────────
def gantt_bar(ax, y, x_start, x_end, color, label_text=None, min_width_h=0.4,
              bar_height=0.6, fontsize=7):
    width = x_end - x_start
    ax.barh(y, width, left=x_start, height=bar_height, color=color,
            edgecolor="white", linewidth=0.5, align="center")
    if label_text and width >= min_width_h:
        ax.text(x_start + width / 2, y, label_text,
                ha="center", va="center", fontsize=fontsize,
                fontproperties=fp(fontsize), color="white", clip_on=True)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 4  P1 A车间同步工序甘特图
# ══════════════════════════════════════════════════════════════════════════════
def fig4():
    print("Drawing 图4 …")
    df = pd.read_csv(os.path.join(BASE, "q1_schedule.csv"))
    df["start_h"] = df["Start_s"] / 3600
    df["end_h"]   = df["End_s"]   / 3600

    process_colors = {"A1": "#4472C4", "A2": "#ED7D31", "A3": "#70AD47"}
    process_labels = {"A1": "工序A1", "A2": "工序A2", "A3": "工序A3"}

    # y positions: one row per equipment
    equip_ids = df["EquipmentID"].tolist()   # preserve original order (No 1-5)
    y_map = {eq: i for i, eq in enumerate(equip_ids)}

    fig, ax = plt.subplots(figsize=(9, 3.6))

    for _, row in df.iterrows():
        gantt_bar(ax, y_map[row["EquipmentID"]],
                  row["start_h"], row["end_h"],
                  process_colors[row["Process"]],
                  label_text=row["Process"], min_width_h=0.3, fontsize=8)

    # completion time vertical line
    cmax_h = 41400 / 3600
    ax.axvline(cmax_h, color="crimson", linewidth=1.2, linestyle="--")
    ax.text(cmax_h + 0.05, len(equip_ids) - 0.1,
            r"$C_A$ = 41400 s",
            fontproperties=fp(9), color="crimson", va="top")

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(equip_ids, fontproperties=fp(9))
    ax.set_xlabel("时间（小时）", fontproperties=fp(10))
    ax.set_title("P1  A车间同步工序甘特图", fontproperties=fp(12))
    ax.set_xlim(left=0)
    ax.grid(False)

    legend_patches = [mpatches.Patch(color=c, label=process_labels[p])
                      for p, c in process_colors.items()]
    ax.legend(handles=legend_patches, prop=fp(9),
              loc="lower right", frameon=True)

    fig.tight_layout()
    save(fig, "图4_P1_A车间同步工序甘特图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 5  P2 单班组五车间设备甘特图
# ══════════════════════════════════════════════════════════════════════════════
def fig5():
    print("Drawing 图5 …")
    df = pd.read_csv(os.path.join(BASE, "q2_schedule.csv"))
    df["start_h"] = df["Start_s"] / 3600
    df["end_h"]   = df["End_s"]   / 3600

    ws_colors = {"A": "#4472C4", "B": "#ED7D31", "C": "#70AD47",
                 "D": "#FF0000", "E": "#7030A0"}
    ws_labels = {k: f"{k}车间" for k in ws_colors}

    # Sort equipment: by workshop then earliest start
    first_start = df.groupby("EquipmentID")["Start_s"].min()
    ws_of = df.drop_duplicates("EquipmentID").set_index("EquipmentID")["Workshop"]
    equip_sorted = (
        pd.DataFrame({"first_start": first_start, "workshop": ws_of})
        .sort_values(["workshop", "first_start"])
        .index.tolist()
    )
    y_map = {eq: i for i, eq in enumerate(equip_sorted)}

    fig, ax = plt.subplots(figsize=(12, 8))

    for _, row in df.iterrows():
        gantt_bar(ax, y_map[row["EquipmentID"]],
                  row["start_h"], row["end_h"],
                  ws_colors[row["Workshop"]],
                  label_text=row["Process"], min_width_h=0.5, fontsize=7)

    cmax_h = 151604 / 3600
    ax.axvline(cmax_h, color="crimson", linewidth=1.2, linestyle="--")
    ax.text(cmax_h + 0.1, len(equip_sorted) - 0.5,
            "$C_{max}$ = 151604 s\n(42:06:44)",
            fontproperties=fp(8), color="crimson", va="top")

    # status box
    ax.text(0.01, 0.01, "状态: OPTIMAL  |  gap = 0.00%",
            transform=ax.transAxes, fontproperties=fp(8),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                      edgecolor="gray", alpha=0.8))

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(equip_sorted, fontproperties=fp(8))
    ax.set_xlabel("时间（小时）", fontproperties=fp(10))
    ax.set_title("P2  单班组五车间设备甘特图", fontproperties=fp(12))
    ax.set_xlim(left=0)
    ax.grid(False)

    legend_patches = [mpatches.Patch(color=c, label=ws_labels[w])
                      for w, c in ws_colors.items()]
    ax.legend(handles=legend_patches, prop=fp(9),
              loc="upper right", frameon=True)

    fig.tight_layout()
    save(fig, "图5_P2单班组五车间设备甘特图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 6  P2/P3 关键设备时间轴对比图  (ASM + HPM only)
# ══════════════════════════════════════════════════════════════════════════════
def fig6():
    print("Drawing 图6 …")
    KEY_TYPES = {
        "Automatic Sensing Multi-Function Machine": ("ASM类型", "#4472C4"),
        "High-speed Polishing Machine":             ("HPM类型", "#ED7D31"),
    }

    def load(path):
        d = pd.read_csv(path)
        d["start_h"] = d["Start_s"] / 3600
        d["end_h"]   = d["End_s"]   / 3600
        return d[d["EquipmentType"].isin(KEY_TYPES)].copy()

    p2 = load(os.path.join(BASE, "q2_schedule.csv"))
    p3 = load(os.path.join(BASE, "q3_schedule.csv"))

    def equip_order(df):
        first = df.groupby("EquipmentID")["Start_s"].min().sort_values()
        return first.index.tolist()

    p2_equip = equip_order(p2)
    p3_equip = equip_order(p3)

    fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=True)

    cmax_p2 = 151604 / 3600
    cmax_p3 = 123844 / 3600

    for ax, df, equip_list, cmax_h, subtitle in [
        (axes[0], p2, p2_equip, cmax_p2, "P2  单班组 — 关键设备（ASM / HPM）"),
        (axes[1], p3, p3_equip, cmax_p3, "P3  双班组 — 关键设备（ASM / HPM）"),
    ]:
        y_map = {eq: i for i, eq in enumerate(equip_list)}
        for _, row in df.iterrows():
            _, color = KEY_TYPES[row["EquipmentType"]]
            gantt_bar(ax, y_map[row["EquipmentID"]],
                      row["start_h"], row["end_h"], color,
                      label_text=row["Process"], min_width_h=0.5, fontsize=7)

        ax.axvline(cmax_h, color="crimson", linewidth=1.2, linestyle="--")
        ax.text(cmax_h + 0.15, len(equip_list) - 0.6,
                f"$C_{{max}}$ = {cmax_h*3600:.0f} s",
                fontproperties=fp(8), color="crimson", va="top")

        ax.set_yticks(list(y_map.values()))
        ax.set_yticklabels(equip_list, fontproperties=fp(8))
        ax.set_title(subtitle, fontproperties=fp(10), loc="left")
        ax.grid(False)

    axes[1].set_xlabel("时间（小时）", fontproperties=fp(10))
    axes[0].set_xlim(left=0, right=44)

    legend_patches = [mpatches.Patch(color=c, label=lbl)
                      for _, (lbl, c) in KEY_TYPES.items()]
    axes[0].legend(handles=legend_patches, prop=fp(9),
                   loc="upper right", frameon=True)

    fig.suptitle("P2 / P3  关键设备时间轴对比图", fontproperties=fp(12), y=1.01)
    fig.tight_layout()
    save(fig, "图6_P2P3关键设备时间轴对比图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 8  P4 购置方案 cost–makespan 分布图
# ══════════════════════════════════════════════════════════════════════════════
def fig8():
    print("Drawing 图8 …")
    df = pd.read_csv(os.path.join(BASE, "q4_procurement_plans.csv"))

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.scatter(df["Cost"], df["Makespan"],
               color="steelblue", alpha=0.65, s=50, zorder=3,
               label="候选购置方案（OPTIMAL）")

    # highlight zero-purchase point
    zero = df[df["Cost"] == 0].iloc[0]
    ax.scatter(zero["Cost"], zero["Makespan"],
               color="crimson", marker="*", s=220, zorder=5,
               label="最优方案：无购置")
    ax.annotate(
        "最优方案：无购置\nCost = 0\n$C_{max}$ = 123844 s",
        xy=(zero["Cost"], zero["Makespan"]),
        xytext=(30000, 123600),
        fontproperties=fp(9), color="crimson",
        arrowprops=dict(arrowstyle="->", color="crimson", lw=1),
    )

    # reference line
    ax.axhline(123844, color="gray", linewidth=1, linestyle="--")
    ax.text(df["Cost"].max() * 0.98, 123844 + 120,
            "最短完工时间 123844 s",
            fontproperties=fp(8), color="gray", ha="right")

    # summary text
    ax.text(0.97, 0.05,
            "60 个可行方案均已评估\n无方案优于 123844 s",
            transform=ax.transAxes, fontproperties=fp(9),
            ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow",
                      edgecolor="gray", alpha=0.85))

    ax.set_xlabel("采购成本（元）", fontproperties=fp(11))
    ax.set_ylabel("完工时间（s）", fontproperties=fp(11))
    ax.set_title("P4  购置方案 cost–makespan 分布图", fontproperties=fp(12))
    ax.set_ylim(118000, 130000)
    ax.grid(False)
    ax.legend(prop=fp(9), loc="upper left", frameon=True)

    fig.tight_layout()
    save(fig, "图8_P4购置方案cost_makespan分布图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 9a  最优性证书 objective–bound 对比图
# ══════════════════════════════════════════════════════════════════════════════
def fig9a():
    print("Drawing 图9a …")
    df = pd.read_csv(os.path.join(BASE, "solver_summary.csv"))

    problems = df["Problem"].tolist()
    objs  = df["Objective_s"].tolist()
    bnds  = df["Bound_s"].tolist()
    hmss  = df["Makespan_hms"].tolist()

    x = np.arange(len(problems))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7, 4.5))

    bars_obj = ax.bar(x - width / 2, objs, width,
                      label="目标值", color="#4472C4", alpha=0.85)
    bars_bnd = ax.bar(x + width / 2, bnds, width,
                      label="下界", color="#ED7D31", alpha=0.85,
                      hatch="//", edgecolor="white")

    # annotate each pair
    for i, (obj, hms) in enumerate(zip(objs, hmss)):
        ax.text(i, obj + obj * 0.01,
                f"gap = 0.00%\nOPTIMAL\n{hms}",
                ha="center", va="bottom", fontproperties=fp(7.5),
                color="#222222")

    ax.set_xticks(x)
    ax.set_xticklabels(problems, fontproperties=fp(10))
    ax.set_ylabel("完工时间（s）", fontproperties=fp(10))
    ax.set_title("最优性证书：目标值与下界对比", fontproperties=fp(12))
    ax.set_ylim(0, max(objs) * 1.22)
    ax.grid(False)
    ax.legend(prop=fp(9), frameon=True)

    fig.tight_layout()
    save(fig, "图9a_最优性证书objective_bound对比")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 9b  可行性审计矩阵
# ══════════════════════════════════════════════════════════════════════════════
def fig9b():
    print("Drawing 图9b …")
    df = pd.read_csv(os.path.join(BASE, "feasibility_audit.csv"))

    # orient: rows = P1–P4, columns = audit items
    audit_items = df["AuditItem"].tolist()
    problems = ["P1", "P2", "P3", "P4"]

    # build numeric matrix and color map
    matrix_text = df[problems].values.T   # shape (4, 9): rows=problems, cols=items
    pass_color = "#4CAF50"
    na_color   = "#BDBDBD"

    fig, ax = plt.subplots(figsize=(12, 3.2))

    n_rows = len(problems)
    n_cols = len(audit_items)

    for r, prob in enumerate(problems):
        for c, item in enumerate(audit_items):
            val = df.loc[df["AuditItem"] == item, prob].values[0]
            color = pass_color if val == "PASS" else na_color
            rect = mpatches.FancyBboxPatch(
                (c + 0.05, r + 0.05), 0.9, 0.9,
                boxstyle="round,pad=0.05",
                facecolor=color, edgecolor="white", linewidth=1.5,
            )
            ax.add_patch(rect)
            text_color = "white" if val == "PASS" else "#555555"
            ax.text(c + 0.5, r + 0.5, val,
                    ha="center", va="center",
                    fontproperties=fp(8.5), color=text_color)

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.set_xticks([c + 0.5 for c in range(n_cols)])
    ax.set_xticklabels(audit_items, fontproperties=fp(8.5), rotation=25, ha="right")
    ax.set_yticks([r + 0.5 for r in range(n_rows)])
    ax.set_yticklabels(problems, fontproperties=fp(10))
    ax.set_title("可行性审计矩阵", fontproperties=fp(12))
    ax.grid(False)
    ax.tick_params(length=0)

    # legend
    pass_patch = mpatches.Patch(color=pass_color, label="PASS")
    na_patch   = mpatches.Patch(color=na_color,   label="N.A.")
    ax.legend(handles=[pass_patch, na_patch], prop=fp(9),
              loc="upper right", bbox_to_anchor=(1.0, -0.25),
              ncol=2, frameon=True)

    fig.tight_layout()
    save(fig, "图9b_可行性审计矩阵")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Using font: {_font_path}\n")
    fig4()
    fig5()
    fig6()
    fig8()
    fig9a()
    fig9b()
    print("\nAll figures generated.")
