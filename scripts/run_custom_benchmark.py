"""Benchmark runner: AutoFab on the custom engineering dataset.

Runs the full pipeline (Planner → Coder → Executor → Validator → Refiner)
on our T1-T3 benchmark (dataset v2) and computes CD/F1/IoU against
reference STLs generated from the hand-verified reference CadQuery code.

Usage:
    conda activate cadquery
    cd ~/Desktop/AutoFab

    # Validation run (2 per tier)
    python3 scripts/run_custom_benchmark.py --experiment-name custom_validation --limit-per-tier 2

    # Single tier
    python3 scripts/run_custom_benchmark.py --experiment-name custom_t1 --tiers T1

    # Full run with refinement
    python3 scripts/run_custom_benchmark.py --experiment-name custom_full --max-iterations 3

    # Single-shot (no refinement) for baseline
    python3 scripts/run_custom_benchmark.py --experiment-name custom_singleshot --mode single-shot
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autofab.pipeline import Pipeline
from autofab.executor import Executor
from autofab.metrics import compare_stl
from autofab import agents

DATA_DIR = PROJECT_ROOT / "data" / "dataset_v2"
RESULTS_BASE_DIR = PROJECT_ROOT / "results"

TIER_FILES = {
    "T1": "t1_primitives.jsonl",
    "T2": "t2_engineering_parts.jsonl",
    "T3": "t3_complex_parts.jsonl",
}


def load_entries(tiers: list[str], limit_per_tier: int = 0) -> list[dict]:
    """Load benchmark entries from custom test JSONL files."""
    entries = []
    for tier in tiers:
        filename = TIER_FILES.get(tier)
        if not filename:
            print(f"WARNING: Unknown tier {tier}, skipping")
            continue
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"WARNING: {filepath} not found, skipping")
            continue

        tier_entries = []
        with open(filepath) as f:
            for line in f:
                entry = json.loads(line)
                tier_entries.append(entry)

        if limit_per_tier > 0:
            tier_entries = tier_entries[:limit_per_tier]

        entries.extend(tier_entries)
        print(f"  {tier}: {len(tier_entries)} entries loaded")

    return entries


def generate_reference_stl(reference_code: str, entry_id: str, output_dir: Path) -> str:
    """Execute reference code and return path to the generated STL."""
    ref_stl_dir = output_dir / "reference_stls"
    ref_stl_dir.mkdir(parents=True, exist_ok=True)

    ref_stl_path = ref_stl_dir / f"{entry_id}.stl"
    if ref_stl_path.exists():
        return str(ref_stl_path)

    executor = Executor(output_dir=str(ref_stl_dir), timeout_seconds=60)
    result = executor.execute(reference_code, name=entry_id)

    if not result.success:
        raise RuntimeError(f"Reference code failed for {entry_id}: {result.error}")

    # The executor exports to ref_stl_dir/{entry_id}.stl
    if not ref_stl_path.exists():
        raise RuntimeError(f"Reference STL not created at {ref_stl_path}")

    return str(ref_stl_path)


def run_single_entry(
    entry: dict,
    output_dir: Path,
    mode: str,
    max_iterations: int,
    max_error_retries: int,
    verbose: bool,
    use_vision: bool = True,
) -> dict:
    """Run the full pipeline on a single custom benchmark entry."""
    entry_id = entry["id"]
    tier = entry["tier"]
    prompt = entry["prompt"]
    reference_code = entry["reference_code"]

    agents.reset_token_usage()
    start_time = time.time()

    # Generate reference STL from reference code
    try:
        ref_stl_path = generate_reference_stl(reference_code, entry_id, output_dir)
    except Exception as e:
        return {
            "id": entry_id, "tier": tier, "prompt": prompt,
            "success": False, "execution_success": False,
            "error": f"Reference STL generation failed: {e}",
        }

    # Set up per-entry output directory
    entry_output_dir = output_dir / "generated_stls"
    entry_output_dir.mkdir(parents=True, exist_ok=True)

    # Configure pipeline
    max_refine = 0 if mode == "single-shot" else max_iterations
    pipeline = Pipeline(
        output_dir=str(entry_output_dir),
        max_error_retries=max_error_retries,
        max_refinement_iterations=max_refine,
        verbose=verbose,
        use_vision=use_vision,
    )

    # Run full pipeline (with Planner)
    try:
        result = pipeline.run(prompt, name=entry_id)
    except Exception as e:
        tokens = agents.get_token_usage()
        return {
            "id": entry_id, "tier": tier, "prompt": prompt,
            "success": False, "execution_success": False,
            "error": str(e), "tokens": tokens,
        }

    tokens = agents.get_token_usage()

    # Build result record
    record = {
        "id": entry_id,
        "tier": tier,
        "prompt": prompt,
        "success": result.converged,
        "execution_success": result.final_geometry is not None,
        "num_iterations": len(result.iterations),
        "num_llm_calls": result.total_llm_calls,
        "total_time_ms": result.total_time_ms,
        "tokens": tokens,
        "geometry": result.final_geometry,
        "converged": result.converged,
        "error": None,
    }

    # Compute CD/F1/IoU against reference STL
    gen_stl = result.final_stl_path
    if gen_stl and Path(gen_stl).exists():
        try:
            metrics = compare_stl(gen_stl, ref_stl_path, normalize=False)
            record["metrics"] = metrics.to_dict()
        except Exception as e:
            record["metrics"] = None
            record["error"] = f"Metrics computation failed: {e}"
    else:
        record["metrics"] = None
        if not record.get("error"):
            record["error"] = "No STL generated"

    # Per-iteration data (for convergence curves)
    per_iter = []
    for it in result.iterations:
        iter_entry = {
            "iteration": it.iteration,
            "type": it.iteration_type,
            "passed": it.passed,
            "execution_success": it.execution is not None and it.execution.get("success", False),
            "code": it.code,
            "error_retries": it.error_retries,
            "feedback_sent": it.feedback_sent,
            "refiner_input": it.refiner_input,
            "refiner_output": it.refiner_output,
        }
        # Compute per-iteration metrics if STL was generated
        iter_stl = entry_output_dir / f"{entry_id}_iter{it.iteration}.stl"
        if iter_stl.exists():
            try:
                iter_metrics = compare_stl(str(iter_stl), ref_stl_path, normalize=False)
                iter_entry["metrics"] = iter_metrics.to_dict()
            except Exception:
                iter_entry["metrics"] = None
        if it.validation:
            iter_entry["validation"] = it.validation
        per_iter.append(iter_entry)
    record["per_iteration"] = per_iter

    return record


def main():
    parser = argparse.ArgumentParser(description="Run AutoFab custom benchmark")
    parser.add_argument("--experiment-name", type=str, required=True,
                        help="Name for this experiment run")
    parser.add_argument("--tiers", type=str, nargs="+", default=["T1", "T2", "T3"],
                        help="Which tiers to run (default: all)")
    parser.add_argument("--mode", type=str, choices=["single-shot", "refinement"],
                        default="refinement",
                        help="single-shot (no refinement) or refinement (default)")
    parser.add_argument("--max-iterations", type=int, default=5,
                        help="Max refinement iterations")
    parser.add_argument("--max-error-retries", type=int, default=3,
                        help="Max error-fix attempts per iteration")
    parser.add_argument("--limit-per-tier", type=int, default=0,
                        help="Max entries per tier (0 = all)")
    parser.add_argument("--ids", type=str, nargs="+", default=None,
                        help="Run only specific entry IDs (e.g., --ids T1_012 T1_014)")
    parser.add_argument("--no-vision", action="store_true",
                        help="Disable vision (rendered image) for the Judge — ablation mode")
    parser.add_argument("--verbose", action="store_true",
                        help="Print detailed pipeline output")
    args = parser.parse_args()

    # Set up output directory
    experiment_dir = RESULTS_BASE_DIR / args.experiment_name
    experiment_dir.mkdir(parents=True, exist_ok=True)

    results_file = experiment_dir / "results.jsonl"
    config_file = experiment_dir / "config.json"

    config = {
        "experiment_name": args.experiment_name,
        "dataset": "dataset_v2",
        "tiers": args.tiers,
        "mode": args.mode,
        "max_iterations": args.max_iterations if args.mode == "refinement" else 0,
        "max_error_retries": args.max_error_retries,
        "limit_per_tier": args.limit_per_tier,
        "model": "claude-sonnet",
        "pipeline": "full" if args.mode == "refinement" else "single-shot",
        "rag_config": "kb1+kb2",
        "vision": not args.no_vision,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    # Load entries
    print(f"Loading custom benchmark entries...")
    entries = load_entries(args.tiers, limit_per_tier=args.limit_per_tier)

    # Filter to specific IDs if requested
    if args.ids:
        id_set = set(args.ids)
        entries = [e for e in entries if e["id"] in id_set]
        print(f"Filtered to {len(entries)} entries: {args.ids}")

    print(f"Total: {len(entries)} entries")

    # Resume support — when using --ids, remove those IDs from completed set
    # so they will re-run even if previously completed
    completed_ids = set()
    if results_file.exists():
        with open(results_file) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    completed_ids.add(r["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    if args.ids:
        # Remove targeted IDs from completed set so they re-run
        completed_ids -= set(args.ids)
    remaining = [e for e in entries if e["id"] not in completed_ids]
    print(f"Already completed: {len(completed_ids)}, remaining: {len(remaining)}")

    if not remaining:
        print("All entries completed.")
        return

    # Run
    start_time = time.time()
    total_done = 0
    exec_ok = 0
    converged = 0
    cd_vals, f1_vals, iou_vals = [], [], []

    # Per-tier tracking
    tier_stats = {}

    for i, entry in enumerate(remaining):
        tier = entry["tier"]
        print(f"\n[{total_done + len(completed_ids) + 1}/{len(entries)}] "
              f"{entry['id']} ({tier}): {entry['prompt'][:60]}...", flush=True)

        record = run_single_entry(
            entry=entry,
            output_dir=experiment_dir,
            mode=args.mode,
            max_iterations=args.max_iterations,
            max_error_retries=args.max_error_retries,
            verbose=args.verbose,
            use_vision=not args.no_vision,
        )

        # Append result
        with open(results_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        total_done += 1
        if record.get("execution_success"):
            exec_ok += 1
        if record.get("converged"):
            converged += 1

        # Track metrics
        if record.get("metrics"):
            m = record["metrics"]
            if m.get("chamfer_distance") is not None:
                cd_vals.append(m["chamfer_distance"])
            if m.get("f1_score") is not None:
                f1_vals.append(m["f1_score"])
            if m.get("volumetric_iou") is not None:
                iou_vals.append(m["volumetric_iou"])

        # Per-tier stats
        if tier not in tier_stats:
            tier_stats[tier] = {"total": 0, "exec_ok": 0, "converged": 0,
                                "cd": [], "f1": [], "iou": []}
        ts = tier_stats[tier]
        ts["total"] += 1
        if record.get("execution_success"):
            ts["exec_ok"] += 1
        if record.get("converged"):
            ts["converged"] += 1
        if record.get("metrics"):
            m = record["metrics"]
            if m.get("chamfer_distance") is not None:
                ts["cd"].append(m["chamfer_distance"])
                ts["f1"].append(m["f1_score"])
                ts["iou"].append(m["volumetric_iou"])

        # Print per-entry status
        tokens = record.get("tokens", {})
        elapsed = time.time() - start_time
        print(f"  exec={record.get('execution_success')}, "
              f"converged={record.get('converged')}, "
              f"iters={record.get('num_iterations')}, "
              f"calls={record.get('num_llm_calls')}, "
              f"time={record.get('total_time_ms', 0)/1000:.1f}s")
        if record.get("metrics"):
            m = record["metrics"]
            print(f"  CD={m['chamfer_distance']:.4f}, "
                  f"F1={m['f1_score']:.4f}, "
                  f"IoU={m['volumetric_iou']:.4f}")
        elif record.get("error"):
            print(f"  ERROR: {record['error'][:120]}")

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"EXPERIMENT COMPLETE: {args.experiment_name}")
    print(f"{'='*70}")
    print(f"Mode: {args.mode}, max_iterations: {args.max_iterations}")
    print(f"Total: {total_done}, Exec OK: {exec_ok}/{total_done} "
          f"({exec_ok/total_done*100:.1f}%), "
          f"Converged: {converged}/{total_done} ({converged/total_done*100:.1f}%)")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")

    tokens_total = sum(r.get("tokens", {}).get("input_tokens", 0) for r in [])  # from file
    # Re-read for token totals
    total_in, total_out = 0, 0
    with open(results_file) as f:
        for line in f:
            r = json.loads(line)
            t = r.get("tokens", {})
            total_in += t.get("input_tokens", 0)
            total_out += t.get("output_tokens", 0)
    cost_in = total_in / 1_000_000 * 3
    cost_out = total_out / 1_000_000 * 15
    print(f"Tokens: {total_in:,} in / {total_out:,} out")
    print(f"Est. cost: ${cost_in + cost_out:.2f}")

    if cd_vals:
        import numpy as np
        print(f"\nOverall Metrics (n={len(cd_vals)}):")
        print(f"  CD  — median: {np.median(cd_vals):.4f}, mean: {np.mean(cd_vals):.4f}")
        print(f"  F1  — median: {np.median(f1_vals):.4f}, mean: {np.mean(f1_vals):.4f}")
        print(f"  IoU — median: {np.median(iou_vals):.4f}, mean: {np.mean(iou_vals):.4f}")

    # Per-tier breakdown
    if tier_stats:
        import numpy as np
        print(f"\nPer-Tier Breakdown:")
        print(f"  {'Tier':<6} {'Exec%':>8} {'Conv%':>8} {'CD Med':>10} {'F1 Med':>10} {'IoU Med':>10}")
        print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
        for tier in sorted(tier_stats.keys()):
            ts = tier_stats[tier]
            exec_pct = ts["exec_ok"] / ts["total"] * 100 if ts["total"] > 0 else 0
            conv_pct = ts["converged"] / ts["total"] * 100 if ts["total"] > 0 else 0
            cd_med = f"{np.median(ts['cd']):.4f}" if ts["cd"] else "—"
            f1_med = f"{np.median(ts['f1']):.4f}" if ts["f1"] else "—"
            iou_med = f"{np.median(ts['iou']):.4f}" if ts["iou"] else "—"
            print(f"  {tier:<6} {exec_pct:>7.1f}% {conv_pct:>7.1f}% "
                  f"{cd_med:>10} {f1_med:>10} {iou_med:>10}")

    print(f"\nResults: {results_file}")
    print(f"Config:  {config_file}")


if __name__ == "__main__":
    main()
