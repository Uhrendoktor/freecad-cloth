"""FreeCAD-independent surface mesh generation for pattern pieces.

The mesher consumes the sewing boundary rather than the cut boundary: seam
allowance is manufacturing geometry, while the cloth solver needs the
physical panel boundary. Constrained Delaunay triangulation is delegated to
Jonathan Shewchuk's Triangle library; the rest of this module preserves the
workbench's semantic boundary/provenance contract.
"""
from dataclasses import dataclass
from math import ceil, hypot, isfinite, isclose
from typing import Dict, List, Sequence, Tuple

from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, Point


@dataclass(frozen=True)
class TriangleMesh:
    """Triangle mesh in pattern coordinates, in millimetres."""
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
        return sum(abs(_triangle_area(self.vertices[a], self.vertices[b], self.vertices[c])) for a, b, c in self.triangles)

    def boundary_edges(self) -> Tuple[Tuple[int, int], ...]:
        indices = self.boundary_vertex_indices
        return tuple((indices[i], indices[(i + 1) % len(indices)]) for i in range(len(indices)))


def refine_linear_boundary(pattern: ParametricPattern, max_spacing: float) -> ParametricPattern:
    """Return a deterministic pattern with straight authored edges subdivided.

    Generated sub-segments use internal IDs derived from the authored semantic
    edge ID; consumers must group them back to the authored edge.
    """
    spacing = float(max_spacing)
    if not isfinite(spacing) or spacing <= 0.0:
        raise ValueError("max boundary spacing must be positive and finite")
    segments = []
    for segment in pattern.segments:
        if not isinstance(segment, LineSegment):
            segments.append(segment)
            continue
        steps = max(1, int(ceil(segment.length() / spacing)))
        for index in range(steps):
            start = segment.point(index / float(steps))
            end = segment.point((index + 1) / float(steps))
            suffix = "" if steps == 1 else "::sub::%d" % index
            segments.append(LineSegment(segment.id + suffix, start, end))
    return ParametricPattern(segments)

def triangulate(pattern: ParametricPattern, curve_samples: int = 16, max_area: float | None = None) -> TriangleMesh:
    """Triangulate a sampled simple polygon with constrained Delaunay Triangle.

    ``max_area`` delegates simulation mesh refinement to Triangle itself. The
    ``Y`` switch forbids Steiner points on authored boundary segments, so
    semantic seam edge indices remain stable while Triangle adds interior
    vertices where needed.
    """
    points = _deduplicate_consecutive(pattern.sampled_outline(curve_samples))
    if len(points) < 3:
        raise ValueError("pattern has too few distinct boundary points")
    if abs(_signed_area(points)) < 1e-9:
        raise ValueError("pattern has zero area")
    if _self_intersects(points):
        raise ValueError("pattern boundary self-intersects")
    edge_ids = _edge_segment_ids(pattern, points)
    if _signed_area(points) < 0:
        points = list(reversed(points))
        edge_ids = _edge_segment_ids(pattern, points)

    if max_area is not None:
        max_area = float(max_area)
        if max_area <= 0.0:
            raise ValueError("max_area must be positive")

    try:
        import numpy as np
        import triangle as tr
    except ImportError as exc:
        raise RuntimeError(
            "PatternMesh requires the 'triangle' package (Shewchuk constrained Delaunay meshing)"
        ) from exc

    vertices_in = np.asarray(points, dtype=np.float64)
    segments = np.asarray(
        [(i, (i + 1) % len(points)) for i in range(len(points))],
        dtype=np.int32,
    )
    options = "pQ"
    if max_area is not None:
        options += "Ya%.12g" % max_area
    result = tr.triangulate({"vertices": vertices_in, "segments": segments}, options)
    result_vertices = np.asarray(result.get("vertices", ()), dtype=np.float64)
    result_triangles = np.asarray(result.get("triangles", ()), dtype=np.int64)
    if len(result_vertices) == 0:
        raise ValueError("Triangle returned no vertices")
    if result_triangles.ndim != 2 or result_triangles.shape[1] != 3:
        raise ValueError("Triangle returned no triangular faces")
    if max_area is None and len(result_vertices) != len(points):
        raise ValueError(
            "Triangle inserted or removed vertices unexpectedly; expected a boundary-only base mesh"
        )

    source_lookup: Dict[Tuple[float, float], int] = {
        (_quantize(x), _quantize(y)): i for i, (x, y) in enumerate(points)
    }
    boundary_indices: List[int] = []
    for source_index, (x, y) in enumerate(points):
        key = (_quantize(x), _quantize(y))
        matches = [i for i, vertex in enumerate(result_vertices.tolist()) if (_quantize(vertex[0]), _quantize(vertex[1])) == key]
        if not matches:
            raise ValueError("Triangle dropped an authored boundary vertex")
        boundary_indices.append(matches[0])

    triangles: List[Tuple[int, int, int]] = []
    for raw in result_triangles.tolist():
        a, b, c = int(raw[0]), int(raw[1]), int(raw[2])
        pa, pb, pc = result_vertices[a], result_vertices[b], result_vertices[c]
        if _cross((float(pa[0]), float(pa[1])), (float(pb[0]), float(pb[1])), (float(pc[0]), float(pc[1]))) < 0.0:
            b, c = c, b
        if len({a, b, c}) != 3:
            raise ValueError("Triangle returned a degenerate face")
        triangles.append((a, b, c))

    vertices = tuple((float(v[0]), float(v[1])) for v in result_vertices.tolist())
    mesh = TriangleMesh(vertices, tuple(triangles), tuple(boundary_indices), tuple(edge_ids))
    mesh.validate()
    expected_area = abs(_signed_area(points))
    if abs(mesh.area - expected_area) > 1e-6 * max(1.0, expected_area):
        raise ValueError("triangulation area does not match pattern area")
    return mesh


def _quantize(value: float) -> float:
    return round(float(value), 9)


def _nearest_point_index(points: Sequence[Point], point: Point) -> int:
    return min(range(len(points)), key=lambda i: hypot(points[i][0] - point[0], points[i][1] - point[1]))


def _deduplicate_consecutive(points: Sequence[Point]) -> List[Point]:
    result: List[Point] = []
    for point in points:
        if not result or not (isclose(point[0], result[-1][0], abs_tol=1e-9) and isclose(point[1], result[-1][1], abs_tol=1e-9)):
            result.append(point)
    if len(result) > 1 and isclose(result[0][0], result[-1][0], abs_tol=1e-9) and isclose(result[0][1], result[-1][1], abs_tol=1e-9):
        result.pop()
    return result


def _edge_segment_ids(pattern: ParametricPattern, points: Sequence[Point]) -> List[str]:
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
