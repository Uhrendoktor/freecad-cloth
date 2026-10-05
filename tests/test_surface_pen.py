"""Pure tests for the bounded 3D Pattern Pen surface-authoring contract."""

from freecad_cloth.pattern.SurfacePen import (
    SurfaceAnchor,
    flatten_surface_patch,
    polygon_area_2d,
    polygon_self_intersects,
    simplify_polyline,
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
