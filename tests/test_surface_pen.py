# Copyright (C) 2026 FreeCAD Cloth contributors
"""Pure tests for the bounded 3D Pattern Pen surface-authoring contract."""

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


def test_flatten_surface_patch_accepts_planar_boundary() -> None:
    """Verify planar boundaries flatten without introducing geometric deviation."""
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 0), (0, 50, 0))
    patch = flatten_surface_patch(points, tolerance_mm=0.1)
    require(condition=len(patch.points) == 4, message="Expected: len(patch.points) == 4")
    require(
        condition=(
            patch.max_deviation_mm <= 1e-9
        ),
        message="Expected: patch.max_deviation_mm <= 1e-9",
    )
    require(
        condition=(
            abs(abs(polygon_area_2d(patch.points)) - 4000.0) < 1e-6
        ),
        message="Expected: abs(abs(polygon_area_2d(patch.points)) - 4000.0) < 1e-6",
    )


def test_flatten_surface_patch_rejects_curvature_beyond_limit() -> None:
    """Verify excessive curvature is rejected at the configured deviation limit."""
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 12), (0, 50, 0))
    with pytest.raises(ValueError, match="too curved"):
        flatten_surface_patch(points, tolerance_mm=2.0)


def test_close_surface_stroke_accepts_nearby_closing_sample() -> None:
    """Verify a nearby closing sample is removed while preserving the authored boundary."""
    anchors = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0.5, 0.2, 0), (0, 0, 1)),
    )
    closed = close_surface_stroke(anchors, tolerance_mm=1.0)
    require(condition=len(closed) == 4, message="Expected: len(closed) == 4")
    require(condition=closed[0] == anchors[0], message="Expected: closed[0] == anchors[0]")
    require(condition=closed[-1] == anchors[3], message="Expected: closed[-1] == anchors[3]")


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
        condition=(
            surface_stroke_can_finish(closed, tolerance_mm=1.0)
        ),
        message="Expected: surface_stroke_can_finish(closed, tolerance_mm=1.0)",
    )
    require(
        condition=(
            not surface_stroke_can_finish(closed, tolerance_mm=0.1)
        ),
        message="Expected: not surface_stroke_can_finish(closed, tolerance_mm=0.1)",
    )
    require(
        condition=(
            not surface_stroke_can_finish(closed[:-1], tolerance_mm=1.0)
        ),
        message="Expected: not surface_stroke_can_finish(closed[:-1], tolerance_mm",
    )
    repeated = (*closed[:2], closed[0])
    require(
        condition=(
            not surface_stroke_can_finish(repeated, tolerance_mm=1.0)
        ),
        message="Expected: not surface_stroke_can_finish(repeated, tolerance_mm=1.",
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
        close_surface_stroke(anchors, tolerance_mm=1.0)


def test_flatten_surface_patch_rejects_self_intersection() -> None:
    """Verify self-intersecting boundaries are rejected before flattening."""
    points = ((0, 0, 0), (50, 50, 0), (0, 50, 0), (50, 0, 0))
    with pytest.raises(ValueError, match="self-intersects"):
        flatten_surface_patch(points, tolerance_mm=1.0)


def test_polygon_self_intersection_excludes_adjacent_edges() -> None:
    """Verify simple polygons pass and crossed polygons are detected."""
    require(
        condition=(
            not polygon_self_intersects(((0, 0), (10, 0), (10, 10), (0, 10)))
        ),
        message="Expected: not polygon_self_intersects(((0, 0), (10, 0), (10, 10),",
    )
    require(
        condition=(
            polygon_self_intersects(((0, 0), (10, 10), (0, 10), (10, 0)))
        ),
        message="Expected: polygon_self_intersects(((0, 0), (10, 10), (0, 10), (10",
    )


def test_simplify_polyline_is_deterministic() -> None:
    """Verify polyline simplification returns a stable reduced point sequence."""
    points = ((0, 0, 0), (1, 0.1, 0), (2, 0, 0), (10, 0, 0))
    require(
        condition=(
            simplify_polyline(points, tolerance_mm=0.5) == (
                    (0.0, 0.0, 0.0),
                    (10.0, 0.0, 0.0),
                )
        ),
        message="Expected: simplify_polyline(points, tolerance_mm=0.5) == ( (0.0, ",
    )


def test_surface_anchor_round_trips_with_six_decimals() -> None:
    """Verify anchor serialization preserves the documented six-decimal precision."""
    anchor = SurfaceAnchor((1.23456789, 2.0, 3.0), (0.0, 0.0, 1.0))
    restored = SurfaceAnchor.from_json(anchor.to_json())
    require(
        condition=(
            restored == SurfaceAnchor((1.234568, 2.0, 3.0), (0.0, 0.0, 1.0))
        ),
        message="Expected: restored == SurfaceAnchor((1.234568, 2.0, 3.0), (0.0, 0",
    )


def test_surface_pick_uses_target_guard_and_viewer_picker() -> None:
    """Verify surface picking normalizes the normal and returns the selected target point."""
    class Target:
        """Avatar metadata used to validate the picked target."""
        Name = "Avatar"
        Label = "Mannequin"

    class Picked:
        """World-space point and surface normal returned by the picker."""
        def getPoint(self) -> tuple[float, float, float]:
            """Return the selected point in world coordinates."""
            return (10.0, 20.0, 30.0)

        def getNormal(self) -> tuple[float, float, float]:
            """Return a non-unit normal to exercise normal normalization."""
            return (0.0, 0.0, 2.0)

    class Viewer:
        """Viewer adapter returning a deterministic picked point."""

        def pickPoint(self, _position: object) -> Picked:
            """Return the synthetic pick for the requested viewport position.

            Args:
                _position: Viewport selection coordinates supplied by the caller.
            """
            return Picked()

    class View:
        """Viewport adapter reporting the expected avatar object."""

        def getObjectInfo(self, _x: int, _y: int) -> dict[str, str]:
            """Return pick metadata for the expected avatar surface.

            Args:
                _x: Horizontal viewport coordinate.
                _y: Vertical viewport coordinate.

            Returns:
                Object and component identifiers for the avatar surface.
            """
            return {"Object": "Avatar", "Component": "Face7"}

        def getViewer(self) -> Viewer:
            """Return the deterministic viewer implementation.

            Returns:
                Viewer stub whose picker returns the expected point.
            """
            return Viewer()

    result = pick_surface_point(View(), 12, 24, Target())
    result = require_not_none(
        result,
        message="Surface picking should return a point for the matching avatar.",
    )
    require(
        condition=(
            result.point == (10.0, 20.0, 30.0)
        ),
        message="Expected: result.point == (10.0, 20.0, 30.0)",
    )
    require(
        condition=(
            result.normal == (0.0, 0.0, 1.0)
        ),
        message="Expected: result.normal == (0.0, 0.0, 1.0)",
    )


def test_surface_pick_rejects_unrelated_visible_object() -> None:
    """Verify an unrelated visible object is rejected before invoking the point picker."""
    class Target:
        """Avatar metadata used to validate the picked target."""
        Name = "Avatar"
        Label = "Mannequin"

    class View:
        """Viewport adapter reporting an unrelated visible object."""

        def getObjectInfo(self, _x: int, _y: int) -> dict[str, str]:
            """Return the unrelated object selected by viewport inspection.

            Args:
                _x: Horizontal viewport coordinate.
                _y: Vertical viewport coordinate.

            Returns:
                Object identifier for the unrelated visible object.
            """
            return {"Object": "Cube"}

        def getViewer(self) -> None:
            """Reject an unexpected viewer request for an unrelated object.

            Raises:
                AssertionError: If the point picker is incorrectly invoked.
            """
            msg = "picker must not be called for an unrelated object"
            raise AssertionError(msg)

    require(
        condition=(
            pick_surface_point(View(), 1, 2, Target()) is None
        ),
        message="Expected: pick_surface_point(View(), 1, 2, Target()) is None",
    )


def test_surface_anchor_round_trips_point_authoring_kind() -> None:
    """Verify corner and curve authoring kinds survive serialization."""
    corner = SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1.0), "corner")
    curve = SurfaceAnchor((4.0, 5.0, 6.0), (0.0, 0.0, 1.0), "curve")
    require(
        condition=(
            SurfaceAnchor.from_json(corner.to_json()) == corner
        ),
        message="Expected: SurfaceAnchor.from_json(corner.to_json()) == corner",
    )
    require(
        condition=(
            SurfaceAnchor.from_json(curve.to_json()) == curve
        ),
        message="Expected: SurfaceAnchor.from_json(curve.to_json()) == curve",
    )


def test_legacy_surface_anchor_json_defaults_to_corner() -> None:
    """Verify legacy anchor JSON defaults its authoring kind to corner."""
    restored = SurfaceAnchor.from_json({"point": [1.0, 2.0, 3.0], "normal": [0.0, 0.0, 1.0]})
    require(
        condition=(
            restored == SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
        ),
        message="Expected: restored == SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1",
    )


def test_surface_segments_preserve_corners_and_build_splines_for_curve_points() -> None:
    """Verify curve anchors form splines while corner anchors remain line segments."""
    points = ((0, 0), (40, 20), (80, 0), (100, 80), (0, 80))
    kinds = ("corner", "curve", "corner", "corner", "corner")
    segments = surface_segments_from_anchor_kinds(points, kinds)

    require(condition=len(segments) == 4, message="Expected: len(segments) == 4")
    require(
        condition=(
            segments[0] == ("bspline", ((0.0, 0.0), (40.0, 20.0), (80.0, 0.0)))
        ),
        message="Expected: segments[0] == (\"bspline\", ((0.0, 0.0), (40.0, 20.0), (",
    )
    require(
        condition=(
            segments[1:] == (
                    ("line", ((80.0, 0.0), (100.0, 80.0))),
                    ("line", ((100.0, 80.0), (0.0, 80.0))),
                    ("line", ((0.0, 80.0), (0.0, 0.0))),
                )
        ),
        message="Expected: segments[1:] == ( (\"line\", ((80.0, 0.0), (100.0, 80.0))",
    )


def test_surface_segments_reject_boundaries_with_too_few_corners() -> None:
    """Verify a boundary with too few authored corners raises a validation error."""
    with pytest.raises(ValueError, match="at least three corner points"):
        surface_segments_from_anchor_kinds(
            ((0, 0), (50, 20), (100, 0), (50, 60)),
            ("corner", "curve", "corner", "curve"),
        )
