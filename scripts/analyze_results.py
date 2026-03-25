"""Analyze benchmark results and generate summary statistics.

Loads results.jsonl from an experiment directory and produces:
  - Aggregate statistics (median/mean CD, F1, IoU, success rates)
  - summary.csv with per-entry breakdown
  - Comparison table against Text-to-CadQuery published baselines
  - Per-iteration convergence data (for refinement experiments)

Usage:
    python3 scripts/analyze_results.py results/<experiment_name>
    python3 scripts/analyze_results.py results/<experiment_name> --compare results/<other_experiment>
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# Text-to-CadQuery published baselines (from their paper)
BASELINES = {
    "Qwen2.5-3B-SFT (Text-to-CadQuery best)": {
        "cd_median": 0.191, "cd_mean": 10.229,
        "f1_median": 0.9836, "iou_median": 0.9868,
        "invalid_rate": 1.32,
    },
    "Mistral-7B-LoRA (Text-to-CadQuery)": {
        "cd_median": 0.218, "cd_mean": 12.753,
        "f1_median": 0.9749, "iou_median": 0.9680,
        "invalid_rate": 3.59,
    },
    "GPT-2 Large SFT (Text-to-CadQuery)": {
        "cd_median": 0.326, "cd_mean": 23.268,
        "f1_median": 0.8975, "iou_median": 0.8497,
        "invalid_rate": 5.69,
    },
    "Text2CAD Transformer (baseline)": {
        "cd_median": 0.370, "cd_mean": 26.417,
        "invalid_rate": 3.50,
    },
}


def load_results(results_dir: Path) -> pd.DataFrame:
    """Load results.jsonl into a DataFrame."""
    results_file = results_dir / "results.jsonl"
    if not results_file.exists():
        print(f"ERROR: {results_file} not found")
        sys.exit(1)

    records = []
    with open(results_file) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not records:
        print("ERROR: No valid records found")
        sys.exit(1)

    # Flatten the records
    flat = []
    for r in records:
        row = {
            "uid": r["uid"],
            "input": r.get("input", "")[:100],
            "success": r.get("success", False),
            "execution_success": r.get("execution_success", False),
            "num_iterations": r.get("num_iterations", 0),
            "num_llm_calls": r.get("num_llm_calls", 0),
            "total_time_ms": r.get("total_time_ms", 0),
            "input_tokens": r.get("tokens", {}).get("input_tokens", 0),
            "output_tokens": r.get("tokens", {}).get("output_tokens", 0),
            "error": r.get("error"),
        }

        # Metrics
        metrics = r.get("metrics") or {}
        row["cd"] = metrics.get("chamfer_distance")
        row["f1"] = metrics.get("f1_score")
        row["iou"] = metrics.get("volumetric_iou")
        row["precision"] = metrics.get("precision")
        row["recall"] = metrics.get("recall")

        # Geometry
        geom = r.get("geometry") or {}
        row["volume"] = geom.get("volume")
        row["is_valid"] = geom.get("is_valid")

        flat.append(row)

    return pd.DataFrame(flat)


def print_summary(df: pd.DataFrame, name: str):
    """Print aggregate statistics."""
    total = len(df)
    exec_ok = df["execution_success"].sum()
    converged = df["success"].sum()

    print(f"\n{'='*70}")
    print(f"  EXPERIMENT: {name}")
    print(f"{'='*70}")
    print(f"  Total entries:       {total}")
    print(f"  Execution success:   {exec_ok}/{total} ({exec_ok/total*100:.1f}%)")
    print(f"  Converged:           {converged}/{total} ({converged/total*100:.1f}%)")

    # Invalid rate (= 1 - execution success rate)
    invalid_rate = (1 - exec_ok / total) * 100 if total > 0 else 0
    print(f"  Invalid rate (IR):   {invalid_rate:.2f}%")

    # Metrics (only for entries with valid STLs)
    valid = df.dropna(subset=["cd"])
    if len(valid) > 0:
        print(f"\n  Metrics (n={len(valid)} with valid STLs):")
        print(f"    CD  — median: {valid['cd'].median():.4f}, "
              f"mean: {valid['cd'].mean():.4f}")
        print(f"    F1  — median: {valid['f1'].median():.4f}, "
              f"mean: {valid['f1'].mean():.4f}")
        print(f"    IoU — median: {valid['iou'].median():.4f}, "
              f"mean: {valid['iou'].mean():.4f}")

    # Token / cost stats
    total_in = df["input_tokens"].sum()
    total_out = df["output_tokens"].sum()
    cost_in = total_in / 1_000_000 * 3
    cost_out = total_out / 1_000_000 * 15
    total_cost = cost_in + cost_out
    per_entry_cost = total_cost / total if total > 0 else 0

    print(f"\n  Tokens: {total_in:,} in / {total_out:,} out")
    print(f"  Est. cost: ${total_cost:.2f} total, ${per_entry_cost:.4f}/entry")
    print(f"  Avg LLM calls/entry: {df['num_llm_calls'].mean():.1f}")
    print(f"  Avg time/entry: {df['total_time_ms'].mean()/1000:.1f}s")

    return valid


def print_comparison_table(df: pd.DataFrame, name: str):
    """Print a comparison table against Text-to-CadQuery baselines."""
    valid = df.dropna(subset=["cd"])
    if len(valid) == 0:
        print("\n  No valid metrics to compare.")
        return

    total = len(df)
    exec_ok = df["execution_success"].sum()
    invalid_rate = (1 - exec_ok / total) * 100 if total > 0 else 0

    print(f"\n{'='*70}")
    print(f"  COMPARISON TABLE (Table 2)")
    print(f"{'='*70}")
    print(f"  {'Model':<45} {'CD Med↓':>8} {'CD Mean↓':>9} "
          f"{'F1 Med↑':>8} {'IoU Med↑':>9} {'IR↓':>6}")
    print(f"  {'-'*45} {'-'*8} {'-'*9} {'-'*8} {'-'*9} {'-'*6}")

    # Baselines
    for baseline_name, b in BASELINES.items():
        f1_str = f"{b['f1_median']:.4f}" if 'f1_median' in b else "—"
        iou_str = f"{b['iou_median']:.4f}" if 'iou_median' in b else "—"
        print(f"  {baseline_name:<45} {b['cd_median']:>8.3f} {b['cd_mean']:>9.3f} "
              f"{f1_str:>8} {iou_str:>9} {b['invalid_rate']:>5.2f}%")

    # Our results
    print(f"  {name:<45} {valid['cd'].median():>8.4f} {valid['cd'].mean():>9.4f} "
          f"{valid['f1'].median():>8.4f} {valid['iou'].median():>9.4f} "
          f"{invalid_rate:>5.2f}%")


def print_convergence_analysis(results_dir: Path):
    """Analyze per-iteration improvement (for refinement experiments)."""
    results_file = results_dir / "results.jsonl"
    records = []
    with open(results_file) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Group by iteration
    iter_stats = {}
    for r in records:
        per_iter = r.get("per_iteration", [])
        for it in per_iter:
            i = it["iteration"]
            if i not in iter_stats:
                iter_stats[i] = {"passed": 0, "total": 0, "exec_success": 0}
            iter_stats[i]["total"] += 1
            if it.get("passed"):
                iter_stats[i]["passed"] += 1
            if it.get("execution_success"):
                iter_stats[i]["exec_success"] += 1

    if not iter_stats:
        return

    print(f"\n{'='*70}")
    print(f"  CONVERGENCE ANALYSIS")
    print(f"{'='*70}")
    print(f"  {'Iteration':>10} {'Exec OK':>10} {'Passed':>10} {'Cumulative':>12}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*12}")

    cumulative_passed = 0
    total_entries = max(s["total"] for s in iter_stats.values())
    for i in sorted(iter_stats.keys()):
        s = iter_stats[i]
        cumulative_passed += s["passed"]
        pct = cumulative_passed / total_entries * 100 if total_entries > 0 else 0
        print(f"  {f'y{i}':>10} {s['exec_success']:>10} "
              f"{s['passed']:>10} {pct:>11.1f}%")


def save_summary_csv(df: pd.DataFrame, output_path: Path):
    """Save per-entry results as CSV for data analysis."""
    cols = ["uid", "execution_success", "success", "num_iterations",
            "num_llm_calls", "total_time_ms", "input_tokens", "output_tokens",
            "cd", "f1", "iou", "precision", "recall", "volume", "is_valid", "error"]
    out_cols = [c for c in cols if c in df.columns]
    df[out_cols].to_csv(output_path, index=False)
    print(f"\n  Summary CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze AutoFab benchmark results")
    parser.add_argument("experiment_dir", type=str,
                        help="Path to experiment results directory")
    parser.add_argument("--compare", type=str, default=None,
                        help="Optional second experiment to compare against")
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    name = experiment_dir.name

    # Load config
    config_file = experiment_dir / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        print(f"Config: mode={config.get('mode')}, "
              f"max_iter={config.get('max_iterations')}, "
              f"model={config.get('model')}")

    # Load and analyze
    df = load_results(experiment_dir)
    valid = print_summary(df, name)

    # Comparison table
    print_comparison_table(df, f"AutoFab ({name})")

    # Convergence analysis (if refinement mode)
    config = json.load(open(config_file)) if config_file.exists() else {}
    if config.get("mode") == "refinement":
        print_convergence_analysis(experiment_dir)

    # Save CSV
    csv_path = experiment_dir / "summary.csv"
    save_summary_csv(df, csv_path)

    # Compare with another experiment if specified
    if args.compare:
        compare_dir = Path(args.compare)
        df2 = load_results(compare_dir)
        print_summary(df2, compare_dir.name)
        print_comparison_table(df2, f"AutoFab ({compare_dir.name})")


if __name__ == "__main__":
    main()
