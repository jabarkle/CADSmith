"""Sandboxed CadQuery code executor.

Runs generated CadQuery scripts in an isolated subprocess with timeout
and resource limits. Returns either a success result with paths to
exported files, or a failure result with the full error traceback.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExecutionResult:
    """Result of executing a CadQuery script."""
    success: bool
    time_ms: float
    # On success:
    step_path: Optional[str] = None
    stl_path: Optional[str] = None
    geometry_json: Optional[dict] = None  # basic shape info extracted in-process
    # On failure:
    error: Optional[str] = None
    error_type: Optional[str] = None  # e.g. "SyntaxError", "StdFail_NotDone"


# This script template is what actually runs inside the subprocess.
# It executes the user's CadQuery code, extracts geometry info, and exports files.
_RUNNER_TEMPLATE = '''
import json
import sys
import os

# Redirect the user code's output
_autofab_output = {{"success": False}}

try:
    # Execute the generated CadQuery code
    _autofab_user_globals = {{}}
    exec(open("{script_path}").read(), _autofab_user_globals)

    # Find the CadQuery result object - look for common variable names
    import cadquery as cq
    _autofab_result = None

    # Priority order for finding the result shape
    _autofab_candidate_names = ["result", "model", "part", "shape", "assembly",
                                 "drone", "chassis", "bracket", "plate", "body"]

    for name in _autofab_candidate_names:
        obj = _autofab_user_globals.get(name)
        if obj is not None and isinstance(obj, cq.Workplane):
            _autofab_result = obj
            break

    # Fallback: find the last Workplane assigned
    if _autofab_result is None:
        for name, obj in reversed(list(_autofab_user_globals.items())):
            if name.startswith("_"):
                continue
            if isinstance(obj, cq.Workplane):
                _autofab_result = obj
                break

    if _autofab_result is None:
        _autofab_output = {{"success": False, "error": "No CadQuery Workplane object found in script output. Assign your final shape to a variable named 'result'.", "error_type": "NoResultError"}}
    else:
        # Extract geometry info
        solid = _autofab_result.val()
        bb = _autofab_result.val().BoundingBox()

        _autofab_geometry = {{
            "volume": solid.Volume(),
            "center_of_mass": solid.Center().toTuple(),
            "bounding_box": {{
                "xmin": bb.xmin, "xmax": bb.xmax, "xlen": bb.xlen,
                "ymin": bb.ymin, "ymax": bb.ymax, "ylen": bb.ylen,
                "zmin": bb.zmin, "zmax": bb.zmax, "zlen": bb.zlen,
            }},
            "is_valid": solid.isValid(),
            "num_faces": len(_autofab_result.faces().vals()),
            "num_edges": len(_autofab_result.edges().vals()),
            "num_vertices": len(_autofab_result.vertices().vals()),
        }}

        # Export STEP and STL
        cq.exporters.export(_autofab_result, "{step_path}")
        cq.exporters.export(_autofab_result, "{stl_path}")

        _autofab_output = {{
            "success": True,
            "geometry": _autofab_geometry,
        }}

except Exception as e:
    import traceback
    _autofab_output = {{
        "success": False,
        "error": traceback.format_exc(),
        "error_type": type(e).__name__,
    }}

# Write result to stdout as JSON
print("__AUTOFAB_RESULT__")
print(json.dumps(_autofab_output))
'''


class Executor:
    """Executes CadQuery scripts in a sandboxed subprocess."""

    def __init__(self, output_dir: Optional[str] = None, timeout_seconds: int = 60):
        self.timeout = timeout_seconds
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Path(tempfile.mkdtemp(prefix="autofab_")).resolve()

    def execute(self, cadquery_code: str, name: str = "part") -> ExecutionResult:
        """Execute a CadQuery script and return the result.

        Args:
            cadquery_code: The CadQuery Python code to execute.
            name: Base name for exported files.

        Returns:
            ExecutionResult with success/failure info and geometry data.
        """
        # Write the user's script to a temp file
        script_path = self.output_dir / f"{name}_script.py"
        step_path = self.output_dir / f"{name}.step"
        stl_path = self.output_dir / f"{name}.stl"

        script_path.write_text(cadquery_code)

        # Build the runner script
        runner_code = _RUNNER_TEMPLATE.format(
            script_path=str(script_path).replace("\\", "\\\\"),
            step_path=str(step_path).replace("\\", "\\\\"),
            stl_path=str(stl_path).replace("\\", "\\\\"),
        )
        runner_path = self.output_dir / f"{name}_runner.py"
        runner_path.write_text(runner_code)

        # Execute in subprocess
        start_time = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(runner_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.output_dir),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # Parse the result from stdout
            stdout = proc.stdout
            if "__AUTOFAB_RESULT__" in stdout:
                result_json_str = stdout.split("__AUTOFAB_RESULT__")[1].strip()
                result_data = json.loads(result_json_str)
            else:
                # Script crashed before producing output
                return ExecutionResult(
                    success=False,
                    time_ms=elapsed_ms,
                    error=proc.stderr or proc.stdout or "No output from runner",
                    error_type="SubprocessError",
                )

            if result_data["success"]:
                return ExecutionResult(
                    success=True,
                    time_ms=elapsed_ms,
                    step_path=str(step_path),
                    stl_path=str(stl_path),
                    geometry_json=result_data["geometry"],
                )
            else:
                return ExecutionResult(
                    success=False,
                    time_ms=elapsed_ms,
                    error=result_data.get("error", "Unknown error"),
                    error_type=result_data.get("error_type", "Unknown"),
                )

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                time_ms=elapsed_ms,
                error=f"Execution timed out after {self.timeout} seconds",
                error_type="TimeoutError",
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                time_ms=elapsed_ms,
                error=str(e),
                error_type=type(e).__name__,
            )
