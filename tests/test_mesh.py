# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for triangular pattern meshing and semantic boundary topology."""

import importlib
from collections.abc import Callable, Sequence
from math import dist
from typing import ClassVar, cast

import pytest
from hypothesis import given, strategies as st

from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    Point,
    PolylineSegment,
    QuadraticBezier,
    rectangle,
)
from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import SewingPatternMesh, build_sewing_constraints
from tests.support.assertions import require


def _load_internal_callable(module_name: str, attribute_name: str) -> object:
    """Load a test-only internal callable by its module and attribute name.

    Args:
        module_name: Dotted import path of the module under test.
        attribute_name: Internal callable attribute to retrieve.

    Returns:
        The requested module attribute.
    """
    module = importlib.import_module(module_name)
    return getattr(module, attribute_name)


BASE_BOUNDARY_VERTEX_COUNT = 4
BASE_RECTANGLE_TRIANGLE_COUNT = 2
CONCAVE_POLYGON_TRIANGLE_COUNT = 3
EXPECTED_RECTANGLE_AREA_MM2 = 5000.0
EXPECTED_CONCAVE_AREA_MM2 = 1200.0
AREA_TOLERANCE_MM2 = 1e-7
MAX_BOUNDARY_SPACING_MM = 20.000001
MINIMUM_REFINED_BOUNDARY_VERTEX_COUNT = 4
DISTANCE_FLOOR_MM = 0.0
ENDPOINT_DISTANCE_TOLERANCE_MM = 1e-8
ORIENTATION_DISTANCE_TOLERANCE_MM = 1e-8
MINIMUM_SEAM_STITCH_COUNT = 2
SUBNORMAL_DISTANCE_MM = 1e-291
SUBNORMAL_SEGMENT_LENGTH_MM = 3.858376809264568e-291
SMALL_COORDINATE_MM = 6.269632363395404e-257
SUBNORMAL_ENDPOINT_MM = 1.6724306261326825e-169
NONFINITE_AREA_LIMITS = (float("nan"), float("inf"))
DISTANCE_EXAMPLES = (
    ((1.0, 1.0), (0.0, 0.0), (2.0, 0.0), 1.0),
    ((-1.0, 0.0), (0.0, 0.0), (2.0, 0.0), 1.0),
    ((3.0, 0.0), (0.0, 0.0), (2.0, 0.0), 1.0),
    ((3.0, 4.0), (0.0, 0.0), (0.0, 0.0), 5.0),
    ((1.0, 1.0), (2.0, 0.0), (0.0, 0.0), 1.0),
    ((0.0, 0.0), (1.0, SMALL_COORDINATE_MM), (1.0, 0.0), 1.0),
    (
        (SUBNORMAL_DISTANCE_MM, 0.0),
        (0.0, 0.0),
        (0.0, SUBNORMAL_SEGMENT_LENGTH_MM),
        SUBNORMAL_DISTANCE_MM,
    ),
    ((0.0, 0.0), (0.0, 0.0), (0.0, SUBNORMAL_SEGMENT_LENGTH_MM), 0.0),
)
PROPERTY_COORDINATE_STRATEGY = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)
PROPERTY_COORDINATES = st.tuples(
    PROPERTY_COORDINATE_STRATEGY,
    PROPERTY_COORDINATE_STRATEGY,
    PROPERTY_COORDINATE_STRATEGY,
    PROPERTY_COORDINATE_STRATEGY,
    PROPERTY_COORDINATE_STRATEGY,
    PROPERTY_COORDINATE_STRATEGY,
)

EDGE_SEGMENT_IDS_FOR_TEST = cast(
    Callable[[ParametricPattern, Sequence[Point]], list[str]],
    _load_internal_callable("freecad_cloth.pattern.PatternMesh", "_edge_segment_ids"),
)
POINT_TO_SEGMENT_DISTANCE_FOR_TEST = cast(
    Callable[[Point, Point, Point], float],
    _load_internal_callable("freecad_cloth.pattern.PatternMesh", "_point_to_segment_distance"),
)
INDEXED_MESH_TOPOLOGY_FOR_TEST = cast(
    Callable[
        [tuple[tuple[int, int, int], ...]],
        tuple[tuple[int, ...], tuple[tuple[int, ...], ...]],
    ],
    _load_internal_callable(
        "freecad_cloth.simulation.SimulationObjects", "_indexed_mesh_topology"
    ),
)


def test_rectangle_mesh_area_and_topology() -> None:
    """Preserve rectangle area, triangulation counts, and authored edge identity."""
    mesh = triangulate(rectangle(100.0, 50.0))

    require(
        condition=len(mesh.vertices) == BASE_BOUNDARY_VERTEX_COUNT,
        message="A rectangular boundary must retain its four authored vertices.",
    )
    require(
        condition=len(mesh.triangles) == BASE_RECTANGLE_TRIANGLE_COUNT,
        message="A rectangular panel must triangulate into two faces.",
    )
    require(
        condition=mesh.area == pytest.approx(EXPECTED_RECTANGLE_AREA_MM2, abs=AREA_TOLERANCE_MM2),
        message="Triangulation must preserve the rectangle area.",
    )
    require(
        condition=mesh.boundary_edge_segment_ids == ("bottom", "right", "top", "left"),
        message="The mesh boundary must retain authored rectangle segment IDs.",
    )
    mesh.validate()


def test_concave_polygon_triangulates() -> None:
    """Preserve area and edge provenance for a concave authored polygon."""
    pattern = ParametricPattern(
        [
            LineSegment("a", (0, 0), (40, 0)),
            LineSegment("b", (40, 0), (40, 40)),
            LineSegment("c", (40, 40), (20, 20)),
            LineSegment("d", (20, 20), (0, 40)),
            LineSegment("e", (0, 40), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)

    require(
        condition=len(mesh.triangles) == CONCAVE_POLYGON_TRIANGLE_COUNT,
        message="The concave polygon must triangulate into three faces.",
    )
    require(
        condition=mesh.area == pytest.approx(EXPECTED_CONCAVE_AREA_MM2, abs=AREA_TOLERANCE_MM2),
        message="Triangulation must preserve the authored concave polygon area.",
    )
    require(
        condition=mesh.boundary_edge_segment_ids == ("a", "b", "c", "d", "e"),
        message="Concave boundary edges must retain their authored IDs.",
    )


def test_polyline_curve_keeps_semantic_provenance_at_both_endpoints() -> None:
    """Assign curved boundary spans to the authored curve, not neighboring lines."""
    pattern = ParametricPattern(
        [
            LineSegment("bottom", (0, 0), (100, 0)),
            LineSegment("right", (100, 0), (100, 100)),
            PolylineSegment(
                "scoop",
                ((100, 100), (99, 90), (50, 80), (1, 90), (0, 100)),
            ),
            LineSegment("left", (0, 100), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)

    require(
        condition=mesh.boundary_edge_segment_ids
        == ("bottom", "right", "scoop", "scoop", "scoop", "scoop", "left"),
        message="Endpoint-near curved spans must retain the curve's semantic provenance.",
    )


def test_reversed_rectangle_retains_segment_provenance() -> None:
    """Preserve authored edge IDs when the source rectangle is traversed in reverse."""
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 50), (0, 0)),
            LineSegment("bottom", (0, 0), (100, 0)),
            LineSegment("right", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
        ]
    )
    mesh = triangulate(pattern)

    require(
        condition=mesh.boundary_edge_segment_ids == ("left", "bottom", "right", "top"),
        message="Reversed rectangle edges must preserve the original segment IDs.",
    )


def test_clockwise_outline_keeps_segment_provenance_on_normalization() -> None:
    """Keep each authored segment ID attached after clockwise winding normalization."""
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 0), (0, 50)),
            LineSegment("top", (0, 50), (100, 50)),
            LineSegment("right", (100, 50), (100, 0)),
            LineSegment("bottom", (100, 0), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)

    require(
        condition=mesh.boundary_edge_segment_ids == ("right", "top", "left", "bottom"),
        message="Clockwise normalization must preserve matching segment provenance.",
    )


def test_linear_boundary_refinement_preserves_authored_segment_identity_and_spacing() -> None:
    """Subdivide linear boundaries without losing source identity or spacing guarantees."""
    pattern = ParametricPattern(
        [
            LineSegment("side", (0, 0), (100, 0)),
            LineSegment("back", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
            LineSegment("left", (0, 50), (0, 0)),
        ]
    )
    mesh = triangulate(refine_linear_boundary(pattern, 20.0))
    authored_ids = ("side", "back", "top", "left")
    boundary_ids = mesh.boundary_edge_segment_ids

    require(
        condition=len(mesh.boundary_vertex_indices) > MINIMUM_REFINED_BOUNDARY_VERTEX_COUNT,
        message="Linear refinement must add boundary vertices beyond the base rectangle.",
    )
    require(
        condition=all(
            identifier == authored or identifier.startswith(f"{authored}::sub::")
            for authored in authored_ids
            for identifier in boundary_ids
            if identifier.startswith(authored)
        ),
        message="Refined segments must retain the authored ID as their prefix.",
    )
    require(
        condition=any(identifier.startswith("side::sub::") for identifier in boundary_ids),
        message="The side edge must expose at least one refined semantic segment ID.",
    )
    require(
        condition=max(dist(mesh.vertices[a], mesh.vertices[b]) for a, b in mesh.boundary_edges())
        <= MAX_BOUNDARY_SPACING_MM,
        message="Every refined boundary edge must respect the maximum spacing.",
    )


@pytest.mark.parametrize(("point", "start", "end", "expected_distance"), DISTANCE_EXAMPLES)
def test_point_to_segment_distance_handles_projection_and_degenerate_segments(
    point: Point,
    start: Point,
    end: Point,
    expected_distance: float,
) -> None:
    """Measure projection, endpoint clamping, reversed endpoints, and degenerate segments.

    Args:
        point: Query point in pattern coordinates.
        start: First endpoint of the candidate segment.
        end: Second endpoint of the candidate segment.
        expected_distance: Expected Euclidean point-to-segment distance.
    """
    actual = POINT_TO_SEGMENT_DISTANCE_FOR_TEST(point, start, end)

    require(
        condition=actual == pytest.approx(expected_distance, rel=1e-12, abs=0.0),
        message="Point-to-segment distance must match the geometric reference case.",
    )


def test_point_to_segment_distance_handles_subnormal_segment_length() -> None:
    """Keep the finite distance contract for extremely short representable segments."""
    distance = point_to_segment_distance_for_test(
        (1.0, 0.0),
        (0.0, 0.0),
        (0.0, SUBNORMAL_ENDPOINT_MM),
    )
    require(
        condition=distance == pytest.approx(1.0, rel=1e-12, abs=0.0),
        message="A subnormal segment must retain the nearest distance to a unit-offset point.",
    )


@given(values=PROPERTY_COORDINATES)
def test_point_to_segment_distance_obeys_metric_properties(
    values: tuple[float, float, float, float, float, float],
) -> None:
    """Verify non-negativity, endpoint bounds, and orientation invariance over finite points.

    Args:
        values: Generated query, start, and end coordinates in flattened XY order.
    """
    px, py, sx, sy, ex, ey = values
    point, start, end = (px, py), (sx, sy), (ex, ey)
    distance = point_to_segment_distance_for_test(point, start, end)
    reversed_distance = point_to_segment_distance_for_test(point, end, start)
    endpoint_bound = min(dist(point, start), dist(point, end))

    require(
        condition=distance >= DISTANCE_FLOOR_MM,
        message="Point-to-segment distance must never be negative.",
    )
    require(
        condition=distance <= endpoint_bound + ENDPOINT_DISTANCE_TOLERANCE_MM,
        message="The closest point on a segment cannot be farther than its nearest endpoint.",
    )
    require(
        condition=abs(distance - reversed_distance) <= ORIENTATION_DISTANCE_TOLERANCE_MM,
        message="Reversing a segment's endpoints must not change its distance.",
    )


def test_seam_generates_stitches() -> None:
    """Create multiple stitch links for matching authored boundary segments."""
    pattern_a = rectangle(100.0, 50.0)
    pattern_b = rectangle(100.0, 50.0)
    side_a = SewingPatternMesh(pattern_a, triangulate(pattern_a))
    side_b = SewingPatternMesh(pattern_b, triangulate(pattern_b))
    constraints = build_sewing_constraints(
        side_a,
        side_b,
        Seam("front", 1, "back", 3, id="side"),
        samples=5,
    )

    require(
        condition=len(constraints.stitches) >= MINIMUM_SEAM_STITCH_COUNT,
        message="Matching seam edges must create at least two stitch links.",
    )
    constraints.validate()


@pytest.mark.parametrize("max_area", NONFINITE_AREA_LIMITS)
def test_triangulation_rejects_nonfinite_area_limits(max_area: float) -> None:
    """Reject a non-finite area limit before it enters constrained triangulation.

    Args:
        max_area: Non-finite area value presented to the mesher.
    """
    with pytest.raises(ValueError, match="finite"):
        triangulate(rectangle(10.0, 10.0), max_area=max_area)


def test_curve_polyline_is_sampled_once_during_segment_provenance_mapping() -> None:
    """Sample each authored curve once while resolving semantic boundary provenance."""

    class CountedCurve(QuadraticBezier):
        """Count sampling calls made by the provenance mapper."""

        calls: ClassVar[int] = 0

        def polyline(self, samples: int = 32) -> list[Point]:
            """Count one sampling request and delegate to the quadratic curve.

            Args:
                samples: Requested number of polyline samples.

            Returns:
                Sampled quadratic curve points.
            """
            type(self).calls += 1
            return super().polyline(samples)

    curve = CountedCurve("curve", (0.0, 0.0), (5.0, 10.0), (10.0, 0.0))
    outline = ((0.0, 0.0), (10.0, 0.0), (10.0, -10.0), (0.0, -10.0))
    pattern = ParametricPattern(
        [
            curve,
            LineSegment("right", (10.0, 0.0), (10.0, -10.0)),
            LineSegment("bottom", (10.0, -10.0), (0.0, -10.0)),
            LineSegment("left", (0.0, -10.0), (0.0, 0.0)),
        ]
    )
    CountedCurve.calls = 0
    result = EDGE_SEGMENT_IDS_FOR_TEST(pattern, outline)

    require(
        condition=len(result) == len(outline),
        message="Provenance mapping must return one segment ID per boundary edge.",
    )
    require(
        condition=CountedCurve.calls == 1,
        message="The authored curve polyline must be sampled once per mapping operation.",
    )


def test_indexed_mesh_topology_reuses_shared_vertices_and_remaps_faces() -> None:
    """Map shared global indices to compact local vertex and triangle indices."""
    triangles = ((0, 1, 2), (0, 2, 3), (5, 6, 7), (3, 2, 0))
    expected_vertices = (0, 1, 2, 3, 5, 6, 7)
    expected_faces = ((0, 1, 2), (0, 2, 3), (4, 5, 6), (3, 2, 0))

    result = INDEXED_MESH_TOPOLOGY_FOR_TEST(triangles)
    vertex_indices, faces = result

    require(
        condition=vertex_indices == expected_vertices,
        message="Topology compaction must retain sorted unique source vertex indices.",
    )
    require(
        condition=faces == expected_faces,
        message="Topology compaction must consistently remap every triangle index.",
    )
    require(
        condition=INDEXED_MESH_TOPOLOGY_FOR_TEST(triangles) is result,
        message="Repeated topology input must reuse its cached compact mapping.",
    )
