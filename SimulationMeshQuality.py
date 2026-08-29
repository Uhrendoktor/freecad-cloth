"""Deterministic boundary discretization for simulation particle-distance presets."""
from math import ceil, hypot


def quality_piece_mesh(piece, start_height, particle_distance):
    from PatternGeometry import LineSegment, ParametricPattern
    from PatternMesh import triangulate
    import FreeCAD as App

    raw = getattr(piece, "SewingOutline", "") or getattr(piece, "DraftingBoundary", "")
    import ast
    points = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(raw))]
    if len(points) < 3:
        raise ValueError("pattern boundary needs at least three points")
    spacing = max(0.25, float(particle_distance))
    dense = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        length = hypot(end[0] - start[0], end[1] - start[1])
        count = max(1, int(ceil(length / spacing)))
        for step in range(count):
            t = step / float(count)
            dense.append((start[0] + (end[0] - start[0]) * t,
                          start[1] + (end[1] - start[1]) * t))
    segments = [LineSegment(f"{piece.PieceId}:edge:{i}", dense[i], dense[(i + 1) % len(dense)]) for i in range(len(dense))]
    mesh = triangulate(ParametricPattern(segments))
    placement = getattr(piece, "Placement", None)
    vertices = []
    for x, y in mesh.vertices:
        point = App.Vector(x, y, float(start_height))
        if placement is not None:
            point = placement.multVec(point)
        vertices.append((float(point.x), float(point.y), float(point.z)))
    return vertices, mesh.triangles, tuple(mesh.boundary_vertex_indices)


def install_quality_mesh_patch():
    """Patch the existing QualitySimulationProxy without duplicating solver code."""
    from SimulationQualityRuntimeV2 import QualitySimulationProxy
    if getattr(QualitySimulationProxy, "_cloth_quality_mesh_patched", False):
        return
    import SimulationObjects
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
