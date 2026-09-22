"""Simulation mesh density delegated to the Triangle constrained-Delaunay library."""
import ast


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
    from math import hypot

    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate

    spacing = max(0.25, float(particle_distance))
    points = _outline_points(piece)
    deduped = []
    for point in points:
        if not deduped or hypot(point[0] - deduped[-1][0], point[1] - deduped[-1][1]) > 1e-9:
            deduped.append(point)
    if len(deduped) > 1 and hypot(deduped[0][0] - deduped[-1][0], deduped[0][1] - deduped[-1][1]) <= 1e-9:
        deduped.pop()
    if len(deduped) < 3:
        raise ValueError("quality simulation boundary collapses after endpoint deduplication")
    segments = [
        LineSegment(f"{piece.PieceId}:edge:{i}", deduped[i], deduped[(i + 1) % len(deduped)])
        for i in range(len(deduped))
    ]
    refined = refine_linear_boundary(ParametricPattern(segments), spacing)
    # For an approximately equilateral triangle lattice, area ~= sqrt(3)/4*d^2.
    # A small safety margin keeps the actual edge spacing below the requested
    # particle distance without hand-written midpoint refinement.
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(refined, max_area=max_area)
    placement = getattr(piece, "Placement", None)
    if placement is None:
        positions = [(x, y, float(start_height)) for x, y in mesh.vertices]
    else:
        import FreeCAD as App
        positions = []
        for x, y in mesh.vertices:
            point = placement.multVec(App.Vector(x, y, float(start_height)))
            positions.append((float(point.x), float(point.y), float(point.z)))
    boundary = mesh.boundary_vertex_indices
    segment_ids = tuple(str(value) for value in mesh.boundary_edge_segment_ids)
    if len(segment_ids) != len(boundary):
        raise ValueError("quality mesh boundary provenance length does not match boundary vertices")
    refined_ids = tuple(segment.id for segment in refined.segments)
    if len(refined_ids) != len(boundary):
        raise ValueError("quality mesh refined boundary count does not match boundary vertices")
    expected_ids = list(refined_ids)
    signed_area = sum(
        deduped[i][0] * deduped[(i + 1) % len(deduped)][1]
        - deduped[(i + 1) % len(deduped)][0] * deduped[i][1]
        for i in range(len(deduped))
    )
    if signed_area < 0.0:
        expected_ids = list(reversed(expected_ids))
        expected_ids = expected_ids[1:] + expected_ids[:1]
    expected_ids = tuple(expected_ids)
    if segment_ids != expected_ids:
        raise ValueError(
            "quality mesh boundary provenance disagrees with authored order: "
            f"expected={expected_ids!r} actual={segment_ids!r}"
        )
    boundary_groups = {}
    for original_index in range(len(deduped)):
        prefix = f"{piece.PieceId}:edge:{original_index}"
        matches = [i for i, segment_id in enumerate(expected_ids)
                   if segment_id == prefix or segment_id.startswith(prefix + "::sub::")]
        if not matches or matches != list(range(matches[0], matches[-1] + 1)):
            raise ValueError(f"quality mesh semantic edge provenance is not contiguous for {prefix}")
        boundary_groups[prefix] = list(boundary[matches[0]:matches[-1] + 2])
    by_index = [tuple(boundary_groups[f"{piece.PieceId}:edge:{edge_index}"]) for edge_index in range(len(deduped))]
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
