# Copyright (C) 2026 FreeCAD Cloth contributors
"""Pure tests for the bounded 3D Pattern Pen surface-authoring contract."""

from freecad_cloth.pattern.SurfacePen import (
    SurfaceAnchor,
    close_surface_stroke,
    flatten_surface_patch,
    polygon_area_2d,
    polygon_self_intersects,
    simplify_polyline,
    surface_segments_from_anchor_kinds,
    surface_stroke_can_finish,
)


def test_flatten_surface_patch_accepts_planar_boundary():
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 0), (0, 50, 0))
    patch = flatten_surface_patch(points, tolerance_mm=0.1)
    assert len(patch.points) == 4
    assert patch.max_deviation_mm <= 1e-9
    assert abs(abs(polygon_area_2d(patch.points)) - 4000.0) < 1e-6


def test_flatten_surface_patch_rejects_curvature_beyond_limit():
    points = ((0, 0, 0), (80, 0, 0), (80, 50, 12), (0, 50, 0))
    try:
        flatten_surface_patch(points, tolerance_mm=2.0)
    except ValueError as exc:
        assert "too curved" in str(exc)
    else:
        raise AssertionError("curved patch exceeded the configured planar deviation limit")


def test_close_surface_stroke_accepts_nearby_closing_sample():
    anchors = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0.5, 0.2, 0), (0, 0, 1)),
    )
    closed = close_surface_stroke(anchors, tolerance_mm=1.0)
    assert len(closed) == 4
    assert closed[0] == anchors[0]
    assert closed[-1] == anchors[3]


def test_surface_stroke_can_finish_requires_closed_distinct_boundary() -> None:
    closed = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0.5, 0.2, 0), (0, 0, 1)),
    )
    assert surface_stroke_can_finish(closed, tolerance_mm=1.0)
    assert not surface_stroke_can_finish(closed, tolerance_mm=0.1)
    assert not surface_stroke_can_finish(closed[:-1], tolerance_mm=1.0)
    repeated = (*closed[:2], closed[0])
    assert not surface_stroke_can_finish(repeated, tolerance_mm=1.0)


def test_close_surface_stroke_rejects_open_boundary():
    anchors = (
        SurfaceAnchor((0, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 0, 0), (0, 0, 1)),
        SurfaceAnchor((80, 50, 0), (0, 0, 1)),
        SurfaceAnchor((0, 50, 0), (0, 0, 1)),
        SurfaceAnchor((10, 10, 0), (0, 0, 1)),
    )
    try:
        close_surface_stroke(anchors, tolerance_mm=1.0)
    except ValueError as exc:
        assert "surface boundary is open" in str(exc)
    else:
        raise AssertionError("open surface boundary was accepted")


def test_flatten_surface_patch_rejects_self_intersection():
    points = ((0, 0, 0), (50, 50, 0), (0, 50, 0), (50, 0, 0))
    try:
        flatten_surface_patch(points, tolerance_mm=1.0)
    except ValueError as exc:
        assert "self-intersects" in str(exc)
    else:
        raise AssertionError("self-intersecting surface boundary was accepted")


def test_polygon_self_intersection_excludes_adjacent_edges():
    assert not polygon_self_intersects(((0, 0), (10, 0), (10, 10), (0, 10)))
    assert polygon_self_intersects(((0, 0), (10, 10), (0, 10), (10, 0)))


def test_simplify_polyline_is_deterministic():
    points = ((0, 0, 0), (1, 0.1, 0), (2, 0, 0), (10, 0, 0))
    assert simplify_polyline(points, tolerance_mm=0.5) == (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
    )


def test_surface_anchor_round_trips_with_six_decimals():
    anchor = SurfaceAnchor((1.23456789, 2.0, 3.0), (0.0, 0.0, 1.0))
    restored = SurfaceAnchor.from_json(anchor.to_json())
    assert restored == SurfaceAnchor((1.234568, 2.0, 3.0), (0.0, 0.0, 1.0))


def test_surface_pick_uses_target_guard_and_viewer_picker():
    from freecad_cloth.pattern.SurfacePen import pick_surface_point

    class Target:
        Name = "Avatar"
        Label = "Mannequin"

    class Picked:
        def getPoint(self):
            return (10.0, 20.0, 30.0)

        def getNormal(self):
            return (0.0, 0.0, 2.0)

    class Viewer:
        def pickPoint(self, _position):
            return Picked()

    class View:
        def getObjectInfo(self, _x, _y):
            return {"Object": "Avatar", "Component": "Face7"}

        def getViewer(self):
            return Viewer()

    result = pick_surface_point(View(), 12, 24, Target())
    assert result is not None
    assert result.point == (10.0, 20.0, 30.0)
    assert result.normal == (0.0, 0.0, 1.0)


def test_surface_pick_rejects_unrelated_visible_object():
    from freecad_cloth.pattern.SurfacePen import pick_surface_point

    class Target:
        Name = "Avatar"
        Label = "Mannequin"

    class View:
        def getObjectInfo(self, _x, _y):
            return {"Object": "Cube"}

        def getViewer(self):
            raise AssertionError("picker must not be called for an unrelated object")

    assert pick_surface_point(View(), 1, 2, Target()) is None


def test_surface_anchor_round_trips_point_authoring_kind() -> None:
    corner = SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1.0), "corner")
    curve = SurfaceAnchor((4.0, 5.0, 6.0), (0.0, 0.0, 1.0), "curve")
    assert SurfaceAnchor.from_json(corner.to_json()) == corner
    assert SurfaceAnchor.from_json(curve.to_json()) == curve


def test_legacy_surface_anchor_json_defaults_to_corner() -> None:
    restored = SurfaceAnchor.from_json({"point": [1.0, 2.0, 3.0], "normal": [0.0, 0.0, 1.0]})
    assert restored == SurfaceAnchor((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))


def test_surface_segments_preserve_corners_and_build_splines_for_curve_points() -> None:
    points = ((0, 0), (40, 20), (80, 0), (100, 80), (0, 80))
    kinds = ("corner", "curve", "corner", "corner", "corner")
    segments = surface_segments_from_anchor_kinds(points, kinds)

    assert len(segments) == 4
    assert segments[0] == ("bspline", ((0.0, 0.0), (40.0, 20.0), (80.0, 0.0)))
    assert segments[1:] == (
        ("line", ((80.0, 0.0), (100.0, 80.0))),
        ("line", ((100.0, 80.0), (0.0, 80.0))),
        ("line", ((0.0, 80.0), (0.0, 0.0))),
    )


def test_surface_segments_reject_boundaries_with_too_few_corners() -> None:
    try:
        surface_segments_from_anchor_kinds(
            ((0, 0), (50, 20), (100, 0), (50, 60)),
            ("corner", "curve", "corner", "curve"),
        )
    except ValueError as exc:
        assert "at least three corner points" in str(exc)
    else:
        raise AssertionError("a curve boundary without three authored corners was accepted")
