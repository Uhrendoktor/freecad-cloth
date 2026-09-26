"""Focused tests for target-relative rigid placement math."""

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetPlacement import closest_surface_anchor, signed_clearance, solve_target_translation


def _plane():
    return surface_from_triangles(
        ((-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 10.0, 0.0), (-10.0, 10.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
    )


def test_closest_anchor_is_deterministic_and_outward():
    surface = _plane()
    first = closest_surface_anchor((2.0, 3.0, 12.0), surface)
    second = closest_surface_anchor((2.0, 3.0, 12.0), surface)
    assert first == second
    assert first["point"] == (2.0, 3.0, 0.0)
    assert first["normal"] == (0.0, 0.0, 1.0)


def test_target_translation_honors_clearance_and_bound():
    surface = _plane()
    translation, match = solve_target_translation((2.0, 3.0, 12.0), surface, clearance=2.0, max_translation=20.0)
    assert match["triangle_index"] == 0
    assert translation == (0.0, 0.0, -10.0)


def test_signed_clearance_rejects_points_on_wrong_side():
    surface = _plane()
    assert signed_clearance(((0.0, 0.0, 3.0),), surface) == 3.0
    assert signed_clearance(((0.0, 0.0, -3.0),), surface) == -3.0


def test_translation_guard_fails_closed_when_out_of_bound():
    surface = _plane()
    try:
        solve_target_translation((2.0, 3.0, 100.0), surface, clearance=2.0, max_translation=20.0)
    except ValueError as exc:
        assert "exceeds maximum translation" in str(exc)
    else:
        raise AssertionError("out-of-bound target placement must fail closed")
