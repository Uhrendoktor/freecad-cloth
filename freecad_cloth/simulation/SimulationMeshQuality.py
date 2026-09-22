"""Deterministic simulation mesh density with authored-boundary refinement."""
import ast
from math import hypot


def _outline_points(piece):
    raw = getattr(piece, "SewingOutline", "") or getattr(piece, "DraftingBoundary", "")
    if not raw:
        width, height = float(piece.Width), float(piece.Height)
        return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    values = ast.literal_eval(str(raw))
    points = [(float(p[0]), float(p[1])) for p in values]
    if len(points) < 3:
        raise ValueError("pattern boundary needs at least three points")
    return points


def quality_piece_mesh(piece, start_height, particle_distance):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate

    spacing = max(0.25, float(particle_distance))
    points = _outline_points(piece)
    segments = [
        LineSegment(f"{piece.PieceId}:edge:{i}", points[i], points[(i + 1) % len(points)])
        for i in range(len(points))
    ]
    # For an approximately equilateral triangle lattice, area ~= sqrt(3)/4*d^2.
    # A small safety margin keeps the actual edge spacing below the requested
    # particle distance without hand-written midpoint refinement.
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(refine_linear_boundary(ParametricPattern(segments), spacing), max_area=max_area)
    placement = getattr(piece, "Placement", None)
    if placement is None:
        positions = [(x, y, float(start_height)) for x, y in mesh.vertices]
    else:
        import FreeCAD as App
        positions = []
        for x, y in mesh.vertices:
            point = placement.multVec(App.Vector(x, y, float(start_height)))
            positions.append((float(point.x), float(point.y), float(point.z)))
    boundary = tuple(int(index) for index in mesh.boundary_vertex_indices)
    segment_ids = tuple(str(value) for value in mesh.boundary_edge_segment_ids)
    if segment_ids and len(segment_ids) != len(boundary):
        raise ValueError("quality mesh boundary provenance length does not match boundary vertices")

    edge_prefixes = tuple(f"{piece.PieceId}:edge:{index}" for index in range(len(points)))
    edge_pairs = {}
    for index, segment_id in enumerate(segment_ids):
        key = next(
            (
                prefix
                for prefix in edge_prefixes
                if segment_id == prefix or segment_id.startswith(prefix + "::sub::")
            ),
            None,
        )
        if key is None:
            raise ValueError(f"quality mesh returned unknown semantic boundary ID: {segment_id}")
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(key, []).append(pair)

    if not edge_pairs:
        edge_pairs = {
            f"{piece.PieceId}:edge:{index}": [(boundary[index], boundary[(index + 1) % len(boundary)])]
            for index in range(len(boundary))
        }

    mesh_vertices = tuple(mesh.vertices)
    by_index = []
    for edge_index, start_point in enumerate(points):
        key = f"{piece.PieceId}:edge:{edge_index}"
        pairs = edge_pairs.get(key)
        if not pairs:
            raise ValueError(f"quality mesh has no boundary provenance for edge {edge_index}")

        end_point = points[(edge_index + 1) % len(points)]
        dx = float(end_point[0]) - float(start_point[0])
        dy = float(end_point[1]) - float(start_point[1])
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-18:
            raise ValueError(f"quality mesh authored edge {edge_index} has zero length")

        vertices = {vertex for pair in pairs for vertex in pair}

        def parameter(vertex_index):
            vertex = mesh_vertices[vertex_index]
            return (
                (float(vertex[0]) - float(start_point[0])) * dx
                + (float(vertex[1]) - float(start_point[1])) * dy
            ) / length_squared

        ordered = tuple(sorted(vertices, key=parameter))
        if len(ordered) < 2:
            raise ValueError(f"quality mesh semantic edge {edge_index} has too few boundary vertices")

        endpoint_tolerance = 1e-7 * max(1.0, hypot(dx, dy))
        first = mesh_vertices[ordered[0]]
        last = mesh_vertices[ordered[-1]]
        if hypot(float(first[0]) - float(start_point[0]), float(first[1]) - float(start_point[1])) > endpoint_tolerance:
            raise ValueError(f"quality mesh semantic edge {edge_index} does not start at its authored vertex")
        if hypot(float(last[0]) - float(end_point[0]), float(last[1]) - float(end_point[1])) > endpoint_tolerance:
            raise ValueError(f"quality mesh semantic edge {edge_index} does not end at its authored vertex")

        actual_pairs = {frozenset(pair) for pair in pairs}
        ordered_pairs = {frozenset((left, right)) for left, right in zip(ordered, ordered[1:])}
        if ordered_pairs != actual_pairs:
            raise ValueError(f"quality mesh semantic edge {edge_index} boundary chain is disconnected")

        max_segment = max(
            hypot(
                float(mesh_vertices[left][0]) - float(mesh_vertices[right][0]),
                float(mesh_vertices[left][1]) - float(mesh_vertices[right][1]),
            )
            for left, right in zip(ordered, ordered[1:])
        )
        if max_segment > spacing + endpoint_tolerance:
            raise ValueError(f"quality mesh semantic edge {edge_index} exceeds requested boundary spacing")

        by_index.append(ordered)
    return positions, tuple(mesh.triangles), tuple(by_index)


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
