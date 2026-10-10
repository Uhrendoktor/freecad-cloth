"""FreeCAD-independent surface mesh generation for pattern pieces.

The mesher consumes the sewing boundary rather than the cut boundary: seam
allowance is manufacturing geometry, while the cloth solver needs the
physical panel boundary. Constrained Delaunay triangulation is delegated to
Jonathan Shewchuk's Triangle library; the rest of this module preserves the
workbench's semantic boundary/provenance contract.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, isclose, isfinite

from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint

from freecad_cloth.common.ValidationModels import TriangulationOptions
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, Point, signed_area


@dataclass(frozen=True)
class TriangleMesh:
    """Triangle mesh in pattern coordinates, in millimetres."""

    vertices: tuple[Point, ...]
    triangles: tuple[tuple[int, int, int], ...]
    boundary_vertex_indices: tuple[int, ...]
    boundary_edge_segment_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if len(self.vertices) < 3:
            raise ValueError("mesh needs at least three vertices")
        n = len(self.vertices)
        for tri in self.triangles:
            if len(set(tri)) != 3 or any(
                type(index) is not int or index < 0 or index >= n for index in tri
            ):
                raise ValueError("invalid triangle index")
        if len(self.boundary_vertex_indices) < 3:
            raise ValueError("mesh needs at least three boundary vertices")
        if any(
            type(index) is not int or index < 0 or index >= n
            for index in self.boundary_vertex_indices
        ):
            raise ValueError("invalid boundary vertex index")
        if any(
            len(point) != 2 or not all(isfinite(coordinate) for coordinate in point)
            for point in self.vertices
        ):
            raise ValueError("mesh coordinates must be finite 2D points")
        if self.boundary_edge_segment_ids and len(self.boundary_edge_segment_ids) != len(
            self.boundary_vertex_indices
        ):
            raise ValueError("boundary provenance must match boundary edge count")

    @property
    def area(self) -> float:
        """Provide the public area operation."""
        total = sum(
            abs(_triangle_area(self.vertices[a], self.vertices[b], self.vertices[c]))
            for a, b, c in self.triangles
        )
        if not isfinite(total):
            raise ValueError("computed mesh area must be finite")
        return total

    def boundary_edges(self) -> tuple[tuple[int, int], ...]:
        """Provide the public boundary edges operation."""
        indices = self.boundary_vertex_indices
        return tuple((indices[i], indices[(i + 1) % len(indices)]) for i in range(len(indices)))


def triangulate(
    pattern: ParametricPattern, curve_samples: int = 16, max_area: float | None = None
) -> TriangleMesh:
    """Triangulate a sampled simple polygon with constrained Delaunay Triangle.

    ``max_area`` delegates simulation mesh refinement to Triangle itself. The
    ``Y`` switch forbids Steiner points on authored boundary segments, so
    semantic seam edge indices remain stable while Triangle adds interior
    vertices where needed.
    """
    options_input = TriangulationOptions.model_validate(
        {"curve_samples": curve_samples, "max_area": max_area}
    )
    curve_samples, max_area = options_input.curve_samples, options_input.max_area
    points = _deduplicate_consecutive(pattern.sampled_outline(curve_samples))
    if len(points) < 3:
        raise ValueError("pattern has too few distinct boundary points")
    outline_area = signed_area(points)
    if abs(outline_area) < 1e-9:
        raise ValueError("pattern has zero area")
    if _self_intersects(points):
        raise ValueError("pattern boundary self-intersects")
    if all(isinstance(segment, LineSegment) for segment in pattern.segments) and len(points) == len(
        pattern.segments
    ):
        edge_ids = [segment.id for segment in pattern.segments]
    else:
        edge_ids = _edge_segment_ids(pattern, points)
    if outline_area < 0:
        points = list(reversed(points))
        # Recompute provenance from geometry after normalization. A refined
        # authored edge can contain several internal sub-segments, so a fixed
        # one-slot rotation is not a valid semantic mapping.
        edge_ids = _edge_segment_ids(pattern, points)

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
        options += f"Ya{max_area:.12g}"
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

    output_index_by_coordinate: dict[tuple[int, int], int] = {}
    for index, vertex in enumerate(result_vertices):
        key = (_quantize(float(vertex[0])), _quantize(float(vertex[1])))
        output_index_by_coordinate.setdefault(key, index)

    boundary_indices: list[int] = []
    for x, y in points:
        key = (_quantize(x), _quantize(y))
        index = output_index_by_coordinate.get(key)
        if index is None:
            raise ValueError("Triangle dropped an authored boundary vertex")
        boundary_indices.append(index)

    triangles: list[tuple[int, int, int]] = []
    for raw in result_triangles.tolist():
        a, b, c = int(raw[0]), int(raw[1]), int(raw[2])
        pa, pb, pc = result_vertices[a], result_vertices[b], result_vertices[c]
        if (
            _cross(
                (float(pa[0]), float(pa[1])),
                (float(pb[0]), float(pb[1])),
                (float(pc[0]), float(pc[1])),
            )
            < 0.0
        ):
            b, c = c, b
        if len({a, b, c}) != 3:
            raise ValueError("Triangle returned a degenerate face")
        triangles.append((a, b, c))

    vertices = tuple((float(v[0]), float(v[1])) for v in result_vertices.tolist())
    mesh = TriangleMesh(vertices, tuple(triangles), tuple(boundary_indices), tuple(edge_ids))
    mesh.validate()
    expected_area = abs(signed_area(points))
    actual_area = mesh.area
    if not isfinite(expected_area) or not isfinite(actual_area):
        raise ValueError("triangulation area must be finite")
    if abs(actual_area - expected_area) > 1e-6 * max(1.0, expected_area):
        raise ValueError("triangulation area does not match pattern area")
    return mesh


def refine_linear_boundary(pattern: ParametricPattern, max_spacing: float) -> ParametricPattern:
    """Subdivide straight authored boundary segments without changing semantic identity."""
    spacing = float(max_spacing)
    if not isfinite(spacing) or spacing <= 0.0:
        raise ValueError("max boundary spacing must be positive and finite")
    segments = []
    for segment in pattern.segments:
        if isinstance(segment, LineSegment):
            steps = max(1, int(ceil(segment.length() / spacing)))
            for index in range(steps):
                start = segment.point(index / float(steps))
                end = segment.point((index + 1) / float(steps))
                suffix = "" if steps == 1 else "::sub::%d" % index
                segments.append(LineSegment(segment.id + suffix, start, end))
        else:
            segments.append(segment)
    return ParametricPattern(segments)


def _quantize(value: float) -> float:
    return round(float(value), 9)


def _deduplicate_consecutive(points: Sequence[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if not result or not (
            isclose(point[0], result[-1][0], abs_tol=1e-9)
            and isclose(point[1], result[-1][1], abs_tol=1e-9)
        ):
            result.append(point)
    if (
        len(result) > 1
        and isclose(result[0][0], result[-1][0], abs_tol=1e-9)
        and isclose(result[0][1], result[-1][1], abs_tol=1e-9)
    ):
        result.pop()
    return result


def _prepare_segment_geometries(
    pattern: ParametricPattern, curve_samples: int
) -> tuple[tuple[str, LineString], ...]:
    """Sample authored curves once and construct GEOS line strings for distance queries."""
    prepared: list[tuple[str, LineString]] = []
    for segment in pattern.segments:
        # Sketcher curves may be sampled polylines without a control attribute.
        points = (
            (segment.start, segment.end)
            if isinstance(segment, LineSegment)
            else segment.polyline(curve_samples)
        )
        prepared.append((segment.id, LineString(points)))
    return tuple(prepared)


def _nearest_segment_id(prepared_segments: Sequence[tuple[str, LineString]], point: Point) -> str:
    """Return the authored segment closest to a query point using GEOS distance."""
    query = ShapelyPoint(point)
    return min(prepared_segments, key=lambda item: item[1].distance(query))[0]


def _edge_segment_ids(pattern: ParametricPattern, points: Sequence[Point]) -> list[str]:
    """Map sampled boundary edges to authored segments with one GEOS query per edge."""
    prepared_segments = _prepare_segment_geometries(pattern, 32)
    result: list[str] = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        result.append(_nearest_segment_id(prepared_segments, midpoint))
    return result


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    """Return GEOS point-to-segment distance with coordinates scaled for tiny geometry.

    GEOS may overflow its internal projection arithmetic for subnormal-length
    segments. Translate to the segment origin and scale the coordinate
    differences into a numerically useful range before delegating the distance
    calculation to GEOS.
    """
    if point in (start, end):
        return 0.0

    with_offset = (
        end[0] - start[0],
        end[1] - start[1],
        point[0] - start[0],
        point[1] - start[1],
    )
    if not all(isfinite(value) for value in with_offset):
        raise ValueError("point-to-segment coordinate differences must be finite")
    scale = max(abs(value) for value in with_offset)
    if scale == 0.0:
        return 0.0

    dx, dy, px, py = (value / scale for value in with_offset)
    normalized_distance = LineString(((0.0, 0.0), (dx, dy))).distance(ShapelyPoint((px, py)))
    distance = scale * normalized_distance
    if not isfinite(distance):
        raise ValueError("computed point-to-segment distance must be finite")
    return distance


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    return _cross(a, b, c) / 2.0


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _self_intersects(points: Sequence[Point]) -> bool:
    """Return whether a closed polygon boundary crosses itself using GEOS."""
    if len(points) < 3:
        return False
    return not LineString([*points, points[0]]).is_simple
