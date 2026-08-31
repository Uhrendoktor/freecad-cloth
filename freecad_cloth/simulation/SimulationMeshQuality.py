"""Deterministic simulation mesh refinement driven by particle distance.

The authoritative PatternMesh triangulation remains unchanged.  Simulation
quality adds interior centroid refinement so boundary vertices and semantic
seam edge indices remain stable while the solver receives a useful topology.
"""
from math import ceil, hypot, log2


def _outline_points(piece):
    import ast
    raw = getattr(piece, "SewingOutline", "") or getattr(piece, "DraftingBoundary", "")
    if not raw:
        width, height = float(piece.Width), float(piece.Height)
        return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    values = ast.literal_eval(str(raw))
    points = [(float(p[0]), float(p[1])) for p in values]
    if len(points) < 3:
        raise ValueError("pattern boundary needs at least three points")
    return points


def _centroid_refine(vertices, triangles):
    """Split each triangle into three using an interior centroid.

    No new boundary vertices are introduced, so existing seam edge indices
    continue to address the same authored pattern boundary.
    """
    result_vertices = list(vertices)
    result_triangles = []
    for a, b, c in triangles:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        centroid = (
            (pa[0] + pb[0] + pc[0]) / 3.0,
            (pa[1] + pb[1] + pc[1]) / 3.0,
        )
        m = len(result_vertices)
        result_vertices.append(centroid)
        result_triangles.extend(((a, b, m), (b, c, m), (c, a, m)))
    return result_vertices, result_triangles


def _refinement_levels(vertices, boundary, particle_distance):
    spacing = max(0.25, float(particle_distance))
    longest = 0.0
    for index, start in enumerate(boundary):
        end = boundary[(index + 1) % len(boundary)]
        a, b = vertices[start], vertices[end]
        longest = max(longest, hypot(b[0] - a[0], b[1] - a[1]))
    if longest <= 4.0 * spacing:
        return 1
    return min(5, max(1, int(ceil(log2(longest / (4.0 * spacing))))))


def quality_piece_mesh(piece, start_height, particle_distance):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate

    points = _outline_points(piece)
    segments = [
        LineSegment(f"{piece.PieceId}:edge:{i}", points[i], points[(i + 1) % len(points)])
        for i in range(len(points))
    ]
    mesh = triangulate(ParametricPattern(segments))
    vertices = [(float(x), float(y)) for x, y in mesh.vertices]
    triangles = [tuple(tri) for tri in mesh.triangles]
    levels = _refinement_levels(vertices, tuple(mesh.boundary_vertex_indices), particle_distance)
    for _ in range(levels):
        vertices, triangles = _centroid_refine(vertices, triangles)
    placement = getattr(piece, "Placement", None)
    if placement is None:
        positions = [(x, y, float(start_height)) for x, y in vertices]
    else:
        import FreeCAD as App
        positions = []
        for x, y in vertices:
            point = placement.multVec(App.Vector(x, y, float(start_height)))
            positions.append((float(point.x), float(point.y), float(point.z)))
    return positions, tuple(triangles), tuple(mesh.boundary_vertex_indices)


def install_quality_mesh_patch():
    """Patch the existing QualitySimulationProxy without duplicating solver code."""
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    if getattr(QualitySimulationProxy, "_cloth_quality_mesh_patched", False):
        return
    import freecad_cloth.simulation.SimulationObjects
    original = QualitySimulationProxy._build_pattern_scene

    def build_pattern_scene(self, obj, pieces, signature):
        previous = SimulationObjects._piece_mesh
        SimulationObjects._piece_mesh = lambda piece, start_height: quality_piece_mesh(
            piece, start_height, float(obj.ParticleDistance)
        )
        try:
            return original(self, obj, pieces, signature)
        finally:
            SimulationObjects._piece_mesh = previous

    QualitySimulationProxy._build_pattern_scene = build_pattern_scene
    QualitySimulationProxy._cloth_quality_mesh_patched = True
