import math

import pytest

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
    assert first.rotation_axis[0] == pytest.approx(1.0)
    assert first.rotation_angle == pytest.approx(90.0)

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
    assert world_center[1] == pytest.approx(-60.0 - 0.0)
    assert target_bounds(((-50, -60, 0), (50, -60, 300))) == (-50.0, 50.0, -60.0, -60.0, 0.0, 300.0)


def test_target_relative_placement_rejects_translation_beyond_bound():
    with pytest.raises(ValueError, match="translation"):
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


def test_target_relative_placement_rejects_rotation_beyond_bound():
    with pytest.raises(ValueError, match="rotation"):
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


def test_rotation_distance_is_shortest_equivalent_angle():
    assert rotation_angle_between((0.0, 0.0, 1.0), 10.0, (0.0, 0.0, 1.0), 350.0) == pytest.approx(20.0, abs=1e-6)
