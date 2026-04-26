#!/usr/bin/env python3

import argparse
import csv
import re
import sys
from pathlib import Path


RUN_RE = re.compile(
    r"^RUN benchmark=(?P<benchmark>\S+) g_mode=(?P<mode>\d+) file=(?P<file>.+)$"
)
RESULT_RE = re.compile(
    r"^RESULT g_mode=(?P<mode>\d+) qor=(?P<qor>[0-9]+(?:\.[0-9]+)?) cuts_used=(?P<cuts>\d+)(?: cpu_time=(?P<cpu_time>[0-9]+(?:\.[0-9]+)?))?(?: post_ml_time=(?P<post_ml_time>[0-9]+(?:\.[0-9]+)?))?"
)
CUT_STATS_RE = re.compile(
    r"^CUT_STATS g_mode=(?P<mode>\d+) candidate_cuts=(?P<candidate_cuts>\d+)$"
)


def parse_log(log_path: Path):
    current = None
    by_benchmark = {}

    for raw_line in log_path.read_text().splitlines():
        line = raw_line.strip()
        run_match = RUN_RE.match(line)
        if run_match:
            benchmark = run_match.group("benchmark")
            mode = int(run_match.group("mode"))
            current = (benchmark, mode)
            by_benchmark.setdefault(benchmark, {}).setdefault(
                mode,
                {"file": run_match.group("file")},
            )
            continue

        if current is None:
            continue

        benchmark, mode = current
        result_match = RESULT_RE.match(line)
        if result_match:
            result_mode = int(result_match.group("mode"))
            if result_mode != mode:
                continue
            cpu_time_str = result_match.group("cpu_time")
            post_ml_time_str = result_match.group("post_ml_time")
            by_benchmark[benchmark].setdefault(mode, {}).update(
                {
                    "qor": float(result_match.group("qor")),
                    "cuts_used": int(result_match.group("cuts")),
                    "cpu_time": float(cpu_time_str) if cpu_time_str is not None else None,
                    "post_ml_time": float(post_ml_time_str) if post_ml_time_str is not None else None,
                }
            )
            continue

        cut_stats_match = CUT_STATS_RE.match(line)
        if cut_stats_match:
            stats_mode = int(cut_stats_match.group("mode"))
            if stats_mode != mode:
                continue
            by_benchmark[benchmark].setdefault(mode, {}).update(
                {
                    "candidate_cuts": int(cut_stats_match.group("candidate_cuts")),
                }
            )

    return by_benchmark


def detect_modes(parsed):
    return sorted({mode for modes in parsed.values() for mode in modes})


def compute_delta(baseline_value, current_value):
    if baseline_value is None or current_value is None:
        return None
    return current_value - baseline_value


def compute_ratio(baseline_value, current_value):
    if baseline_value in (None, 0) or current_value is None:
        return None
    return current_value / baseline_value


def build_rows(parsed, baseline_mode, selected_modes):
    rows = []
    for benchmark in sorted(parsed):
        benchmark_modes = parsed[benchmark]
        baseline = benchmark_modes.get(baseline_mode, {})

        for mode in selected_modes:
            current = benchmark_modes.get(mode)
            if current is None:
                continue

            row = {
                "benchmark": benchmark,
                "file": current.get("file", baseline.get("file")),
                "mode": mode,
                "baseline_mode": baseline_mode,
                "qor": current.get("qor"),
                "cuts_used": current.get("cuts_used"),
                "candidate_cuts": current.get("candidate_cuts"),
                "cpu_time": current.get("cpu_time"),
                "post_ml_time": current.get("post_ml_time"),
                "qor_baseline": baseline.get("qor"),
                "cuts_used_baseline": baseline.get("cuts_used"),
                "candidate_cuts_baseline": baseline.get("candidate_cuts"),
                "cpu_time_baseline": baseline.get("cpu_time"),
                "post_ml_time_baseline": baseline.get("post_ml_time"),
                "qor_delta_vs_baseline": None,
                "cuts_used_delta_vs_baseline": None,
                "candidate_cuts_delta_vs_baseline": None,
                "candidate_cuts_ratio_vs_baseline": None,
                "cpu_time_delta_vs_baseline": None,
                "cpu_time_ratio_vs_baseline": None,
                "post_ml_time_delta_vs_baseline": None,
                "post_ml_time_ratio_vs_baseline": None,
            }

            if mode != baseline_mode and baseline:
                row["qor_delta_vs_baseline"] = compute_delta(
                    baseline.get("qor"), current.get("qor")
                )
                row["cuts_used_delta_vs_baseline"] = compute_delta(
                    baseline.get("cuts_used"), current.get("cuts_used")
                )
                row["candidate_cuts_delta_vs_baseline"] = compute_delta(
                    baseline.get("candidate_cuts"), current.get("candidate_cuts")
                )
                row["candidate_cuts_ratio_vs_baseline"] = compute_ratio(
                    baseline.get("candidate_cuts"), current.get("candidate_cuts")
                )
                row["cpu_time_delta_vs_baseline"] = compute_delta(
                    baseline.get("cpu_time"), current.get("cpu_time")
                )
                row["cpu_time_ratio_vs_baseline"] = compute_ratio(
                    baseline.get("cpu_time"), current.get("cpu_time")
                )
                row["post_ml_time_delta_vs_baseline"] = compute_delta(
                    baseline.get("post_ml_time"), current.get("post_ml_time")
                )
                row["post_ml_time_ratio_vs_baseline"] = compute_ratio(
                    baseline.get("post_ml_time"), current.get("post_ml_time")
                )

            rows.append(row)

    return rows


def write_csv(rows, output_path: Path):
    fieldnames = [
        "benchmark",
        "file",
        "mode",
        "baseline_mode",
        "qor",
        "cuts_used",
        "candidate_cuts",
        "cpu_time",
        "post_ml_time",
        "qor_baseline",
        "cuts_used_baseline",
        "candidate_cuts_baseline",
        "cpu_time_baseline",
        "post_ml_time_baseline",
        "qor_delta_vs_baseline",
        "cuts_used_delta_vs_baseline",
        "candidate_cuts_delta_vs_baseline",
        "candidate_cuts_ratio_vs_baseline",
        "cpu_time_delta_vs_baseline",
        "cpu_time_ratio_vs_baseline",
        "post_ml_time_delta_vs_baseline",
        "post_ml_time_ratio_vs_baseline",
    ]
    with output_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_float(value):
    if value is None:
        return ""
    return f"{value:.2f}"


def render_ratio(value):
    if value is None:
        return ""
    return f"{value:.3f}"


def print_table(rows, baseline_mode):
    headers = [
        "benchmark",
        "mode",
        "qor",
        "cuts_used",
        "candidate_cuts",
        "cpu_time",
        "post_ml_time",
        f"delta_qor_vs_g{baseline_mode}",
        f"delta_cuts_vs_g{baseline_mode}",
        f"delta_candidates_vs_g{baseline_mode}",
        f"candidate_ratio_vs_g{baseline_mode}",
        f"delta_cpu_vs_g{baseline_mode}",
        f"cpu_ratio_vs_g{baseline_mode}",
        f"delta_post_ml_vs_g{baseline_mode}",
        f"post_ml_ratio_vs_g{baseline_mode}",
    ]
    widths = {header: len(header) for header in headers}

    rendered_rows = []
    for row in rows:
        rendered = {
            "benchmark": row["benchmark"],
            "mode": str(row["mode"]),
            "qor": render_float(row["qor"]),
            "cuts_used": "" if row["cuts_used"] is None else str(row["cuts_used"]),
            "candidate_cuts": ""
            if row["candidate_cuts"] is None
            else str(row["candidate_cuts"]),
            f"delta_qor_vs_g{baseline_mode}": render_float(
                row["qor_delta_vs_baseline"]
            ),
            f"delta_cuts_vs_g{baseline_mode}": ""
            if row["cuts_used_delta_vs_baseline"] is None
            else str(row["cuts_used_delta_vs_baseline"]),
            f"delta_candidates_vs_g{baseline_mode}": ""
            if row["candidate_cuts_delta_vs_baseline"] is None
            else str(row["candidate_cuts_delta_vs_baseline"]),
            f"candidate_ratio_vs_g{baseline_mode}": render_ratio(
                row["candidate_cuts_ratio_vs_baseline"]
            ),
            "cpu_time": render_float(row["cpu_time"]),
            "post_ml_time": render_float(row["post_ml_time"]),
            f"delta_cpu_vs_g{baseline_mode}": render_float(
                row["cpu_time_delta_vs_baseline"]
            ),
            f"cpu_ratio_vs_g{baseline_mode}": render_ratio(
                row["cpu_time_ratio_vs_baseline"]
            ),
            f"delta_post_ml_vs_g{baseline_mode}": render_float(
                row["post_ml_time_delta_vs_baseline"]
            ),
            f"post_ml_ratio_vs_g{baseline_mode}": render_ratio(
                row["post_ml_time_ratio_vs_baseline"]
            ),
        }
        rendered_rows.append(rendered)
        for key, value in rendered.items():
            widths[key] = max(widths[key], len(value))

    header_line = "  ".join(header.ljust(widths[header]) for header in headers)
    print(header_line)
    print("  ".join("-" * widths[header] for header in headers))
    for row in rendered_rows:
        print("  ".join(row[header].ljust(widths[header]) for header in headers))


def print_summary(rows, baseline_mode):
    print()
    print(f"Summary vs g{baseline_mode}")
    summary = {}
    for row in rows:
        mode = row["mode"]
        if mode == baseline_mode:
            continue
        summary.setdefault(
            mode,
            {
                "benchmarks": 0,
                "wins": 0,
                "losses": 0,
                "neutral": 0,
                "candidate_ratios": [],
                "cpu_ratios": [],
                "post_ml_ratios": [],
            },
        )
        item = summary[mode]
        item["benchmarks"] += 1

        delta_qor = row["qor_delta_vs_baseline"]
        if delta_qor is not None:
            if delta_qor < 0:
                item["wins"] += 1
            elif delta_qor > 0:
                item["losses"] += 1
            else:
                item["neutral"] += 1

        ratio = row["candidate_cuts_ratio_vs_baseline"]
        if ratio is not None:
            item["candidate_ratios"].append(ratio)
            
        cpu_ratio = row["cpu_time_ratio_vs_baseline"]
        if cpu_ratio is not None:
            item["cpu_ratios"].append(cpu_ratio)
            
        post_ml_ratio = row["post_ml_time_ratio_vs_baseline"]
        if post_ml_ratio is not None:
            item["post_ml_ratios"].append(post_ml_ratio)

    if not summary:
        print("No comparison modes found.")
        return

    for mode in sorted(summary):
        item = summary[mode]
        avg_ratio = None
        avg_reduction = None
        if item["candidate_ratios"]:
            avg_ratio = sum(item["candidate_ratios"]) / len(item["candidate_ratios"])
            avg_reduction = (1.0 - avg_ratio) * 100.0

        ratio_text = "" if avg_ratio is None else f"{avg_ratio:.3f}"
        reduction_text = "" if avg_reduction is None else f"{avg_reduction:.2f}%"
        
        avg_cpu_ratio = None
        if item["cpu_ratios"]:
            avg_cpu_ratio = sum(item["cpu_ratios"]) / len(item["cpu_ratios"])
        cpu_ratio_text = "" if avg_cpu_ratio is None else f"{avg_cpu_ratio:.3f}"
        
        avg_post_ml_ratio = None
        if item["post_ml_ratios"]:
            avg_post_ml_ratio = sum(item["post_ml_ratios"]) / len(item["post_ml_ratios"])
        post_ml_ratio_text = "" if avg_post_ml_ratio is None else f"{avg_post_ml_ratio:.3f}"
        
        print(
            f"g{mode}: benchmarks={item['benchmarks']} "
            f"wins={item['wins']} losses={item['losses']} neutral={item['neutral']} "
            f"avg_candidate_ratio={ratio_text} avg_candidate_reduction={reduction_text} "
            f"avg_cpu_ratio={cpu_ratio_text} avg_post_ml_ratio={post_ml_ratio_text}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Parse ABC mapping results with candidate cut statistics."
    )
    parser.add_argument(
        "log_file", type=Path, help="Log file produced by scripts/run_blif_tests.sh"
    )
    parser.add_argument(
        "-b",
        "--baseline",
        type=int,
        default=0,
        help="Baseline mode used for delta columns. Default: 0",
    )
    parser.add_argument(
        "-m",
        "--modes",
        type=int,
        nargs="*",
        help="Optional list of modes to include. Default: all modes found in the log",
    )
    parser.add_argument("-o", "--output", type=Path, help="Optional CSV output path")
    args = parser.parse_args()

    if not args.log_file.is_file():
        print(f"Missing log file: {args.log_file}", file=sys.stderr)
        return 1

    parsed = parse_log(args.log_file)
    detected_modes = detect_modes(parsed)
    if not detected_modes:
        print(f"No RUN/RESULT blocks found in {args.log_file}", file=sys.stderr)
        return 1

    selected_modes = detected_modes if args.modes is None else sorted(set(args.modes))
    rows = build_rows(parsed, args.baseline, selected_modes)
    print_table(rows, args.baseline)
    print_summary(rows, args.baseline)

    if args.output is not None:
        write_csv(rows, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
