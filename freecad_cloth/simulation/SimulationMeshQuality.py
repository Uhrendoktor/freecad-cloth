"""Simulation mesh density delegated to the Triangle constrained-Delaunay library."""
from math import hypot, isfinite


def quality_piece_mesh(piece, start_height, particle_distance, piece_ir=None):
    from freecad_cloth.common.PatternSimulationAdapter import geometry_from_piece_ir, resolve_piece_ir
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate

    spacing = max(0.25, float(particle_distance))
    if piece_ir is None:
        piece_ir = resolve_piece_ir(piece)

    pattern = geometry_from_piece_ir(piece_ir)
    max_area = 0.45 * spacing * spacing
    mesh = triangulate(
        refine_linear_boundary(pattern, spacing),
        max_area=max_area,
    )
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
        base = next(
            (
                str(boundary_ir.id)
                for boundary_ir in piece_ir.boundaries
                if raw_key == str(boundary_ir.id)
                or raw_key.startswith(str(boundary_ir.id) + "::sub::")
            ),
            None,
        )
        if base is None:
            raise ValueError(
                "quality mesh boundary provenance contains an unknown semantic edge"
            )
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(base, []).append(pair)

    by_id = {}
    mesh_vertices = tuple(mesh.vertices)
    for boundary_ir in piece_ir.boundaries:
        edge_id = str(boundary_ir.id)
        pairs = edge_pairs.get(edge_id)
        if not pairs:
            raise ValueError(
                "quality mesh has no boundary provenance for semantic edge %s"
                % edge_id
            )
        vertex_indices = {vertex for pair in pairs for vertex in pair}
        authored = tuple(tuple(point[:2]) for point in boundary_ir.samples)
        ordered = tuple(
            sorted(
                vertex_indices,
                key=lambda vertex: _polyline_parameter(mesh_vertices[vertex], authored),
            )
        )
        if len(ordered) < 2:
            raise ValueError(
                "quality mesh semantic edge %s has too few boundary vertices"
                % edge_id
            )
        endpoint_tolerance = 1e-7 * max(1.0, boundary_ir.length)
        first = mesh_vertices[ordered[0]]
        last = mesh_vertices[ordered[-1]]
        if hypot(
            float(first[0]) - float(authored[0][0]),
            float(first[1]) - float(authored[0][1]),
        ) > endpoint_tolerance:
            raise ValueError(
                "quality mesh semantic edge %s does not start at its authored vertex"
                % edge_id
            )
        if hypot(
            float(last[0]) - float(authored[-1][0]),
            float(last[1]) - float(authored[-1][1]),
        ) > endpoint_tolerance:
            raise ValueError(
                "quality mesh semantic edge %s does not end at its authored vertex"
                % edge_id
            )

        actual_pairs = {frozenset(pair) for pair in pairs}
        ordered_pairs = {
            frozenset((left, right))
            for left, right in zip(ordered, ordered[1:])
        }
        if ordered_pairs != actual_pairs:
            raise ValueError(
                "quality mesh semantic edge %s boundary chain is disconnected"
                % edge_id
            )

        for left, right in zip(ordered, ordered[1:]):
            span = hypot(
                float(mesh_vertices[left][0]) - float(mesh_vertices[right][0]),
                float(mesh_vertices[left][1]) - float(mesh_vertices[right][1]),
            )
            if span > float(spacing) + endpoint_tolerance:
                raise ValueError(
                    "quality mesh semantic edge %s exceeds requested boundary spacing"
                    % edge_id
                )
        by_id[edge_id] = ordered

    return positions, tuple(mesh.triangles), tuple(
        tuple(by_id[str(boundary_ir.id)])
        for boundary_ir in piece_ir.boundaries
    )


def _polyline_parameter(point, polyline):
    if len(polyline) < 2:
        return 0.0
    total = 0.0
    spans = []
    for start, end in zip(polyline, polyline[1:]):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        length = (dx * dx + dy * dy) ** 0.5
        spans.append((total, start, end, length))
        total += length
    if total <= 1e-12:
        return 0.0
    best = None
    for offset, start, end, length in spans:
        if length <= 1e-12:
            continue
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        t = (
            (float(point[0]) - float(start[0])) * dx
            + (float(point[1]) - float(start[1])) * dy
        ) / (length * length)
        t = max(0.0, min(1.0, t))
        px = float(start[0]) + t * dx
        py = float(start[1]) + t * dy
        distance = (float(point[0]) - px) ** 2 + (float(point[1]) - py) ** 2
        candidate = (distance, offset + t * length)
        best = candidate if best is None or candidate < best else best
    return best[1] / total if best else 0.0


def install_quality_mesh_patch():
    """Patch the existing QualitySimulationProxy without duplicating solver code."""
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    if getattr(QualitySimulationProxy, "_cloth_quality_mesh_patched", False):
        return
    from freecad_cloth.simulation import SimulationObjects
    original = QualitySimulationProxy._build_pattern_scene

    def build_pattern_scene(self, obj, pieces, signature):
        previous = SimulationObjects._piece_mesh
        SimulationObjects._piece_mesh = lambda piece, start_height, piece_ir=None: quality_piece_mesh(
            piece,
            start_height,
            float(obj.ParticleDistance),
            piece_ir=piece_ir,
        )
        try:
            return original(self, obj, pieces, signature)
        finally:
            SimulationObjects._piece_mesh = previous

    QualitySimulationProxy._build_pattern_scene = build_pattern_scene
    QualitySimulationProxy._cloth_quality_mesh_patched = True
