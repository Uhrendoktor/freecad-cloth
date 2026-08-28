"""FreeCAD-independent surface mesh generation for pattern pieces.

The mesher deliberately consumes the sewing boundary rather than the cut
boundary: seam allowance is manufacturing geometry, while the cloth solver
needs the physical panel boundary.  Ear clipping keeps this first backend
small and deterministic; FreeCAD-facing MeshPart/Netgen adapters can replace
it without changing the semantic mesh contract.
"""
from dataclasses import dataclass
from math import hypot, isclose
from typing import Dict, List, Sequence, Tuple

from PatternGeometry import ParametricPattern, Point


@dataclass(frozen=True)
class TriangleMesh:
    """Triangle mesh in pattern coordinates, in millimetres.

    ``boundary_edge_segment_ids`` is optional provenance for the ordered
    boundary edges.  It lets native meshing adapters retain stable pattern
    segment IDs even when the tessellator inserts or reorders vertices.
    """
    vertices: Tuple[Point, ...]
    triangles: Tuple[Tuple[int, int, int], ...]
    boundary_vertex_indices: Tuple[int, ...]
    boundary_edge_segment_ids: Tuple[str, ...] = ()

    def validate(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("mesh needs at least three vertices")
        n = len(self.vertices)
        for tri in self.triangles:
            if len(set(tri)) != 3 or any(i < 0 or i >= n for i in tri):
                raise ValueError("invalid triangle index")
        if len(self.boundary_vertex_indices) < 3:
            raise ValueError("mesh needs at least three boundary vertices")
        if self.boundary_edge_segment_ids and len(self.boundary_edge_segment_ids) != len(self.boundary_vertex_indices):
            raise ValueError("boundary provenance must match boundary edge count")

    @property
    def area(self) -> float:
        return sum(abs(_triangle_area(self.vertices[a], self.vertices[b], self.vertices[c]))
                   for a, b, c in self.triangles)

    def boundary_edges(self) -> Tuple[Tuple[int, int], ...]:
        indices = self.boundary_vertex_indices
        return tuple((indices[i], indices[(i + 1) % len(indices)]) for i in range(len(indices)))


def triangulate(pattern: ParametricPattern, curve_samples: int = 16) -> TriangleMesh:
    """Triangulate a sampled simple polygon deterministically with ear clipping."""
    points = pattern.sampled_outline(curve_samples)
    if len(points) < 3:
        raise ValueError("pattern has too few sampled boundary points")
    points = _deduplicate_consecutive(points)
    if len(points) < 3:
        raise ValueError("pattern has too few distinct boundary points")
    if abs(_signed_area(points)) < 1e-9:
        raise ValueError("pattern has zero area")
    if _self_intersects(points):
        raise ValueError("pattern boundary self-intersects")

    edge_ids = _edge_segment_ids(pattern, points)

    # Ear clipping is easiest in counter-clockwise orientation.
    if _signed_area(points) < 0:
        points = list(reversed(points))
        edge_ids = list(reversed(edge_ids))
    vertices = tuple(points)
    remaining = list(range(len(vertices)))
    triangles: List[Tuple[int, int, int]] = []
    guard = len(vertices) * len(vertices)
    while len(remaining) > 3 and guard:
        guard -= 1
        clipped = False
        for pos in range(len(remaining)):
            a = remaining[pos - 1]
            b = remaining[pos]
            c = remaining[(pos + 1) % len(remaining)]
            if _cross(vertices[a], vertices[b], vertices[c]) <= 1e-10:
                continue
            if any(i not in (a, b, c) and _point_in_triangle(vertices[i], vertices[a], vertices[b], vertices[c])
                   for i in remaining):
                continue
            triangles.append((a, b, c))
            remaining.pop(pos)
            clipped = True
            break
        if not clipped:
            raise ValueError("unable to triangulate polygon; boundary may be degenerate")
    if len(remaining) == 3:
        triangles.append(tuple(remaining))
    mesh = TriangleMesh(vertices, tuple(triangles), tuple(range(len(vertices))), tuple(edge_ids))
    mesh.validate()
    return mesh


def _deduplicate_consecutive(points: Sequence[Point]) -> List[Point]:
    result: List[Point] = []
    for point in points:
        if not result or not (isclose(point[0], result[-1][0], abs_tol=1e-9) and
                              isclose(point[1], result[-1][1], abs_tol=1e-9)):
            result.append(point)
    if len(result) > 1 and isclose(result[0][0], result[-1][0], abs_tol=1e-9) and isclose(result[0][1], result[-1][1], abs_tol=1e-9):
        result.pop()
    return result


def _edge_segment_ids(pattern: ParametricPattern, points: Sequence[Point]) -> List[str]:
    """Map sampled boundary edges to stable semantic pattern segment IDs."""
    result: List[str] = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        best_index = 0
        best_distance = float("inf")
        for segment_index, segment in enumerate(pattern.segments):
            if hasattr(segment, "control"):
                samples = segment.polyline(32)
                distance = min(_point_to_segment_distance(midpoint, a, b) for a, b in zip(samples, samples[1:]))
            else:
                distance = _point_to_segment_distance(midpoint, segment.start, segment.end)
            if distance < best_distance:
                best_index = segment_index
                best_distance = distance
        result.append(pattern.segments[best_index].id)
    return result


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-24:
        return hypot(point[0] - start[0], point[1] - start[1])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    closest = (start[0] + t * dx, start[1] + t * dy)
    return hypot(point[0] - closest[0], point[1] - closest[1])


def _signed_area(points: Sequence[Point]) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, list(points[1:]) + [points[0]]))


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    return _cross(a, b, c) / 2.0


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle(p: Point, a: Point, b: Point, c: Point) -> bool:
    d1, d2, d3 = _cross(p, a, b), _cross(p, b, c), _cross(p, c, a)
    return d1 >= -1e-10 and d2 >= -1e-10 and d3 >= -1e-10


def _self_intersects(points: Sequence[Point]) -> bool:
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j in (i, (i + 1) % n, (i - 1) % n):
                continue
            c, d = points[j], points[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab1, ab2 = _cross(a, b, c), _cross(a, b, d)
    cd1, cd2 = _cross(c, d, a), _cross(c, d, b)
    return ab1 * ab2 < -1e-10 and cd1 * cd2 < -1e-10
