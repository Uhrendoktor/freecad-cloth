from math import isclose

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    average_point,
    minimum_signed_clearance,
    nearest_target_projection,
)


def _top_surface():
    return CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0),
            (10.0, -10.0, 0.0),
            (10.0, 10.0, 0.0),
            (-10.0, 10.0, 0.0),
        ),
        triangles=((0, 1, 2), (0, 2, 3)),
    )


def test_nearest_projection_reports_outward_normal_and_distance():
    surface = _top_surface()
    projection = nearest_target_projection((0.0, 0.0, 5.0), surface)
    assert projection.triangle_index in {0, 1}
    assert isclose(projection.point[2], 0.0)
    assert projection.normal == (0.0, 0.0, 1.0)
    assert isclose(projection.distance, 5.0)


def test_signed_clearance_rejects_points_inside_target():
    surface = _top_surface()
    assert isclose(minimum_signed_clearance(((0.0, 0.0, 4.0),), surface).minimum_signed_clearance, 4.0)
    assert isclose(minimum_signed_clearance(((0.0, 0.0, -4.0),), surface).minimum_signed_clearance, -4.0)


def test_nearest_projection_fails_closed_on_opposing_ambiguous_normals():
    surface = CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0),
            (-10.0, -10.0, 0.0), (0.0, 10.0, 0.0), (10.0, -10.0, 0.0),
        ),
        triangles=((0, 1, 2), (3, 4, 5)),
    )
    try:
        nearest_target_projection((0.0, 0.0, 5.0), surface)
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("opposing equally-near target normals must fail closed")


def test_average_point_is_deterministic():
    assert average_point(((0.0, 0.0, 2.0), (2.0, 4.0, 4.0))) == (1.0, 2.0, 3.0)


def test_anchor_projection_honors_expected_normal():
    surface = CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 10.0, 0.0), (-10.0, 10.0, 0.0),
            (-10.0, -10.0, 0.0), (-10.0, 10.0, 0.0), (10.0, 10.0, 0.0), (10.0, -10.0, 0.0),
        ),
        triangles=((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)),
    )
    front = nearest_target_projection((0.0, 0.0, 5.0), surface, expected_normal=(0.0, 0.0, 1.0))
    assert front.normal == (0.0, 0.0, 1.0)


def test_rigid_anchor_solution_is_deterministic_and_bounded():
    from freecad_cloth.avatar.TargetPlacement import solve_rigid_z
    source = ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0))
    target = ((0.0, -5.0, 2.0), (0.0, 5.0, 2.0))
    result = solve_rigid_z(source, target, max_translation=100.0, max_rotation=45.0)
    assert isclose(result.rotation_z, 90.0)


def test_rigid_anchor_solution_rejects_transform_bounds():
    from freecad_cloth.avatar.TargetPlacement import solve_rigid_z
    try:
        solve_rigid_z(((0.0, 0.0, 0.0),), ((1001.0, 0.0, 0.0),), max_translation=100.0)
    except ValueError as exc:
        assert "translation guard" in str(exc)
    else:
        raise AssertionError("out-of-bound rigid translation must fail closed")
    try:
        solve_rigid_z(((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)), ((0.0, -5.0, 0.0), (0.0, 5.0, 0.0)), max_rotation=45.0)
    except ValueError as exc:
        assert "rotation guard" in str(exc)
    else:
        raise AssertionError("out-of-bound rigid rotation must fail closed")
