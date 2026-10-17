from __future__ import annotations

from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FIG_DIR = RESULTS_DIR / "figures"
OUTPUT_DATE = datetime.now().strftime("%Y%m%d")
FIG_DIR.mkdir(parents=True, exist_ok=True)


def plot_cmehi_trend():
    report_path = RESULTS_DIR / "CMEHI_Report.csv"
    if not report_path.exists():
        print(" 未找到 CMEHI_Report.csv，无法生成趋势图。")
        return

    df = pd.read_csv(report_path)
    if df.empty:
        print(" 报告为空，无法生成趋势图。")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["CMEHI"], marker="o", linewidth=2)
    plt.title("CMEHI 时间变化趋势")
    plt.xlabel("时间")
    plt.ylabel("CMEHI")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "CMEHI_trend.png", dpi=300)
    plt.close()


def plot_component_bar():
    report_path = RESULTS_DIR / "CMEHI_Report.csv"
    if not report_path.exists():
        return

    df = pd.read_csv(report_path)
    if df.empty:
        return

    latest = df.iloc[-1]
    labels = ["S_声景", "S_鸟类多样性", "S_通讯干扰", "S_空气", "S_光污染"]
    values = [latest[column] for column in labels]

    plt.figure(figsize=(10, 5))
    plt.bar(
        labels,
        values,
        color=["#4e79a7", "#59a14f", "#af7aa1", "#f28e2b", "#e15759"],
    )
    plt.title("各分项得分")
    plt.ylabel("得分")
    plt.ylim(0, 100)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "component_scores.png", dpi=300)
    plt.close()


def plot_component_area():
    report_path = RESULTS_DIR / "CMEHI_Report.csv"
    if not report_path.exists():
        return

    df = pd.read_csv(report_path)
    if df.empty or "S_光污染" not in df.columns:
        return

    plot_cols = [
        "S_声景", "S_鸟类多样性", "S_通讯干扰", "S_空气", "S_光污染",
    ]
    present_cols = [col for col in plot_cols if col in df.columns]
    if not present_cols:
        return

    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.stackplot(x, *[df[col].fillna(0).to_numpy() for col in present_cols], labels=present_cols, alpha=0.8)
    ax.set_title("各分项随时间贡献变化")
    ax.set_xlabel("采样序号")
    ax.set_ylabel("分项得分")
    ax.set_xlim(0, max(len(df) - 1, 1))
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "component_area.png", dpi=300)
    plt.close()


def plot_air_and_birds():
    detection_path = RESULTS_DIR / f"detections_{OUTPUT_DATE}.csv"
    air_path = RESULTS_DIR / "air_quality.csv"
    if not detection_path.exists() or not air_path.exists():
        return

    try:
        detections = pd.read_csv(detection_path)
        air = pd.read_csv(air_path)
    except Exception:
        return

    if detections.empty or air.empty:
        return

    bird_counts = detections.groupby(detections["audio_file"]).size().reset_index(name="bird_count")
    merged = pd.concat([bird_counts, air.iloc[:len(bird_counts)].reset_index(drop=True)], axis=1)
    if merged.empty:
        return

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    ax1.plot(merged.index, merged["pm2_5_atm"], color="tab:blue", marker="o", label="PM2.5")
    ax2.plot(merged.index, merged["bird_count"], color="tab:green", marker="s", label="鸟鸣次数")

    ax1.set_xlabel("采样序号")
    ax1.set_ylabel("PM2.5 (μg/m³)", color="tab:blue")
    ax2.set_ylabel("鸟鸣次数", color="tab:green")
    plt.title("PM2.5 与鸟鸣频次双轴图")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "air_birds_dual_axis.png", dpi=300)
    plt.close()


def plot_light_pollution_trend():
    report_path = RESULTS_DIR / "CMEHI_Report.csv"
    if not report_path.exists():
        return
    df = pd.read_csv(report_path)
    if df.empty or "S_光污染" not in df.columns:
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["S_晨鸣"], marker="o", label="S_晨鸣", color="#f28e2b")
    plt.plot(df["timestamp"], df["S_夜鸣"], marker="s", label="S_夜鸣", color="#4e79a7")
    plt.plot(df["timestamp"], df["S_光污染"], marker="^", label="S_光污染", color="#e15759", linewidth=2)
    plt.title("光污染指示：晨鸣 / 夜鸣 / 融合")
    plt.xlabel("时间")
    plt.ylabel("得分")
    plt.ylim(0, 100)
    plt.legend()
    plt.xticks(rotation=30)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "light_pollution_trend.png", dpi=300)
    plt.close()


def main():
    plot_cmehi_trend()
    plot_component_bar()
    plot_component_area()
    plot_air_and_birds()
    plot_light_pollution_trend()
    print(f" 可视化图表已保存到：{FIG_DIR.resolve()}")


if __name__ == "__main__":
    main()
