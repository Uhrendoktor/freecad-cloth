"""Simulation mesh density delegated to the Triangle constrained-Delaunay library."""
import ast
from math import hypot, isfinite


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


def quality_piece_mesh(piece, start_height, particle_distance, pattern_ir=None):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate

    spacing = max(0.25, float(particle_distance))
    if pattern_ir is None:
        points = _outline_points(piece)
        segments = [
            LineSegment(f"{piece.PieceId}:edge:{i}", points[i], points[(i + 1) % len(points)])
            for i in range(len(points))
        ]
        edge_prefixes = [f"{piece.PieceId}:edge:{i}" for i in range(len(points))]
    else:
        pattern_ir.validate()
        piece_ir = pattern_ir.piece(str(piece.PieceId))
        pattern = pattern_ir.to_parametric_pattern(str(piece.PieceId))
        points = [
            (float(boundary.samples[0][0]), float(boundary.samples[0][1]))
            for boundary in piece_ir.boundaries
        ]
        segments = list(pattern.segments)
        edge_prefixes = [str(boundary.id) for boundary in piece_ir.boundaries]
    pattern = ParametricPattern(segments)
    # For an approximately equilateral triangle lattice, area ~= sqrt(3)/4*d^2.
    # A small safety margin keeps the actual edge spacing below the requested
    # particle distance without hand-written midpoint refinement.
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(refine_linear_boundary(pattern, spacing), max_area=max_area)
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
    if not segment_ids:
        raise ValueError("quality mesh boundary provenance is missing")
    if len(segment_ids) != len(boundary):
        raise ValueError("quality mesh boundary provenance length does not match boundary vertices")

    edge_pairs = {}
    for index, segment_id in enumerate(segment_ids):
        raw_key = str(segment_id)
        matches = [
            prefix for prefix in edge_prefixes
            if raw_key == prefix or raw_key.startswith(prefix + "::sub::")
        ]
        if not matches:
            raise ValueError("quality mesh boundary provenance contains an unknown semantic edge")
        key = matches[0]
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(key, []).append(pair)

    by_index = []
    mesh_vertices = tuple(mesh.vertices)
    for edge_index, start_point in enumerate(points):
        end_point = points[(edge_index + 1) % len(points)]
        key = edge_prefixes[edge_index]
        pairs = edge_pairs.get(key)
        if not pairs:
            raise ValueError(f"quality mesh has no boundary provenance for edge {key}")

        vertex_indices = {vertex for pair in pairs for vertex in pair}
        dx = float(end_point[0]) - float(start_point[0])
        dy = float(end_point[1]) - float(start_point[1])
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-18:
            raise ValueError(f"quality mesh authored edge {key} has zero length")

        def parameter(vertex_index):
            vertex = mesh_vertices[vertex_index]
            return (
                (float(vertex[0]) - float(start_point[0])) * dx
                + (float(vertex[1]) - float(start_point[1])) * dy
            ) / length_squared

        ordered = tuple(sorted(vertex_indices, key=parameter))
        if len(ordered) < 2:
            raise ValueError(f"quality mesh semantic edge {key} has too few boundary vertices")

        endpoint_tolerance = 1e-7 * max(1.0, hypot(dx, dy))
        first = mesh_vertices[ordered[0]]
        last = mesh_vertices[ordered[-1]]
        if hypot(float(first[0]) - float(start_point[0]), float(first[1]) - float(start_point[1])) > endpoint_tolerance:
            raise ValueError(f"quality mesh semantic edge {key} does not start at its authored vertex")
        if hypot(float(last[0]) - float(end_point[0]), float(last[1]) - float(end_point[1])) > endpoint_tolerance:
            raise ValueError(f"quality mesh semantic edge {key} does not end at its authored vertex")

        actual_pairs = {frozenset(pair) for pair in pairs}
        ordered_pairs = {frozenset((left, right)) for left, right in zip(ordered, ordered[1:])}
        if ordered_pairs != actual_pairs:
            raise ValueError(f"quality mesh semantic edge {key} boundary chain is disconnected")

        for left, right in zip(ordered, ordered[1:]):
            span = hypot(
                float(mesh_vertices[left][0]) - float(mesh_vertices[right][0]),
                float(mesh_vertices[left][1]) - float(mesh_vertices[right][1]),
            )
            if span > float(spacing) + endpoint_tolerance:
                raise ValueError(
                    f"quality mesh semantic edge {key} exceeds requested boundary spacing"
                )
        by_index.append(ordered)
    legacy_result = (positions, tuple(mesh.triangles), tuple(by_index))
    if pattern_ir is None:
        return legacy_result
    return legacy_result + ({key: tuple(chain) for key, chain in zip(edge_prefixes, by_index)},)




def install_quality_mesh_patch():
    """Patch the existing QualitySimulationProxy without duplicating solver code."""
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    if getattr(QualitySimulationProxy, "_cloth_quality_mesh_patched", False):
        return
    from freecad_cloth.simulation import SimulationObjects
    original = QualitySimulationProxy._build_pattern_scene

    def build_pattern_scene(self, obj, pieces, signature, pattern_ir=None):
        previous = SimulationObjects._piece_mesh
        SimulationObjects._piece_mesh = lambda piece, start_height, _pattern_ir=None: quality_piece_mesh(
            piece,
            start_height,
            float(obj.ParticleDistance),
            pattern_ir=_pattern_ir if _pattern_ir is not None else pattern_ir,
        )
        try:
            return original(self, obj, pieces, signature, pattern_ir)
        finally:
            SimulationObjects._piece_mesh = previous

    QualitySimulationProxy._build_pattern_scene = build_pattern_scene
    QualitySimulationProxy._cloth_quality_mesh_patched = True
