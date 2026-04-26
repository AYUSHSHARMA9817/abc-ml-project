#!/usr/bin/env python3
"""
Aggregate all benchmark results from result.csv and produce a single summary
PNG showing how key metrics change across modes.

Usage:
    python3 plot_aggregate.py                  # uses defaults
    python3 plot_aggregate.py --csv result.csv --output summary.png
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_MODES = [0, 1, 2, 3]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark results across modes into a single summary plot."
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        default=Path(__file__).with_name("result.csv"),
        help="Path to the CSV file. Default: scripts/result.csv",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        type=int,
        default=DEFAULT_MODES,
        help="Modes to include. Default: 0 1 2 3",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("plots") / "aggregate_summary.png",
        help="Output image path. Default: scripts/plots/aggregate_summary.png",
    )
    return parser.parse_args()


def read_rows(csv_path: Path):
    with csv_path.open(newline="") as f:
        return list(csv.DictReader(f))


def to_float(row, field):
    value = (row.get(field) or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def collect_stats(rows, modes):
    """
    For each mode, collect lists of values across all benchmarks that have data.
    Returns a dict: mode -> {field: [values]}
    """
    # Group rows by (benchmark, mode)
    by_bench_mode = {}
    for row in rows:
        bench = (row.get("benchmark") or "").strip()
        mode_val = to_float(row, "mode")
        if not bench or mode_val is None:
            continue
        mode = int(mode_val)
        if mode not in modes:
            continue
        by_bench_mode[(bench, mode)] = row

    # Find benchmarks that have data (non-empty qor) for at least mode 0
    all_benchmarks = set()
    for (bench, mode), row in by_bench_mode.items():
        if to_float(row, "qor") is not None:
            all_benchmarks.add(bench)

    # Only keep benchmarks that have mode 0 data (baseline)
    valid_benchmarks = set()
    for bench in all_benchmarks:
        if (bench, 0) in by_bench_mode and to_float(by_bench_mode[(bench, 0)], "qor") is not None:
            valid_benchmarks.add(bench)

    fields = [
        "qor", "cuts_used", "candidate_cuts", "cpu_time", "post_ml_time",
        "qor_delta_vs_baseline", "candidate_cuts_delta_vs_baseline",
        "candidate_cuts_ratio_vs_baseline", "cpu_time_ratio_vs_baseline",
        "post_ml_time_ratio_vs_baseline",
    ]

    stats = {mode: {f: [] for f in fields} for mode in modes}
    # Also track win/loss/neutral for QoR
    qor_counts = {mode: {"win": 0, "loss": 0, "neutral": 0} for mode in modes}

    for bench in sorted(valid_benchmarks):
        baseline_row = by_bench_mode.get((bench, 0))
        baseline_qor = to_float(baseline_row, "qor") if baseline_row else None
        baseline_cuts = to_float(baseline_row, "candidate_cuts") if baseline_row else None

        for mode in modes:
            row = by_bench_mode.get((bench, mode))
            if not row:
                continue

            for field in fields:
                val = to_float(row, field)
                if val is not None:
                    stats[mode][field].append(val)

            # Compute ratio ourselves for consistency (in case CSV has gaps)
            mode_cuts = to_float(row, "candidate_cuts")
            if baseline_cuts and baseline_cuts > 0 and mode_cuts is not None:
                if "candidate_cuts_ratio_computed" not in stats[mode]:
                    stats[mode]["candidate_cuts_ratio_computed"] = []
                stats[mode]["candidate_cuts_ratio_computed"].append(
                    mode_cuts / baseline_cuts
                )

            # QoR win/loss
            if mode != 0 and baseline_qor is not None:
                mode_qor = to_float(row, "qor")
                if mode_qor is not None:
                    delta = mode_qor - baseline_qor
                    if delta < -0.001:
                        qor_counts[mode]["win"] += 1  # lower QoR (area) is better
                    elif delta > 0.001:
                        qor_counts[mode]["loss"] += 1
                    else:
                        qor_counts[mode]["neutral"] += 1

    return stats, qor_counts, len(valid_benchmarks)


def safe_mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def main():
    args = parse_args()
    rows = read_rows(args.csv_path)
    modes = args.modes
    stats, qor_counts, n_benchmarks = collect_stats(rows, modes)

    print(f"CSV: {args.csv_path}")
    print(f"Valid benchmarks (with mode-0 data): {n_benchmarks}")
    print(f"Modes: {modes}")
    print()

    # ── Compute per-mode aggregates ──────────────────────────────────
    avg_qor = [safe_mean(stats[m]["qor"]) for m in modes]
    avg_cuts_used = [safe_mean(stats[m]["cuts_used"]) for m in modes]
    avg_candidate_cuts = [safe_mean(stats[m]["candidate_cuts"]) for m in modes]
    avg_candidate_ratio = [safe_mean(stats[m]["candidate_cuts_ratio_vs_baseline"]) for m in modes]
    avg_qor_delta = [safe_mean(stats[m]["qor_delta_vs_baseline"]) for m in modes]
    avg_cuts_delta = [safe_mean(stats[m]["candidate_cuts_delta_vs_baseline"]) for m in modes]
    avg_cpu_time = [safe_mean(stats[m]["cpu_time"]) for m in modes]
    avg_cpu_ratio = [safe_mean(stats[m]["cpu_time_ratio_vs_baseline"]) for m in modes]
    avg_post_ml_time = [safe_mean(stats[m]["post_ml_time"]) for m in modes]
    avg_post_ml_ratio = [safe_mean(stats[m]["post_ml_time_ratio_vs_baseline"]) for m in modes]

    # Candidate cuts reduction % vs mode 0
    avg_reduction_pct = []
    for m in modes:
        ratio = safe_mean(stats[m].get("candidate_cuts_ratio_computed", []))
        if ratio is not None:
            avg_reduction_pct.append((1.0 - ratio) * 100.0)
        else:
            avg_reduction_pct.append(None)

    # Print summary table
    print(f"{'Mode':<6} {'Avg QoR':>10} {'Avg Cuts Used':>14} {'Avg Cand. Cuts':>15} "
          f"{'Avg Cand Ratio':>15} {'Avg Cut Reduc%':>15} {'Avg CPU':>10} {'Avg CPU Ratio':>15} {'Avg P.ML':>10} {'Avg P.ML Ratio':>15} {'QoR Wins':>9} {'QoR Losses':>11} {'Neutral':>8}")
    print("-" * 165)
    for i, m in enumerate(modes):
        qor_str = f"{avg_qor[i]:.2f}" if avg_qor[i] is not None else "N/A"
        cu_str = f"{avg_cuts_used[i]:.1f}" if avg_cuts_used[i] is not None else "N/A"
        cc_str = f"{avg_candidate_cuts[i]:.1f}" if avg_candidate_cuts[i] is not None else "N/A"
        ratio_str = f"{avg_candidate_ratio[i]:.4f}" if avg_candidate_ratio[i] is not None else "N/A"
        reduc_str = f"{avg_reduction_pct[i]:.2f}%" if avg_reduction_pct[i] is not None else "N/A"
        cpu_str = f"{avg_cpu_time[i]:.2f}" if avg_cpu_time[i] is not None else "N/A"
        cratio_str = f"{avg_cpu_ratio[i]:.4f}" if avg_cpu_ratio[i] is not None else "N/A"
        pml_str = f"{avg_post_ml_time[i]:.2f}" if avg_post_ml_time[i] is not None else "N/A"
        pmlr_str = f"{avg_post_ml_ratio[i]:.4f}" if avg_post_ml_ratio[i] is not None else "N/A"
        w = qor_counts[m]["win"]
        l = qor_counts[m]["loss"]
        n = qor_counts[m]["neutral"]
        print(f"{m:<6} {qor_str:>10} {cu_str:>14} {cc_str:>15} {ratio_str:>15} {reduc_str:>15} {cpu_str:>10} {cratio_str:>15} {pml_str:>10} {pmlr_str:>15} {w:>9} {l:>11} {n:>8}")

    # ── Build the plot ───────────────────────────────────────────────
    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    fig.suptitle(
        f"Aggregate Results Across {n_benchmarks} Benchmarks\n(modes {modes})",
        fontsize=15, fontweight="bold", y=0.98,
    )

    bar_color = "#4C72B0"
    line_color = "#DD8452"

    def plot_bars(ax, values, title, ylabel, fmt=".1f", color=bar_color):
        x = np.arange(len(modes))
        valid_vals = [v if v is not None else 0 for v in values]
        bars = ax.bar(x, valid_vals, color=color, alpha=0.85, width=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([f"Mode {m}" for m in modes])
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        for bar, val in zip(bars, values):
            if val is not None:
                ax.annotate(
                    f"{val:{fmt}}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=9, fontweight="bold",
                )

    # 1) Average QoR (total mapped area) per mode
    plot_bars(axes[0, 0], avg_qor, "Average QoR (Mapped Area)", "Area")

    # 2) Average candidate cuts per mode
    plot_bars(axes[0, 1], avg_candidate_cuts, "Average Candidate Cuts", "Cuts")

    # 3) Average candidate cuts ratio vs baseline
    plot_bars(axes[0, 2], avg_candidate_ratio, "Avg Candidate Cuts Ratio vs Mode 0",
              "Ratio", fmt=".4f", color="#55A868")

    # 4) Average candidate cuts reduction %
    plot_bars(axes[1, 0], avg_reduction_pct, "Avg Candidate Cuts Reduction %",
              "Reduction %", fmt=".2f", color="#C44E52")

    # 5) Average QoR delta vs baseline
    plot_bars(axes[1, 1], avg_qor_delta, "Avg QoR Delta vs Mode 0",
              "QoR Δ", fmt=".3f", color="#8172B2")

    # 6) QoR Win/Loss/Neutral stacked bar
    ax = axes[1, 2]
    x = np.arange(len(modes))
    wins = [qor_counts[m]["win"] for m in modes]
    losses = [qor_counts[m]["loss"] for m in modes]
    neutrals = [qor_counts[m]["neutral"] for m in modes]
    w = 0.5
    ax.bar(x, wins, w, label="Wins (QoR ↓)", color="#55A868", alpha=0.85)
    ax.bar(x, losses, w, bottom=wins, label="Losses (QoR ↑)", color="#C44E52", alpha=0.85)
    bottoms = [wi + lo for wi, lo in zip(wins, losses)]
    ax.bar(x, neutrals, w, bottom=bottoms, label="Neutral", color="#CCCCCC", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Mode {m}" for m in modes])
    ax.set_title("QoR Win / Loss / Neutral vs Mode 0", fontsize=12, fontweight="bold")
    ax.set_ylabel("# Benchmarks")
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    # Annotate totals
    for i_x, m in enumerate(modes):
        total = wins[i_x] + losses[i_x] + neutrals[i_x]
        if total > 0:
            # label wins and losses
            if wins[i_x] > 0:
                ax.text(i_x, wins[i_x] / 2, str(wins[i_x]), ha="center", va="center", fontsize=9, fontweight="bold")
            if losses[i_x] > 0:
                ax.text(i_x, wins[i_x] + losses[i_x] / 2, str(losses[i_x]), ha="center", va="center", fontsize=9, fontweight="bold")

    # 7) Average CPU Time
    plot_bars(axes[2, 0], avg_cpu_time, "Average CPU Time", "CPU Time", color="#A8A8A8")

    # 8) Average CPU Time Ratio
    plot_bars(axes[2, 1], avg_cpu_ratio, "Average CPU Time Ratio vs Mode 0", "Ratio", fmt=".4f", color="#5E99D3")

    # 9) Average Post-ML Time Ratio
    plot_bars(axes[2, 2], avg_post_ml_ratio, "Average Post-ML Time Ratio vs Mode 0", "Ratio", fmt=".4f", color="#D9A84E")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160, bbox_inches="tight")
    plt.close(fig)

    print(f"\nWrote aggregate plot: {args.output}")


if __name__ == "__main__":
    main()
