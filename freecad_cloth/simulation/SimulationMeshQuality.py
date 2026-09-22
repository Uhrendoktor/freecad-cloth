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
    boundary_groups = {}
    boundary = mesh.boundary_vertex_indices
    segment_ids = mesh.boundary_edge_segment_ids
    if segment_ids and len(segment_ids) != len(boundary):
        raise ValueError("quality mesh boundary provenance length does not match boundary vertices")
    edge_prefixes = [f"{piece.PieceId}:edge:{index}" for index in range(len(points))]
    for index, segment_id in enumerate(segment_ids):
        raw_key = str(segment_id)
        key = next(
            prefix for prefix in edge_prefixes
            if raw_key == prefix or raw_key.startswith(prefix + "::sub::")
        )
        start = int(boundary[index])
        end = int(boundary[(index + 1) % len(boundary)])
        group = boundary_groups.setdefault(key, [start])
        if group[-1] != start:
            raise ValueError("quality mesh semantic edge provenance is not contiguous")
        group.append(end)
    if not boundary_groups:
        boundary_groups = {
            f"{piece.PieceId}:edge:{index}": [int(boundary[index]), int(boundary[(index + 1) % len(boundary)])]
            for index in range(len(boundary))
        }
    by_index = []
    for edge_index in range(len(points)):
        key = f"{piece.PieceId}:edge:{edge_index}"
        if key in boundary_groups:
            by_index.append(tuple(boundary_groups[key]))
        elif edge_index < len(boundary):
            by_index.append((int(boundary[edge_index]), int(boundary[(edge_index + 1) % len(boundary)])))
        else:
            raise ValueError(f"quality mesh has no boundary provenance for edge {edge_index}")
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
