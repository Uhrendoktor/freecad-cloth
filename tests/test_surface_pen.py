# Copyright (C) 2026 FreeCAD Cloth contributors
"""Pure tests for the bounded 3D Pattern Pen surface-authoring contract."""

from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.SurfacePen import (
    SurfaceAnchor,
    close_surface_stroke,
    flatten_surface_patch,
    pick_surface_point,
    polygon_area_2d,
    polygon_self_intersects,
    simplify_polyline,
    surface_segments_from_anchor_kinds,
    surface_stroke_can_finish,
)
from tests.support.assertions import require, require_not_none

EXPECTED_QUADRILATERAL_VERTICES = 4
EXPECTED_SEGMENT_COUNT = 4
PLANAR_DEVIATION_TOLERANCE_MM = 1e-9
AREA_TOLERANCE_MM2 = 1e-6
EXPECTED_PLANAR_AREA_MM2 = 4000.0
CLOSURE_TOLERANCE_MM = 1.0
CURVATURE_LIMIT_MM = 2.0
EXPECTED_PICK_POINT = (10.0, 20.0, 30.0)
NON_UNIT_PICK_NORMAL = (0.0, 0.0, 2.0)
EXPECTED_PICK_NORMAL = (0.0, 0.0, 1.0)
EXPECTED_SIMPLIFIED_POLYLINE = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
EXPECTED_BSPLINE_SEGMENT = ("bspline", ((0.0, 0.0), (40.0, 20.0), (80.0, 0.0)))
EXPECTED_LINE_SEGMENTS = (
    ("line", ((80.0, 0.0), (100.0, 80.0))),
    ("line", ((100.0, 80.0), (0.0, 80.0))),
    ("line", ((0.0, 80.0), (0.0, 0.0))),
)


def test_flatten_surface_patch_accepts_planar_boundary() -> None:
    """Verify planar boundaries flatten without introducing geometric deviation."""
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 0), (0, 50, 0))
    patch = flatten_surface_patch(points, tolerance_mm=0.1)
    require(
        condition=len(patch.points) == EXPECTED_QUADRILATERAL_VERTICES,
        message="Planar boundary should retain its four corner points.",
    )
    require(
        condition=patch.max_deviation_mm <= PLANAR_DEVIATION_TOLERANCE_MM,
        message="Planar boundary should flatten within numerical precision.",
    )
    area = polygon_area_2d(patch.points)
    require(
        condition=abs(abs(area) - EXPECTED_PLANAR_AREA_MM2) < AREA_TOLERANCE_MM2,
        message="Flattened rectangle should preserve its authored area.",
    )


def test_flatten_surface_patch_rejects_curvature_beyond_limit() -> None:
    """Verify excessive curvature is rejected at the configured deviation limit."""
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 12), (0, 50, 0))
    with pytest.raises(ValueError, match="too curved"):
        flatten_surface_patch(points, tolerance_mm=CURVATURE_LIMIT_MM)


def test_close_surface_stroke_accepts_nearby_closing_sample() -> None:
    """Verify a nearby closing sample is removed while preserving the authored boundary."""
    anchors = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0.5, 0.2, 0), (0, 0, 1)),
    )
    closed = close_surface_stroke(anchors, tolerance_mm=CLOSURE_TOLERANCE_MM)
    require(
        condition=len(closed) == EXPECTED_QUADRILATERAL_VERTICES,
        message="Closing sample should be removed from the resulting boundary.",
    )
    require(
        condition=closed[0] == anchors[0],
        message="Closing should preserve the first authored anchor.",
    )
    require(
        condition=closed[-1] == anchors[3],
        message="Closing should preserve the final distinct boundary anchor.",
    )


def test_surface_stroke_can_finish_requires_closed_distinct_boundary() -> None:
    """Verify finishing requires a closed boundary with distinct points."""
    closed = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0.5, 0.2, 0), (0, 0, 1)),
    )
    require(
        condition=surface_stroke_can_finish(closed, tolerance_mm=CLOSURE_TOLERANCE_MM),
        message="A sufficiently close endpoint should allow finishing.",
    )
    require(
        condition=not surface_stroke_can_finish(closed, tolerance_mm=0.1),
        message="Finishing should reject an endpoint beyond the smaller tolerance.",
    )
    require(
        condition=not surface_stroke_can_finish(
            closed[:-1],
            tolerance_mm=CLOSURE_TOLERANCE_MM,
        ),
        message="Finishing should reject a stroke without a closing sample.",
    )
    repeated = (*closed[:2], closed[0])
    require(
        condition=not surface_stroke_can_finish(
            repeated,
            tolerance_mm=CLOSURE_TOLERANCE_MM,
        ),
        message="Finishing should reject a boundary with repeated points.",
    )


def test_close_surface_stroke_rejects_open_boundary() -> None:
    """Verify an open stroke cannot be closed when its endpoint is too far away."""
    anchors = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((10, 10, 0), (0, 0, 1)),
    )
    with pytest.raises(ValueError, match="surface boundary is open"):
        close_surface_stroke(anchors, tolerance_mm=CLOSURE_TOLERANCE_MM)


def test_flatten_surface_patch_rejects_self_intersection() -> None:
    """Verify self-intersecting boundaries are rejected before flattening."""
    points = ((0, 0, 0), (50, 50, 0), (0, 50, 0), (50, 0, 0))
    with pytest.raises(ValueError, match="self-intersects"):
        flatten_surface_patch(points, tolerance_mm=1.0)


def test_polygon_self_intersection_excludes_adjacent_edges() -> None:
    """Verify simple polygons pass and crossed polygons are detected."""
    simple_polygon = ((0, 0), (10, 0), (10, 10), (0, 10))
    crossing_polygon = ((0, 0), (10, 10), (0, 10), (10, 0))
    require(
        condition=not polygon_self_intersects(simple_polygon),
        message="Adjacent polygon edges should not be reported as self-intersections.",
    )
    require(
        condition=polygon_self_intersects(crossing_polygon),
        message="Crossing polygon edges should be detected.",
    )


def test_simplify_polyline_is_deterministic() -> None:
    """Verify polyline simplification returns a stable reduced point sequence."""
    points = ((0, 0, 0), (1, 0.1, 0), (2, 0, 0), (10, 0, 0))
    simplified = simplify_polyline(points, tolerance_mm=0.5)
    require(
        condition=simplified == EXPECTED_SIMPLIFIED_POLYLINE,
        message="Polyline simplification should produce the deterministic endpoints.",
    )


def test_surface_anchor_round_trips_with_six_decimals() -> None:
    """Verify anchor serialization preserves the documented six-decimal precision."""
    anchor = SurfaceAnchor((1.23456789, 2.0, 3.0), (0.0, 0.0, 1.0))
    restored = SurfaceAnchor.from_json(anchor.to_json())
    expected = SurfaceAnchor((1.234568, 2.0, 3.0), (0.0, 0.0, 1.0))
    require(
        condition=restored == expected,
        message="Anchor serialization should preserve six-decimal coordinate precision.",
    )


def test_surface_pick_uses_target_guard_and_viewer_picker() -> None:
    """Verify picking normalizes the normal and returns the selected target point."""
    picked = SimpleNamespace(
        getPoint=lambda: EXPECTED_PICK_POINT,
        getNormal=lambda: NON_UNIT_PICK_NORMAL,
    )
    viewer = SimpleNamespace(pickPoint=lambda _position: picked)
    view = SimpleNamespace(
        getObjectInfo=lambda _x, _y: {"Object": "Avatar", "Component": "Face7"},
        getViewer=lambda: viewer,
    )
    target = SimpleNamespace(Name="Avatar", Label="Mannequin")

    result = require_not_none(
        pick_surface_point(view, 12, 24, target),
        message="Picking the target avatar should return a surface point.",
    )
    require(
        condition=result.point == EXPECTED_PICK_POINT,
        message="Surface picking should retain the selected world-space point.",
    )
    require(
        condition=result.normal == EXPECTED_PICK_NORMAL,
        message="Surface picking should normalize the selected surface normal.",
    )


def test_surface_pick_rejects_unrelated_visible_object() -> None:
    """Verify an unrelated object is rejected before invoking the point picker."""
    view = SimpleNamespace(
        getObjectInfo=lambda _x, _y: {"Object": "Cube"},
        getViewer=lambda: pytest.fail("Viewer picker called for an unrelated object."),
    )
    target = SimpleNamespace(Name="Avatar", Label="Mannequin")
    result = pick_surface_point(view, 1, 2, target)
    require(
        condition=result is None,
        message="Picking should reject an unrelated visible object.",
    )


def test_surface_anchor_round_trips_point_authoring_kind() -> None:
    """Verify corner and curve authoring kinds survive serialization."""
    corner = SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1.0), "corner")
    curve = SurfaceAnchor((4.0, 5.0, 6.0), (0.0, 0.0, 1.0), "curve")
    require(
        condition=SurfaceAnchor.from_json(corner.to_json()) == corner,
        message="Corner authoring kind should survive anchor serialization.",
    )
    require(
        condition=SurfaceAnchor.from_json(curve.to_json()) == curve,
        message="Curve authoring kind should survive anchor serialization.",
    )


def test_surface_anchor_json_requires_explicit_authoring_kind() -> None:
    """Reject serialized anchors that omit the required authoring kind."""
    payload = {"point": [1.0, 2.0, 3.0], "normal": [0.0, 0.0, 1.0]}
    with pytest.raises(ValueError, match="requires an explicit point type"):
        SurfaceAnchor.from_json(payload)


def test_surface_segments_preserve_corners_and_build_splines_for_curve_points() -> None:
    """Verify curve anchors form splines while corner anchors remain line segments."""
    points = ((0, 0), (40, 20), (80, 0), (100, 80), (0, 80))
    kinds = ("corner", "curve", "corner", "corner", "corner")
    segments = surface_segments_from_anchor_kinds(points, kinds)
    require(
        condition=len(segments) == EXPECTED_SEGMENT_COUNT,
        message="Surface segments should include one spline and three line segments.",
    )
    require(
        condition=segments[0] == EXPECTED_BSPLINE_SEGMENT,
        message="Curve anchors should form the expected B-spline segment.",
    )
    require(
        condition=segments[1:] == EXPECTED_LINE_SEGMENTS,
        message="Corner anchors should remain line segments in the authored order.",
    )


def test_surface_segments_reject_boundaries_with_too_few_corners() -> None:
    """Verify a boundary with too few authored corners raises a validation error."""
    with pytest.raises(ValueError, match="at least three corner points"):
        surface_segments_from_anchor_kinds(
            ((0, 0), (50, 20), (100, 0), (50, 60)),
            ("corner", "curve", "corner", "curve"),
        )
