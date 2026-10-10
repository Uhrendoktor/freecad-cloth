import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_cloth.avatar.AvatarModel import (
    DEFAULT_MEASUREMENTS,
    AvatarParameters,
    Pose,
    generate_mesh,
)


def test_default_avatar_is_valid_and_deterministic():
    params = AvatarParameters()
    first = generate_mesh(params)
    second = generate_mesh(params)
    assert first == second
    assert len(first[0]) > 100
    assert len(first[1]) > 100
    assert {landmark.name for landmark in first[2]} >= {
        "neck",
        "chest",
        "waist",
        "hip",
        "shoulder_left",
        "shoulder_right",
    }


def test_measurement_change_changes_geometry_without_mutating_source():
    params = AvatarParameters()
    wider = params.with_measurements(chest=params.measurement("chest") + 100)
    assert params.measurement("chest") == DEFAULT_MEASUREMENTS["chest"]
    assert wider.measurement("chest") == DEFAULT_MEASUREMENTS["chest"] + 100
    assert generate_mesh(params)[0] != generate_mesh(wider)[0]


def test_skin_offset_changes_collision_geometry():
    base = AvatarParameters(skin_offset=0)
    padded = AvatarParameters(skin_offset=8)
    assert generate_mesh(base)[0] != generate_mesh(padded)[0]


def test_pose_round_trip_is_persistent_and_validated():
    params = AvatarParameters(pose=Pose("sewing"))
    restored = AvatarParameters.from_json(params.to_json())
    assert restored == params
    try:
        Pose("invalid").validate()
    except ValueError as exc:
        assert "unsupported avatar pose" in str(exc)
    else:
        raise AssertionError("invalid pose was accepted")


def test_t_pose_preset_round_trips_and_has_a_horizontal_arm_envelope():
    t_pose = AvatarParameters(pose=Pose("t_pose"))
    standing = AvatarParameters(pose=Pose("standing"))
    assert (t_pose.pose.left_arm_angle, t_pose.pose.right_arm_angle) == (12.0, 12.0)
    assert AvatarParameters.from_json(t_pose.to_json()) == t_pose

    def x_bounds(params):
        xs = [float(point[0]) for point in generate_mesh(params)[0]]
        return min(xs), max(xs)

    horizontal, relaxed = x_bounds(t_pose), x_bounds(standing)
    assert horizontal[0] < relaxed[0] - 100.0
    assert horizontal[1] > relaxed[1] + 100.0


def test_invalid_measurements_are_rejected():
    try:
        AvatarParameters().with_measurements(underbust=1200, chest=1000)
    except ValueError as exc:
        assert "underbust" in str(exc)
    else:
        raise AssertionError("invalid circumference relationship was accepted")
