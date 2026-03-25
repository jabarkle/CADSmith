"""AutoFab agent definitions.

Implements the multi-agent pipeline:
  Planner → Coder → Executor → Validator → Refiner (loop)
                                          → Error Refiner (on code errors)
"""

import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Token usage tracking
# ---------------------------------------------------------------------------

_token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def get_token_usage() -> dict:
    """Return accumulated token usage since last reset."""
    return dict(_token_usage)


def reset_token_usage():
    """Reset the token usage counters."""
    _token_usage["input_tokens"] = 0
    _token_usage["output_tokens"] = 0
    _token_usage["calls"] = 0


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _call_claude(system: str, user: str, model: str = "claude-sonnet-4-5-20250929", max_tokens: int = 4096) -> str:
    """Call Claude and return the text response. Tracks token usage."""
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # Accumulate token usage
    if hasattr(response, "usage") and response.usage:
        _token_usage["input_tokens"] += response.usage.input_tokens
        _token_usage["output_tokens"] += response.usage.output_tokens
    _token_usage["calls"] += 1
    return response.content[0].text


# ---------------------------------------------------------------------------
# PLANNER AGENT
# ---------------------------------------------------------------------------

PLANNER_SYSTEM = """You are the Planner Agent in the AutoFab CAD generation system.

Your job: take a natural language description of a 3D part and produce a structured design plan.

Output a JSON object with these fields:
{
  "description": "Brief summary of the part",
  "components": ["list of sub-components"],
  "dimensions": {
    "overall_bbox": {"xlen": mm, "ylen": mm, "zlen": mm},
    "key_dimensions": {"dimension_name": value_mm, ...}
  },
  "constraints": {
    "volume_estimate": estimated_volume_mm3,
    "num_holes": count_or_null,
    "hole_diameter": mm_or_null,
    "symmetry": "description or null"
  },
  "acceptance_criteria": {
    "volume_error_threshold_pct": 5,
    "bbox_iou_threshold": 0.90
  },
  "notes": "Any special considerations for the Coder agent"
}

Be precise with dimensions. If the user prompt includes explicit dimensions, use them exactly.
If dimensions are not specified, estimate reasonable engineering dimensions and state your assumptions.
Output ONLY valid JSON, no other text."""


def plan(prompt: str) -> dict:
    """Planner agent: natural language → structured design plan."""
    import json
    response = _call_claude(PLANNER_SYSTEM, prompt)
    # Strip markdown code fences if present
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        elif "```" in text:
            text = text[:text.rfind("```")]
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# CODER AGENT
# ---------------------------------------------------------------------------

CODER_SYSTEM = """You are the Coder Agent in the AutoFab CAD generation system.

Your job: generate a complete, executable CadQuery Python script from a design plan.

ORIENTATION CONVENTION (always follow):
- Build parts on the XY workplane. The Z-axis points UP.
- Flat parts (plates, brackets): lie flat on XY, thickness in +Z.
- Cylindrical parts (shafts, gears, bushings): axis along +Z, standing upright.
- L/T/U shapes: base on XY, vertical element rises in +Z.
- Center the part on the origin when possible (use centered=True).
- "top face" = +Z face. "bottom" = -Z face.
- "length" = longest horizontal dimension, typically X. "width" = Y. "height/thickness" = Z.
- If the prompt specifies axis directions (e.g., "along X"), follow those exactly.

CRITICAL RULES:
1. Import cadquery as cq at the top.
2. Assign your final shape to a variable called `result` (type: cq.Workplane).
3. Do NOT import or use ocp_vscode, show(), save_screenshot(), or any visualization.
4. Do NOT call cq.exporters — the system handles export.
5. The script must be self-contained and executable with just CadQuery installed.
6. Use parametric variables at the top for all dimensions.
7. Add brief comments explaining each construction step.
8. Ensure the final solid is valid (watertight, no self-intersections).

Output ONLY the Python code. No markdown fences. No explanation text."""


def generate_code(design_plan: dict, prompt: str) -> str:
    """Coder agent: design plan → CadQuery Python code."""
    import json
    from .rag_kb1 import get_api_context

    # Retrieve relevant CadQuery API docs from KB1
    kb1_context = get_api_context(design_plan, prompt)

    user_msg = f"""Original user request: {prompt}

Design plan:
{json.dumps(design_plan, indent=2)}

{kb1_context}Generate the CadQuery Python script. Remember: assign the final shape to `result`."""

    response = _call_claude(CODER_SYSTEM, user_msg)
    # Strip markdown code fences if present
    code = response.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


# ---------------------------------------------------------------------------
# ERROR REFINER AGENT
# ---------------------------------------------------------------------------

ERROR_REFINER_SYSTEM = """You are the Error Refiner Agent in the AutoFab CAD generation system.

Your job: fix CadQuery code that failed to execute.

You receive:
1. The original code that failed
2. The full error traceback
3. The original design plan
4. Relevant CadQuery API documentation and error-solution patterns

CRITICAL RULES:
1. Output ONLY the corrected Python code. No explanations.
2. Keep the same variable named `result` for the final shape.
3. Do NOT import ocp_vscode or call show()/save_screenshot().
4. Do NOT call cq.exporters.
5. Fix the specific error while preserving the design intent.
6. If a fillet/chamfer fails, reduce the radius or remove it — do not leave broken code.
7. If a boolean operation fails, check that shapes actually overlap."""


def fix_error(code: str, error: str, design_plan: dict) -> str:
    """Error Refiner agent: broken code + error → fixed code."""
    import json
    from .rag_kb1 import get_api_context
    from .rag_kb2 import get_error_context

    # Retrieve matching error-solution patterns from KB2
    kb2_context = get_error_context(error)

    # Retrieve relevant API docs from KB1
    kb1_context = get_api_context(design_plan, "")

    user_msg = f"""The following CadQuery code failed with an error.

FAILED CODE:
```python
{code}
```

ERROR:
{error}

{kb2_context}
{kb1_context}DESIGN PLAN:
{json.dumps(design_plan, indent=2)}

Fix the code. Output ONLY the corrected Python code."""

    response = _call_claude(ERROR_REFINER_SYSTEM, user_msg)
    code = response.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


# ---------------------------------------------------------------------------
# VALIDATOR AGENT (LLM-as-a-Judge)
# ---------------------------------------------------------------------------

VALIDATOR_SYSTEM = """You are the Validator Agent in the AutoFab CAD generation system.
Your job is to rigorously and objectively evaluate if generated CadQuery code and its resulting geometric metrics fulfill the original user request.

You will receive:
1. The original user prompt.
2. The generated CadQuery code.
3. The exact geometric measurements from the OCCT CAD kernel (volume, bounding box, face/edge counts).
4. A rendered image of the generated part showing THREE views side by side:
   - LEFT:   Isometric view — shows overall 3D shape
   - CENTER: High-angle rear view — looks down at the top face, reveals holes,
             bores, cavities, and internal features
   - RIGHT:  Front profile view — near side-on, shows vertical profile, wall
             heights, gear spacing, slots, and layered features

IMPORTANT: The three rendered views supplement the kernel metrics — use BOTH together.
The image may not reveal every feature (hidden internal geometry, small details), but
it will help you catch major failures that metrics alone can miss:
- A shape that is fundamentally wrong (e.g., a solid block instead of a hollow shell)
- Features that appear in the code but are clearly absent in the render
- False convergence where metrics look acceptable but the part is visually incorrect
- Gross proportion errors visible at a glance

Your evaluation must be highly analytical and Socratic. Cross-reference ALL evidence:
- Does the code explicitly construct all features requested in the prompt?
- Do the kernel bounding box dimensions align with the prompt's requirements? (Note: For non-rectangular shapes like polygons, cylinders, or spheres, the bounding box will naturally be smaller than characteristic dimensions like circumscribed circle diameter. Do not flag this as an error.)
- Does the rendered image confirm that the constructed features are actually present and correct?
- Are there missing features, or extra features that were not requested?
- Is the volume physically plausible for the described shape and dimensions?
- If the prompt specifies holes, bolts, or mounting points: COUNT them in the rendered views
  and verify the number matches the prompt exactly. Also check their approximate placement
  (e.g., evenly spaced on a bolt circle, centered, at corners, etc.).

You may also receive YOUR OWN PRIOR FEEDBACK from previous iterations. This is critical:
- If you gave feedback before and the same issue persists, ESCALATE. Do not repeat the same suggestion.
- Note what was tried and failed, then recommend a fundamentally different approach.
- Example: if you said "revolve the profile" twice and the result is still flat, say
  "Previous revolve attempts failed. Try a completely different construction: extrude a
  circle and use boolean cuts instead."

Output a JSON object with EXACTLY these fields:
{
  "passed": boolean,
  "feedback": "Direct, analytical feedback detailing exact discrepancies. If passed, write 'All constraints met.' If failed, state exactly what is wrong — referencing what you see in the image AND the metrics — and suggest a DIFFERENT approach if prior feedback was not addressed."
}
Output ONLY valid JSON, no other text."""


def evaluate_geometry(
    prompt: str,
    code: str,
    geometry_metrics: dict,
    stl_path: str = "",
    render_save_path: str = "",
    prior_judge_feedback: list[str] | None = None,
) -> dict:
    """Validator agent: evaluates code, kernel metrics, and rendered image against the prompt.

    Uses Claude Opus as the Judge model — a stronger model than the Coder
    (Sonnet) to avoid confirmation bias from self-evaluation.

    When stl_path is provided, renders a three-view image and sends it
    alongside the text evidence for visual cross-referencing.

    Args:
        prompt: Original user request.
        code: Generated CadQuery code.
        geometry_metrics: Kernel measurements dict.
        stl_path: Path to the generated STL. If provided, a three-view
            render is created and sent to the Judge.
        render_save_path: If provided, the rendered PNG is saved here
            (for paper figures / iteration progression). Otherwise a
            temporary file is used and cleaned up.
        prior_judge_feedback: List of feedback strings from previous
            iterations (oldest first). Allows the Judge to escalate
            when repeated issues are not addressed.
    """
    import json
    import base64

    text_content = (
        f"ORIGINAL PROMPT:\n{prompt}\n\n"
        f"GENERATED CODE:\n```python\n{code}\n```\n\n"
        f"KERNEL METRICS:\n{json.dumps(geometry_metrics, indent=2)}\n\n"
    )

    if prior_judge_feedback:
        text_content += "YOUR PRIOR FEEDBACK (from previous iterations, oldest first):\n"
        for i, fb in enumerate(prior_judge_feedback):
            text_content += f"  Iteration {i}: {fb}\n"
        text_content += "\nIf the same issues persist, escalate — recommend a fundamentally different approach.\n\n"

    text_content += "Evaluate and return JSON."

    # Build message content — with or without image
    message_content = []

    if stl_path:
        try:
            from .render import render_stl_to_png
            import tempfile
            import os

            # Render to a persistent path if provided, otherwise temp
            if render_save_path:
                png_path = render_save_path
                os.makedirs(os.path.dirname(png_path) if os.path.dirname(png_path) else ".", exist_ok=True)
            else:
                tmp_dir = tempfile.mkdtemp(prefix="autofab_judge_")
                png_path = os.path.join(tmp_dir, "judge_render.png")

            render_stl_to_png(stl_path, png_path)

            with open(png_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            message_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data,
                },
            })

            # Clean up only if we used a temp file
            if not render_save_path:
                try:
                    os.remove(png_path)
                    os.rmdir(tmp_dir)
                except OSError:
                    pass

        except Exception:
            # If rendering fails, proceed without image — don't block validation
            pass

    message_content.append({"type": "text", "text": text_content})

    # Call Opus with vision-capable message format
    client = _get_client()
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4096,
        system=VALIDATOR_SYSTEM,
        messages=[{"role": "user", "content": message_content}],
    )

    # Track token usage
    if hasattr(response, "usage") and response.usage:
        _token_usage["input_tokens"] += response.usage.input_tokens
        _token_usage["output_tokens"] += response.usage.output_tokens
    _token_usage["calls"] += 1

    text = response.content[0].text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    return json.loads(text)


# ---------------------------------------------------------------------------
# REFINER AGENT
# ---------------------------------------------------------------------------

REFINER_SYSTEM = """You are the Refiner Agent in the AutoFab CAD generation system.

Your job: improve CadQuery code based on PRECISE GEOMETRIC FEEDBACK from the validator.

ORIENTATION CONVENTION (always follow):
- Build parts on the XY workplane. The Z-axis points UP.
- Flat parts (plates, brackets): lie flat on XY, thickness in +Z.
- Cylindrical parts (shafts, gears, bushings): axis along +Z, standing upright.
- L/T/U shapes: base on XY, vertical element rises in +Z.
- Center the part on the origin when possible (use centered=True).
- "top face" = +Z face. "bottom" = -Z face.
- "length" = longest horizontal dimension, typically X. "width" = Y. "height/thickness" = Z.
- If the prompt specifies axis directions (e.g., "along X"), follow those exactly.

You receive:
1. The current code (which executes successfully but produces incorrect geometry)
2. Structured validation feedback with exact numeric measurements
3. The original design plan with target dimensions
4. History of previous refinement attempts (if any)

The feedback contains exact measurements like:
- "bbox_xlen: actual=18.5, target=20.0, error=7.5% FAIL"
- "volume: actual=7000.0, bounds=[400.0, 8000.0] FAIL"

Use these PRECISE NUMBERS to make targeted corrections. For example:
- If bbox is wrong in X, adjust X-axis dimensions specifically
- If volume is outside bounds, check for missing/extra features

IMPORTANT: If previous refinement attempts are shown, learn from them. Do NOT repeat
the same fix that already failed. If a dimension keeps oscillating, re-examine the
overall geometry construction approach rather than tweaking the same parameter.

CRITICAL RULES:
1. Output ONLY the corrected Python code.
2. Make MINIMAL changes — fix only what the feedback identifies as wrong.
3. Keep `result` as the final variable name.
4. Do NOT import ocp_vscode or call show()/save_screenshot()/exporters."""


def refine_geometry(
    code: str,
    feedback: str,
    design_plan: dict,
    prompt: str,
    iteration: int = 0,
    history: list[dict] | None = None,
) -> str:
    """Refiner agent: code + geometric feedback → improved code.

    Args:
        code: Current CadQuery code that executes but has wrong geometry.
        feedback: Structured validation feedback with exact measurements.
        design_plan: Planner output with target dimensions.
        prompt: Original user request.
        iteration: Current refinement iteration number (0-indexed).
        history: List of previous iteration dicts with keys
                 'iteration', 'feedback', 'approach'. Used to prevent
                 the Refiner from repeating failed fixes.
    """
    import json
    from .rag_kb1 import get_api_context

    # Retrieve relevant CadQuery API docs from KB1
    kb1_context = get_api_context(design_plan, prompt)

    # Build iteration history context
    history_text = ""
    if history:
        history_text = "\nPREVIOUS REFINEMENT ATTEMPTS (learn from these — do NOT repeat failed approaches):\n"
        for h in history:
            history_text += f"\n  Iteration {h['iteration']}:\n"
            history_text += f"    Feedback: {h['feedback'][:300]}\n"
            if h.get('approach'):
                history_text += f"    What was tried: {h['approach']}\n"
        history_text += "\n"

    # Escalation guidance for later iterations
    escalation = ""
    if iteration >= 3:
        escalation = """
NOTE: This is refinement attempt #{iteration}. Previous targeted fixes have not resolved the issue.
Consider a more fundamental approach:
- Re-examine whether the overall construction strategy is correct
- Check if features (ears, flanges, gussets) are being positioned correctly
- Consider rebuilding the problematic section from scratch rather than tweaking parameters
""".format(iteration=iteration)

    user_msg = f"""Original request: {prompt}

CURRENT CODE (executes but geometry is wrong):
```python
{code}
```

GEOMETRIC VALIDATION FEEDBACK:
{feedback}
{history_text}{escalation}
{kb1_context}DESIGN PLAN:
{json.dumps(design_plan, indent=2)}

Fix the geometry issues identified above. Make targeted changes based on the exact measurements provided. Output ONLY the corrected Python code."""

    response = _call_claude(REFINER_SYSTEM, user_msg)
    code = response.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code
