"""Optional FreeCAD-facing MeshPart/Netgen pattern meshing adapter.

The semantic PatternModel and TriangleMesh remain FreeCAD-independent. This
module is imported only by FreeCAD-facing code and converts a sampled sewing
boundary into a planar Part face, delegates tessellation to MeshPart, then
canonicalizes the result back into TriangleMesh while retaining semantic
boundary-segment provenance.
"""
from math import hypot
from typing import Dict, Iterable, List, Sequence, Tuple

from PatternGeometry import ParametricPattern, Point
from PatternMesh import TriangleMesh


def mesh_from_pattern(
    pattern: ParametricPattern,
    linear_deflection: float = 0.5,
    angular_deflection: float = 0.5,
    curve_samples: int = 32,
) -> TriangleMesh:
    """Mesh a pattern with FreeCAD MeshPart and return the semantic mesh.

    ``linear_deflection`` and ``angular_deflection`` are passed to
    ``MeshPart.meshFromShape`` with ``Relative=False``. The returned mesh is
    canonicalized by vertex coordinates so native tessellator ordering cannot
    change sewing-constraint vertex IDs between runs.
    """
    if linear_deflection <= 0:
        raise ValueError("linear_deflection must be positive")
    if angular_deflection <= 0:
        raise ValueError("angular_deflection must be positive")
    if curve_samples < 2:
        raise ValueError("curve_samples must be at least 2")

    try:
        import FreeCAD as App
        import MeshPart
        import Part
    except ImportError as exc:
        raise RuntimeError("FreeCAD MeshPart is required for native pattern meshing") from exc

    points = pattern.sampled_outline(curve_samples)
    if len(points) < 3:
        raise ValueError("pattern has too few sampled boundary points")
    vectors = [App.Vector(x, y, 0.0) for x, y in points]
    vectors.append(vectors[0])
    wire = Part.makePolygon(vectors)
    face = Part.Face(wire)
    if face.isNull():
        raise ValueError("unable to construct a planar pattern face")

    native = MeshPart.meshFromShape(
        Shape=face,
        LinearDeflection=float(linear_deflection),
        AngularDeflection=float(angular_deflection),
        Relative=False,
    )
    vertices, triangles = _mesh_topology(native)
    return _canonical_triangle_mesh(pattern, vertices, triangles)


def mesh_shape(shape, linear_deflection: float = 0.5, angular_deflection: float = 0.5):
    """Expose the native MeshPart result for FreeCAD document adapters."""
    if linear_deflection <= 0 or angular_deflection <= 0:
        raise ValueError("mesh deflections must be positive")
    try:
        import MeshPart
    except ImportError as exc:
        raise RuntimeError("FreeCAD MeshPart is required for native pattern meshing") from exc
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=float(linear_deflection),
        AngularDeflection=float(angular_deflection),
        Relative=False,
    )


def _mesh_topology(native) -> Tuple[List[Point], List[Tuple[int, int, int]]]:
    """Read Mesh.Mesh topology across supported FreeCAD Python APIs."""
    topology = getattr(native, "Topology", None)
    if topology is not None:
        points, facets = topology
        vertices = [(float(point.x), float(point.y)) for point in points]
        triangles = [tuple(int(index) for index in facet) for facet in facets]
        return vertices, triangles

    points = getattr(native, "Points", None)
    facets = getattr(native, "Facets", None)
    if points is None or facets is None:
        raise RuntimeError("FreeCAD mesh does not expose Topology or Points/Facets")
    vertices = [(float(point.x), float(point.y)) for point in points]
    triangles = []
    for facet in facets:
        indices = getattr(facet, "PointIndices", None)
        if indices is None:
            indices = facet
        triangles.append(tuple(int(index) for index in indices))
    return vertices, triangles


def _canonical_triangle_mesh(
    pattern: ParametricPattern,
    vertices: Sequence[Point],
    triangles: Sequence[Tuple[int, int, int]],
) -> TriangleMesh:
    """Canonicalize native vertex ordering and recover boundary provenance."""
    if len(vertices) < 3 or not triangles:
        raise ValueError("native tessellator returned an empty mesh")

    order = sorted(range(len(vertices)), key=lambda index: _point_key(vertices[index]))
    remap = {old: new for new, old in enumerate(order)}
    canonical_vertices = tuple((float(vertices[index][0]), float(vertices[index][1])) for index in order)
    canonical_triangles = tuple(
        tuple(remap[index] for index in triangle)
        for triangle in triangles
        if len(triangle) == 3 and len(set(triangle)) == 3
    )
    if not canonical_triangles:
        raise ValueError("native tessellator returned no triangular facets")

    boundary_edges = _boundary_edges(canonical_triangles)
    boundary_loop = _canonical_boundary_loop(boundary_edges, canonical_vertices)
    edge_ids = tuple(
        _nearest_segment_id(pattern, _midpoint(canonical_vertices[a], canonical_vertices[b]))
        for a, b in _loop_edges(boundary_loop)
    )
    mesh = TriangleMesh(canonical_vertices, canonical_triangles, tuple(boundary_loop), edge_ids)
    mesh.validate()
    return mesh


def _point_key(point: Point) -> Tuple[float, float]:
    return (round(float(point[0]), 12), round(float(point[1]), 12))


def _boundary_edges(triangles: Sequence[Tuple[int, int, int]]) -> List[Tuple[int, int]]:
    counts: Dict[Tuple[int, int], int] = {}
    for a, b, c in triangles:
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (start, end) if start < end else (end, start)
            counts[edge] = counts.get(edge, 0) + 1
    return [edge for edge, count in counts.items() if count == 1]


def _canonical_boundary_loop(edges: Sequence[Tuple[int, int]], vertices: Sequence[Point]) -> List[int]:
    if len(edges) < 3:
        raise ValueError("native tessellator returned no closed boundary")
    adjacency: Dict[int, List[int]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise ValueError("native tessellator returned a boundary with multiple loops or branches")

    start = min(adjacency, key=lambda index: _point_key(vertices[index]))
    neighbors = sorted(adjacency[start], key=lambda index: _point_key(vertices[index]))
    loop = [start]
    previous = None
    current = start
    next_vertex = neighbors[0]
    while next_vertex != start:
        loop.append(next_vertex)
        previous, current = current, next_vertex
        candidates = [index for index in adjacency[current] if index != previous]
        if len(candidates) != 1:
            raise ValueError("native tessellator boundary traversal is ambiguous")
        next_vertex = candidates[0]
        if len(loop) > len(edges):
            raise ValueError("native tessellator boundary is not a simple loop")
    return loop


def _loop_edges(loop: Sequence[int]) -> Iterable[Tuple[int, int]]:
    return ((loop[index], loop[(index + 1) % len(loop)]) for index in range(len(loop)))


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _nearest_segment_id(pattern: ParametricPattern, point: Point) -> str:
    best_id = pattern.segments[0].id
    best_distance = float("inf")
    for segment in pattern.segments:
        if hasattr(segment, "control"):
            samples = segment.polyline(64)
        else:
            samples = (segment.start, segment.end)
        distance = min(hypot(point[0] - sample[0], point[1] - sample[1]) for sample in samples)
        if distance < best_distance:
            best_id = segment.id
            best_distance = distance
    return best_id
