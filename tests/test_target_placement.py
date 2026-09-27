from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    nearest_surface_distance,
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
