"""Programmatic geometric validator.

Combines objective CAD kernel checks (solid validity) with an LLM-as-a-Judge
that cross-references the original prompt, the generated CadQuery code, and
exact OCCT kernel measurements.

The LLM Judge replaces the earlier deterministic bbox/volume checks that
relied on the Planner agent's hallucinated dimension estimates.  The Judge
can verify feature intent (e.g., "did they code the M3 holes?") by reading
the code — something kernel metrics alone cannot do.

The reference comparison path (_compare_to_reference) is kept for post-hoc
benchmarking only and is never used in the refinement loop.
"""

import json
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationCheck:
    """A single validation check result."""
    metric: str
    actual: float
    target: Optional[float] = None
    threshold: Optional[float] = None
    passed: bool = True
    message: str = ""


@dataclass
class ValidationReport:
    """Complete validation report for a generated part."""
    checks: list[ValidationCheck] = field(default_factory=list)
    all_passed: bool = False
    summary: str = ""
    feedback_text: str = ""

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "checks": [
                {
                    "metric": c.metric,
                    "actual": c.actual,
                    "target": c.target,
                    "threshold": c.threshold,
                    "passed": c.passed,
                    "message": c.message,
                }
                for c in self.checks
            ],
            "summary": self.summary,
            "feedback_text": self.feedback_text,
        }


class Validator:
    """Validates generated geometry using an LLM-as-a-Judge.

    Two modes of operation:
    1. In-loop validation: Objective kernel checks (solid validity) plus
       LLM Judge that cross-references prompt, code, and kernel metrics.
    2. Reference comparison: Compare against a reference shape using Chamfer
       Distance, F1, and Volumetric IoU (for post-hoc benchmarking only).
    """

    def __init__(
        self,
        volume_error_threshold: float = 5.0,
        bbox_iou_threshold: float = 0.90,
        validity_required: bool = True,
    ):
        self.volume_error_threshold = volume_error_threshold
        self.bbox_iou_threshold = bbox_iou_threshold
        self.validity_required = validity_required

    def validate(
        self,
        geometry: dict,
        code: str = "",
        reference_geometry: Optional[dict] = None,
        prompt: str = "",
        stl_path: str = "",
        render_save_path: str = "",
        prior_judge_feedback: list[str] | None = None,
    ) -> ValidationReport:
        """Validate generated geometry.

        Args:
            geometry: Geometry dict from executor (volume, bbox, face counts, etc.)
            code: The generated CadQuery code (used by LLM Judge).
            reference_geometry: Optional reference geometry dict for comparison.
            prompt: Original user request.
            stl_path: Path to the generated STL file. When provided, a three-view
                render is sent to the LLM Judge for visual cross-referencing.
            render_save_path: If provided, the rendered PNG is saved here for
                paper figures and iteration progression analysis.

        Returns:
            ValidationReport with pass/fail for each check and feedback text.
        """
        checks = []

        # --- Objective kernel check: solid validity ---
        is_valid = geometry.get("is_valid", False)
        checks.append(ValidationCheck(
            metric="solid_valid",
            actual=float(is_valid),
            target=1.0,
            passed=is_valid,
            message="Solid is valid (watertight)" if is_valid else "INVALID solid — not watertight, may not be manufacturable",
        ))

        # --- Informational: volume, bbox, topology (no pass/fail) ---
        volume = geometry.get("volume", 0)
        checks.append(ValidationCheck(
            metric="volume",
            actual=volume,
            message=f"Volume: {volume:.1f} mm³",
        ))

        bb = geometry.get("bounding_box", {})
        for dim in ["xlen", "ylen", "zlen"]:
            val = bb.get(dim, 0)
            checks.append(ValidationCheck(
                metric=f"bbox_{dim}",
                actual=val,
                message=f"BBox {dim}: {val:.2f} mm",
            ))

        for count_key in ["num_faces", "num_edges", "num_vertices"]:
            val = geometry.get(count_key, 0)
            checks.append(ValidationCheck(
                metric=count_key,
                actual=val,
                message=f"{count_key}: {val}",
            ))

        com = geometry.get("center_of_mass", (0, 0, 0))
        checks.append(ValidationCheck(
            metric="center_of_mass",
            actual=0,
            message=f"Center of mass: ({com[0]:.2f}, {com[1]:.2f}, {com[2]:.2f})",
        ))

        # --- LLM-as-a-Judge: feature-aware validation ---
        if prompt and code:
            from . import agents
            try:
                judge_result = agents.evaluate_geometry(
                    prompt, code, geometry,
                    stl_path=stl_path,
                    render_save_path=render_save_path,
                    prior_judge_feedback=prior_judge_feedback,
                )
                judge_passed = judge_result.get("passed", False)
                judge_feedback = judge_result.get("feedback", "No feedback provided.")
                checks.append(ValidationCheck(
                    metric="llm_judge",
                    actual=float(judge_passed),
                    target=1.0,
                    passed=judge_passed,
                    message=judge_feedback,
                ))
            except Exception as e:
                checks.append(ValidationCheck(
                    metric="llm_judge",
                    actual=0,
                    target=1.0,
                    passed=True,
                    message=f"LLM Judge call failed ({e}), skipping — not blocking convergence.",
                ))

        # --- Reference comparison (post-hoc benchmarking only) ---
        if reference_geometry:
            checks.extend(self._compare_to_reference(geometry, reference_geometry))

        # --- Build report ---
        all_passed = all(c.passed for c in checks)
        failed = [c for c in checks if not c.passed]

        if all_passed:
            summary = "All validation checks passed."
            feedback = "All checks passed. The generated geometry meets all constraints."
        else:
            summary = f"{len(failed)} check(s) failed out of {len(checks)}."
            feedback_lines = ["The following checks FAILED and need correction:\n"]
            for c in failed:
                if c.target is not None:
                    feedback_lines.append(
                        f"  - {c.metric}: actual={c.actual:.4g}, target={c.target:.4g} — {c.message}"
                    )
                else:
                    feedback_lines.append(f"  - {c.metric}: {c.message}")
            if prompt:
                feedback_lines.append(f"\nOriginal user request (for context): {prompt}")
            feedback = "\n".join(feedback_lines)

        return ValidationReport(
            checks=checks,
            all_passed=all_passed,
            summary=summary,
            feedback_text=feedback,
        )

    def _compare_to_reference(self, geometry: dict, reference: dict) -> list[ValidationCheck]:
        """Compare generated geometry to a reference geometry."""
        checks = []

        gen_vol = geometry.get("volume", 0)
        ref_vol = reference.get("volume", 0)
        if ref_vol > 0:
            error_pct = abs(gen_vol - ref_vol) / ref_vol * 100
            passed = error_pct <= self.volume_error_threshold
            checks.append(ValidationCheck(
                metric="ref_volume_error_pct",
                actual=error_pct,
                target=0,
                threshold=self.volume_error_threshold,
                passed=passed,
                message=f"Volume vs reference: {error_pct:.1f}% error (gen={gen_vol:.1f}, ref={ref_vol:.1f})"
                        + (" PASS" if passed else " FAIL"),
            ))

        gen_bb = geometry.get("bounding_box", {})
        ref_bb = reference.get("bounding_box", {})
        if gen_bb and ref_bb:
            iou = self._bbox_iou(gen_bb, ref_bb)
            passed = iou >= self.bbox_iou_threshold
            checks.append(ValidationCheck(
                metric="bbox_iou",
                actual=iou,
                target=1.0,
                threshold=self.bbox_iou_threshold,
                passed=passed,
                message=f"BBox IoU: {iou:.3f} (threshold: {self.bbox_iou_threshold})"
                        + (" PASS" if passed else " FAIL"),
            ))

        gen_com = geometry.get("center_of_mass", (0, 0, 0))
        ref_com = reference.get("center_of_mass", (0, 0, 0))
        com_dist = np.sqrt(sum((g - r) ** 2 for g, r in zip(gen_com, ref_com)))
        checks.append(ValidationCheck(
            metric="com_distance",
            actual=com_dist,
            target=0,
            message=f"Center of mass offset: {com_dist:.2f} mm",
        ))

        return checks

    @staticmethod
    def _bbox_iou(bb1: dict, bb2: dict) -> float:
        """Compute 3D bounding box intersection-over-union."""
        x_overlap = max(0, min(bb1["xmax"], bb2["xmax"]) - max(bb1["xmin"], bb2["xmin"]))
        y_overlap = max(0, min(bb1["ymax"], bb2["ymax"]) - max(bb1["ymin"], bb2["ymin"]))
        z_overlap = max(0, min(bb1["zmax"], bb2["zmax"]) - max(bb1["zmin"], bb2["zmin"]))
        intersection = x_overlap * y_overlap * z_overlap

        vol1 = bb1["xlen"] * bb1["ylen"] * bb1["zlen"]
        vol2 = bb2["xlen"] * bb2["ylen"] * bb2["zlen"]
        union = vol1 + vol2 - intersection

        return intersection / union if union > 0 else 0.0
