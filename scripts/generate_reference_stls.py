"""Generate reference STLs from Text-to-CadQuery test set.

Reads data/data_test.jsonl, preprocesses each script (strips exporters,
vis imports, ensures a `result` variable), executes it via subprocess
with CadQuery, and saves the resulting STL to data/reference_stls/{uid}.stl.

Usage:
    conda activate cadquery
    python3 scripts/generate_reference_stls.py [--workers 4] [--limit 100]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "reference_stls"

# Runner template — executes the script and exports STL
RUNNER_TEMPLATE = '''
import json, sys

try:
    _user_globals = {{}}
    exec(open("{script_path}").read(), _user_globals)

    import cadquery as cq
    _result = None

    # Find the result shape
    for name in ["result", "assembly", "model", "part", "shape", "body",
                  "part_1", "part_2", "part_3"]:
        obj = _user_globals.get(name)
        if obj is not None and isinstance(obj, cq.Workplane):
            _result = obj
            break

    # Fallback: last Workplane assigned
    if _result is None:
        for name, obj in reversed(list(_user_globals.items())):
            if name.startswith("_"):
                continue
            if isinstance(obj, cq.Workplane):
                _result = obj
                break

    if _result is None:
        print(json.dumps({{"success": False, "error": "No Workplane found"}}))
    else:
        cq.exporters.export(_result, "{stl_path}")
        solid = _result.val()
        bb = solid.BoundingBox()
        print(json.dumps({{
            "success": True,
            "volume": solid.Volume(),
            "bbox": {{"xlen": bb.xlen, "ylen": bb.ylen, "zlen": bb.zlen}},
            "is_valid": solid.isValid(),
        }}))
except Exception as e:
    import traceback
    print(json.dumps({{"success": False, "error": traceback.format_exc()[:500]}}))
'''


def preprocess_code(code: str) -> str:
    """Strip exporters, vis imports, and ensure result variable exists."""
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip exporter calls
        if "exporters.export" in stripped:
            continue
        # Skip vis imports
        if "from cadquery.vis" in stripped or "from ocp_vscode" in stripped:
            continue
        if "import ocp_vscode" in stripped:
            continue
        # Skip show() calls
        if stripped.startswith("show(") or stripped.startswith("show_object("):
            continue
        cleaned.append(line)

    cleaned_code = "\n".join(cleaned)

    # Ensure a `result` variable exists
    if "result" not in cleaned_code:
        # Find the last assigned Workplane variable
        # Common patterns: assembly = ..., part_1 = ..., etc.
        last_var = None
        for line in reversed(cleaned):
            match = re.match(r'^(\w+)\s*=', line.strip())
            if match:
                last_var = match.group(1)
                if not last_var.startswith("_"):
                    break
                last_var = None
        if last_var:
            cleaned_code += f"\nresult = {last_var}\n"

    return cleaned_code


def execute_one(args: tuple) -> dict:
    """Execute a single test entry. Called in subprocess pool."""
    idx, uid, code = args
    stl_path = OUTPUT_DIR / f"{uid}.stl"

    if stl_path.exists():
        return {"idx": idx, "uid": uid, "success": True, "skipped": True}

    cleaned = preprocess_code(code)

    # Write script and runner to temp files
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"autofab_ref_{uid}_"))
    script_path = tmp_dir / "script.py"
    runner_path = tmp_dir / "runner.py"

    script_path.write_text(cleaned)
    runner_code = RUNNER_TEMPLATE.format(
        script_path=str(script_path).replace("\\", "\\\\"),
        stl_path=str(stl_path).replace("\\", "\\\\"),
    )
    runner_path.write_text(runner_code)

    try:
        proc = subprocess.run(
            [sys.executable, str(runner_path)],
            capture_output=True, text=True, timeout=30,
        )
        stdout = proc.stdout.strip()
        if stdout:
            result_data = json.loads(stdout)
            return {"idx": idx, "uid": uid, **result_data, "skipped": False}
        else:
            return {"idx": idx, "uid": uid, "success": False,
                    "error": proc.stderr[:300] or "No output", "skipped": False}
    except subprocess.TimeoutExpired:
        return {"idx": idx, "uid": uid, "success": False,
                "error": "Timeout (30s)", "skipped": False}
    except Exception as e:
        return {"idx": idx, "uid": uid, "success": False,
                "error": str(e)[:300], "skipped": False}
    finally:
        # Cleanup temp files
        for f in tmp_dir.iterdir():
            f.unlink()
        tmp_dir.rmdir()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load test entries
    entries = []
    with open(DATA_DIR / "data_test.jsonl") as f:
        for i, line in enumerate(f):
            entry = json.loads(line)
            uid_match = re.search(r'(\d{8})\.stl', entry["output"])
            uid = uid_match.group(1) if uid_match else f"unknown_{i:06d}"
            entries.append((i, uid, entry["output"]))

    if args.limit > 0:
        entries = entries[:args.limit]

    print(f"Processing {len(entries)} entries with {args.workers} workers...")
    print(f"Output: {OUTPUT_DIR}/")

    start = time.time()
    success = 0
    failed = 0
    skipped = 0
    errors = []

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute_one, e): e for e in entries}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result.get("skipped"):
                skipped += 1
            elif result["success"]:
                success += 1
            else:
                failed += 1
                errors.append(result)

            done = success + failed + skipped
            if done % 100 == 0 or done == len(entries):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  [{done}/{len(entries)}] "
                      f"OK={success} FAIL={failed} SKIP={skipped} "
                      f"({rate:.1f}/s, {elapsed:.0f}s elapsed)")

    elapsed = time.time() - start
    total_run = success + failed
    pct = success / total_run * 100 if total_run > 0 else 0

    print(f"\n{'='*60}")
    print(f"DONE in {elapsed:.0f}s")
    print(f"  Success: {success}/{total_run} ({pct:.1f}%)")
    print(f"  Failed:  {failed}/{total_run}")
    print(f"  Skipped: {skipped} (already existed)")

    # Save error log
    if errors:
        log_path = DATA_DIR / "reference_stl_errors.json"
        with open(log_path, "w") as f:
            json.dump(errors, f, indent=2)
        print(f"  Error log: {log_path}")

        # Show top error types
        from collections import Counter
        error_types = Counter()
        for e in errors:
            err = e.get("error", "")
            if "threePointArc" in err or "GC_MakeArc" in err:
                error_types["threePointArc/GC_MakeArc"] += 1
            elif "StdFail_NotDone" in err:
                error_types["StdFail_NotDone"] += 1
            elif "Timeout" in err:
                error_types["Timeout"] += 1
            elif "SyntaxError" in err:
                error_types["SyntaxError"] += 1
            elif "NameError" in err:
                error_types["NameError"] += 1
            elif "No Workplane" in err:
                error_types["No Workplane found"] += 1
            else:
                error_types["Other"] += 1

        print(f"\n  Top error types:")
        for err_type, count in error_types.most_common(10):
            print(f"    {err_type}: {count}")


if __name__ == "__main__":
    main()
