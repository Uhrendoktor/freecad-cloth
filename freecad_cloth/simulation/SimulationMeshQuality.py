"""Deterministic simulation mesh density and authored-boundary refinement."""
import ast
from math import ceil, hypot, isfinite


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



def refine_linear_boundary(pattern, max_spacing):
    """Subdivide authored straight edges without changing their semantic IDs.

    The returned ParametricPattern uses temporary mesh-only sub-edge IDs. The
    second return value maps each temporary ID back to the authored edge ID so
    simulation sewing continues to address the original edge ordinal.
    """
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern

    spacing = float(max_spacing)
    if not isfinite(spacing) or spacing <= 0.0:
        raise ValueError("max boundary spacing must be positive and finite")

    segments = []
    subedge_to_authored = {}
    for segment in pattern.segments:
        if isinstance(segment, LineSegment):
            steps = max(1, int(ceil(segment.length() / spacing)))
            for index in range(steps):
                subedge_id = (
                    segment.id
                    if steps == 1
                    else f"{segment.id}::simulation-sub::{index}"
                )
                start_t = index / float(steps)
                end_t = (index + 1) / float(steps)
                segments.append(
                    LineSegment(
                        subedge_id,
                        segment.point(start_t),
                        segment.point(end_t),
                    )
                )
                subedge_to_authored[subedge_id] = segment.id
        else:
            segments.append(segment)
            subedge_to_authored[segment.id] = segment.id

    return ParametricPattern(segments), subedge_to_authored


def quality_piece_mesh(piece, start_height, particle_distance):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate

    spacing = float(particle_distance)
    if not isfinite(spacing) or spacing <= 0.0:
        raise ValueError("particle_distance must be positive and finite")
    points = _outline_points(piece)
    segments = [
        LineSegment(f"{piece.PieceId}:edge:{i}", points[i], points[(i + 1) % len(points)])
        for i in range(len(points))
    ]
    # For an approximately equilateral triangle lattice, area ~= sqrt(3)/4*d^2.
    # A small safety margin keeps the actual edge spacing below the requested
    # particle distance without hand-written midpoint refinement.
    pattern = ParametricPattern(segments)
    refined_pattern, subedge_to_authored = refine_linear_boundary(pattern, spacing)
    # Triangle still receives Y: all boundary refinement points are authored
    # inputs, while max_area only adds interior density as a separate concern.
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(refined_pattern, max_area=max_area)
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
        key = subedge_to_authored.get(segment_id)
        if key is None:
            raise ValueError("quality mesh boundary provenance contains an unknown sub-edge")
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(key, []).append(pair)

    by_index = []
    mesh_vertices = tuple(mesh.vertices)
    for edge_index, start_point in enumerate(points):
        end_point = points[(edge_index + 1) % len(points)]
        key = f"{piece.PieceId}:edge:{edge_index}"
        pairs = edge_pairs.get(key)
        if not pairs:
            raise ValueError(f"quality mesh has no boundary provenance for edge {edge_index}")

        vertex_indices = {vertex for pair in pairs for vertex in pair}
        dx = float(end_point[0]) - float(start_point[0])
        dy = float(end_point[1]) - float(start_point[1])
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-18:
            raise ValueError(f"quality mesh authored edge {edge_index} has zero length")

        def parameter(vertex_index):
            vertex = mesh_vertices[vertex_index]
            return (
                (float(vertex[0]) - float(start_point[0])) * dx
                + (float(vertex[1]) - float(start_point[1])) * dy
            ) / length_squared

        ordered = tuple(sorted(vertex_indices, key=parameter))
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

        max_segment = 0.0
        for left, right in zip(ordered, ordered[1:]):
            max_segment = max(
                max_segment,
                hypot(
                    float(mesh_vertices[left][0]) - float(mesh_vertices[right][0]),
                    float(mesh_vertices[left][1]) - float(mesh_vertices[right][1]),
                ),
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
