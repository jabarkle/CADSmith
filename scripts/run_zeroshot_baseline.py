"""Zero-shot baseline: raw Claude Sonnet with no agentic scaffolding.

One LLM call per entry. No Planner, no RAG, no refinement loop, no vision
Judge, no error retries. Measures what the bare model can do so we can
quantify the value of AutoFab's multi-agent architecture.

The system prompt is intentionally minimal — just enough for the model to
know it should produce CadQuery code and assign to `result`.

Usage:
    conda activate cadquery
    cd ~/Desktop/AutoFab

    # Full run (all tiers)
    python3 scripts/run_zeroshot_baseline.py --experiment-name track2_zeroshot

    # Single tier
    python3 scripts/run_zeroshot_baseline.py --experiment-name track2_zeroshot --tiers T1

    # Specific entries
    python3 scripts/run_zeroshot_baseline.py --experiment-name track2_zeroshot --ids T1_001 T2_005
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autofab.executor import Executor
from autofab.metrics import compare_stl
from autofab.render import render_stl_to_png

DATA_DIR = PROJECT_ROOT / "data" / "dataset_v2"
RESULTS_BASE_DIR = PROJECT_ROOT / "results"

TIER_FILES = {
    "T1": "t1_primitives.jsonl",
    "T2": "t2_engineering_parts.jsonl",
    "T3": "t3_complex_parts.jsonl",
}

MODEL = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """You are a CAD engineer. Generate a complete, executable Python script using the CadQuery library to create the requested 3D part.

Rules:
1. import cadquery as cq
2. Assign your final shape to a variable called `result` (type: cq.Workplane).
3. Do NOT import or use ocp_vscode, show(), save_screenshot(), or any visualization.
4. Do NOT call cq.exporters — the system handles export.
5. Output ONLY the Python code. No markdown fences. No explanation text."""


def load_entries(tiers: list[str], limit_per_tier: int = 0) -> list[dict]:
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
                tier_entries.append(json.loads(line))

        if limit_per_tier > 0:
            tier_entries = tier_entries[:limit_per_tier]

        entries.extend(tier_entries)
        print(f"  {tier}: {len(tier_entries)} entries loaded")

    return entries


def generate_reference_stl(reference_code: str, entry_id: str, output_dir: Path) -> str:
    ref_stl_dir = output_dir / "reference_stls"
    ref_stl_dir.mkdir(parents=True, exist_ok=True)

    ref_stl_path = ref_stl_dir / f"{entry_id}.stl"
    if ref_stl_path.exists():
        return str(ref_stl_path)

    executor = Executor(output_dir=str(ref_stl_dir), timeout_seconds=60)
    result = executor.execute(reference_code, name=entry_id)

    if not result.success:
        raise RuntimeError(f"Reference code failed for {entry_id}: {result.error}")
    if not ref_stl_path.exists():
        raise RuntimeError(f"Reference STL not created at {ref_stl_path}")

    return str(ref_stl_path)


def zero_shot_generate(prompt: str) -> tuple[str, dict]:
    """One raw LLM call. Returns (code, token_usage)."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    tokens = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "calls": 1,
    }

    code = response.content[0].text.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    return code, tokens


def run_single_entry(entry: dict, output_dir: Path) -> dict:
    entry_id = entry["id"]
    tier = entry["tier"]
    prompt = entry["prompt"]
    reference_code = entry["reference_code"]

    start_time = time.time()

    # Generate reference STL
    try:
        ref_stl_path = generate_reference_stl(reference_code, entry_id, output_dir)
    except Exception as e:
        return {
            "id": entry_id, "tier": tier, "prompt": prompt,
            "success": False, "execution_success": False,
            "error": f"Reference STL generation failed: {e}",
        }

    # Zero-shot: one LLM call, no retries
    try:
        code, tokens = zero_shot_generate(prompt)
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "id": entry_id, "tier": tier, "prompt": prompt,
            "success": False, "execution_success": False,
            "error": f"LLM call failed: {e}",
            "total_time_ms": elapsed_ms, "tokens": {},
        }

    # Execute — one attempt, no error refinement
    gen_stl_dir = output_dir / "generated_stls"
    gen_stl_dir.mkdir(parents=True, exist_ok=True)

    executor = Executor(output_dir=str(gen_stl_dir), timeout_seconds=60)
    exec_result = executor.execute(code, name=entry_id)

    elapsed_ms = (time.time() - start_time) * 1000

    record = {
        "id": entry_id,
        "tier": tier,
        "prompt": prompt,
        "code": code,
        "execution_success": exec_result.success,
        "success": False,
        "total_time_ms": elapsed_ms,
        "tokens": tokens,
        "geometry": exec_result.geometry_json,
        "error": exec_result.error if not exec_result.success else None,
        "error_type": exec_result.error_type if not exec_result.success else None,
        "metrics": None,
    }

    # If execution succeeded, compute metrics and render
    if exec_result.success and exec_result.stl_path and Path(exec_result.stl_path).exists():
        # Render three-view image
        try:
            render_path = str(gen_stl_dir / f"{entry_id}_render.png")
            render_stl_to_png(exec_result.stl_path, render_path)
        except Exception:
            pass

        # Compute CD / F1 / IoU against reference
        try:
            metrics = compare_stl(exec_result.stl_path, ref_stl_path, normalize=False)
            record["metrics"] = metrics.to_dict()
            record["success"] = True
        except Exception as e:
            record["error"] = f"Metrics computation failed: {e}"

    return record


def main():
    parser = argparse.ArgumentParser(description="Zero-shot baseline for AutoFab Track 2")
    parser.add_argument("--experiment-name", type=str, required=True)
    parser.add_argument("--tiers", type=str, nargs="+", default=["T1", "T2", "T3"])
    parser.add_argument("--limit-per-tier", type=int, default=0)
    parser.add_argument("--ids", type=str, nargs="+", default=None)
    args = parser.parse_args()

    experiment_dir = RESULTS_BASE_DIR / args.experiment_name
    experiment_dir.mkdir(parents=True, exist_ok=True)

    results_file = experiment_dir / "results.jsonl"
    config_file = experiment_dir / "config.json"

    config = {
        "experiment_name": args.experiment_name,
        "dataset": "dataset_v2",
        "tiers": args.tiers,
        "mode": "zero-shot",
        "model": MODEL,
        "system_prompt": SYSTEM_PROMPT,
        "pipeline": "none (raw LLM call)",
        "rag": False,
        "planner": False,
        "refinement": False,
        "vision_judge": False,
        "error_retries": False,
        "limit_per_tier": args.limit_per_tier,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Loading benchmark entries...")
    entries = load_entries(args.tiers, limit_per_tier=args.limit_per_tier)

    if args.ids:
        id_set = set(args.ids)
        entries = [e for e in entries if e["id"] in id_set]
        print(f"Filtered to {len(entries)} entries: {args.ids}")

    print(f"Total: {len(entries)} entries")

    # Resume support
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
    metrics_ok = 0
    cd_vals, f1_vals, iou_vals = [], [], []
    tier_stats = {}

    for i, entry in enumerate(remaining):
        tier = entry["tier"]
        print(f"\n[{total_done + len(completed_ids) + 1}/{len(entries)}] "
              f"{entry['id']} ({tier}): {entry['prompt'][:60]}...", flush=True)

        record = run_single_entry(entry, experiment_dir)

        with open(results_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        total_done += 1
        if record.get("execution_success"):
            exec_ok += 1
        if record.get("metrics"):
            metrics_ok += 1
            m = record["metrics"]
            cd_vals.append(m["chamfer_distance"])
            f1_vals.append(m["f1_score"])
            iou_vals.append(m["volumetric_iou"])

        # Per-tier tracking
        if tier not in tier_stats:
            tier_stats[tier] = {"total": 0, "exec_ok": 0,
                                "cd": [], "f1": [], "iou": []}
        ts = tier_stats[tier]
        ts["total"] += 1
        if record.get("execution_success"):
            ts["exec_ok"] += 1
        if record.get("metrics"):
            ts["cd"].append(m["chamfer_distance"])
            ts["f1"].append(m["f1_score"])
            ts["iou"].append(m["volumetric_iou"])

        # Per-entry status
        elapsed = time.time() - start_time
        if record.get("execution_success"):
            status = "EXEC_OK"
            if record.get("metrics"):
                m = record["metrics"]
                print(f"  {status}  CD={m['chamfer_distance']:.4f}, "
                      f"F1={m['f1_score']:.4f}, IoU={m['volumetric_iou']:.4f}  "
                      f"({record['total_time_ms']/1000:.1f}s)")
            else:
                print(f"  {status}  metrics failed: {record.get('error', '')[:80]}")
        else:
            print(f"  EXEC_FAIL  {record.get('error_type', '')}: "
                  f"{record.get('error', '')[:120]}")

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"ZERO-SHOT BASELINE COMPLETE: {args.experiment_name}")
    print(f"{'='*70}")
    print(f"Model: {MODEL}")
    print(f"Total: {total_done}, Exec OK: {exec_ok}/{total_done} "
          f"({exec_ok/total_done*100:.1f}%)")
    print(f"Metrics computed: {metrics_ok}/{total_done}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")

    # Token costs
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

    if tier_stats:
        import numpy as np
        print(f"\nPer-Tier Breakdown:")
        print(f"  {'Tier':<6} {'N':>4} {'Exec%':>8} {'CD Med':>10} {'F1 Med':>10} {'IoU Med':>10}")
        print(f"  {'-'*6} {'-'*4} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
        for tier in sorted(tier_stats.keys()):
            ts = tier_stats[tier]
            exec_pct = ts["exec_ok"] / ts["total"] * 100 if ts["total"] > 0 else 0
            cd_med = f"{np.median(ts['cd']):.4f}" if ts["cd"] else "—"
            f1_med = f"{np.median(ts['f1']):.4f}" if ts["f1"] else "—"
            iou_med = f"{np.median(ts['iou']):.4f}" if ts["iou"] else "—"
            n_metrics = len(ts["cd"])
            print(f"  {tier:<6} {n_metrics:>4} {exec_pct:>7.1f}% "
                  f"{cd_med:>10} {f1_med:>10} {iou_med:>10}")

    print(f"\nResults: {results_file}")
    print(f"Config:  {config_file}")


if __name__ == "__main__":
    main()
