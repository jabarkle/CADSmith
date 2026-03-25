"""AutoFab pipeline: the full agentic loop.

Planner → Coder → Executor → Validator → Refiner → loop
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .executor import Executor, ExecutionResult
from .validator import Validator, ValidationReport
from . import agents


@dataclass
class IterationLog:
    """Log entry for one iteration of the pipeline."""
    iteration: int
    iteration_type: str  # "initial", "error_fix", "geometric_refinement"
    code: str
    execution: Optional[dict] = None
    validation: Optional[dict] = None
    passed: bool = False
    feedback_sent: str = ""
    error_retries: list[dict] = field(default_factory=list)  # [{error, error_type, fix_code}, ...]
    refiner_input: Optional[str] = None   # feedback sent to Refiner
    refiner_output: Optional[str] = None  # code returned by Refiner


@dataclass
class PipelineResult:
    """Final result of the full pipeline run."""
    prompt: str
    design_plan: dict
    iterations: list[IterationLog] = field(default_factory=list)
    converged: bool = False
    final_code: Optional[str] = None
    final_geometry: Optional[dict] = None
    final_step_path: Optional[str] = None
    final_stl_path: Optional[str] = None
    total_time_ms: float = 0
    total_llm_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "design_plan": self.design_plan,
            "converged": self.converged,
            "total_iterations": len(self.iterations),
            "total_time_ms": self.total_time_ms,
            "total_llm_calls": self.total_llm_calls,
            "final_geometry": self.final_geometry,
            "final_step_path": self.final_step_path,
            "final_stl_path": self.final_stl_path,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "type": it.iteration_type,
                    "execution": it.execution,
                    "validation": it.validation,
                    "passed": it.passed,
                    "feedback_sent": it.feedback_sent,
                    "error_retries": it.error_retries,
                    "refiner_input": it.refiner_input,
                    "refiner_output": it.refiner_output,
                }
                for it in self.iterations
            ],
        }


class Pipeline:
    """The full AutoFab agentic pipeline."""

    def __init__(
        self,
        output_dir: str = "outputs",
        max_error_retries: int = 3,
        max_refinement_iterations: int = 5,
        verbose: bool = True,
        use_vision: bool = True,
    ):
        """
        Args:
            output_dir: Directory for output files (STEP, STL, logs).
            max_error_retries: Max error-fix attempts per iteration.
            max_refinement_iterations: Max geometric refinement iterations.
            verbose: Print progress messages.
            use_vision: If True (default), send rendered three-view image to
                the Judge. If False, Judge sees only code + kernel metrics.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_error_retries = max_error_retries
        self.max_refinements = max_refinement_iterations
        self.verbose = verbose
        self.use_vision = use_vision
        self.executor = Executor(output_dir=str(self.output_dir), timeout_seconds=60)
        self.validator = Validator()

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(self, prompt: str, name: str = "part") -> PipelineResult:
        """Run the full pipeline on a prompt.

        Args:
            prompt: Natural language CAD description.
            name: Base name for output files.

        Returns:
            PipelineResult with full iteration history.
        """
        start_time = time.time()
        llm_calls = 0

        # ---- Step 1: PLANNER ----
        self.log(f"\n{'='*60}")
        self.log(f"AUTOFAB PIPELINE: {prompt[:80]}...")
        self.log(f"{'='*60}")
        self.log("\n[1/4] PLANNER: Decomposing design...")

        design_plan = agents.plan(prompt)
        llm_calls += 1
        self.log(f"  Components: {design_plan.get('components', [])}")
        self.log(f"  Dimensions: {json.dumps(design_plan.get('dimensions', {}), indent=4)}")

        # ---- Step 2: CODER ----
        self.log("\n[2/4] CODER: Generating CadQuery code...")
        code = agents.generate_code(design_plan, prompt)
        llm_calls += 1
        self.log(f"  Generated {len(code.splitlines())} lines of code")

        # ---- Step 3 & 4: EXECUTE → VALIDATE → REFINE loop ----
        iterations = []
        iteration_num = 0
        current_code = code
        refinement_history = []  # Track previous feedback for the Refiner
        judge_feedback_history = []  # Track Judge's own feedback for escalation

        while iteration_num <= self.max_refinements:
            self.log(f"\n--- Iteration {iteration_num} ---")

            # Execute the code (with error retry sub-loop)
            exec_result, error_retries, current_code, retry_log = self._execute_with_retries(
                current_code, design_plan, name, iteration_num
            )
            llm_calls += error_retries  # each retry is an LLM call

            if not exec_result.success:
                # Couldn't fix the code after max retries
                self.log(f"  FAILED: Code doesn't execute after {error_retries} error-fix attempts")
                iterations.append(IterationLog(
                    iteration=iteration_num,
                    iteration_type="error_fix_exhausted",
                    code=current_code,
                    execution={"success": False, "error": exec_result.error},
                    passed=False,
                    feedback_sent=f"Code execution failed: {exec_result.error_type}",
                    error_retries=retry_log,
                ))
                break

            # Validate the geometry (LLM Judge + kernel checks, optionally with vision)
            vision_label = "with visual" if self.use_vision else "no visual"
            self.log(f"  [VALIDATE] Checking geometry ({vision_label})...")
            render_path = str(self.output_dir / f"{name}_iter{iteration_num}_render.png")
            stl_for_judge = (exec_result.stl_path or "") if self.use_vision else ""
            report = self.validator.validate(
                exec_result.geometry_json,
                code=current_code,
                prompt=prompt,
                stl_path=stl_for_judge,
                render_save_path=render_path if self.use_vision else "",
                prior_judge_feedback=judge_feedback_history if judge_feedback_history else None,
            )
            llm_calls += 1  # LLM Judge call

            iter_log = IterationLog(
                iteration=iteration_num,
                iteration_type="initial" if iteration_num == 0 else "geometric_refinement",
                code=current_code,
                execution={
                    "success": True,
                    "time_ms": exec_result.time_ms,
                },
                validation=report.to_dict(),
                passed=report.all_passed,
                feedback_sent=report.feedback_text,
                error_retries=retry_log,
            )
            iterations.append(iter_log)

            if report.all_passed:
                self.log(f"  ALL CHECKS PASSED at iteration {iteration_num}!")
                elapsed = (time.time() - start_time) * 1000
                return PipelineResult(
                    prompt=prompt,
                    design_plan=design_plan,
                    iterations=iterations,
                    converged=True,
                    final_code=current_code,
                    final_geometry=exec_result.geometry_json,
                    final_step_path=exec_result.step_path,
                    final_stl_path=exec_result.stl_path,
                    total_time_ms=elapsed,
                    total_llm_calls=llm_calls,
                )

            # Print failures
            failed = [c for c in report.checks if not c.passed]
            for c in failed:
                self.log(f"  [FAIL] {c.metric}: {c.message}")

            # Track Judge's feedback for escalation in future iterations
            judge_feedback_history.append(report.feedback_text)

            # Record this iteration's feedback for history
            refinement_history.append({
                "iteration": iteration_num,
                "feedback": report.feedback_text,
                "approach": None,
            })

            # Refine if we haven't hit the limit
            if iteration_num < self.max_refinements:
                self.log(f"\n  [REFINE] Sending geometric feedback to Refiner agent (attempt {iteration_num + 1}/{self.max_refinements})...")
                pre_refine_code = current_code
                current_code = agents.refine_geometry(
                    current_code,
                    report.feedback_text,
                    design_plan,
                    prompt,
                    iteration=iteration_num,
                    history=refinement_history[:-1] if len(refinement_history) > 1 else None,
                )
                llm_calls += 1
                self.log(f"  Refiner produced {len(current_code.splitlines())} lines")

                # Log refiner input/output on the current iteration
                iter_log.refiner_input = report.feedback_text
                iter_log.refiner_output = current_code
            else:
                self.log(f"\n  Max refinement iterations ({self.max_refinements}) reached.")

            iteration_num += 1

        # Did not converge
        elapsed = (time.time() - start_time) * 1000
        last_exec = iterations[-1] if iterations else None
        return PipelineResult(
            prompt=prompt,
            design_plan=design_plan,
            iterations=iterations,
            converged=False,
            final_code=current_code,
            final_geometry=exec_result.geometry_json if exec_result and exec_result.success else None,
            final_step_path=exec_result.step_path if exec_result and exec_result.success else None,
            final_stl_path=exec_result.stl_path if exec_result and exec_result.success else None,
            total_time_ms=elapsed,
            total_llm_calls=llm_calls,
        )

    def _execute_with_retries(self, code: str, design_plan: dict, name: str, iteration: int):
        """Try to execute code, with error-fix retries.

        Returns: (ExecutionResult, num_error_retries, final_code, retry_log)
            retry_log is a list of dicts with error, error_type, and fix_code
            for each retry attempt.
        """
        current_code = code
        error_retries = 0
        retry_log = []
        part_name = f"{name}_iter{iteration}"

        while error_retries <= self.max_error_retries:
            exec_result = self.executor.execute(current_code, name=part_name)

            if exec_result.success:
                self.log(f"  [EXEC] Success in {exec_result.time_ms:.0f}ms")
                return exec_result, error_retries, current_code, retry_log

            self.log(f"  [EXEC] Error ({exec_result.error_type}): {exec_result.error[:200]}...")

            if error_retries < self.max_error_retries:
                self.log(f"  [ERROR FIX] Attempt {error_retries + 1}/{self.max_error_retries}...")
                fixed_code = agents.fix_error(current_code, exec_result.error, design_plan)
                retry_log.append({
                    "attempt": error_retries + 1,
                    "error_type": exec_result.error_type,
                    "error": exec_result.error,
                    "fix_code": fixed_code,
                })
                current_code = fixed_code
                error_retries += 1
            else:
                break

        return exec_result, error_retries, current_code, retry_log

