# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-independent surface mesh generation for pattern pieces.

The mesher consumes the sewing boundary rather than the cut boundary: seam
allowance is manufacturing geometry, while the cloth solver needs the
physical panel boundary. Constrained Delaunay triangulation is delegated to
Jonathan Shewchuk's Triangle library; the rest of this module preserves the
workbench's semantic boundary/provenance contract.
"""

from collections.abc import Sequence
from math import ceil, hypot, isclose, isfinite

import numpy as np
from pydantic.dataclasses import dataclass as pydantic_dataclass
from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint

from freecad_cloth.common.ValidationModels import TriangulationOptions
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, Point, signed_area


TRIANGLE_VERTEX_COUNT = 3
TRIANGLE_ARRAY_DIMENSIONS = 2
MINIMUM_OUTLINE_AREA_MM2 = 1e-9
TRIANGULATION_AREA_RELATIVE_TOLERANCE = 1e-6
VERTEX_RECONCILIATION_DECIMALS = 9
CURVE_PROVENANCE_SAMPLES = 32


@pydantic_dataclass(frozen=True)
class TriangleMesh:
    """Triangle mesh in pattern coordinates, in millimetres."""

    vertices: tuple[Point, ...]
    triangles: tuple[tuple[int, int, int], ...]
    boundary_vertex_indices: tuple[int, ...]
    boundary_edge_segment_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        """Validate mesh indices, boundary data, and finite vertex coordinates.

        Raises:
            ValueError: If vertices, triangles, boundary indices, or provenance are invalid.
        """
        if len(self.vertices) < TRIANGLE_VERTEX_COUNT:
            msg = "mesh needs at least three vertices"
            raise ValueError(msg)
        if not self.triangles:
            msg = "mesh needs at least one triangle"
            raise ValueError(msg)

        vertices: np.ndarray | None = None
        valid_vertices = False
        try:
            vertices = np.asarray(self.vertices, dtype=np.float64)
            valid_vertices = vertices.shape == (len(self.vertices), 2) and bool(
                np.isfinite(vertices).all()
            )
        except (TypeError, ValueError, OverflowError):
            valid_vertices = False
        if vertices is None or not valid_vertices:
            msg = "mesh coordinates must be finite 2D points"
            raise ValueError(msg)
        vertex_count = len(vertices)

        valid_triangles = all(
            len(triangle) == TRIANGLE_VERTEX_COUNT
            and all(type(index) is int and 0 <= index < vertex_count for index in triangle)
            and len(set(triangle)) == TRIANGLE_VERTEX_COUNT
            for triangle in self.triangles
        )
        if not valid_triangles:
            msg = "invalid triangle index"
            raise ValueError(msg)

        if len(self.boundary_vertex_indices) < TRIANGLE_VERTEX_COUNT:
            msg = "mesh needs at least three boundary vertices"
            raise ValueError(msg)
        try:
            boundary = np.asarray(self.boundary_vertex_indices)
            valid_boundary = (
                boundary.shape == (len(self.boundary_vertex_indices),)
                and np.issubdtype(boundary.dtype, np.integer)
                and bool(((boundary >= 0) & (boundary < vertex_count)).all())
            )
        except (TypeError, ValueError, OverflowError):
            valid_boundary = False
        if not valid_boundary:
            msg = "invalid boundary vertex index"
            raise ValueError(msg)
        if self.boundary_edge_segment_ids and len(self.boundary_edge_segment_ids) != len(
            self.boundary_vertex_indices
        ):
            msg = "boundary provenance must match boundary edge count"
            raise ValueError(msg)

    @property
    def area(self) -> float:
        """Area of the triangle mesh in square millimetres.

        Returns:
            Sum of the absolute areas of all mesh triangles.

        Raises:
            ValueError: If the computed area is not finite.
        """
        vertices = np.asarray(self.vertices, dtype=np.float64)
        triangles = np.asarray(self.triangles, dtype=np.intp)
        first = vertices[triangles[:, 0]]
        edge_a = vertices[triangles[:, 1]] - first
        edge_b = vertices[triangles[:, 2]] - first
        doubled_area = edge_a[:, 0] * edge_b[:, 1] - edge_a[:, 1] * edge_b[:, 0]
        total = float(np.abs(doubled_area).sum(dtype=np.float64) / 2.0)
        if not isfinite(total):
            msg = "computed mesh area must be finite"
            raise ValueError(msg)
        return total

    def boundary_edges(self) -> tuple[tuple[int, int], ...]:
        """Return consecutive vertex-index pairs around the mesh boundary.

        Returns:
            Boundary edges in boundary-vertex order, including the closing edge.
        """
        indices = self.boundary_vertex_indices
        return tuple((indices[i], indices[(i + 1) % len(indices)]) for i in range(len(indices)))


def triangulate(
    pattern: ParametricPattern, curve_samples: int = 16, max_area: float | None = None
) -> TriangleMesh:
    """Triangulate a sampled simple polygon with constrained Delaunay Triangle.

    The optional maximum area delegates simulation mesh refinement to Triangle.
    The Y switch forbids Steiner points on authored boundary segments, preserving
    semantic seam edge indices while Triangle adds interior vertices where needed.

    Args:
        pattern: Authored polygon boundary to triangulate.
        curve_samples: Sampling count for each curved boundary segment.
        max_area: Optional positive maximum triangle area for interior refinement.

    Returns:
        Validated triangular mesh with semantic boundary provenance.

    """
    options = TriangulationOptions.model_validate(
        {"curve_samples": curve_samples, "max_area": max_area}
    )
    points, edge_ids = _normalized_boundary(pattern, options.curve_samples)
    result_vertices, result_triangles = _run_triangle_triangulation(points, options.max_area)
    boundary_indices = _map_boundary_vertices(points, result_vertices)
    triangles = _orient_triangles(result_triangles, result_vertices)
    vertices = tuple((float(vertex[0]), float(vertex[1])) for vertex in result_vertices.tolist())
    mesh = TriangleMesh(vertices, tuple(triangles), tuple(boundary_indices), tuple(edge_ids))
    mesh.validate()
    _validate_triangulation_area(mesh, points)
    return mesh


def _normalized_boundary(
    pattern: ParametricPattern,
    curve_samples: int,
) -> tuple[list[Point], list[str]]:
    """Prepare the sampled polygon boundary and preserve segment provenance.

    Args:
        pattern: Authored parametric pattern.
        curve_samples: Number of samples for each curved segment.

    Returns:
        Counter-clockwise boundary points and their authored segment IDs.

    Raises:
        ValueError: If the sampled boundary has too few points, zero area, or self-intersects.
    """
    points = _deduplicate_consecutive(pattern.sampled_outline(curve_samples))
    if len(points) < TRIANGLE_VERTEX_COUNT:
        msg = "pattern has too few distinct boundary points"
        raise ValueError(msg)
    outline_area = signed_area(points)
    if abs(outline_area) < MINIMUM_OUTLINE_AREA_MM2:
        msg = "pattern has zero area"
        raise ValueError(msg)
    if _self_intersects(points):
        msg = "pattern boundary self-intersects"
        raise ValueError(msg)

    if all(isinstance(segment, LineSegment) for segment in pattern.segments) and len(points) == len(
        pattern.segments
    ):
        edge_ids = [segment.id for segment in pattern.segments]
    else:
        edge_ids = _edge_segment_ids(pattern, points)
    if outline_area < 0.0:
        points = list(reversed(points))
        # Recompute provenance from geometry after normalization. A refined
        # authored edge can contain several internal sub-segments, so a fixed
        # one-slot rotation is not a valid semantic mapping.
        edge_ids = _edge_segment_ids(pattern, points)
    return points, edge_ids


def _run_triangle_triangulation(
    points: Sequence[Point],
    max_area: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run Triangle and validate its raw vertex/face arrays.

    Args:
        points: Counter-clockwise sampled polygon boundary.
        max_area: Optional maximum area for interior mesh refinement.

    Returns:
        Triangle's finite vertex array and triangular face-index array.

    Raises:
        ValueError: If Triangle returns invalid topology or changes the boundary unexpectedly.
        RuntimeError: If the required Triangle package is unavailable.
    """
    try:
        import triangle as tr
    except ImportError as exc:
        msg = "PatternMesh requires the 'triangle' package (Shewchuk constrained Delaunay meshing)"
        raise RuntimeError(msg) from exc

    vertices_in = np.asarray(points, dtype=np.float64)
    segments = np.asarray(
        [(index, (index + 1) % len(points)) for index in range(len(points))],
        dtype=np.int32,
    )
    triangle_options = "pQ"
    if max_area is not None:
        triangle_options += f"Ya{max_area:.12g}"
    result = tr.triangulate({"vertices": vertices_in, "segments": segments}, triangle_options)
    result_vertices = np.asarray(result.get("vertices", ()), dtype=np.float64)
    result_triangles = np.asarray(result.get("triangles", ()), dtype=np.int64)
    if len(result_vertices) == 0:
        msg = "Triangle returned no vertices"
        raise ValueError(msg)
    if (
        result_triangles.ndim != TRIANGLE_ARRAY_DIMENSIONS
        or result_triangles.shape[1] != TRIANGLE_VERTEX_COUNT
    ):
        msg = "Triangle returned no triangular faces"
        raise ValueError(msg)
    if max_area is None and len(result_vertices) != len(points):
        msg = (
            "Triangle inserted or removed vertices unexpectedly; expected a boundary-only base mesh"
        )
        raise ValueError(msg)
    return result_vertices, result_triangles


def _map_boundary_vertices(
    points: Sequence[Point],
    result_vertices: np.ndarray,
) -> list[int]:
    """Map authored boundary points to Triangle's vertex indices.

    Args:
        points: Authored sampled boundary points.
        result_vertices: Vertices returned by Triangle.

    Returns:
        Boundary vertex indices in the same order as the authored points.

    Raises:
        ValueError: If Triangle drops an authored boundary vertex.
    """
    output_index_by_coordinate: dict[tuple[float, float], int] = {}
    for index, vertex in enumerate(result_vertices):
        key = (_quantize(float(vertex[0])), _quantize(float(vertex[1])))
        output_index_by_coordinate.setdefault(key, index)

    boundary_indices: list[int] = []
    for x, y in points:
        key = (_quantize(x), _quantize(y))
        index = output_index_by_coordinate.get(key)
        if index is None:
            msg = "Triangle dropped an authored boundary vertex"
            raise ValueError(msg)
        boundary_indices.append(index)
    return boundary_indices


def _orient_triangles(
    result_triangles: np.ndarray,
    result_vertices: np.ndarray,
) -> list[tuple[int, int, int]]:
    """Normalize triangle winding and reject repeated vertex indices.

    Args:
        result_triangles: Raw faces returned by Triangle.
        result_vertices: Vertex coordinates used to determine face orientation.

    Returns:
        Triangles with counter-clockwise winding.

    Raises:
        ValueError: If Triangle returns a degenerate face.
    """
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
        if len({a, b, c}) != TRIANGLE_VERTEX_COUNT:
            msg = "Triangle returned a degenerate face"
            raise ValueError(msg)
        triangles.append((a, b, c))
    return triangles


def _validate_triangulation_area(mesh: TriangleMesh, points: Sequence[Point]) -> None:
    """Verify that triangulation preserves the authored polygon area.

    Args:
        mesh: Validated triangulated mesh.
        points: Normalized authored polygon boundary.

    Raises:
        ValueError: If area calculations are non-finite or the area delta is too large.
    """
    expected_area = abs(signed_area(points))
    actual_area = mesh.area
    if not isfinite(expected_area) or not isfinite(actual_area):
        msg = "triangulation area must be finite"
        raise ValueError(msg)
    if abs(actual_area - expected_area) > TRIANGULATION_AREA_RELATIVE_TOLERANCE * max(
        1.0, expected_area
    ):
        msg = "triangulation area does not match pattern area"
        raise ValueError(msg)


def refine_linear_boundary(pattern: ParametricPattern, max_spacing: float) -> ParametricPattern:
    """Subdivide straight authored boundary segments without changing semantic identity.

    Args:
        pattern: Authored boundary whose straight segments may be subdivided.
        max_spacing: Maximum allowed spacing between linear boundary vertices.

    Returns:
        Pattern with refined linear segments and stable authored-segment identity.

    Raises:
        ValueError: If the maximum spacing is not positive and finite.
    """
    spacing = float(max_spacing)
    if not isfinite(spacing) or spacing <= 0.0:
        msg = "max boundary spacing must be positive and finite"
        raise ValueError(msg)
    segments = []
    for segment in pattern.segments:
        if isinstance(segment, LineSegment):
            steps = max(1, ceil(segment.length() / spacing))
            for index in range(steps):
                start = segment.point(index / steps)
                end = segment.point((index + 1) / steps)
                suffix = "" if steps == 1 else f"::sub::{index}"
                segments.append(LineSegment(segment.id + suffix, start, end))
        else:
            segments.append(segment)
    return ParametricPattern(segments)


def _quantize(value: float) -> float:
    """Round a coordinate to the precision used for vertex reconciliation.

    Args:
        value: Finite coordinate value.

    Returns:
        Coordinate rounded to nine decimal places.
    """
    return round(float(value), VERTEX_RECONCILIATION_DECIMALS)


def _deduplicate_consecutive(points: Sequence[Point]) -> list[Point]:
    """Remove adjacent duplicate points and a repeated polygon-closing point.

    Args:
        points: Ordered boundary points to deduplicate.

    Returns:
        Points with consecutive and closing duplicates removed.
    """
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
    """Sample authored curves once and construct GEOS line strings for distance queries.

    Args:
        pattern: Authored boundary segments to sample.
        curve_samples: Number of points used to sample each curved segment.

    Returns:
        Segment IDs paired with their prepared GEOS line strings.
    """
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
    """Return the authored segment closest to a query point using GEOS distance.

    Args:
        prepared_segments: Authored segment IDs paired with their GEOS geometries.
        point: Query point in pattern coordinates.

    Returns:
        ID of the closest authored segment.
    """
    query = ShapelyPoint(point)
    return min(prepared_segments, key=lambda item: item[1].distance(query))[0]


def _edge_segment_ids(pattern: ParametricPattern, points: Sequence[Point]) -> list[str]:
    """Map sampled boundary edges to authored segments with one GEOS query per edge.

    Args:
        pattern: Authored segments used as provenance candidates.
        points: Ordered points of the sampled boundary.

    Returns:
        Segment ID for each boundary edge, in boundary order.
    """
    prepared_segments = _prepare_segment_geometries(pattern, CURVE_PROVENANCE_SAMPLES)
    result: list[str] = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        result.append(_nearest_segment_id(prepared_segments, midpoint))
    return result


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    """Return a robust point-to-segment distance, including subnormal segments.

    Normalize coordinate differences before asking GEOS to avoid overflow for
    tiny coordinates. If GEOS still returns a non-finite distance because its
    projection arithmetic underflows, use a unit-direction projection fallback.

    Args:
        point: Point to measure against the segment.
        start: First endpoint of the segment.
        end: Second endpoint of the segment.

    Returns:
        Finite Euclidean distance in pattern-coordinate units.

    Raises:
        ValueError: If coordinate differences or the computed distance are non-finite.
    """
    if point in {start, end}:
        return 0.0

    with_offset = (
        end[0] - start[0],
        end[1] - start[1],
        point[0] - start[0],
        point[1] - start[1],
    )
    if not all(isfinite(value) for value in with_offset):
        msg = "point-to-segment coordinate differences must be finite"
        raise ValueError(msg)
    scale = max(abs(value) for value in with_offset)
    if not scale:
        return 0.0

    dx, dy, px, py = (value / scale for value in with_offset)
    normalized_distance = float(LineString(((0.0, 0.0), (dx, dy))).distance(ShapelyPoint((px, py))))
    distance = scale * normalized_distance
    if isfinite(distance):
        return distance
    return _fallback_point_to_segment_distance(point, start, end)


def _fallback_point_to_segment_distance(
    point: Point,
    start: Point,
    end: Point,
) -> float:
    """Calculate point-to-segment distance using a unit-direction projection.

    Args:
        point: Point to measure against the segment.
        start: First segment endpoint.
        end: Second segment endpoint.

    Returns:
        Finite Euclidean distance using the closest clamped segment position.

    Raises:
        ValueError: If the fallback produces a non-finite distance.
    """
    sx, sy = start
    px, py = point
    dx, dy = end[0] - sx, end[1] - sy
    length = hypot(dx, dy)
    if not length:
        distance = hypot(px - sx, py - sy)
    else:
        unit_x, unit_y = dx / length, dy / length
        projection = (px - sx) * unit_x + (py - sy) * unit_y
        clamped = max(0.0, min(length, projection))
        closest_x = sx + clamped * unit_x
        closest_y = sy + clamped * unit_y
        distance = hypot(px - closest_x, py - closest_y)
    if not isfinite(distance):
        msg = "computed point-to-segment distance must be finite"
        raise ValueError(msg)
    return distance


def _cross(a: Point, b: Point, c: Point) -> float:
    """Return twice the signed area of the triangle formed by three points.

    Args:
        a: First point.
        b: Second point.
        c: Third point.

    Returns:
        Positive, negative, or zero determinant according to point orientation.
    """
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _self_intersects(points: Sequence[Point]) -> bool:
    """Return whether a closed polygon boundary crosses itself using GEOS.

    Args:
        points: Ordered vertices of the closed polygon boundary.

    Returns:
        Whether the boundary is not simple, excluding undersized point lists.
    """
    if len(points) < TRIANGLE_VERTEX_COUNT:
        return False
    return not LineString([*points, points[0]]).is_simple
