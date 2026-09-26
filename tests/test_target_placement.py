import math

from freecad_cloth.avatar.TargetPlacement import (
    plan_target_relative_placement,
    rotation_angle_between,
    target_bounds,
)


def test_target_relative_placement_is_deterministic_and_outside_requested_side():
    kwargs = dict(
        home_position=(-300.0, 0.0, 0.0),
        home_rotation_axis=(0.0, 0.0, 1.0),
        home_rotation_angle=0.0,
        piece_bounds=(0.0, 100.0, 0.0, 200.0),
        target_bounds=(-50.0, 50.0, -60.0, 260.0, 0.0, 300.0),
        wrap_direction="front",
        clearance=10.0,
        max_translation=1000.0,
        max_rotation=180.0,
    )
    first = plan_target_relative_placement(**kwargs)
    second = plan_target_relative_placement(**kwargs)
    assert first == second
    assert abs(first.rotation_axis[0] - 1.0) < 1e-9
    assert abs(first.rotation_angle - 90.0) < 1e-9

    # The local pattern is rigidly rotated so its complete planar span lies on
    # the front target side at exactly the configured clearance.
    local_center = (50.0, 100.0, 0.0)
    angle = math.radians(first.rotation_angle)
    rotated_center = (
        local_center[0],
        -local_center[2] * math.sin(angle) + local_center[1] * math.cos(angle),
        local_center[2] * math.cos(angle) + local_center[1] * math.sin(angle),
    )
    world_center = tuple(first.position[i] + rotated_center[i] for i in range(3))
    assert abs(world_center[1] + 70.0) < 1e-9
    assert target_bounds(((-50, -60, 0), (50, -60, 300))) == (-50.0, 50.0, -60.0, -60.0, 0.0, 300.0)



def test_target_relative_placement_honors_explicit_anchor_position():
    plan = plan_target_relative_placement(
        home_position=(0.0, 0.0, 0.0),
        home_rotation_axis=(0.0, 0.0, 1.0),
        home_rotation_angle=0.0,
        piece_bounds=(0.0, 100.0, 0.0, 200.0),
        target_bounds=(-50.0, 50.0, -60.0, 260.0, 0.0, 300.0),
        wrap_direction="front",
        clearance=10.0,
        max_translation=1000.0,
        max_rotation=180.0,
        anchor_position=(25.0, 0.0, 120.0),
    )
    local_center = (50.0, 100.0, 0.0)
    angle = math.radians(plan.rotation_angle)
    rotated_center = (
        local_center[0],
        local_center[1] * math.cos(angle),
        local_center[1] * math.sin(angle),
    )
    world_center = tuple(plan.position[i] + rotated_center[i] for i in range(3))
    assert abs(world_center[0] - 25.0) < 1e-9
    assert abs(world_center[2] - 120.0) < 1e-9

def test_target_relative_placement_rejects_translation_beyond_bound():
    try:
        plan_target_relative_placement(
            home_position=(10000.0, 10000.0, 10000.0),
            home_rotation_axis=(0.0, 0.0, 1.0),
            home_rotation_angle=0.0,
            piece_bounds=(0.0, 10.0, 0.0, 10.0),
            target_bounds=(-10.0, 10.0, -10.0, 10.0, 0.0, 100.0),
            wrap_direction="front",
            clearance=8.0,
            max_translation=10.0,
            max_rotation=180.0,
        )
    except ValueError as exc:
        assert "translation" in str(exc)
    else:
        raise AssertionError("expected translation bound rejection")


def test_target_relative_placement_rejects_rotation_beyond_bound():
    try:
        plan_target_relative_placement(
            home_position=(0.0, 0.0, 0.0),
            home_rotation_axis=(0.0, 0.0, 1.0),
            home_rotation_angle=0.0,
            piece_bounds=(0.0, 10.0, 0.0, 10.0),
            target_bounds=(-10.0, 10.0, -10.0, 10.0, 0.0, 100.0),
            wrap_direction="front",
            clearance=8.0,
            max_translation=1000.0,
            max_rotation=45.0,
        )
    except ValueError as exc:
        assert "rotation" in str(exc)
    else:
        raise AssertionError("expected rotation bound rejection")


def test_rotation_distance_is_shortest_equivalent_angle():
    assert abs(rotation_angle_between((0.0, 0.0, 1.0), 10.0, (0.0, 0.0, 1.0), 350.0) - 20.0) < 1e-6


if __name__ == "__main__":
    tests = (
        test_target_relative_placement_is_deterministic_and_outside_requested_side,
        test_target_relative_placement_honors_explicit_anchor_position,
        test_target_relative_placement_rejects_translation_beyond_bound,
        test_target_relative_placement_rejects_rotation_beyond_bound,
        test_rotation_distance_is_shortest_equivalent_angle,
    )
    for test in tests:
        test()
    print("test_target_placement: passed")
