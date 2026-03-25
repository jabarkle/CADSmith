"""Render STL files to PNG images for vision agent inspection.

Uses VTK for proper Phong-shaded 3D rendering with smooth surface
normals, specular highlights, and no visible triangle mesh edges.

Produces a three-view composite image:
  - Left:   Isometric view (elev=35, azim=45)
  - Center: High-angle rear view (elev=65, azim=220) — reveals top-face
            features like holes, bores, cavities
  - Right:  Low front profile (elev=10, azim=0) — shows vertical profile,
            wall heights, gear spacing, slots
"""

import os
import numpy as np


def render_stl_to_png(stl_path: str, png_path: str, title: str = "") -> str:
    """Render an STL file to a three-view composite PNG.

    Three complementary views are placed side-by-side in a single image:
    isometric (left), high-angle rear (center), and front profile (right).

    Args:
        stl_path: Path to the STL file.
        png_path: Output PNG path.
        title: Optional title (unused, kept for API compatibility).

    Returns:
        The png_path on success.
    """
    import vtk

    # Read STL
    reader = vtk.vtkSTLReader()
    reader.SetFileName(stl_path)
    reader.Update()

    # Compute smooth normals, splitting at sharp edges
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(reader.GetOutputPort())
    normals.SetFeatureAngle(30.0)
    normals.SplittingOn()
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()

    # Compute camera framing from mesh bounds
    bounds = normals.GetOutput().GetBounds()
    center = [
        (bounds[0] + bounds[1]) / 2,
        (bounds[2] + bounds[3]) / 2,
        (bounds[4] + bounds[5]) / 2,
    ]
    extent = max(
        bounds[1] - bounds[0],
        bounds[3] - bounds[2],
        bounds[5] - bounds[4],
    )

    def _make_actor():
        """Create a Phong-shaded actor from the STL normals pipeline."""
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.45, 0.68, 0.95)  # Light blue
        actor.GetProperty().SetSpecular(0.3)
        actor.GetProperty().SetSpecularPower(20)
        actor.GetProperty().SetAmbient(0.2)
        actor.GetProperty().SetDiffuse(0.8)
        actor.GetProperty().SetInterpolationToPhong()
        return actor

    def _setup_camera(renderer, elev, azim, zoom=0.85):
        """Position camera at given elevation/azimuth angles."""
        distance = extent * 2.5
        elev_rad = np.radians(elev)
        azim_rad = np.radians(azim)
        cam_x = center[0] + distance * np.cos(elev_rad) * np.cos(azim_rad)
        cam_y = center[1] + distance * np.cos(elev_rad) * np.sin(azim_rad)
        cam_z = center[2] + distance * np.sin(elev_rad)
        camera = renderer.GetActiveCamera()
        camera.SetPosition(cam_x, cam_y, cam_z)
        camera.SetFocalPoint(*center)
        camera.SetViewUp(0, 0, 1)
        renderer.ResetCamera()
        camera.Zoom(zoom)

    # View 1 (left): Isometric — overall shape
    ren1 = vtk.vtkRenderer()
    ren1.AddActor(_make_actor())
    ren1.SetBackground(1.0, 1.0, 1.0)
    ren1.SetViewport(0, 0, 1 / 3, 1.0)
    _setup_camera(ren1, 35, 45)

    # View 2 (center): High-angle rear — top-face features
    ren2 = vtk.vtkRenderer()
    ren2.AddActor(_make_actor())
    ren2.SetBackground(1.0, 1.0, 1.0)
    ren2.SetViewport(1 / 3, 0, 2 / 3, 1.0)
    _setup_camera(ren2, 65, 220)

    # View 3 (right): Low front profile — vertical profile
    ren3 = vtk.vtkRenderer()
    ren3.AddActor(_make_actor())
    ren3.SetBackground(1.0, 1.0, 1.0)
    ren3.SetViewport(2 / 3, 0, 1.0, 1.0)
    _setup_camera(ren3, 10, 0)

    # Offscreen render window
    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)
    render_window.AddRenderer(ren1)
    render_window.AddRenderer(ren2)
    render_window.AddRenderer(ren3)
    render_window.SetSize(2400, 800)
    render_window.Render()

    # Write PNG at 2x resolution
    os.makedirs(os.path.dirname(png_path) if os.path.dirname(png_path) else ".", exist_ok=True)
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(render_window)
    w2i.SetScale(2)
    w2i.Update()

    writer = vtk.vtkPNGWriter()
    writer.SetFileName(png_path)
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()

    render_window.Finalize()

    return png_path
