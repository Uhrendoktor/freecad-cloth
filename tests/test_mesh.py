import sys
from math import dist
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    QuadraticBezier,
    rectangle,
)
from freecad_cloth.pattern.PatternMesh import (
    _edge_segment_ids,
    _point_to_segment_distance,
    refine_linear_boundary,
    triangulate,
)
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import build_sewing_constraints


def test_rectangle_mesh_area_and_topology():
    pattern = rectangle(100.0, 50.0)
    mesh = triangulate(pattern)
    assert len(mesh.vertices) == 4
    assert len(mesh.triangles) == 2
    assert abs(mesh.area - 5000.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("bottom", "right", "top", "left")
    mesh.validate()


def test_concave_polygon_triangulates():
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
    assert len(mesh.triangles) == 3
    assert abs(mesh.area - 1200.0) < 1e-7
    assert mesh.boundary_edge_segment_ids == ("a", "b", "c", "d", "e")


def test_reversed_rectangle_retains_segment_provenance():
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 50), (0, 0)),
            LineSegment("bottom", (0, 0), (100, 0)),
            LineSegment("right", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
        ]
    )
    mesh = triangulate(pattern)
    assert mesh.boundary_edge_segment_ids == ("left", "bottom", "right", "top")


def test_clockwise_outline_keeps_segment_provenance_on_normalization():
    # This order is genuinely clockwise: bottom-left -> top-left -> top-right -> bottom-right.
    pattern = ParametricPattern(
        [
            LineSegment("left", (0, 0), (0, 50)),
            LineSegment("top", (0, 50), (100, 50)),
            LineSegment("right", (100, 50), (100, 0)),
            LineSegment("bottom", (100, 0), (0, 0)),
        ]
    )
    mesh = triangulate(pattern)
    assert mesh.boundary_edge_segment_ids == ("right", "top", "left", "bottom")


def test_linear_boundary_refinement_preserves_authored_segment_identity_and_spacing():
    pattern = ParametricPattern(
        [
            LineSegment("side", (0, 0), (100, 0)),
            LineSegment("back", (100, 0), (100, 50)),
            LineSegment("top", (100, 50), (0, 50)),
            LineSegment("left", (0, 50), (0, 0)),
        ]
    )
    refined = refine_linear_boundary(pattern, 20.0)
    mesh = triangulate(refined)
    assert len(mesh.boundary_vertex_indices) > 4
    ids = mesh.boundary_edge_segment_ids
    assert all(
        identifier == authored or identifier.startswith(authored + "::sub::")
        for authored in ("side", "back", "top", "left")
        for identifier in ids
        if identifier.startswith(authored)
    )
    assert any(identifier.startswith("side::sub::") for identifier in ids)
    points = mesh.vertices
    assert max(dist(points[a], points[b]) for a, b in mesh.boundary_edges()) <= 20.000001


def test_point_to_segment_distance_handles_projection_and_degenerate_segments():
    assert _point_to_segment_distance((1.0, 1.0), (0.0, 0.0), (2.0, 0.0)) == 1.0
    assert _point_to_segment_distance((-1.0, 0.0), (0.0, 0.0), (2.0, 0.0)) == 1.0
    assert _point_to_segment_distance((3.0, 0.0), (0.0, 0.0), (2.0, 0.0)) == 1.0
    assert _point_to_segment_distance((3.0, 4.0), (0.0, 0.0), (0.0, 0.0)) == 5.0
    assert _point_to_segment_distance((1.0, 1.0), (2.0, 0.0), (0.0, 0.0)) == 1.0
    assert (
        _point_to_segment_distance((1e-291, 0.0), (0.0, 0.0), (0.0, 3.858376809264568e-291))
        == 1e-291
    )
    assert _point_to_segment_distance((0.0, 0.0), (0.0, 0.0), (0.0, 3.858376809264568e-291)) == 0.0

def test_point_to_segment_distance_handles_subnormal_segment_length():
    endpoint = 1.6724306261326825e-169
    assert _point_to_segment_distance((0.0, 0.0), (0.0, 0.0), (0.0, endpoint)) == 0.0
    distance = _point_to_segment_distance((1.0, 0.0), (0.0, 0.0), (0.0, endpoint))
    assert distance == 1.0



@given(
    px=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    py=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    sx=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    sy=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    ex=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    ey=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_point_to_segment_distance_obeys_metric_properties(
    px: float, py: float, sx: float, sy: float, ex: float, ey: float
) -> None:
    """GEOS-backed distance is non-negative, endpoint-bounded, and orientation-invariant."""
    point, start, end = (px, py), (sx, sy), (ex, ey)
    distance = _point_to_segment_distance(point, start, end)
    reversed_distance = _point_to_segment_distance(point, end, start)
    endpoint_bound = min(dist(point, start), dist(point, end))
    assert distance >= 0.0
    assert distance <= endpoint_bound + 1e-8
    assert abs(distance - reversed_distance) <= 1e-8


def test_seam_generates_stitches():
    a = rectangle(100.0, 50.0)
    b = rectangle(100.0, 50.0)
    ma, mb = triangulate(a), triangulate(b)
    constraints = build_sewing_constraints(
        a, ma, b, mb, Seam("front", 1, "back", 3, id="side"), samples=5
    )
    assert len(constraints.stitches) >= 2
    constraints.validate()


def test_triangulation_rejects_nonfinite_area_limits() -> None:
    """NaN and infinity must not bypass the maximum-area positivity guard."""
    for max_area in (float("nan"), float("inf")):
        try:
            triangulate(rectangle(10.0, 10.0), max_area=max_area)
        except ValueError as exc:
            assert "finite" in str(exc).lower()
        else:
            raise AssertionError("non-finite max_area was accepted")


def test_curve_polyline_is_sampled_once_during_segment_provenance_mapping() -> None:
    class CountedCurve(QuadraticBezier):
        calls = 0

        def polyline(self, samples=32):
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
    result = _edge_segment_ids(pattern, outline)
    assert len(result) == len(outline)
    assert CountedCurve.calls == 1


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("mesh tests passed")
