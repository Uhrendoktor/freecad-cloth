"""Deterministic simulation mesh density and authored-boundary refinement."""
import ast
from math import ceil, isfinite


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
    boundary_groups = {}
    boundary = mesh.boundary_vertex_indices
    segment_ids = mesh.boundary_edge_segment_ids
    if not segment_ids:
        raise ValueError("quality mesh boundary provenance is missing")
    if len(segment_ids) != len(boundary):
        raise ValueError("quality mesh boundary provenance length does not match boundary vertices")
    for index, segment_id in enumerate(segment_ids):
        raw_key = str(segment_id)
        key = subedge_to_authored.get(raw_key)
        if key is None:
            raise ValueError("quality mesh boundary provenance contains an unknown sub-edge")
        start = int(boundary[index])
        end = int(boundary[(index + 1) % len(boundary)])
        group = boundary_groups.setdefault(key, [start])
        if group[-1] != start:
            raise ValueError("quality mesh semantic edge provenance is not contiguous")
        group.append(end)
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
