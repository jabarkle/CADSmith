"""KB1: CadQuery API Documentation Knowledge Base.

Curated Workplane method docs, selector syntax reference, and example
patterns — retrieved via keyword matching (same approach as KB2).

The API docs are hardcoded from CadQuery 2.x documentation at
cadquery.readthedocs.io.  This ensures the knowledge base works
regardless of whether CadQuery is importable in the current Python
environment (the executor runs it in a subprocess).

Sources:
  - CadQuery readthedocs (cadquery.readthedocs.io/en/latest/classreference.html)
  - CadQuery selectors reference (cadquery.readthedocs.io/en/latest/selectors.html)
  - CadQuery examples (cadquery.readthedocs.io/en/latest/examples.html)
"""

from dataclasses import dataclass, field


# ===================================================================
# Data structures
# ===================================================================

@dataclass
class APIDoc:
    """A single CadQuery API method/concept documentation entry."""
    name: str                        # e.g. "Workplane.fillet"
    signature: str                   # e.g. "fillet(radius)"
    description: str                 # concise docstring
    category: str                    # grouping key for retrieval
    keywords: list[str] = field(default_factory=list)  # trigger words
    example: str = ""                # short usage example
    notes: str = ""                  # gotchas, tips


@dataclass
class ExampleDoc:
    """A curated CadQuery example with metadata."""
    name: str                        # e.g. "Plate with Hole"
    description: str                 # what it demonstrates
    code: str                        # the actual CadQuery code
    keywords: list[str] = field(default_factory=list)


# ===================================================================
# Selectors reference (always included — compact and critical)
# ===================================================================

SELECTORS_REFERENCE = """## CadQuery Selectors Reference

Selectors filter Faces, Edges, Vertices. Use with .faces(), .edges(), .vertices().

### Direction / Position Selectors
| Selector | Meaning                    | Example                     |
|----------|----------------------------|-----------------------------|
| >Z       | Topmost (max Z)            | .faces(">Z") → top face     |
| <Z       | Bottommost (min Z)         | .faces("<Z") → bottom face  |
| >X       | Rightmost (max X)          | .faces(">X") → right face   |
| <X       | Leftmost (min X)           | .faces("<X") → left face    |
| >Y       | Frontmost (max Y)          | .faces(">Y") → front face   |
| <Y       | Backmost (min Y)           | .faces("<Y") → back face    |
| +Z       | Normal pointing in +Z dir  | .faces("+Z") → upward face  |
| -Z       | Normal pointing in -Z dir  | .faces("-Z") → downward     |

### Parallel / Perpendicular
| Selector | Meaning                        | Example                        |
|----------|--------------------------------|--------------------------------|
| |Z       | Parallel to Z axis             | .edges("|Z") → vertical edges  |
| |X       | Parallel to X axis             | .edges("|X") → left-right edges|
| |Y       | Parallel to Y axis             | .edges("|Y") → front-back edges|
| #Z       | Perpendicular to Z axis        | .edges("#Z") → horizontal edges|
| #X       | Perpendicular to X axis        | .edges("#X")                   |

### Nearest / Type / Radius
| Selector      | Meaning                           |
|---------------|-----------------------------------|
| >>[]          | Nearest to point: .edges(">>[-1,0,0]") |
| %Circle       | Edges of type Circle              |
| %Line         | Edges of type Line                |
| %Plane        | Faces of type Plane               |
| %Cylinder     | Faces of type Cylinder            |

### Combining Selectors
Use `and`, `or`, `not`, `exc` (except/set-difference):
  .edges("|Z and >Y")       → vertical edges on the front
  .edges("not(|Z)")         → all non-vertical edges
  .faces(">Z or <Z")        → top and bottom faces

### Nth Selectors (indexing into ordered results)
| Selector      | Meaning                                        |
|---------------|------------------------------------------------|
| >Z[-2]        | 2nd farthest face/edge (normal-aligned to Z)   |
| <Z[0]         | 1st closest face/edge (normal-aligned to Z)    |
| >>Z[-2]       | 2nd farthest by center position in Z           |
| <<Z[0]        | 1st closest by center position in Z            |

Note: >Z / <Z with index only match faces/edges whose normal is parallel to Z.
>>Z / <<Z with index use center-of-mass distance — works for any orientation.

### Geometry Type Selectors (%)
**Faces:** %PLANE, %CYLINDER, %CONE, %SPHERE, %TORUS, %BEZIER, %BSPLINE, %REVOLUTION, %EXTRUSION, %OFFSET
**Edges:** %LINE, %CIRCLE, %ELLIPSE, %HYPERBOLA, %PARABOLA, %BEZIER, %BSPLINE, %OFFSET

### Custom Direction Selectors
Use arbitrary direction vectors in selector strings:
  .edges(">(-1, 1, 0)")     → edge farthest in (-1, 1, 0) direction
  .faces(">(0, 0.5, 1)")    → face farthest in custom direction

### Selector Objects (programmatic)
  NearestToPointSelector((x,y,z))           → nearest to a point
  BoxSelector((x0,y0,z0), (x1,y1,z1))      → inside a 3D bounding box
  LengthNthSelector(n)                       → nth by length (0=shortest, -1=longest)
  AreaNthSelector(n)                         → nth by area (0=smallest, -1=largest)
  RadiusNthSelector(n)                       → nth by radius (arcs/circles)
  DirectionNthSelector(Vector(0,0,1), n=1)  → nth along direction

### Topological Selectors
  .faces(">Z").edges("<Y").ancestors("Face")  → faces containing the selected edge
  .faces(">Z").siblings("Edge")               → faces sharing edges with top face

### Programmatic Filtering
  .filter(lambda s: s.Volume() <= 3)          → filter by predicate
  .sort(lambda s: s.Volume())[:3]             → sort + slice

### Important Notes
- Non-linear edges (arcs, splines) are NOT returned by direction selectors (+X, |X, etc.)
- Use %Circle or %Line to select curved/straight edges by type
- If a face is not planar, selectors evaluate at its center of mass
- After boolean ops with clean=True, edge references may change — use direction selectors
"""


# ===================================================================
# Workplane API docs — the core ~80 methods
# ===================================================================

WORKPLANE_DOCS: list[APIDoc] = [

    # --- PRIMITIVE 3D SHAPES ---

    APIDoc(
        name="Workplane.box",
        signature="box(length, width, height, centered=(True, True, True), combine=True, clean=True)",
        description="Create a 3D box (rectangular prism). Dimensions are along X, Y, Z respectively. "
                    "The centered parameter controls centering on each axis independently.",
        category="3d_primitives",
        keywords=["box", "cube", "rectangular", "prism", "block", "plate", "brick"],
        example='result = cq.Workplane("XY").box(10, 20, 5)',
        notes="centered can be a tuple of 3 bools: (True, True, False) centers on X,Y but sits on workplane in Z.",
    ),
    APIDoc(
        name="Workplane.sphere",
        signature="sphere(radius, direct=(0,0,1), angle1=-90, angle2=90, angle3=360, centered=(True,True,True), combine=True, clean=True)",
        description="Create a sphere. Can create partial spheres by adjusting angle parameters. "
                    "WARNING: For hemispheres/domes, do NOT use angle1/angle2 with centered — "
                    "the positioning is unreliable. Instead use sphere(R) then .split(keepTop=True).",
        category="3d_primitives",
        keywords=["sphere", "ball", "dome", "hemisphere", "round", "half"],
        example='result = cq.Workplane("XY").sphere(10)',
        notes="For a hemisphere (dome), use: .sphere(R).split(keepTop=True) — NOT angle parameters. "
              "The angle1/angle2 parameters interact unpredictably with centered, producing wrong geometry.",
    ),
    APIDoc(
        name="Workplane.cylinder",
        signature="cylinder(height, radius, direct=(0,0,1), angle=360, centered=(True,True,True), combine=True, clean=True)",
        description="Create a cylinder. Set angle < 360 for a partial cylinder (wedge).",
        category="3d_primitives",
        keywords=["cylinder", "rod", "tube", "pipe", "pillar", "round", "circular"],
        example='result = cq.Workplane("XY").cylinder(20, 5)',
    ),
    APIDoc(
        name="Workplane.wedge",
        signature="wedge(dx, dy, dz, xmin, zmin, xmax, zmax, pnt=(0,0,0), dir=(0,0,1), centered=True, combine=True, clean=True)",
        description="Create a wedge (tapered box). Useful for ramps, tapers.",
        category="3d_primitives",
        keywords=["wedge", "taper", "ramp", "slope", "pyramid"],
    ),

    # --- 2D SKETCH SHAPES ---

    APIDoc(
        name="Workplane.rect",
        signature="rect(xLen, yLen, centered=True, forConstruction=False)",
        description="Draw a rectangle on the current workplane. Creates a closed wire that can be extruded.",
        category="2d_sketch",
        keywords=["rect", "rectangle", "square", "slot", "profile"],
        example='.rect(10, 20).extrude(5)',
    ),
    APIDoc(
        name="Workplane.circle",
        signature="circle(radius, forConstruction=False)",
        description="Draw a circle on the current workplane. Creates a closed wire.",
        category="2d_sketch",
        keywords=["circle", "round", "ring", "disc", "cylinder", "hole", "bore"],
        example='.circle(5).extrude(10)',
    ),
    APIDoc(
        name="Workplane.ellipse",
        signature="ellipse(x_radius, y_radius, rotation_angle=0, forConstruction=False)",
        description="Draw an ellipse on the current workplane.",
        category="2d_sketch",
        keywords=["ellipse", "oval", "elliptical"],
    ),
    APIDoc(
        name="Workplane.polygon",
        signature="polygon(nSides, diameter, forConstruction=False, circumscribed=False)",
        description="Draw a regular polygon inscribed in a circle of the given diameter "
                    "(i.e., diameter = circumscribed circle diameter). "
                    "ALWAYS use this for regular polygon cross-sections (triangle, hex, octagon, etc.) "
                    "instead of manually computing vertices with polyline.",
        category="2d_sketch",
        keywords=["polygon", "hex", "hexagon", "pentagon", "octagon", "triangle", "equilateral",
                  "triangular", "prism", "circumscribed", "inscribed", "regular"],
        example='.polygon(3, 30).extrude(50)  # equilateral triangular prism, circumscribed circle diam=30mm',
        notes="The diameter parameter is the circumscribed circle diameter (vertex-to-vertex). "
              "polygon(3, 30) = equilateral triangle with circumscribed circle diameter 30mm. "
              "polygon(6, 20) = regular hexagon with circumscribed circle diameter 20mm. "
              "Do NOT manually compute vertices — polygon() handles orientation and centering correctly.",
    ),
    APIDoc(
        name="Workplane.slot2D",
        signature="slot2D(length, diameter, angle=0)",
        description="Draw a slot (stadium/oblong shape). Two semicircles connected by straight lines.",
        category="2d_sketch",
        keywords=["slot", "oblong", "stadium", "oval", "elongated"],
    ),
    APIDoc(
        name="Workplane.polyline",
        signature="polyline(listOfXYTuple, forConstruction=False, includeCurrent=False)",
        description="Draw a polyline through a list of (x, y) points. Does NOT close automatically.",
        category="2d_sketch",
        keywords=["polyline", "path", "line", "points", "vertices", "profile"],
        example='.polyline([(0,0), (10,0), (10,5), (0,5)]).close().extrude(3)',
        notes="Call .close() after polyline to close the wire before extruding.",
    ),
    APIDoc(
        name="Workplane.spline",
        signature="spline(listOfXYTuple, tangents=None, periodic=False, forConstruction=False, includeCurrent=False, makeWire=False)",
        description="Draw a spline curve through a list of points. Can specify start/end tangent vectors.",
        category="2d_sketch",
        keywords=["spline", "curve", "smooth", "freeform", "bezier", "interpolate"],
        example='.spline([(0,0), (5,5), (10,0)]).close().extrude(3)',
        notes="For closed splines set periodic=True. tangents is a tuple of two Vectors for start/end direction.",
    ),

    # --- LINE DRAWING ---

    APIDoc(
        name="Workplane.lineTo",
        signature="lineTo(x, y, forConstruction=False)",
        description="Draw a line from the current point to (x, y) in workplane coordinates.",
        category="2d_drawing",
        keywords=["line", "lineto", "draw", "path", "profile"],
    ),
    APIDoc(
        name="Workplane.line",
        signature="line(xDist, yDist, forConstruction=False)",
        description="Draw a line from the current point by a relative offset (dx, dy).",
        category="2d_drawing",
        keywords=["line", "draw", "relative", "offset"],
    ),
    APIDoc(
        name="Workplane.vLine",
        signature="vLine(distance, forConstruction=False)",
        description="Draw a vertical line (relative move in Y).",
        category="2d_drawing",
        keywords=["vline", "vertical", "line", "draw"],
    ),
    APIDoc(
        name="Workplane.hLine",
        signature="hLine(distance, forConstruction=False)",
        description="Draw a horizontal line (relative move in X).",
        category="2d_drawing",
        keywords=["hline", "horizontal", "line", "draw"],
    ),
    APIDoc(
        name="Workplane.moveTo",
        signature="moveTo(x=0, y=0)",
        description="Move to a new point without drawing. Sets the current point for the next drawing operation.",
        category="2d_drawing",
        keywords=["moveto", "move", "jump", "reposition"],
    ),
    APIDoc(
        name="Workplane.close",
        signature="close()",
        description="Close the current wire by drawing a line from the current point back to the start point. "
                    "Required before .extrude() or .revolve() when using line-drawing methods.",
        category="2d_drawing",
        keywords=["close", "finish", "wire", "loop", "seal"],
        notes="Forgetting .close() before .extrude() is a common error → 'outer wire is not closed'.",
    ),

    # --- ARC DRAWING ---

    APIDoc(
        name="Workplane.radiusArc",
        signature="radiusArc(endPoint, radius)",
        description="Draw an arc from the current point to endPoint with the given radius. "
                    "Positive radius = counter-clockwise, negative = clockwise.",
        category="2d_drawing",
        keywords=["arc", "radius", "curve", "circular", "radiusarc"],
        example='.radiusArc((10, 0), 8)  # CCW arc',
        notes="More robust than threePointArc. Radius must be >= half the chord length. "
              "On non-XY workplanes (e.g. XZ for pipe paths), the sign still controls arc "
              "direction but relative to that plane's axes — positive radius on XZ typically "
              "curves toward +Z (upward). Test with a simple arc first if unsure.",
    ),
    APIDoc(
        name="Workplane.sagittaArc",
        signature="sagittaArc(endPoint, sag)",
        description="Draw an arc from current point to endPoint with given sagitta (arc height). "
                    "Positive sag = arc bulges left, negative = right.",
        category="2d_drawing",
        keywords=["arc", "sagitta", "curve", "sagittaarc", "bow"],
    ),
    APIDoc(
        name="Workplane.threePointArc",
        signature="threePointArc(point1, point2)",
        description="Draw an arc from current point through point1 to point2. "
                    "WARNING: Fails with GC_MakeArcOfCircle if points are nearly collinear.",
        category="2d_drawing",
        keywords=["arc", "threepoint", "curve", "threepointarc"],
        notes="AVOID: use radiusArc or sagittaArc instead — threePointArc is fragile with collinear points.",
    ),
    APIDoc(
        name="Workplane.tangentArcPoint",
        signature="tangentArcPoint(endpoint, relative=True)",
        description="Draw an arc tangent to the current edge ending at the given point.",
        category="2d_drawing",
        keywords=["arc", "tangent", "smooth", "continuous"],
    ),

    # --- 3D OPERATIONS ---

    APIDoc(
        name="Workplane.extrude",
        signature="extrude(until, combine=True, clean=True, both=False, taper=None)",
        description="Extrude pending wires by a distance. Creates a solid from 2D sketch. "
                    "Set both=True to extrude symmetrically in both directions (but known to be buggy). "
                    "taper sets a draft angle in degrees.",
        category="3d_operations",
        keywords=["extrude", "pull", "depth", "thickness", "height", "solid", "prism"],
        example='.rect(10, 20).extrude(5)',
        notes="Requires pending wires (from .rect(), .circle(), etc.). "
              "If selecting existing geometry, use .wires().toPending() first.",
    ),
    APIDoc(
        name="Workplane.revolve",
        signature="revolve(angleDegrees=360, axisStart=None, axisEnd=None, combine=True, clean=True)",
        description="Revolve pending wires around an axis to create a solid of revolution. "
                    "Default axis is the workplane's X axis if not specified.",
        category="3d_operations",
        keywords=["revolve", "revolution", "rotate", "lathe", "spin", "turn", "axisymmetric", "pipe"],
        example='.lineTo(5, 0).lineTo(5, 10).lineTo(0, 10).close().revolve(360)',
        notes="For 360-degree revolves, consider using 359.9 degrees to avoid OCCT seam issues.",
    ),
    APIDoc(
        name="Workplane.sweep",
        signature="sweep(path, multisection=False, makeSolid=True, isFrenet=False, combine=True, clean=True, transition='right', auxSpine=None)",
        description="Sweep the pending wire(s) along a path wire to create a solid. "
                    "Path is typically created with .spline() or line drawing on another workplane.",
        category="3d_operations",
        keywords=["sweep", "path", "along", "tube", "pipe", "profile", "rail"],
        notes="The path must be a wire. Use transition='round' for smoother corners. "
              "isFrenet=True uses Frenet frame (better for non-planar paths). "
              "For HOLLOW swept shapes (e.g. pipes), sweep the outer and inner profiles "
              "separately along the same path, then .cut() inner from outer. Do NOT try "
              "to sweep a pre-cut annular profile — it can produce degenerate solids.",
    ),
    APIDoc(
        name="Workplane.loft",
        signature="loft(filled=True, ruled=False, combine=True, clean=True)",
        description="Loft (blend) between two or more pending wire profiles to create a smooth solid. "
                    "Profiles are drawn on workplanes at different heights.",
        category="3d_operations",
        keywords=["loft", "blend", "morph", "transition", "taper", "smooth"],
        example=(
            'result = (cq.Workplane("XY")\n'
            '    .rect(10, 10)\n'
            '    .workplane(offset=20)\n'
            '    .circle(5)\n'
            '    .loft())'
        ),
        notes="Requires at least 2 pending wires. For best results, use same edge count on all profiles.",
    ),

    # --- HOLE OPERATIONS ---

    APIDoc(
        name="Workplane.hole",
        signature="hole(diameter, depth=None, clean=True)",
        description="Create a hole centered on the current point. Default depth goes through the entire part. "
                    "IMPORTANT: For multiple holes on a bolt circle or pattern, use .pushPoints() with all "
                    "positions computed upfront, then call .hole() once. Do NOT loop .faces('>Z').workplane()"
                    ".center(x,y).hole() — after the first hole is cut, .faces('>Z') may select a different "
                    "face (e.g. the hole bottom), causing subsequent holes to be misplaced or missing.",
        category="holes",
        keywords=["hole", "drill", "bore", "through", "opening"],
        example='.faces(">Z").workplane().pushPoints([(x1,y1),(x2,y2)]).hole(10)',
    ),
    APIDoc(
        name="Workplane.cboreHole",
        signature="cboreHole(diameter, cboreDiameter, cboreDepth, depth=None, clean=True)",
        description="Create a counterbored hole. The counterbore is a larger-diameter recess at the top.",
        category="holes",
        keywords=["counterbore", "cbore", "hole", "bolt", "screw", "socket", "recess"],
        example='.faces(">Z").workplane().cboreHole(2.4, 4.4, 2.1)',
    ),
    APIDoc(
        name="Workplane.cskHole",
        signature="cskHole(diameter, cskDiameter, cskAngle, depth=None, clean=True)",
        description="Create a countersunk hole. The countersink is a conical taper at the top.",
        category="holes",
        keywords=["countersink", "csk", "hole", "flathead", "screw", "taper"],
        example='.faces(">Z").workplane().cskHole(2.4, 4.4, 82)',
    ),

    # --- EDGE/FACE MODIFICATION ---

    APIDoc(
        name="Workplane.fillet",
        signature="fillet(radius)",
        description="Round (fillet) the selected edges with the given radius. "
                    "Radius must be less than half the shortest adjacent edge length.",
        category="modification",
        keywords=["fillet", "round", "radius", "edge", "smooth", "blend"],
        example='.edges("|Z").fillet(1)',
        notes="Common failure: StdFail_NotDone means radius is too large. "
              "Apply BEFORE boolean operations if possible. Wrap in try/except for safety.",
    ),
    APIDoc(
        name="Workplane.chamfer",
        signature="chamfer(length, length2=None)",
        description="Chamfer (bevel) the selected edges. One length = symmetric 45° chamfer. "
                    "Two lengths = asymmetric chamfer.",
        category="modification",
        keywords=["chamfer", "bevel", "edge", "cut", "angle", "45"],
        example='.edges("|Z").chamfer(0.5)',
    ),
    APIDoc(
        name="Workplane.shell",
        signature="shell(thickness, kind='arc')",
        description="Hollow out a solid, leaving walls of the specified thickness. "
                    "Select faces to remove BEFORE calling .shell(). "
                    "Positive thickness = shell outward (outer dims grow), "
                    "negative thickness = shell inward (outer dims preserved).",
        category="modification",
        keywords=["shell", "hollow", "thin", "wall", "thickness", "empty", "box"],
        example='.faces(">Z").shell(-2)  # remove top face, shell inward 2mm (preserves outer dims)',
        notes="Shell BEFORE applying fillets. Negative thickness = inward (most common). "
              "Select the face(s) to remove: .faces('>Z').shell(thickness).",
    ),

    # --- BOOLEAN / COMBINING ---

    APIDoc(
        name="Workplane.cut",
        signature="cut(toCut, clean=True, tol=None)",
        description="Boolean subtraction: remove toCut from the current solid.",
        category="boolean",
        keywords=["cut", "subtract", "remove", "boolean", "difference", "minus"],
        example='result = base.cut(tool)',
        notes="Use clean=False if fillet fails after cut. Use tol=1e-3 for fuzzy boolean.",
    ),
    APIDoc(
        name="Workplane.union",
        signature="union(toUnion=None, clean=True, tol=None)",
        description="Boolean union: merge two solids together.",
        category="boolean",
        keywords=["union", "add", "merge", "combine", "join", "fuse", "boolean"],
        example='result = part1.union(part2)',
    ),
    APIDoc(
        name="Workplane.intersect",
        signature="intersect(toIntersect, clean=True, tol=None)",
        description="Boolean intersection: keep only the overlapping volume.",
        category="boolean",
        keywords=["intersect", "common", "overlap", "boolean", "and"],
    ),

    # --- WORKPLANE MANAGEMENT ---

    APIDoc(
        name="Workplane.workplane",
        signature="workplane(offset=0.0, invert=False, centerOption='CenterOfMass', origin=None)",
        description="Create a new workplane. Often used after .faces() to position a new sketch.",
        category="workplane",
        keywords=["workplane", "plane", "offset", "level", "layer", "stack"],
        example='.faces(">Z").workplane().rect(5, 5).extrude(3)',
        notes="centerOption can be 'CenterOfMass', 'CenterOfBoundBox', or 'ProjectedOrigin'.",
    ),
    APIDoc(
        name="Workplane.workplaneFromTagged",
        signature="workplaneFromTagged(name)",
        description="Restore a previously tagged workplane by name.",
        category="workplane",
        keywords=["tag", "tagged", "restore", "workplane", "reference"],
    ),
    APIDoc(
        name="Workplane.transformed",
        signature="transformed(rotate=(0,0,0), offset=(0,0,0))",
        description="Create a new workplane that is rotated and/or offset from the current one.",
        category="workplane",
        keywords=["transform", "rotate", "offset", "angle", "tilt", "incline"],
        example='.transformed(rotate=(45, 0, 0)).rect(5, 5).extrude(3)',
    ),
    APIDoc(
        name="Workplane.copyWorkplane",
        signature="copyWorkplane(obj)",
        description="Copy the workplane from another Workplane object. Useful for aligning two workplanes.",
        category="workplane",
        keywords=["copy", "workplane", "align", "match"],
    ),

    # --- FACE / EDGE SELECTION ---

    APIDoc(
        name="Workplane.faces",
        signature="faces(selector=None, tag=None)",
        description="Select faces of the current solid. Use selector strings like '>Z', '<X', '|Y'.",
        category="selection",
        keywords=["faces", "face", "select", "filter", "top", "bottom", "side"],
        example='.faces(">Z")  # select the topmost face',
    ),
    APIDoc(
        name="Workplane.edges",
        signature="edges(selector=None, tag=None)",
        description="Select edges of the current solid. Use selector strings like '|Z', '>X'.",
        category="selection",
        keywords=["edges", "edge", "select", "filter", "vertical", "horizontal"],
        example='.edges("|Z")  # select all vertical edges',
    ),
    APIDoc(
        name="Workplane.vertices",
        signature="vertices(selector=None, tag=None)",
        description="Select vertices of the current solid.",
        category="selection",
        keywords=["vertices", "vertex", "point", "corner", "select"],
    ),
    APIDoc(
        name="Workplane.wires",
        signature="wires(selector=None, tag=None)",
        description="Select wires from the current solid.",
        category="selection",
        keywords=["wires", "wire", "loop", "boundary", "outline"],
    ),

    # --- POSITIONING / TRANSFORM ---

    APIDoc(
        name="Workplane.translate",
        signature="translate(vec)",
        description="Translate (move) the current solid by a vector (x, y, z).",
        category="transform",
        keywords=["translate", "move", "shift", "offset", "position", "displace"],
        example='.translate((10, 0, 0))  # move 10mm in X',
    ),
    APIDoc(
        name="Workplane.rotate",
        signature="rotate(axisStartPoint, axisEndPoint, angleDegrees)",
        description="Rotate the solid around an axis defined by two points, by angleDegrees.",
        category="transform",
        keywords=["rotate", "turn", "spin", "angle", "degrees", "orientation"],
        example='.rotate((0,0,0), (0,0,1), 45)  # rotate 45° around Z axis',
    ),
    APIDoc(
        name="Workplane.rotateAboutCenter",
        signature="rotateAboutCenter(axisEndPoint, angleDegrees)",
        description="Rotate about the center of the current workplane.",
        category="transform",
        keywords=["rotate", "center", "spin", "angle"],
    ),
    APIDoc(
        name="Workplane.mirror",
        signature="mirror(mirrorPlane='XY', basePointVector=(0,0,0), union=False)",
        description="Mirror the solid about a plane. Set union=True to keep both halves.",
        category="transform",
        keywords=["mirror", "reflect", "symmetry", "symmetric", "flip"],
        example='.mirror("YZ", union=True)  # mirror across YZ plane, keep both halves',
    ),

    # --- MULTI-POINT OPERATIONS ---

    APIDoc(
        name="Workplane.pushPoints",
        signature="pushPoints(pntList)",
        description="Set multiple points as current working points. Subsequent operations "
                    "(circle, hole, etc.) are performed at each point.",
        category="multi_point",
        keywords=["pushpoints", "pattern", "array", "multiple", "repeat", "grid"],
        example='.pushPoints([(0,0), (10,0), (10,10), (0,10)]).circle(1).extrude(2)',
    ),
    APIDoc(
        name="Workplane.rarray",
        signature="rarray(xSpacing, ySpacing, xCount, yCount, center=True)",
        description="Create a rectangular array of points centered on the current point.",
        category="multi_point",
        keywords=["array", "grid", "rectangular", "pattern", "repeat", "matrix"],
        example='.rarray(10, 10, 3, 3).circle(2).extrude(5)  # 3x3 grid of cylinders',
    ),
    APIDoc(
        name="Workplane.polarArray",
        signature="polarArray(radius, startAngle, angle, count, fill=True, rotate=True)",
        description="Create a polar (circular) array of points.",
        category="multi_point",
        keywords=["polar", "circular", "radial", "array", "pattern", "bolt", "ring"],
        example='.polarArray(20, 0, 360, 6).circle(2).extrude(5)  # 6 cylinders in a ring',
    ),

    # --- UTILITY / OTHER ---

    APIDoc(
        name="Workplane.tag",
        signature="tag(name)",
        description="Tag the current workplane state so it can be restored later with .workplaneFromTagged().",
        category="utility",
        keywords=["tag", "save", "bookmark", "reference", "name"],
        example='.tag("base_plane")',
    ),
    APIDoc(
        name="Workplane.val",
        signature="val()",
        description="Return the first object on the stack (typically a Shape/Solid). "
                    "Useful for extracting the underlying OCCT shape for analysis.",
        category="utility",
        keywords=["val", "value", "shape", "solid", "extract", "get"],
    ),
    APIDoc(
        name="Workplane.vals",
        signature="vals()",
        description="Return all objects on the stack as a list.",
        category="utility",
        keywords=["vals", "values", "all", "list", "stack"],
    ),
    APIDoc(
        name="Workplane.toPending",
        signature="toPending()",
        description="Register selected wires as pending wires for extrude/revolve/loft. "
                    "Required when selecting existing geometry via .faces()/.wires() before extruding.",
        category="utility",
        keywords=["pending", "wire", "register", "extrude", "topending"],
        example='.faces(">Z").wires().toPending().workplane().extrude(5)',
        notes="This is needed when .faces() or .wires() selects existing geometry — "
              "those selections don't auto-register as pending wires.",
    ),
    APIDoc(
        name="Workplane.split",
        signature="split(keepTop=False, keepBottom=False)",
        description="Split the solid using the current workplane as a cutting plane. "
                    "keepTop=True keeps the part above the plane, keepBottom=True keeps below.",
        category="3d_operations",
        keywords=["split", "cut", "slice", "divide", "half", "hemisphere", "dome", "top", "bottom"],
        example='.sphere(20).split(keepTop=True)  # upper hemisphere',
        notes="The idiomatic way to create a hemisphere: create a full sphere, then split. "
              "Example: cq.Workplane('XY').workplane(offset=3).sphere(20).split(keepTop=True) "
              "creates an upper hemisphere sitting at z=3.",
    ),
    APIDoc(
        name="Workplane.offset2D",
        signature="offset2D(d, kind='arc', forConstruction=False)",
        description="Offset the current 2D wire(s) by distance d. "
                    "Positive = outward, negative = inward.",
        category="2d_sketch",
        keywords=["offset", "expand", "shrink", "inset", "outset", "grow"],
    ),
    APIDoc(
        name="Workplane.section",
        signature="section(height=0.0)",
        description="Create a cross-section of the solid at the given height.",
        category="3d_operations",
        keywords=["section", "cross", "slice", "profile", "intersection"],
    ),
    APIDoc(
        name="Workplane.text",
        signature="text(txt, fontsize, distance, cut=True, combine=False, clean=True, font='Arial', fontPath=None, kind='regular', halign='center', valign='center')",
        description="Create 3D text. Can be cut into or combined with the solid.",
        category="3d_operations",
        keywords=["text", "font", "letter", "engrave", "emboss", "label", "write"],
        example='.faces(">Z").workplane().text("HELLO", 10, 1)',
    ),

    # --- NAMED WORKPLANES ---

    APIDoc(
        name="Workplane (constructor)",
        signature='Workplane(inPlane="XY", origin=(0,0,0), obj=None)',
        description="Create a new Workplane. inPlane can be: XY, YZ, ZX, XZ, YX, ZY, "
                    "front, back, left, right, top, bottom.",
        category="workplane",
        keywords=["workplane", "plane", "origin", "start", "initial", "create", "front", "top", "xy"],
        example='cq.Workplane("XY")  # horizontal plane at origin',
        notes=(
            "Named planes and their normal directions:\n"
            "  XY/front → +Z normal    YZ → +X normal    ZX → +Y normal\n"
            "  XZ/bottom → -Y normal   YX → -Z normal    ZY → -X normal\n"
            "  top → +Y normal (X right, Z toward you)\n"
            "  right → +X normal      left → -X normal"
        ),
    ),

    # --- EACH / ITERATION ---

    APIDoc(
        name="Workplane.each",
        signature="each(callback, useLocalCoordinates=False, combine=True, clean=True)",
        description="Apply a callback function to each item on the stack. "
                    "The callback receives a Shape and should return a Shape.",
        category="utility",
        keywords=["each", "iterate", "map", "apply", "callback", "custom"],
    ),
    APIDoc(
        name="Workplane.eachpoint",
        signature="eachpoint(callback, useLocalCoordinates=False, combine=True, clean=True)",
        description="Apply a callback at each point on the stack. "
                    "Useful for placing custom geometry at multiple locations.",
        category="utility",
        keywords=["eachpoint", "iterate", "place", "at", "point", "custom"],
    ),

    # --- CENTER / POINT MANAGEMENT ---

    APIDoc(
        name="Workplane.center",
        signature="center(x, y)",
        description="Shift the workplane center by (x, y) in local coordinates.",
        category="workplane",
        keywords=["center", "move", "offset", "origin", "shift"],
    ),
    APIDoc(
        name="Workplane.vertices",
        signature="vertices(selector=None, tag=None)",
        description="Select vertices from the current solid.",
        category="selection",
        keywords=["vertices", "vertex", "corner", "point"],
    ),

    # --- MISSING 3D OPERATIONS ---

    APIDoc(
        name="Workplane.cutBlind",
        signature="cutBlind(until, clean=True, both=False, taper=None)",
        description="Cut (subtractive extrude) into the solid to a given depth. "
                    "Negative values cut into the solid. Can also use 'next' or 'last' to cut to a face.",
        category="3d_operations",
        keywords=["cut", "blind", "pocket", "groove", "recess", "subtract", "depth", "slot"],
        example='.faces(">Z").workplane().rect(5, 5).cutBlind(-3)',
        notes="Use negative depth to cut into the solid. 'next' cuts to the next face, 'last' to the furthest.",
    ),
    APIDoc(
        name="Workplane.cutThruAll",
        signature="cutThruAll(clean=True, taper=0)",
        description="Cut through the entire part using pending wires. Equivalent to cutBlind through all material.",
        category="3d_operations",
        keywords=["cut", "through", "thru", "all", "slot", "hole", "pierce", "penetrate"],
        example='.faces(">Z").workplane().rect(5, 2).cutThruAll()',
    ),
    APIDoc(
        name="Workplane.twistExtrude",
        signature="twistExtrude(distance, angleDegrees, combine=True, clean=True)",
        description="Extrude pending wires while rotating them by angleDegrees over the given distance. "
                    "Creates twisted/helical solids.",
        category="3d_operations",
        keywords=["twist", "extrude", "helical", "spiral", "rotate", "screw", "gear"],
        example='.polygon(6, 10).twistExtrude(20, 90)',
    ),

    # --- MISSING 2D OPERATIONS ---

    APIDoc(
        name="Workplane.bezier",
        signature="bezier(listOfXYTuple, forConstruction=False, includeCurrent=False)",
        description="Draw a bezier curve through the given control points.",
        category="2d_sketch",
        keywords=["bezier", "curve", "control", "smooth", "freeform"],
    ),
    APIDoc(
        name="Workplane.parametricCurve",
        signature="parametricCurve(func, N=400, start=0, stop=1, makeWire=True, tol=1e-3)",
        description="Draw a curve from a parametric function func(t) -> (x, y). "
                    "The function maps t in [start, stop] to 2D workplane coordinates.",
        category="2d_sketch",
        keywords=["parametric", "curve", "function", "custom", "gear", "cam", "profile"],
        example='.parametricCurve(lambda t: (cos(t*2*pi)*5, sin(t*2*pi)*5))',
    ),
    APIDoc(
        name="Workplane.ellipseArc",
        signature="ellipseArc(x_radius, y_radius, angle1=0, angle2=360, rotation_angle=0, sense=1, forConstruction=False, startAtCurrent=True, makeWire=False)",
        description="Draw an elliptical arc.",
        category="2d_sketch",
        keywords=["ellipse", "arc", "partial", "oval"],
    ),
    APIDoc(
        name="Workplane.vLineTo",
        signature="vLineTo(yCoord, forConstruction=False)",
        description="Draw a vertical line to the given Y coordinate (absolute).",
        category="2d_drawing",
        keywords=["vline", "vertical", "line", "absolute", "to"],
    ),
    APIDoc(
        name="Workplane.hLineTo",
        signature="hLineTo(xCoord, forConstruction=False)",
        description="Draw a horizontal line to the given X coordinate (absolute).",
        category="2d_drawing",
        keywords=["hline", "horizontal", "line", "absolute", "to"],
    ),
    APIDoc(
        name="Workplane.polarLine",
        signature="polarLine(distance, angle, forConstruction=False)",
        description="Draw a line at the given angle (degrees) from the current point, for the given distance.",
        category="2d_drawing",
        keywords=["polar", "line", "angle", "direction", "diagonal"],
    ),
    APIDoc(
        name="Workplane.polarLineTo",
        signature="polarLineTo(distance, angle, forConstruction=False)",
        description="Draw a line to a point specified in polar coordinates from the workplane origin.",
        category="2d_drawing",
        keywords=["polar", "line", "angle", "absolute"],
    ),
    APIDoc(
        name="Workplane.move",
        signature="move(xDist, yDist)",
        description="Move the current drawing point by a relative offset without drawing a line.",
        category="2d_drawing",
        keywords=["move", "relative", "jump", "skip"],
    ),
    APIDoc(
        name="Workplane.mirrorY",
        signature="mirrorY()",
        description="Mirror pending 2D wires around the Y axis of the workplane. "
                    "Useful for building symmetric profiles — draw one half, then mirror.",
        category="2d_sketch",
        keywords=["mirror", "symmetry", "symmetric", "half", "reflect", "profile", "mirrory"],
        example='.hLine(5).vLine(3).hLine(-5).mirrorY().extrude(1)',
    ),
    APIDoc(
        name="Workplane.mirrorX",
        signature="mirrorX()",
        description="Mirror pending 2D wires around the X axis of the workplane.",
        category="2d_sketch",
        keywords=["mirror", "symmetry", "symmetric", "reflect", "mirrorx"],
    ),
    APIDoc(
        name="Workplane.wire",
        signature="wire(forConstruction=False)",
        description="Convert pending edges into a wire. Rarely needed — .close() usually suffices.",
        category="2d_drawing",
        keywords=["wire", "edges", "convert", "pending"],
    ),

    # --- STACK / UTILITY ---

    APIDoc(
        name="Workplane.all",
        signature="all()",
        description="Return all items on the stack as a list of individual Workplane objects.",
        category="utility",
        keywords=["all", "list", "iterate", "stack", "items"],
    ),
    APIDoc(
        name="Workplane.size",
        signature="size()",
        description="Return the number of items on the stack.",
        category="utility",
        keywords=["size", "count", "length", "stack"],
    ),
    APIDoc(
        name="Workplane.first",
        signature="first()",
        description="Return the first item on the stack as a Workplane.",
        category="utility",
        keywords=["first", "head", "stack"],
    ),
    APIDoc(
        name="Workplane.last",
        signature="last()",
        description="Return the last item on the stack as a Workplane.",
        category="utility",
        keywords=["last", "tail", "stack"],
    ),
    APIDoc(
        name="Workplane.item",
        signature="item(i)",
        description="Return the ith item on the stack as a Workplane.",
        category="utility",
        keywords=["item", "index", "stack", "get"],
    ),
    APIDoc(
        name="Workplane.end",
        signature="end(n=1)",
        description="Return the nth parent in the chain. Useful for going back up the operation chain.",
        category="utility",
        keywords=["end", "parent", "back", "undo", "chain"],
    ),
    APIDoc(
        name="Workplane.add",
        signature="add(obj)",
        description="Add a Workplane, shape, or list of shapes to the stack.",
        category="utility",
        keywords=["add", "append", "stack", "combine"],
    ),
    APIDoc(
        name="Workplane.combine",
        signature="combine(clean=True, glue=False, tol=None)",
        description="Combine all solids on the stack into one via boolean union.",
        category="boolean",
        keywords=["combine", "merge", "union", "all", "stack"],
    ),
    APIDoc(
        name="Workplane.consolidateWires",
        signature="consolidateWires()",
        description="Try to merge all wires on the stack into a single wire.",
        category="utility",
        keywords=["consolidate", "merge", "wire", "join"],
    ),

    # --- SELECTION ---

    APIDoc(
        name="Workplane.solids",
        signature="solids(selector=None, tag=None)",
        description="Select solids from the current compound/assembly.",
        category="selection",
        keywords=["solids", "solid", "body", "select"],
    ),
    APIDoc(
        name="Workplane.shells",
        signature="shells(selector=None, tag=None)",
        description="Select shells from the current solid.",
        category="selection",
        keywords=["shells", "shell", "surface", "select"],
    ),
    APIDoc(
        name="Workplane.compounds",
        signature="compounds(selector=None, tag=None)",
        description="Select compounds from the current object.",
        category="selection",
        keywords=["compounds", "compound", "group", "select"],
    ),

    # --- TOPOLOGICAL SELECTION ---

    APIDoc(
        name="Workplane.ancestors",
        signature="ancestors(kind)",
        description="Select ancestor shapes containing the current selection. "
                    "e.g. select an edge, then .ancestors('Face') to get faces containing that edge.",
        category="selection",
        keywords=["ancestors", "parent", "containing", "topology", "face", "edge"],
        example='.faces(">Z").edges("<Y").ancestors("Face")',
    ),
    APIDoc(
        name="Workplane.siblings",
        signature="siblings(kind, level=1)",
        description="Select sibling shapes that share sub-shapes with the current selection. "
                    "e.g. select a face, then .siblings('Edge') for adjacent faces.",
        category="selection",
        keywords=["siblings", "adjacent", "neighbor", "connected", "topology"],
        example='.faces(">Z").siblings("Edge")',
    ),
    APIDoc(
        name="Workplane.filter",
        signature="filter(callback)",
        description="Filter stack items by a predicate function. "
                    "The callback receives a Shape and returns True/False.",
        category="utility",
        keywords=["filter", "predicate", "select", "custom", "conditional"],
        example='.filter(lambda s: s.Volume() <= 3)',
    ),
    APIDoc(
        name="Workplane.sort",
        signature="sort(key)",
        description="Sort stack items by a key function. Supports slicing after sort.",
        category="utility",
        keywords=["sort", "order", "rank", "key", "custom"],
        example='.sort(lambda s: s.Volume())[:3]  # 3 smallest by volume',
    ),

    # --- EXPORT ---

    APIDoc(
        name="Workplane.export",
        signature="export(fname, exportType=None, tolerance=0.1, angularTolerance=0.1)",
        description="Export the solid to a file. Format is inferred from extension: "
                    ".step, .stl, .svg, .brep, .gltf, .vrml.",
        category="export",
        keywords=["export", "save", "file", "step", "stl", "output", "write"],
        example='result.export("output.step")',
    ),
]


# ===================================================================
# Sketch API docs
# ===================================================================

SKETCH_DOCS: list[APIDoc] = [
    APIDoc(
        name="Sketch (constructor)",
        signature="cq.Sketch()",
        description="Create a standalone Sketch for 2D sketching. Use face-based or edge-based approach. "
                    "Can also be started inline: .faces('>Z').sketch()...finalize()",
        category="sketch",
        keywords=["sketch", "2d", "profile", "draw", "face"],
        example='s = cq.Sketch().rect(10, 5).circle(2, mode="s")',
    ),
    APIDoc(
        name="Sketch.rect",
        signature="rect(w, h, angle=0, mode='a', tag=None)",
        description="Add a rectangle to the sketch. mode controls boolean: 'a'=add, 's'=subtract, 'i'=intersect, 'c'=construction.",
        category="sketch",
        keywords=["sketch", "rect", "rectangle", "square"],
    ),
    APIDoc(
        name="Sketch.circle",
        signature="circle(r, mode='a', tag=None)",
        description="Add a circle to the sketch.",
        category="sketch",
        keywords=["sketch", "circle", "round", "hole"],
    ),
    APIDoc(
        name="Sketch.ellipse",
        signature="ellipse(a1, a2, angle=0, mode='a', tag=None)",
        description="Add an ellipse to the sketch.",
        category="sketch",
        keywords=["sketch", "ellipse", "oval"],
    ),
    APIDoc(
        name="Sketch.trapezoid",
        signature="trapezoid(w, h, a1, a2=None, angle=0, mode='a', tag=None)",
        description="Add a trapezoid to the sketch. a1/a2 are the side angles in degrees.",
        category="sketch",
        keywords=["sketch", "trapezoid", "shape"],
    ),
    APIDoc(
        name="Sketch.slot",
        signature="slot(w, h, angle=0, mode='a', tag=None)",
        description="Add a slot (stadium/oblong) shape to the sketch.",
        category="sketch",
        keywords=["sketch", "slot", "oblong", "stadium"],
    ),
    APIDoc(
        name="Sketch.regularPolygon",
        signature="regularPolygon(r, n, angle=0, mode='a', tag=None)",
        description="Add a regular polygon with n sides inscribed in a circle of radius r.",
        category="sketch",
        keywords=["sketch", "polygon", "hex", "regular", "triangle"],
    ),
    APIDoc(
        name="Sketch.polygon",
        signature="polygon(pts, angle=0, mode='a', tag=None)",
        description="Add a polygon defined by a list of (x, y) points.",
        category="sketch",
        keywords=["sketch", "polygon", "points", "custom"],
    ),
    APIDoc(
        name="Sketch.hull",
        signature="hull(mode='a', tag=None)",
        description="Compute the convex hull of the current selection.",
        category="sketch",
        keywords=["sketch", "hull", "convex", "envelope"],
    ),
    APIDoc(
        name="Sketch.offset (Sketch)",
        signature="offset(d, mode='a', tag=None)",
        description="Offset selected wires/edges by distance d. Positive=outward, negative=inward.",
        category="sketch",
        keywords=["sketch", "offset", "expand", "shrink", "inset"],
    ),
    APIDoc(
        name="Sketch.fillet (Sketch)",
        signature="fillet(d)",
        description="Fillet selected vertices in the sketch with radius d.",
        category="sketch",
        keywords=["sketch", "fillet", "round", "corner"],
        example='.rect(10, 5).vertices().fillet(1)',
    ),
    APIDoc(
        name="Sketch.chamfer (Sketch)",
        signature="chamfer(d)",
        description="Chamfer selected vertices in the sketch with distance d.",
        category="sketch",
        keywords=["sketch", "chamfer", "bevel", "corner"],
    ),

    # --- Sketch arrays ---

    APIDoc(
        name="Sketch.rarray",
        signature="rarray(xs, ys, nx, ny)",
        description="Create a rectangular array of locations in the sketch. "
                    "Subsequent operations apply at all array points.",
        category="sketch",
        keywords=["sketch", "rarray", "array", "grid", "rectangular", "pattern"],
        example='cq.Sketch().rarray(10, 10, 3, 3).circle(2)',
    ),
    APIDoc(
        name="Sketch.parray",
        signature="parray(r, a1, da, n, rotate=True)",
        description="Create a polar array of locations in the sketch.",
        category="sketch",
        keywords=["sketch", "parray", "polar", "circular", "array", "ring"],
    ),
    APIDoc(
        name="Sketch.push",
        signature="push(locs, tag=None)",
        description="Push specific locations onto the sketch selection for subsequent operations.",
        category="sketch",
        keywords=["sketch", "push", "locations", "points"],
    ),
    APIDoc(
        name="Sketch.distribute",
        signature="distribute(n, start=0, stop=1, rotate=True)",
        description="Distribute n locations evenly along the currently selected edges/wires.",
        category="sketch",
        keywords=["sketch", "distribute", "along", "edge", "wire", "spacing"],
        example='cq.Sketch().circle(5).wires().distribute(8).circle(0.5)',
    ),

    # --- Sketch edge-based ---

    APIDoc(
        name="Sketch.segment",
        signature="segment(p1, p2, tag=None) / segment(p2, tag=None) / segment(length, angle, tag=None)",
        description="Draw a line segment in the sketch. Three forms: two-point, from-current-point, or polar.",
        category="sketch",
        keywords=["sketch", "segment", "line", "edge"],
    ),
    APIDoc(
        name="Sketch.arc (Sketch)",
        signature="arc(p1, p2, p3, tag=None) / arc(center, r, angle, da, tag=None)",
        description="Draw an arc in the sketch. Three-point form or center+radius+angles form.",
        category="sketch",
        keywords=["sketch", "arc", "curve", "circular"],
    ),
    APIDoc(
        name="Sketch.assemble",
        signature="assemble(mode='a', tag=None)",
        description="Convert pending sketch edges into a face. Required after edge-based sketching.",
        category="sketch",
        keywords=["sketch", "assemble", "edges", "face", "build"],
    ),
    APIDoc(
        name="Sketch.constrain",
        signature="constrain(tag1, [tag2,] kind, param)",
        description="Add a geometric constraint between sketch entities. "
                    "Kinds: Fixed, FixedPoint, Coincident, Angle, Length, Distance, Radius, Orientation, ArcAngle.",
        category="sketch",
        keywords=["sketch", "constrain", "constraint", "parametric", "solve"],
    ),
    APIDoc(
        name="Sketch.solve",
        signature="solve()",
        description="Solve all sketch constraints. Call after adding constraints, before .assemble().",
        category="sketch",
        keywords=["sketch", "solve", "constraint", "parametric"],
    ),

    # --- Sketch selection/state ---

    APIDoc(
        name="Sketch.reset",
        signature="reset()",
        description="Clear the current sketch selection. Required before boolean operators on Sketch objects.",
        category="sketch",
        keywords=["sketch", "reset", "clear", "selection"],
    ),
    APIDoc(
        name="Sketch.select",
        signature="select(*tags)",
        description="Select sketch entities by tag name.",
        category="sketch",
        keywords=["sketch", "select", "tag", "named"],
    ),
    APIDoc(
        name="Sketch.clean (Sketch)",
        signature="clean()",
        description="Remove internal wires from the sketch face. Useful after complex boolean operations.",
        category="sketch",
        keywords=["sketch", "clean", "internal", "wires"],
    ),
    APIDoc(
        name="Sketch.delete",
        signature="delete()",
        description="Delete the currently selected sketch objects.",
        category="sketch",
        keywords=["sketch", "delete", "remove"],
    ),

    # --- Sketch integration ---

    APIDoc(
        name="Workplane.sketch",
        signature="sketch()",
        description="Enter sketch mode on the current workplane face. "
                    "Must call .finalize() to return to Workplane operations.",
        category="sketch",
        keywords=["sketch", "enter", "mode", "face", "inline"],
        example='.faces(">Z").sketch().rect(5, 5).finalize().extrude(2)',
    ),
    APIDoc(
        name="Sketch.finalize",
        signature="finalize()",
        description="Exit sketch mode and return to the parent Workplane. "
                    "The sketch result becomes pending wires for extrude/cut operations.",
        category="sketch",
        keywords=["sketch", "finalize", "exit", "done", "return"],
    ),
    APIDoc(
        name="Workplane.placeSketch",
        signature="placeSketch(*sketches)",
        description="Place one or more pre-built Sketch objects onto the current workplane. "
                    "Can place multiple sketches at different heights for lofting.",
        category="sketch",
        keywords=["sketch", "place", "loft", "multiple", "profile"],
        example=(
            's1 = cq.Sketch().rect(10, 10).vertices().fillet(1)\n'
            's2 = cq.Sketch().circle(3)\n'
            'result = cq.Workplane().placeSketch(s1, s2.moved(z=10)).loft()'
        ),
    ),
]


# ===================================================================
# Assembly API docs
# ===================================================================

ASSEMBLY_DOCS: list[APIDoc] = [
    APIDoc(
        name="Assembly (constructor)",
        signature="cq.Assembly(obj=None, loc=None, name=None, color=None)",
        description="Create an assembly. Assemblies combine multiple shapes with constraints and colors.",
        category="assembly",
        keywords=["assembly", "multi", "part", "component", "combine", "group"],
        example='assy = cq.Assembly(box, name="base", color=cq.Color("red"))',
    ),
    APIDoc(
        name="Assembly.add",
        signature="add(obj, loc=None, name=None, color=None)",
        description="Add a Shape, Workplane, or sub-Assembly to this assembly.",
        category="assembly",
        keywords=["assembly", "add", "part", "component", "insert"],
    ),
    APIDoc(
        name="Assembly.constrain",
        signature="constrain(id1, [id2,] kind, param=None)",
        description="Add a constraint between assembly parts. "
                    "Kinds: Plane, Point, Axis, PointInPlane, Fixed, FixedPoint, FixedAxis, PointOnLine, FixedRotation. "
                    "Use 'name?face@selector' syntax for sub-shape selection.",
        category="assembly",
        keywords=["assembly", "constrain", "constraint", "align", "mate", "position"],
        example='assy.constrain("base?faces@>Z", "top?faces@<Z", "Plane")',
    ),
    APIDoc(
        name="Assembly.solve",
        signature="solve(verbosity=0)",
        description="Solve all assembly constraints to position the parts.",
        category="assembly",
        keywords=["assembly", "solve", "position", "constraint"],
    ),
    APIDoc(
        name="Assembly.save",
        signature="save(path, exportType=None, mode='default', tolerance=0.1, angularTolerance=0.1)",
        description="Save the assembly to a file. Supported types: STEP, XML, XBF, GLTF, VTKJS, VRML, STL. "
                    "mode='fused' merges all parts (STEP only).",
        category="assembly",
        keywords=["assembly", "save", "export", "step", "gltf", "file"],
    ),
    APIDoc(
        name="Assembly.toCompound",
        signature="toCompound()",
        description="Convert the assembly to a single Compound shape.",
        category="assembly",
        keywords=["assembly", "compound", "convert", "merge", "flatten"],
    ),
    APIDoc(
        name="Color",
        signature="cq.Color(name) / cq.Color(r, g, b, a=0)",
        description="Create a color for assembly visualization. Named colors from OCCT (e.g. 'red', 'blue', 'green').",
        category="assembly",
        keywords=["color", "assembly", "visual", "display", "red", "blue", "green"],
    ),
]


# ===================================================================
# Shape class method docs (for validation, analysis, low-level ops)
# ===================================================================

SHAPE_DOCS: list[APIDoc] = [
    APIDoc(
        name="Shape.Area",
        signature="shape.Area()",
        description="Return the surface area of the shape as a float.",
        category="shape_analysis",
        keywords=["area", "surface", "measure", "size", "shape"],
    ),
    APIDoc(
        name="Shape.Volume",
        signature="shape.Volume(tol=None)",
        description="Return the volume of the shape as a float.",
        category="shape_analysis",
        keywords=["volume", "size", "measure", "capacity", "shape"],
    ),
    APIDoc(
        name="Shape.BoundingBox",
        signature="shape.BoundingBox()",
        description="Return the axis-aligned bounding box. Access .xmin, .xmax, .ymin, .ymax, .zmin, .zmax, "
                    ".xlen, .ylen, .zlen, .center (Vector).",
        category="shape_analysis",
        keywords=["bounding", "box", "bounds", "extents", "size", "dimensions", "center"],
        example='bb = result.val().BoundingBox(); print(bb.xlen, bb.ylen, bb.zlen)',
    ),
    APIDoc(
        name="Shape.Center",
        signature="shape.Center()",
        description="Return the center of mass of the shape as a Vector.",
        category="shape_analysis",
        keywords=["center", "mass", "centroid", "midpoint", "position"],
    ),
    APIDoc(
        name="Shape.isValid",
        signature="shape.isValid()",
        description="Check if the shape is topologically valid.",
        category="shape_analysis",
        keywords=["valid", "check", "verify", "topology", "repair"],
    ),
    APIDoc(
        name="Shape.geomType",
        signature="shape.geomType()",
        description="Return the geometry type string: 'Solid', 'PLANE', 'LINE', 'CIRCLE', etc.",
        category="shape_analysis",
        keywords=["type", "geometry", "kind", "classify"],
    ),
    APIDoc(
        name="Shape.distance",
        signature="shape.distance(other)",
        description="Return the minimum distance between this shape and another shape.",
        category="shape_analysis",
        keywords=["distance", "gap", "clearance", "closest", "minimum"],
    ),
    APIDoc(
        name="Solid.isInside",
        signature="solid.isInside(point, tolerance=1e-6)",
        description="Check if a point (x, y, z) is inside the solid.",
        category="shape_analysis",
        keywords=["inside", "contains", "point", "containment", "test"],
    ),
    APIDoc(
        name="Face.normalAt",
        signature="face.normalAt(locationVector=None)",
        description="Return the outward normal vector at a point on the face. "
                    "No argument = normal at center of face.",
        category="shape_analysis",
        keywords=["normal", "direction", "perpendicular", "face", "orientation"],
    ),
    APIDoc(
        name="Shape.scale",
        signature="shape.scale(factor)",
        description="Scale the shape by a factor. Returns a new scaled shape.",
        category="shape_transform",
        keywords=["scale", "resize", "enlarge", "shrink", "factor"],
    ),
    APIDoc(
        name="Shape.moved",
        signature="shape.moved(loc)",
        description="Return a copy of the shape moved by a Location (relative transform). "
                    "Can pass multiple Locations to create a Compound of copies.",
        category="shape_transform",
        keywords=["moved", "copy", "translate", "location", "duplicate"],
        example='copy = shape.moved(cq.Location(cq.Vector(10, 0, 0)))',
    ),
    APIDoc(
        name="Shape.located",
        signature="shape.located(loc)",
        description="Return a copy of the shape at an absolute Location.",
        category="shape_transform",
        keywords=["located", "absolute", "position", "location"],
    ),

    # --- Low-level constructors ---

    APIDoc(
        name="Solid.makeBox",
        signature="cq.Solid.makeBox(length, width, height, pnt=(0,0,0), dir=(0,0,1))",
        description="Create a solid box directly (bypassing Workplane). Corner at pnt, aligned to dir.",
        category="shape_primitive",
        keywords=["makebox", "box", "solid", "primitive", "direct"],
    ),
    APIDoc(
        name="Solid.makeCylinder",
        signature="cq.Solid.makeCylinder(radius, height, pnt=(0,0,0), dir=(0,0,1), angleDegrees=360)",
        description="Create a solid cylinder directly.",
        category="shape_primitive",
        keywords=["makecylinder", "cylinder", "solid", "primitive", "direct"],
    ),
    APIDoc(
        name="Solid.makeSphere",
        signature="cq.Solid.makeSphere(radius, pnt=(0,0,0), dir=(0,0,1), angle1=-90, angle2=90, angle3=360)",
        description="Create a solid sphere directly.",
        category="shape_primitive",
        keywords=["makesphere", "sphere", "solid", "primitive", "direct"],
    ),
    APIDoc(
        name="Solid.makeCone",
        signature="cq.Solid.makeCone(radius1, radius2, height, pnt=(0,0,0), dir=(0,0,1), angleDegrees=360)",
        description="Create a solid cone or frustum directly.",
        category="shape_primitive",
        keywords=["makecone", "cone", "frustum", "solid", "primitive", "direct", "taper"],
    ),
    APIDoc(
        name="Solid.makeTorus",
        signature="cq.Solid.makeTorus(radius1, radius2, pnt=(0,0,0), dir=(0,0,1), angle1=0, angle2=360)",
        description="Create a solid torus (donut) directly. radius1=major, radius2=minor.",
        category="shape_primitive",
        keywords=["maketorus", "torus", "donut", "ring", "solid", "primitive"],
    ),
    APIDoc(
        name="Solid.makeLoft",
        signature="cq.Solid.makeLoft(listOfWire, ruled=False)",
        description="Create a lofted solid from a list of wires.",
        category="shape_primitive",
        keywords=["makeloft", "loft", "wire", "solid", "blend"],
    ),
    APIDoc(
        name="Solid.extrudeLinear",
        signature="cq.Solid.extrudeLinear(outerWire, innerWires, vecNormal, taper=0)",
        description="Extrude wires linearly to create a solid. Low-level alternative to Workplane.extrude.",
        category="shape_primitive",
        keywords=["extrude", "linear", "wire", "solid", "direct"],
    ),
    APIDoc(
        name="Edge.makeLine",
        signature="cq.Edge.makeLine(v1, v2)",
        description="Create a line edge between two Vector points.",
        category="shape_primitive",
        keywords=["edge", "line", "make", "segment", "direct"],
    ),
    APIDoc(
        name="Edge.makeSpline",
        signature="cq.Edge.makeSpline(listOfVector, tangents=None, periodic=False)",
        description="Create a spline edge through a list of Vector points.",
        category="shape_primitive",
        keywords=["edge", "spline", "make", "curve", "direct"],
    ),
    APIDoc(
        name="Wire.makeHelix",
        signature="cq.Wire.makeHelix(pitch, height, radius, center=(0,0,0), dir=(0,0,1), angle=360)",
        description="Create a helical wire. Useful as a sweep path for threads/springs.",
        category="shape_primitive",
        keywords=["helix", "spiral", "thread", "spring", "coil", "wire", "path"],
    ),
    APIDoc(
        name="Face.makeFromWires",
        signature="cq.Face.makeFromWires(outerWire, innerWires=[])",
        description="Create a face from an outer wire and optional inner wires (holes).",
        category="shape_primitive",
        keywords=["face", "wire", "make", "surface", "direct"],
    ),
]


# ===================================================================
# Geometry class docs
# ===================================================================

GEOMETRY_DOCS: list[APIDoc] = [
    APIDoc(
        name="Vector",
        signature="cq.Vector(x, y, z) / cq.Vector((x, y, z)) / cq.Vector(x, y)",
        description="3D vector. Supports arithmetic (+, -, multiply), normalized(), "
                    "projectToLine(), projectToPlane(). Access .x, .y, .z properties.",
        category="geometry",
        keywords=["vector", "point", "direction", "xyz", "coordinate"],
    ),
    APIDoc(
        name="Location",
        signature="cq.Location(vec) / cq.Location(x, y, z, rx, ry, rz) / cq.Location(plane) / cq.Location(vec, axis, angle)",
        description="Represents a position + orientation transform. "
                    "Compose with *: combined = loc1 * loc2. "
                    "Convert with .toTuple() → ((tx,ty,tz), (rx,ry,rz)).",
        category="geometry",
        keywords=["location", "transform", "position", "orientation", "placement"],
    ),
    APIDoc(
        name="Plane",
        signature="cq.Plane(origin, xDir=None, normal=(0,0,1)) / cq.Plane.named('XY') / cq.Plane.XY()",
        description="A coordinate plane in 3D space. Use .toLocalCoords(obj) and .toWorldCoords((x,y)) "
                    "for coordinate conversion. .rotated((rx, ry, rz)) creates a rotated copy.",
        category="geometry",
        keywords=["plane", "coordinate", "system", "local", "world", "convert"],
    ),
    APIDoc(
        name="BoundBox",
        signature="shape.BoundingBox()",
        description="Axis-aligned bounding box. Properties: xmin, xmax, ymin, ymax, zmin, zmax, "
                    "xlen, ylen, zlen, center. Methods: add(obj), enlarge(tol), isInside(other_bb).",
        category="geometry",
        keywords=["boundbox", "bounding", "box", "extents", "dimensions", "size"],
    ),
]


# ===================================================================
# Curated examples
# ===================================================================

EXAMPLES: list[ExampleDoc] = [
    ExampleDoc(
        name="Simple Rectangular Plate",
        description="Basic box creation",
        code='result = cq.Workplane("front").box(2.0, 2.0, 0.5)',
        keywords=["box", "plate", "simple", "basic"],
    ),
    ExampleDoc(
        name="Plate with Hole",
        description="Box with a through-hole centered on the top face",
        code=(
            'length = 80.0\n'
            'height = 60.0\n'
            'thickness = 10.0\n'
            'center_hole_dia = 22.0\n'
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .box(length, height, thickness)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .hole(center_hole_dia)\n'
            ')'
        ),
        keywords=["box", "hole", "plate", "through", "bore"],
    ),
    ExampleDoc(
        name="Extruded Prismatic Solid",
        description="Circle and rect drawn on same workplane then extruded together",
        code='result = cq.Workplane("front").circle(2.0).rect(0.5, 0.75).extrude(0.5)',
        keywords=["extrude", "circle", "rect", "profile", "prism"],
    ),
    ExampleDoc(
        name="Building Profile with Lines and Arcs",
        description="Drawing a custom 2D profile using line methods",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .lineTo(2.0, 0)\n'
            '    .lineTo(2.0, 1.0)\n'
            '    .threePointArc((1.0, 1.5), (0.0, 1.0))\n'
            '    .close()\n'
            '    .extrude(0.25)\n'
            ')'
        ),
        keywords=["line", "arc", "profile", "custom", "draw", "lineto"],
    ),
    ExampleDoc(
        name="Polygon Array of Holes",
        description="Using pushPoints to create multiple holes",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .box(4.0, 4.0, 0.25)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .pushPoints([(0, 0.75), (0, -0.75)])\n'
            '    .hole(0.5)\n'
            ')'
        ),
        keywords=["pushpoints", "hole", "pattern", "array", "multiple"],
    ),
    ExampleDoc(
        name="Creating Workplanes on Faces",
        description="Selecting a face and creating a new workplane for additional features",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .box(3, 2, 0.5)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .hole(0.5)\n'
            ')'
        ),
        keywords=["face", "workplane", "select", "feature", "hole"],
    ),
    ExampleDoc(
        name="Shelling to Create Thin Walls",
        description="Hollowing out a box to create a container",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .box(3, 2, 1)\n'
            '    .faces(">Z")\n'
            '    .shell(0.1)\n'
            ')'
        ),
        keywords=["shell", "hollow", "thin", "wall", "container", "box"],
    ),
    ExampleDoc(
        name="Making Lofts",
        description="Loft between a rectangle and a circle at different heights",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .box(4.0, 4.0, 0.25)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .rect(3.0, 3.0)\n'
            '    .workplane(offset=3.0)\n'
            '    .circle(1.0)\n'
            '    .loft(combine=True)\n'
            ')'
        ),
        keywords=["loft", "blend", "transition", "taper", "shape"],
    ),
    ExampleDoc(
        name="Counterbored and Countersunk Holes",
        description="Different hole types on a plate",
        code=(
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .box(4, 2, 0.5)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .center(-1.5, 0)\n'
            '    .cboreHole(0.15, 0.25, 0.1)\n'
            '    .center(1.5, 0)\n'
            '    .cskHole(0.15, 0.25, 82)\n'
            ')'
        ),
        keywords=["counterbore", "countersink", "hole", "bolt", "screw", "cbore", "csk"],
    ),
    ExampleDoc(
        name="Regular Polygon Prism (Triangular, Hexagonal, etc.)",
        description="Use polygon(nSides, diameter) for any regular polygon cross-section. "
                    "The diameter is the circumscribed circle diameter.",
        code=(
            '# Equilateral triangular prism: circumscribed circle diam = 30mm, height = 50mm\n'
            'result = cq.Workplane("XY").polygon(3, 30).extrude(50)\n\n'
            '# Regular hexagonal prism: circumscribed circle diam = 20mm\n'
            '# result = cq.Workplane("XY").polygon(6, 20).extrude(30)\n\n'
            '# Regular octagonal prism: circumscribed circle diam = 40mm\n'
            '# result = cq.Workplane("XY").polygon(8, 40).extrude(25)'
        ),
        keywords=["polygon", "triangle", "triangular", "hexagon", "hexagonal", "octagon",
                  "octagonal", "prism", "regular", "equilateral", "circumscribed"],
    ),
    ExampleDoc(
        name="Sphere Split (Hemisphere Technique)",
        description="Create a hemisphere by making a full sphere and splitting it. "
                    "Do NOT use sphere angle parameters for hemispheres.",
        code=(
            '# Half-sphere on a cylindrical pedestal\n'
            'pedestal = cq.Workplane("XY").circle(15).extrude(5)\n'
            'half_sphere = cq.Workplane("XY").workplane(offset=5).sphere(15).split(keepTop=True)\n'
            'result = pedestal.union(half_sphere)'
        ),
        keywords=["dome", "hemisphere", "sphere", "split", "half", "cap", "round", "top"],
    ),
    ExampleDoc(
        name="Filleting Edges",
        description="Rounding vertical edges of a box",
        code='result = cq.Workplane("XY").box(3, 3, 0.5).edges("|Z").fillet(0.125)',
        keywords=["fillet", "round", "edge", "smooth", "box"],
    ),
    ExampleDoc(
        name="Offset Workplanes",
        description="Building features at different heights using workplane offset",
        code=(
            'result = (\n'
            '    cq.Workplane("front")\n'
            '    .box(3, 2, 0.5)\n'
            '    .faces(">Z")\n'
            '    .workplane(offset=0.5)\n'
            '    .rect(1.5, 1.0)\n'
            '    .extrude(0.5)\n'
            ')'
        ),
        keywords=["offset", "workplane", "stack", "level", "height", "step"],
    ),
    ExampleDoc(
        name="Mirroring Symmetric Geometry",
        description="Build half a shape then mirror it",
        code=(
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .moveTo(10, 0)\n'
            '    .lineTo(5, 0)\n'
            '    .threePointArc((3.9393, 0.4393), (3.5, 1.5))\n'
            '    .threePointArc((3.0607, 2.5607), (2, 3))\n'
            '    .lineTo(1.5, 3)\n'
            '    .threePointArc((0.4393, 3.4393), (0, 4.5))\n'
            '    .lineTo(0, 13.5)\n'
            '    .threePointArc((0.4393, 14.5607), (1.5, 15))\n'
            '    .lineTo(28, 15)\n'
            '    .lineTo(28, 13.5)\n'
            '    .lineTo(24, 13.5)\n'
            '    .lineTo(24, 11.5)\n'
            '    .lineTo(27, 11.5)\n'
            '    .lineTo(27, 10)\n'
            '    .lineTo(22, 10)\n'
            '    .lineTo(22, 13.5)\n'
            '    .lineTo(14, 13.5)\n'
            '    .lineTo(14, 11.5)\n'
            '    .lineTo(17, 11.5)\n'
            '    .lineTo(17, 10)\n'
            '    .lineTo(12, 10)\n'
            '    .lineTo(12, 13.5)\n'
            '    .lineTo(6, 13.5)\n'
            '    .lineTo(6, 11.5)\n'
            '    .lineTo(9, 11.5)\n'
            '    .lineTo(9, 10)\n'
            '    .lineTo(4, 10)\n'
            '    .lineTo(4, 13.5)\n'
            '    .lineTo(2, 13.5)\n'
            '    .threePointArc((1.0607, 13.0607), (0.5, 12))\n'
            '    .lineTo(0.5, 6)\n'
            '    .threePointArc((1.0607, 4.9393), (2, 4.5))\n'
            '    .lineTo(5, 4.5)\n'
            '    .threePointArc((6.0607, 4.0607), (6.5, 3))\n'
            '    .lineTo(6.5, 1.5)\n'
            '    .threePointArc((7.0607, 0.4393), (8, 0))\n'
            '    .lineTo(10, 0)\n'
            '    .mirrorY()\n'
            '    .extrude(0.5)\n'
            ')'
        ),
        keywords=["mirror", "symmetry", "half", "reflect", "profile"],
    ),
    ExampleDoc(
        name="Parametric Block with Central Hole and Corner Fasteners",
        description="Demonstrates parametric variables, central hole, corner counterbore pattern, and fillet",
        code=(
            'length = 40\n'
            'width = 25\n'
            'thickness = 8\n'
            'center_hole = 16\n'
            'bolt_diam = 3.0\n'
            'cbore_diam = 5.5\n'
            'cbore_depth = 2.5\n\n'
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .box(length, width, thickness)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .hole(center_hole)\n'
            '    .faces(">Z")\n'
            '    .workplane()\n'
            '    .rect(length - 10, width - 10, forConstruction=True)\n'
            '    .vertices()\n'
            '    .cboreHole(bolt_diam, cbore_diam, cbore_depth)\n'
            '    .edges("|Z")\n'
            '    .fillet(2.0)\n'
            ')'
        ),
        keywords=["parametric", "bolt", "counterbore", "fillet", "complete", "fastener", "hole", "pattern"],
    ),
    ExampleDoc(
        name="Half-Cylinder (Arc Profile Extruded)",
        description="Create a half-cylinder or trough by drawing a semicircular arc "
                    "cross-section and extruding it. Use radiusArc to draw the semicircle, "
                    "close the profile, then extrude along the perpendicular axis. "
                    "Do NOT use cylinder(angle=180) — it produces unreliable geometry.",
        code=(
            '# Solid half-cylinder: semicircular profile on XZ, extruded along Y\n'
            'result = (\n'
            '    cq.Workplane("XZ")\n'
            '    .radiusArc((40, 0), -20)  # arc from origin to (2*r, 0), radius=-r\n'
            '    .lineTo(0, 0)             # close the flat side\n'
            '    .close()\n'
            '    .extrude(60)              # extrude along Y\n'
            ')\n'
            '# For a hollow half-pipe, subtract a smaller concentric arc:\n'
            '# inner = cq.Workplane("XZ").moveTo(t, 0).radiusArc((2*r - t, 0), -(r - t)).lineTo(t, 0).close().extrude(L)\n'
            '# result = outer.cut(inner)'
        ),
        keywords=["half", "cylinder", "semicircular", "arc", "trough", "pipe", "half-pipe",
                  "half-cylinder", "channel", "gutter", "radiusArc"],
    ),
    ExampleDoc(
        name="Two-Body Union with Inner Fillet",
        description="Joining two rectangular bodies at a right angle with a fillet at the junction",
        code=(
            '# Two perpendicular plates joined with a fillet\n'
            'plate_a = cq.Workplane("XY").box(5, 30, 60, centered=(True, True, False))\n'
            'plate_b = cq.Workplane("XY").box(35, 30, 5, centered=(False, True, False))\n'
            'result = plate_a.union(plate_b)\n'
            '# Fillet the inner junction edge\n'
            'result = result.edges("|Y").edges(">Z").edges("<X").fillet(3)'
        ),
        keywords=["union", "join", "two", "parts", "fillet", "junction", "perpendicular", "angle"],
    ),

    # --- Additional examples from documentation ---

    ExampleDoc(
        name="Parametric Enclosure (Lid + Body)",
        description="Rounded enclosure with shelled interior — demonstrates rect extrude, "
                    "edge fillet by selector, shell by face subtraction, and parametric variables.",
        code=(
            'p_outerWidth, p_outerLength, p_outerHeight = 100.0, 150.0, 50.0\n'
            'p_thickness = 3.0\n'
            'p_sideRadius, p_topAndBottomRadius = 10.0, 2.0\n\n'
            'oshell = (\n'
            '    cq.Workplane("XY")\n'
            '    .rect(p_outerWidth, p_outerLength)\n'
            '    .extrude(p_outerHeight)\n'
            ')\n'
            'oshell = oshell.edges("|Z").fillet(p_sideRadius)\n'
            'oshell = oshell.edges("#Z").fillet(p_topAndBottomRadius)\n\n'
            'ishell = (\n'
            '    oshell.faces("<Z").workplane(p_thickness, True)\n'
            '    .rect(p_outerWidth - 2*p_thickness, p_outerLength - 2*p_thickness)\n'
            '    .extrude(p_outerHeight - 2*p_thickness, False)\n'
            ')\n'
            'ishell = ishell.edges("|Z").fillet(p_sideRadius - p_thickness)\n'
            'result = oshell.cut(ishell)'
        ),
        keywords=["enclosure", "box", "shell", "fillet", "parametric", "container", "case",
                  "housing", "rounded", "hollow", "thickness"],
    ),
    ExampleDoc(
        name="Lego Brick",
        description="Parametric LEGO brick with bumps — demonstrates shell, rarray, and stacking features.",
        code=(
            'lbumps, wbumps = 6, 2\n'
            'pitch, bumpDiam, bumpHeight = 8.0, 4.8, 1.8\n'
            'height = 3.2\n'
            't = (pitch - bumpDiam) / 2.0 - 0.1\n'
            'total_length = lbumps * pitch - 0.2\n'
            'total_width = wbumps * pitch - 0.2\n\n'
            's = cq.Workplane("XY").box(total_length, total_width, height)\n'
            's = s.faces("<Z").shell(-1.0 * t)\n'
            'result = (\n'
            '    s.faces(">Z").workplane()\n'
            '    .rarray(pitch, pitch, lbumps, wbumps, True)\n'
            '    .circle(bumpDiam / 2.0)\n'
            '    .extrude(bumpHeight)\n'
            ')'
        ),
        keywords=["lego", "brick", "bump", "array", "rarray", "shell", "grid", "pattern", "toy"],
    ),
    ExampleDoc(
        name="Cycloidal Gear (parametricCurve + twistExtrude)",
        description="Complex gear profile using parametric curves and twist extrusion.",
        code=(
            'from math import sin, cos, pi, floor\n\n'
            'def hypocycloid(t, r1, r2):\n'
            '    return ((r1-r2)*cos(t) + r2*cos(r1/r2*t - t),\n'
            '            (r1-r2)*sin(t) + r2*sin(-(r1/r2*t - t)))\n\n'
            'def epicycloid(t, r1, r2):\n'
            '    return ((r1+r2)*cos(t) - r2*cos(r1/r2*t + t),\n'
            '            (r1+r2)*sin(t) - r2*sin(r1/r2*t + t))\n\n'
            'def gear(t, r1=4, r2=1):\n'
            '    if (-1)**(1 + floor(t/2/pi*(r1/r2))) < 0:\n'
            '        return epicycloid(t, r1, r2)\n'
            '    else:\n'
            '        return hypocycloid(t, r1, r2)\n\n'
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .parametricCurve(lambda t: gear(t*2*pi, 6, 1))\n'
            '    .twistExtrude(15, 90)\n'
            '    .faces(">Z").workplane()\n'
            '    .circle(2).cutThruAll()\n'
            ')'
        ),
        keywords=["gear", "parametric", "curve", "twist", "extrude", "cycloidal", "helical",
                  "complex", "profile", "mechanical"],
    ),
    ExampleDoc(
        name="Classic OCC Bottle",
        description="The classic OpenCASCADE bottle tutorial — demonstrates threePointArc, mirrorX, "
                    "shell, workplane centerOption, and multi-step modeling.",
        code=(
            '(L, w, t) = (20.0, 6.0, 3.0)\n'
            's = cq.Workplane("XY")\n'
            'p = (\n'
            '    s.center(-L/2.0, 0)\n'
            '    .vLine(w/2.0)\n'
            '    .threePointArc((L/2.0, w/2.0 + t), (L, w/2.0))\n'
            '    .vLine(-w/2.0)\n'
            '    .mirrorX()\n'
            '    .extrude(30.0, True)\n'
            ')\n'
            'p = p.faces(">Z").workplane(centerOption="CenterOfMass").circle(3.0).extrude(2.0, True)\n'
            'result = p.faces(">Z").shell(0.3)'
        ),
        keywords=["bottle", "arc", "mirror", "shell", "classic", "tutorial", "neck",
                  "centerofmass", "workplane"],
    ),
    ExampleDoc(
        name="I-Beam (Polyline + Mirror)",
        description="Structural I-beam using polyline for half-profile, then mirror.",
        code=(
            '(L, H, W, t) = (100.0, 20.0, 20.0, 1.0)\n'
            'pts = [\n'
            '    (0, H/2.0), (W/2.0, H/2.0), (W/2.0, H/2.0 - t),\n'
            '    (t/2.0, H/2.0 - t), (t/2.0, t - H/2.0),\n'
            '    (W/2.0, t - H/2.0), (W/2.0, H/-2.0), (0, H/-2.0),\n'
            ']\n'
            'result = cq.Workplane("front").polyline(pts).mirrorY().extrude(L)'
        ),
        keywords=["ibeam", "beam", "structural", "polyline", "mirror", "profile", "cross",
                  "section", "steel", "extrude"],
    ),
    ExampleDoc(
        name="Sketch In-Place (Extrude from Sketch on Face)",
        description="Inline sketch on a face — demonstrates .sketch()/.finalize() pattern with "
                    "regularPolygon, subtract mode, vertex fillet.",
        code=(
            'result = (\n'
            '    cq.Workplane().box(5, 5, 1)\n'
            '    .faces(">Z").sketch()\n'
            '    .regularPolygon(2, 3, tag="outer")\n'
            '    .regularPolygon(1.5, 3, mode="s")\n'
            '    .vertices(tag="outer").fillet(0.2)\n'
            '    .finalize()\n'
            '    .extrude(0.5)\n'
            ')'
        ),
        keywords=["sketch", "inline", "face", "finalize", "polygon", "subtract", "fillet",
                  "vertex", "triangle"],
    ),
    ExampleDoc(
        name="Loft Between Two Sketches",
        description="Lofting between two Sketch profiles at different heights using placeSketch.",
        code=(
            's1 = cq.Sketch().trapezoid(3, 1, 110).vertices().fillet(0.2)\n'
            's2 = cq.Sketch().rect(2, 1).vertices().fillet(0.2)\n'
            'result = cq.Workplane().placeSketch(s1, s2.moved(z=3)).loft()'
        ),
        keywords=["loft", "sketch", "place", "two", "profiles", "blend", "transition",
                  "trapezoid", "moved"],
    ),
    ExampleDoc(
        name="Tagging and Workplane Recovery (with selectors)",
        description="Using .tag() to save state and reference tagged geometry in selectors.",
        code=(
            'result = (\n'
            '    cq.Workplane("XY")\n'
            '    .polygon(3, 5).extrude(4).tag("prism")\n'
            '    .sphere(10)\n'
            '    .faces("<X", tag="prism").workplane().circle(1).cutThruAll()\n'
            '    .faces(">X", tag="prism").faces(">Y").workplane().circle(1).cutThruAll()\n'
            ')'
        ),
        keywords=["tag", "tagged", "workplane", "restore", "reference", "selector", "prism",
                  "sphere", "complex"],
    ),
    ExampleDoc(
        name="3D Mirroring with Union",
        description="Mirror a solid across a face and union the result.",
        code=(
            'result = cq.Workplane("XY").line(0, 1).line(1, 0).line(0, -0.5).close().extrude(1)\n'
            'result = result.mirror(result.faces(">X"), union=True)'
        ),
        keywords=["mirror", "3d", "union", "face", "reflect", "symmetric", "copy"],
    ),
    ExampleDoc(
        name="2D Wire Offset for Bolt Hole Pattern",
        description="Offset existing edges inward to create a bolt hole pattern that follows the part outline.",
        code=(
            'result = (\n'
            '    cq.Workplane().box(4, 2, 0.5)\n'
            '    .faces(">Z").edges().toPending()\n'
            '    .offset2D(-0.25, forConstruction=True)\n'
            '    .vertices()\n'
            '    .cboreHole(0.125, 0.25, 0.125, depth=None)\n'
            ')'
        ),
        keywords=["offset", "bolt", "hole", "pattern", "wire", "inset", "topending",
                  "counterbore", "edge"],
    ),
    ExampleDoc(
        name="Swept Hollow Pipe Elbow (90-degree bend)",
        description="Create a hollow 90-degree pipe elbow by sweeping circular profiles along "
                    "an arc path on the XZ plane. The key pattern: sweep outer circle and inner "
                    "circle separately along the SAME path, then cut inner from outer. "
                    "Do NOT sweep a pre-cut annular ring — it can produce degenerate solids.",
        code=(
            'import cadquery as cq\n'
            'bend_r = 40.0   # bend centerline radius\n'
            'pipe_or = 10.0  # outer radius\n'
            'pipe_ir = 8.0   # inner radius (2mm wall)\n'
            '\n'
            '# Path: quarter-circle arc on XZ plane\n'
            'path = cq.Workplane("XZ").radiusArc((bend_r, bend_r), bend_r)\n'
            '\n'
            '# Sweep outer and inner profiles separately, then cut\n'
            'outer = cq.Workplane("XY").circle(pipe_or).sweep(path)\n'
            'inner = cq.Workplane("XY").circle(pipe_ir).sweep(path)\n'
            'result = outer.cut(inner)'
        ),
        keywords=["sweep", "pipe", "elbow", "bend", "hollow", "tube", "arc",
                  "radiusArc", "path", "plumbing", "fitting"],
    ),
]


# ===================================================================
# Keyword-matching retrieval
# ===================================================================

def _extract_keywords(text: str) -> set[str]:
    """Extract lowercase words from a text string for matching."""
    import re
    # Split on non-alphanumeric, keep meaningful words
    words = set(re.findall(r'[a-z][a-z0-9_]*', text.lower()))
    # Remove very short or very common words
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'has', 'have', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'shall', 'can',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'it', 'its', 'this', 'that', 'these', 'those',
        'and', 'or', 'but', 'not', 'no', 'nor',
        'if', 'then', 'else', 'when', 'up', 'so', 'than',
        'all', 'each', 'every', 'both', 'few', 'more',
        'as', 'into', 'about', 'out', 'use', 'using',
        'mm', 'cm', 'true', 'false', 'none', 'null',
    }
    return words - stopwords


def _score_doc(doc: APIDoc, query_keywords: set[str]) -> int:
    """Score how relevant a doc is to the query keywords."""
    doc_keywords = set(kw.lower() for kw in doc.keywords)
    # Direct keyword overlap (highest signal)
    overlap = query_keywords & doc_keywords
    score = len(overlap) * 3

    # Check if method name appears in query
    method_lower = doc.name.split('.')[-1].lower()
    if method_lower in query_keywords:
        score += 10  # strong match: user explicitly mentioned this method

    # Check description words
    desc_words = _extract_keywords(doc.description)
    desc_overlap = query_keywords & desc_words
    score += len(desc_overlap)

    return score


def _score_example(example: ExampleDoc, query_keywords: set[str]) -> int:
    """Score how relevant an example is to the query keywords."""
    ex_keywords = set(kw.lower() for kw in example.keywords)
    overlap = query_keywords & ex_keywords
    score = len(overlap) * 3

    desc_words = _extract_keywords(example.description)
    desc_overlap = query_keywords & desc_words
    score += len(desc_overlap)

    return score


def get_api_context(design_plan: dict, prompt: str, max_docs: int = 8, max_examples: int = 2) -> str:
    """Retrieve relevant CadQuery API docs for a given design plan and prompt.

    Returns a formatted string of relevant method docs, selectors reference,
    and example code to inject into the Coder/Refiner agent prompt.

    Args:
        design_plan: The structured design plan from the Planner agent.
        prompt: The original user request text.
        max_docs: Maximum number of API method docs to include.
        max_examples: Maximum number of example scripts to include.

    Returns:
        Formatted string of relevant API documentation, or empty string
        if no relevant docs are found.
    """
    import json

    # Build query text from both prompt and design plan
    query_text = prompt.lower()
    if design_plan:
        plan_str = json.dumps(design_plan, indent=0).lower()
        query_text += " " + plan_str

    query_keywords = _extract_keywords(query_text)

    # Score and rank API docs (search all doc lists)
    all_docs = WORKPLANE_DOCS + SKETCH_DOCS + ASSEMBLY_DOCS + SHAPE_DOCS + GEOMETRY_DOCS
    scored_docs = [(doc, _score_doc(doc, query_keywords)) for doc in all_docs]
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    top_docs = [(doc, score) for doc, score in scored_docs if score > 0][:max_docs]

    # Score and rank examples
    scored_examples = [(ex, _score_example(ex, query_keywords)) for ex in EXAMPLES]
    scored_examples.sort(key=lambda x: x[1], reverse=True)
    top_examples = [(ex, score) for ex, score in scored_examples if score > 0][:max_examples]

    if not top_docs and not top_examples:
        return ""

    # Build output
    lines = ["CADQUERY API REFERENCE (from AutoFab knowledge base):\n"]

    # Include selectors reference only when the prompt/plan suggests
    # face/edge selection will be needed.  Derived from Dataset V2 tiers:
    #   - T1 (primitives): selectors almost never needed
    #   - T2: only chamfer/counterbore/face-targeted ops need them
    #   - T3: fillet, shell, face-workplane ops need them heavily
    _SELECTOR_TRIGGER_WORDS = {
        # CQ operations that require selectors
        "fillet", "chamfer", "shell", "countersink", "counterbore",
        "cborehole", "cskhole",
        # Geometry-selection language common in prompts
        "face", "faces", "edge", "edges", "vertex", "vertices",
        "select", "selector",
        # Spatial references that imply face selection
        "top", "bottom", "front", "back", "side",
        # Adjectives that imply fillet/shell
        "rounded", "rounding", "hollow", "hollowed",
    }
    if query_keywords & _SELECTOR_TRIGGER_WORDS:
        lines.append(SELECTORS_REFERENCE)

    # Add relevant method docs
    if top_docs:
        lines.append("## Relevant CadQuery Methods\n")
        for doc, score in top_docs:
            lines.append(f"### {doc.name}")
            lines.append(f"  Signature: {doc.signature}")
            lines.append(f"  {doc.description}")
            if doc.example:
                lines.append(f"  Example: {doc.example}")
            if doc.notes:
                lines.append(f"  Note: {doc.notes}")
            lines.append("")

    # Add relevant examples
    if top_examples:
        lines.append("## Relevant CadQuery Examples\n")
        for ex, score in top_examples:
            lines.append(f"### Example: {ex.name}")
            lines.append(f"  {ex.description}")
            lines.append(f"```python\n{ex.code}\n```")
            lines.append("")

    return "\n".join(lines)
