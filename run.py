"""Run the AutoFab pipeline on a prompt."""

import json
import sys
from autofab.pipeline import Pipeline


def main():
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "A rectangular mounting plate, 80mm x 60mm x 4mm thick, "
        "with four M3 clearance holes (3.4mm diameter) in a 70mm x 50mm "
        "rectangular pattern centered on the plate."
    )

    pipeline = Pipeline(
        output_dir="outputs",
        max_error_retries=3,
        max_refinement_iterations=5,
        verbose=True,
    )

    result = pipeline.run(prompt, name="test_part")

    print(f"\n{'='*60}")
    print(f"RESULT: {'CONVERGED' if result.converged else 'DID NOT CONVERGE'}")
    print(f"Iterations: {len(result.iterations)}")
    print(f"LLM calls: {result.total_llm_calls}")
    print(f"Total time: {result.total_time_ms/1000:.1f}s")
    if result.final_geometry:
        g = result.final_geometry
        print(f"Final volume: {g['volume']:.1f} mm³")
        bb = g['bounding_box']
        print(f"Final bbox: {bb['xlen']:.1f} x {bb['ylen']:.1f} x {bb['zlen']:.1f} mm")
        print(f"Valid solid: {g['is_valid']}")
    if result.final_step_path:
        print(f"STEP file: {result.final_step_path}")

    # Save full log
    log_path = "outputs/test_part_log.json"
    with open(log_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"Full log: {log_path}")


if __name__ == "__main__":
    main()
