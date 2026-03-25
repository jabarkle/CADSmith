"""Point-based geometric comparison metrics.

Implements the same metrics as Text-to-CadQuery (arXiv:2505.06507)
for direct comparison with their published results:

  - Chamfer Distance (Eq. 2): avg squared nearest-neighbor distance
  - F1 Score (Eq. 3): bidirectional precision/recall at τ=0.02
  - Volumetric IoU (Eq. 4): voxel intersection-over-union

All metrics operate on STL meshes loaded via trimesh.

Alignment pipeline (applied before metrics):
  1. Bbox center co-registration: both meshes translated so their
     bounding box center is at the origin.
  2. ICP (Iterative Closest Point): optimal rigid-body alignment of
     the generated mesh to the reference, eliminating orientation
     mismatches from different construction coordinate frames.

Two comparison modes:
  - normalize=True (default): Both meshes normalized to [0,1]³ before
    comparison. Measures shape similarity independent of scale.
  - normalize=False: Meshes compared in absolute space (mm). Measures
    both shape and dimensional accuracy. Used for our benchmark
    (explicit mm dimensions).
"""

import numpy as np
import trimesh
from trimesh.registration import icp as trimesh_icp
from scipy.spatial import KDTree
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MeshMetrics:
    """Results from comparing two meshes."""
    chamfer_distance: float       # Lower is better
    f1_score: float               # Higher is better (0-1)
    volumetric_iou: float         # Higher is better (0-1)
    precision: float              # For F1 breakdown
    recall: float                 # For F1 breakdown
    num_points_generated: int
    num_points_reference: int

    def to_dict(self) -> dict:
        return {
            "chamfer_distance": self.chamfer_distance,
            "f1_score": self.f1_score,
            "volumetric_iou": self.volumetric_iou,
            "precision": self.precision,
            "recall": self.recall,
        }


def load_and_normalize(stl_path: str, normalize: bool = True) -> trimesh.Trimesh:
    """Load an STL mesh, optionally normalizing to [0,1]³.

    Args:
        stl_path: Path to the STL file.
        normalize: If True, scale to fit in [0,1]³ unit cube (for shape-only
            comparison). If False, keep absolute coordinates (for dimensional
            accuracy). In BOTH cases, the mesh is translated so its bounding
            box center is at the origin to remove arbitrary offset penalties.
    """
    mesh = trimesh.load(stl_path)

    # ALWAYS co-register by moving bounding box center to origin.
    # This prevents false F1/CD penalties when identical shapes are
    # placed at different origins (e.g. centered=True vs False in CadQuery).
    # We use bbox center rather than centroid because centroid shifts when
    # internal features (holes) differ, while bbox center stays stable.
    bbox_center = (mesh.bounds[0] + mesh.bounds[1]) / 2.0
    mesh.apply_translation(-bbox_center)

    if normalize:
        # Scale to fit in unit cube
        extent = mesh.bounds[1] - mesh.bounds[0]
        max_extent = extent.max()
        if max_extent > 0:
            mesh.apply_scale(1.0 / max_extent)

    return mesh


def sample_points(mesh: trimesh.Trimesh, n_points: int = 10000) -> np.ndarray:
    """Uniformly sample points on the mesh surface."""
    points, _ = trimesh.sample.sample_surface(mesh, n_points)
    return points


def align_icp(
    mesh_gen: trimesh.Trimesh,
    mesh_ref: trimesh.Trimesh,
    n_samples: int = 5000,
    max_iterations: int = 100,
) -> trimesh.Trimesh:
    """Align generated mesh to reference using Iterative Closest Point.

    Finds the optimal rigid-body transformation (rotation + translation)
    to minimize surface distance between the two meshes. Both meshes
    should already be co-registered by bbox center before calling this.

    Args:
        mesh_gen: The generated mesh to be aligned.
        mesh_ref: The reference mesh (target).
        n_samples: Points to sample for ICP alignment.
        max_iterations: Maximum ICP iterations.

    Returns:
        A copy of mesh_gen with the ICP transformation applied.
        Falls back to the original mesh if ICP fails.
    """
    pts_gen = sample_points(mesh_gen, n_samples)
    pts_ref = sample_points(mesh_ref, n_samples)

    try:
        matrix, _transformed, _cost = trimesh_icp(
            pts_gen, pts_ref, max_iterations=max_iterations
        )
        mesh_aligned = mesh_gen.copy()
        mesh_aligned.apply_transform(matrix)
        return mesh_aligned
    except Exception:
        return mesh_gen


def chamfer_distance(points_gen: np.ndarray, points_ref: np.ndarray) -> float:
    """Chamfer Distance (Text-to-CadQuery Eq. 2).

    CD(P,Q) = (1/|P|) Σ min‖p-q‖² + (1/|Q|) Σ min‖q-p‖²

    Both point sets should be from normalized meshes.
    Uses squared distances to match the paper's formulation.
    """
    tree_ref = KDTree(points_ref)
    tree_gen = KDTree(points_gen)

    # Forward: for each generated point, find nearest reference point
    dists_gen_to_ref, _ = tree_ref.query(points_gen)
    # Backward: for each reference point, find nearest generated point
    dists_ref_to_gen, _ = tree_gen.query(points_ref)

    # Squared distances, averaged
    cd = (np.mean(dists_gen_to_ref ** 2) + np.mean(dists_ref_to_gen ** 2))
    return float(cd)


def f1_score(
    points_gen: np.ndarray,
    points_ref: np.ndarray,
    tau: float = 0.02,
) -> tuple[float, float, float]:
    """F1 Score (Text-to-CadQuery Eq. 3).

    A point is "correct" if its nearest neighbor in the other set
    is within distance τ (in normalized [0,1]³ space).

    Precision = fraction of generated points that are correct
    Recall = fraction of reference points that are correct
    F1 = 2 * precision * recall / (precision + recall)

    Returns: (f1, precision, recall)
    """
    tree_ref = KDTree(points_ref)
    tree_gen = KDTree(points_gen)

    dists_gen_to_ref, _ = tree_ref.query(points_gen)
    dists_ref_to_gen, _ = tree_gen.query(points_ref)

    precision = float(np.mean(dists_gen_to_ref < tau))
    recall = float(np.mean(dists_ref_to_gen < tau))

    if precision + recall == 0:
        return 0.0, precision, recall

    f1 = 2 * precision * recall / (precision + recall)
    return float(f1), precision, recall


def volumetric_iou(
    mesh_gen: trimesh.Trimesh,
    mesh_ref: trimesh.Trimesh,
    resolution: float = 0.02,
) -> float:
    """Volumetric IoU (Text-to-CadQuery Eq. 4).

    Voxelize both meshes at the given resolution within [0,1]³,
    then compute intersection / union of occupied voxels.

    Both meshes must already be normalized to [0,1]³.
    """
    # Pad slightly to avoid boundary issues
    pad = resolution
    pitch = resolution

    voxels_gen = mesh_gen.voxelized(pitch=pitch)
    voxels_ref = mesh_ref.voxelized(pitch=pitch)

    # Get filled voxel indices as sets
    indices_gen = set(map(tuple, voxels_gen.sparse_indices))
    indices_ref = set(map(tuple, voxels_ref.sparse_indices))

    intersection = len(indices_gen & indices_ref)
    union = len(indices_gen | indices_ref)

    if union == 0:
        return 0.0

    return float(intersection / union)


def compare_stl(
    generated_stl: str,
    reference_stl: str,
    n_points: int = 10000,
    f1_tau: float = 0.02,
    iou_resolution: float = 0.02,
    normalize: bool = True,
    use_icp: bool = True,
) -> MeshMetrics:
    """Compare two STL files using all three metrics.

    This is the main entry point.

    Args:
        generated_stl: Path to the generated STL file.
        reference_stl: Path to the reference/ground-truth STL file.
        n_points: Number of surface points to sample (default 10K per paper).
        f1_tau: Distance threshold for F1 score. In normalized mode, 0.02
            means 2% of the unit cube. In absolute mode (normalize=False),
            this is in mm — default 1.0mm for engineering tolerance.
        iou_resolution: Voxel pitch for IoU. In normalized mode, 0.02.
            In absolute mode, 1.0mm.
        normalize: If True, normalize both meshes to [0,1]³.
            If False, compare in absolute mm space.
        use_icp: If True, run ICP alignment after bbox centering to find
            the optimal rigid-body transformation. Handles orientation
            mismatches where the generated mesh is geometrically correct
            but built in a different coordinate frame.

    Returns:
        MeshMetrics with all comparison results.
    """
    # Use appropriate defaults for absolute mode
    if not normalize:
        if f1_tau == 0.02:
            f1_tau = 1.0  # 1mm tolerance in absolute space
        if iou_resolution == 0.02:
            iou_resolution = 1.0  # 1mm voxel pitch

    # Load meshes (normalize only if requested; always bbox-centered)
    mesh_gen = load_and_normalize(generated_stl, normalize=normalize)
    mesh_ref = load_and_normalize(reference_stl, normalize=normalize)

    # ICP alignment: find optimal rigid-body transform to align
    # generated mesh to reference, eliminating orientation mismatches
    if use_icp:
        mesh_gen = align_icp(mesh_gen, mesh_ref)

    # Adaptive IoU resolution: cap voxel grid at ~100 subdivisions per axis
    # to prevent OOM on large parts (e.g., 200mm plate at 1mm = 8M voxels).
    # Parts <= 100mm use the original resolution; larger parts scale up.
    max_extent = max(mesh_gen.extents.max(), mesh_ref.extents.max())
    safe_iou_resolution = max(iou_resolution, max_extent / 100.0)

    # Sample surface points
    pts_gen = sample_points(mesh_gen, n_points)
    pts_ref = sample_points(mesh_ref, n_points)

    # Compute metrics
    cd = chamfer_distance(pts_gen, pts_ref)
    f1, prec, rec = f1_score(pts_gen, pts_ref, tau=f1_tau)
    iou = volumetric_iou(mesh_gen, mesh_ref, resolution=safe_iou_resolution)

    return MeshMetrics(
        chamfer_distance=cd,
        f1_score=f1,
        volumetric_iou=iou,
        precision=prec,
        recall=rec,
        num_points_generated=len(pts_gen),
        num_points_reference=len(pts_ref),
    )
