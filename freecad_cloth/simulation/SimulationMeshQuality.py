"""Deterministic simulation mesh refinement driven by particle distance."""
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


def _midpoint_refine(vertices, triangles, boundary):
    """Split each triangle into four using shared edge midpoints.

    Original boundary vertices remain at their original indices. Midpoints on
    the authored boundary are added to the boundary chain so seam sampling
    gains resolution without invalidating existing seam edge references.
    """
    result_vertices = list(vertices)
    edge_midpoints = {}

    def midpoint_index(a, b):
        edge = (min(a, b), max(a, b))
        existing = edge_midpoints.get(edge)
        if existing is not None:
            return existing
        pa, pb = result_vertices[a], result_vertices[b]
        index = len(result_vertices)
        result_vertices.append(((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0))
        edge_midpoints[edge] = index
        return index

    result_triangles = []
    for a, b, c in triangles:
        ab = midpoint_index(a, b)
        bc = midpoint_index(b, c)
        ca = midpoint_index(c, a)
        result_triangles.extend(((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)))

    result_boundary = []
    for index, start in enumerate(boundary):
        end = boundary[(index + 1) % len(boundary)]
        result_boundary.append(start)
        result_boundary.append(midpoint_index(start, end))

    return result_vertices, result_triangles, tuple(result_boundary)


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
    boundary = tuple(mesh.boundary_vertex_indices)
    levels = _refinement_levels(vertices, boundary, particle_distance)
    for _ in range(levels):
        vertices, triangles, boundary = _midpoint_refine(vertices, triangles, boundary)
    placement = getattr(piece, "Placement", None)
    if placement is None:
        positions = [(x, y, float(start_height)) for x, y in vertices]
    else:
        import FreeCAD as App
        positions = []
        for x, y in vertices:
            point = placement.multVec(App.Vector(x, y, float(start_height)))
            positions.append((float(point.x), float(point.y), float(point.z)))
    return positions, tuple(triangles), tuple(boundary)


def install_quality_mesh_patch():
    """Patch the existing QualitySimulationProxy without duplicating solver code."""
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    if getattr(QualitySimulationProxy, "_cloth_quality_mesh_patched", False):
        return
    from freecad_cloth.simulation import SimulationObjects
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
