from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    nearest_surface_distance,
    point_inside_closed_surface,
    target_surface_anchor,
    translation_to_target,
)


def _plane(z=0.0):
    surface = CollisionSurface(
        ((-50.0, -50.0, z), (50.0, -50.0, z), (50.0, 50.0, z), (-50.0, 50.0, z)),
        ((0, 1, 2), (0, 2, 3)),
        "target",
    )
    surface.validate()
    return surface





def test_anchor_allows_equidistant_surface_patches_with_same_normal():
    surface = CollisionSurface(
        (
            (-10.0, -10.0, 0.0), (-1.0, -10.0, 0.0), (-1.0, 10.0, 0.0), (-10.0, 10.0, 0.0),
            (1.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 10.0, 0.0), (1.0, 10.0, 0.0),
        ),
        ((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)),
        "target",
    )
    surface.validate()
    hit = target_surface_anchor(surface, (0.0, 0.0, 5.0))
    assert hit.normal == (0.0, 0.0, 1.0)
    assert abs(hit.distance - 5.0) < 1e-12

def test_anchor_uses_nearest_surface_and_outward_normal():
    hit = target_surface_anchor(_plane(), (0.0, 0.0, 25.0))
    assert hit.triangle_index in (0, 1)
    assert hit.point == (0.0, 0.0, 0.0)
    assert hit.normal == (0.0, 0.0, 1.0)
    assert hit.distance == 25.0


def test_translation_to_target_is_bounded():
    delta, hit = translation_to_target(_plane(), (0.0, 0.0, 25.0), clearance=8.0, max_translation=20.0)
    assert delta == (0.0, 0.0, -17.0)
    assert hit.normal == (0.0, 0.0, 1.0)


def test_translation_to_target_rejects_excessive_travel():
    try:
        translation_to_target(_plane(), (0.0, 0.0, 100.0), clearance=8.0, max_translation=50.0)
    except ValueError as exc:
        assert "translation bound" in str(exc)
    else:
        raise AssertionError("excessive target travel was accepted")


def test_nearest_surface_distance_is_surface_based():
    assert nearest_surface_distance(_plane(), ((0.0, 0.0, 12.5),)) == 12.5


def _box(size=20.0):
    h = float(size) / 2.0
    vertices = (
        (-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
        (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    surface = CollisionSurface(vertices, triangles, "target")
    surface.validate()
    return surface


def test_closed_surface_classifies_inside_and_outside():
    surface = _box()
    assert point_inside_closed_surface(surface, (0.0, 0.0, 0.0)) is True
    assert point_inside_closed_surface(surface, (20.0, 0.0, 0.0)) is False


def test_closed_surface_rejects_open_surface():
    surface = _plane()
    try:
        point_inside_closed_surface(surface, (0.0, 0.0, 1.0))
    except ValueError as exc:
        assert "not closed" in str(exc)
    else:
        raise AssertionError("open target surface was accepted as closed")


def test_translation_anchor_is_outside_after_bounded_move():
    surface = _box()
    delta, _hit = translation_to_target(surface, (0.0, 0.0, 30.0), clearance=8.0, max_translation=30.0)
    placed = (0.0 + delta[0], 0.0 + delta[1], 30.0 + delta[2])
    assert point_inside_closed_surface(surface, placed) is False
    assert nearest_surface_distance(surface, (placed,)) >= 8.0 - 1e-6


def test_minimum_outward_clearance_rejects_inward_points():
    from freecad_cloth.avatar.TargetPlacement import minimum_outward_clearance
    assert minimum_outward_clearance(_plane(), ((0.0, 0.0, 8.0),)) == 8.0
    assert minimum_outward_clearance(_plane(), ((0.0, 0.0, -2.0),)) < 0.0


def test_box_corner_anchor_is_deterministic_across_shared_surface_normals():
    hit = target_surface_anchor(_box(), (15.0, 15.0, 15.0))
    assert hit.point == (10.0, 10.0, 10.0)
    assert abs(hit.normal[0] - hit.normal[1]) < 1e-9
    assert abs(hit.normal[1] - hit.normal[2]) < 1e-9
    assert hit.normal[0] > 0.0


def test_central_closed_surface_anchor_remains_fail_closed_when_multiple_regions_tie():
    try:
        target_surface_anchor(_box(), (0.0, 0.0, 0.0))
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("central multi-region target anchor was guessed")
