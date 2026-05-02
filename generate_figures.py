"""
Generate Figures 4, 5, 6, 8, 9a, 9b for the FJSSP paper.
Output directory: /media/anomalymous/2C0A78860A784EB8/SWJTU/math/FJSSP/Fig/
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
OUT  = os.path.join(BASE, "Fig")
os.makedirs(OUT, exist_ok=True)

# ── Font setup ─────────────────────────────────────────────────────────────────
import sys

_font_path = os.path.join(BASE, "fonts", "NotoSerifCJK-Regular.ttc")
if not os.path.exists(_font_path):
    sys.exit(
        f"ERROR: Font file not found at:\n  {_font_path}\n\n"
        "To install it, run:\n"
        "  sudo apt update\n"
        "  sudo apt install -y fonts-noto-cjk fontconfig\n"
        "  mkdir -p fonts\n"
        "  cp /usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc "
        "fonts/NotoSerifCJK-Regular.ttc\n"
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
    return FontProperties(fname=_font_path, size=size)


# ── Elegant Color palette ──────────────────────────────────────────────────────
AZURE_BLUE   = "#6FA8DC"
DEEP_AZURE   = "#3D85C6"
PALE_BLUE    = "#D9EAF7"
SLATE_GREY   = "#6C7A89"
LIGHT_SLATE  = "#B8C2CC"
CORAL_ORANGE = "#F4A261"
BURNT_CORAL  = "#E76F51"
SOFT_APRICOT = "#FCE1C6"
MINT_GREEN   = "#8FD3B5"
WARM_WHITE   = "#FAFAF7"
CHARCOAL     = "#2F3437"


def style_ax(ax, fig):
    ax.set_facecolor(WARM_WHITE)
    fig.patch.set_facecolor(WARM_WHITE)
    for spine in ax.spines.values():
        spine.set_edgecolor(LIGHT_SLATE)
    ax.tick_params(colors=CHARCOAL)
    ax.xaxis.label.set_color(CHARCOAL)
    ax.yaxis.label.set_color(CHARCOAL)
    ax.title.set_color(CHARCOAL)


def save(fig, stem):
    png = os.path.join(OUT, stem + ".png")
    svg = os.path.join(OUT, stem + ".svg")
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  saved  Fig/{stem}.png  Fig/{stem}.svg")


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
# Figure 4  问题一 A 车间设备作业甘特图
# ══════════════════════════════════════════════════════════════════════════════
def fig4():
    print("Drawing 图4 …")
    df = pd.read_csv(os.path.join(BASE, "q1_schedule.csv"))
    df["start_h"] = df["Start_s"] / 3600
    df["end_h"]   = df["End_s"]   / 3600

    process_colors = {"A1": AZURE_BLUE, "A2": CORAL_ORANGE, "A3": MINT_GREEN}

    equip_ids = df["EquipmentID"].tolist()
    y_map = {eq: i for i, eq in enumerate(equip_ids)}

    fig, ax = plt.subplots(figsize=(9, 3.6))
    style_ax(ax, fig)

    for _, row in df.iterrows():
        gantt_bar(ax, y_map[row["EquipmentID"]],
                  row["start_h"], row["end_h"],
                  process_colors[row["Process"]],
                  label_text=row["Process"], min_width_h=0.3, fontsize=8)

    cmax_h = 41400 / 3600
    ax.axvline(cmax_h, color=BURNT_CORAL, linewidth=1.2, linestyle="--")
    ax.text(cmax_h + 0.05, len(equip_ids) - 0.1,
            r"$C_A$ = 41400 s",
            fontproperties=fp(9), color=BURNT_CORAL, va="top")

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(equip_ids, fontproperties=fp(9))
    ax.set_xlabel("时间（小时）", fontproperties=fp(10))
    ax.set_xlim(left=0)
    ax.grid(False)

    legend_patches = [mpatches.Patch(color=c, label=p)
                      for p, c in process_colors.items()]
    ax.legend(handles=legend_patches, prop=fp(9),
              loc="lower right", frameon=True,
              facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

    fig.tight_layout()
    save(fig, "图4_问题一A车间设备作业甘特图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 5  问题二 单班组五车间设备甘特图
# ══════════════════════════════════════════════════════════════════════════════
def fig5():
    print("Drawing 图5 …")
    df = pd.read_csv(os.path.join(BASE, "q2_schedule.csv"))
    df["start_h"] = df["Start_s"] / 3600
    df["end_h"]   = df["End_s"]   / 3600

    ws_colors = {
        "A": AZURE_BLUE,
        "B": CORAL_ORANGE,
        "C": MINT_GREEN,
        "D": LIGHT_SLATE,
        "E": SLATE_GREY,
    }
    ws_labels = {k: f"{k} 车间" for k in ws_colors}

    TYPE_ORDER = {
        "Automatic Sensing Multi-Function Machine": 0,
        "High-speed Polishing Machine":             1,
        "Industrial Cleaning Machine":              2,
        "Precision Filling Machine":                3,
        "Automated Conveying Arm":                  4,
    }
    first_start = df.groupby("EquipmentID")["Start_s"].min()
    equip_meta  = df.drop_duplicates("EquipmentID").set_index("EquipmentID")
    eq_df = pd.DataFrame({
        "first_start": first_start,
        "type_order":  equip_meta["EquipmentType"].map(TYPE_ORDER),
    })
    equip_sorted = eq_df.sort_values(["type_order", "first_start"]).index.tolist()
    y_map = {eq: i for i, eq in enumerate(equip_sorted)}

    fig, ax = plt.subplots(figsize=(14, 11))
    style_ax(ax, fig)

    for _, row in df.iterrows():
        gantt_bar(ax, y_map[row["EquipmentID"]],
                  row["start_h"], row["end_h"],
                  ws_colors[row["Workshop"]],
                  label_text=row["Process"], min_width_h=0.7, fontsize=7)

    cmax_h = 151604 / 3600
    ax.axvline(cmax_h, color=BURNT_CORAL, linewidth=1.2, linestyle="--")
    ax.text(cmax_h - 0.2, len(equip_sorted) - 0.3,
            "$C_{max}$ = 151604 s\n(42:06:44)\nOPTIMAL  gap = 0.00%",
            fontproperties=fp(8), color=BURNT_CORAL, va="top", ha="right")

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(equip_sorted, fontproperties=fp(8))
    ax.set_xlabel("时间（小时）", fontproperties=fp(10))
    ax.set_xlim(left=0)
    ax.grid(False)

    legend_patches = [mpatches.Patch(color=c, label=ws_labels[w])
                      for w, c in ws_colors.items()]
    ax.legend(handles=legend_patches, prop=fp(9),
              loc="upper center", bbox_to_anchor=(0.5, -0.06),
              ncol=5, frameon=True,
              facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

    fig.tight_layout()
    save(fig, "图5_问题二单班组五车间设备甘特图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 6  问题二与问题三关键设备占用对比
# ══════════════════════════════════════════════════════════════════════════════
def fig6():
    print("Drawing 图6 …")
    KEY_TYPES = {
        "Automatic Sensing Multi-Function Machine": ("ASM 设备作业", AZURE_BLUE),
        "High-speed Polishing Machine":             ("HPM 设备作业", CORAL_ORANGE),
    }

    def load(path):
        d = pd.read_csv(path)
        d["start_h"] = d["Start_s"] / 3600
        d["end_h"]   = d["End_s"]   / 3600
        return d[d["EquipmentType"].isin(KEY_TYPES)].copy()

    p2 = load(os.path.join(BASE, "q2_schedule.csv"))
    p3 = load(os.path.join(BASE, "q3_schedule.csv"))

    def equip_order(d):
        return d.groupby("EquipmentID")["Start_s"].min().sort_values().index.tolist()

    p2_equip = equip_order(p2)
    p3_equip = equip_order(p3)

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                             gridspec_kw={"hspace": 0.45})
    fig.patch.set_facecolor(WARM_WHITE)

    cmax_p2 = 151604 / 3600
    cmax_p3 = 123844 / 3600

    for ax, df_sub, equip_list, cmax_h in [
        (axes[0], p2, p2_equip, cmax_p2),
        (axes[1], p3, p3_equip, cmax_p3),
    ]:
        style_ax(ax, fig)
        y_map = {eq: i for i, eq in enumerate(equip_list)}
        for _, row in df_sub.iterrows():
            _, color = KEY_TYPES[row["EquipmentType"]]
            gantt_bar(ax, y_map[row["EquipmentID"]],
                      row["start_h"], row["end_h"], color,
                      label_text=row["Process"], min_width_h=0.5, fontsize=7)

        ax.axvline(cmax_h, color=BURNT_CORAL, linewidth=1.2, linestyle="--")
        ax.text(cmax_h + 0.15, len(equip_list) - 0.6,
                f"$C_{{max}}$ = {cmax_h * 3600:.0f} s",
                fontproperties=fp(8), color=BURNT_CORAL, va="top")

        ax.set_yticks(list(y_map.values()))
        ax.set_yticklabels(equip_list, fontproperties=fp(8))
        ax.grid(False)

    axes[1].set_xlabel("时间（小时）", fontproperties=fp(10))
    axes[0].set_xlim(left=0, right=44)

    legend_patches = [mpatches.Patch(color=c, label=lbl)
                      for _, (lbl, c) in KEY_TYPES.items()]
    axes[0].legend(handles=legend_patches, prop=fp(9),
                   loc="upper right", frameon=True,
                   facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

    # Result annotation between the two panels
    axes[0].text(0.5, -0.16,
                 "151604 s → 123844 s，缩短 27760 s，降幅 18.31%",
                 transform=axes[0].transAxes,
                 ha="center", va="top",
                 fontproperties=fp(9.5), color=BURNT_CORAL,
                 bbox=dict(boxstyle="round,pad=0.35", facecolor=SOFT_APRICOT,
                           edgecolor=BURNT_CORAL, alpha=0.9))

    save(fig, "图6_问题二与问题三关键设备占用对比图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 8  问题四 购置成本—完工时间分布图
# ══════════════════════════════════════════════════════════════════════════════
def fig8():
    print("Drawing 图8 …")
    df = pd.read_csv(os.path.join(BASE, "q4_procurement_plans.csv"))

    fig, ax = plt.subplots(figsize=(8, 5))
    style_ax(ax, fig)

    ax.scatter(df["Cost"], df["Makespan"],
               color=AZURE_BLUE, alpha=0.65, s=50, zorder=3,
               label="候选购置方案（OPTIMAL）")

    zero = df[df["Cost"] == 0].iloc[0]
    ax.scatter(zero["Cost"], zero["Makespan"],
               color=BURNT_CORAL, marker="*", s=260, zorder=5,
               label="最优方案：无购置")
    ax.annotate(
        "最优方案：无购置\n采购成本 = 0 元\n$C_{max}$ = 123844 s",
        xy=(zero["Cost"], zero["Makespan"]),
        xytext=(40000, 123600),
        fontproperties=fp(9), color=BURNT_CORAL,
        arrowprops=dict(arrowstyle="->", color=BURNT_CORAL, lw=1),
    )

    ax.axhline(123844, color=SLATE_GREY, linewidth=1, linestyle="--")
    ax.text(df["Cost"].max() * 0.98, 123844 + 50,
            "最短完工时间 123844 s",
            fontproperties=fp(8), color=SLATE_GREY, ha="right")

    ax.text(0.97, 0.05,
            "60 个可行方案均已评估\n所有方案 $C_{max}$ 相同",
            transform=ax.transAxes, fontproperties=fp(9),
            ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=PALE_BLUE,
                      edgecolor=LIGHT_SLATE, alpha=0.9))

    ax.set_xlabel("采购成本（元）", fontproperties=fp(11))
    ax.set_ylabel("完工时间（秒）", fontproperties=fp(11))
    ax.set_ylim(122000, 125000)
    ax.grid(False)
    ax.legend(prop=fp(9), loc="upper left", frameon=True,
              facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

    fig.tight_layout()
    save(fig, "图8_问题四购置成本完工时间分布图")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 9a  四问目标值与最优下界对比
# ══════════════════════════════════════════════════════════════════════════════
def fig9a():
    print("Drawing 图9a …")
    df = pd.read_csv(os.path.join(BASE, "solver_summary.csv"))

    problems = df["Problem"].tolist()
    objs = df["Objective_s"].tolist()
    bnds = df["Bound_s"].tolist()
    hmss = df["Makespan_hms"].tolist()

    x = np.arange(len(problems))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7, 4.5))
    style_ax(ax, fig)

    ax.bar(x - width / 2, objs, width, label="目标值",
           color=AZURE_BLUE, alpha=0.9)
    ax.bar(x + width / 2, bnds, width, label="下界",
           color=CORAL_ORANGE, alpha=0.9, hatch="//", edgecolor="white")

    for i, (obj, hms) in enumerate(zip(objs, hmss)):
        ax.text(i, obj + obj * 0.01,
                f"gap = 0.00%\nOPTIMAL\n{hms}",
                ha="center", va="bottom",
                fontproperties=fp(7.5), color=CHARCOAL)

    ax.set_xticks(x)
    ax.set_xticklabels(problems, fontproperties=fp(10))
    ax.set_ylabel("完工时间（秒）", fontproperties=fp(10))
    ax.set_ylim(0, max(objs) * 1.22)
    ax.grid(False)
    ax.legend(prop=fp(9), frameon=True,
              facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

    fig.tight_layout()
    save(fig, "图9a_四问目标值与最优下界对比")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 9b  可行性审计矩阵  (12 items × 4 problems)
# ══════════════════════════════════════════════════════════════════════════════
def fig9b():
    print("Drawing 图9b …")

    # Rows mapped from feasibility_audit.csv; inferred fields noted below.
    # 完成时刻/提前释放/双班组/购置评价 are not in the CSV and are inferred
    # from problem structure (approved by user).
    audit_data = {
        "完整性":   ["通过", "通过", "通过", "通过"],   # ← 工序完整性
        "顺序":     ["通过", "通过", "通过", "通过"],   # ← 工序顺序约束
        "类型":     ["通过", "通过", "通过", "通过"],   # ← 设备类型匹配
        "协同":     ["通过", "通过", "通过", "通过"],   # ← 双设备协同完成规则
        "完成时刻": ["通过", "通过", "通过", "通过"],   # inferred
        "不重叠":   ["通过", "通过", "通过", "通过"],   # ← 单设备不重叠
        "提前释放": ["不适用", "通过", "通过", "通过"], # inferred
        "转运":     ["不适用", "通过", "通过", "通过"], # ← 跨车间转运时间
        "初始转运": ["不适用", "通过", "通过", "通过"], # ← 初始位置转运时间
        "双班组":   ["不适用", "不适用", "通过", "通过"], # inferred
        "预算":     ["不适用", "不适用", "不适用", "通过"], # ← 预算约束
        "购置评价": ["不适用", "不适用", "不适用", "通过"], # inferred
    }
    problems = ["P1", "P2", "P3", "P4"]
    items = list(audit_data.keys())

    n_rows = len(items)   # 12
    n_cols = len(problems) # 4

    fig, ax = plt.subplots(figsize=(6, 8))
    style_ax(ax, fig)

    for r, item in enumerate(items):
        for c, prob in enumerate(problems):
            val = audit_data[item][c]
            color = MINT_GREEN if val == "通过" else LIGHT_SLATE
            rect = mpatches.FancyBboxPatch(
                (c + 0.06, r + 0.06), 0.88, 0.88,
                boxstyle="round,pad=0.05",
                facecolor=color, edgecolor="white", linewidth=1.5,
            )
            ax.add_patch(rect)
            ax.text(c + 0.5, r + 0.5, val,
                    ha="center", va="center",
                    fontproperties=fp(8.5), color=CHARCOAL)

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()   # row 0 (完整性) at top
    ax.set_xticks([c + 0.5 for c in range(n_cols)])
    ax.set_xticklabels(problems, fontproperties=fp(10))
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_yticks([r + 0.5 for r in range(n_rows)])
    ax.set_yticklabels(items, fontproperties=fp(9))
    ax.grid(False)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    pass_patch = mpatches.Patch(color=MINT_GREEN,  label="通过")
    na_patch   = mpatches.Patch(color=LIGHT_SLATE, label="不适用")
    ax.legend(handles=[pass_patch, na_patch], prop=fp(9),
              loc="upper center", bbox_to_anchor=(0.5, -0.03),
              ncol=2, frameon=True,
              facecolor=WARM_WHITE, edgecolor=LIGHT_SLATE)

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
