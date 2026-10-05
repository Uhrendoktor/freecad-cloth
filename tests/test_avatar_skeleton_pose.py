"""Tests for the manual mannequin skeleton pose contract."""

import json

import pytest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose
from freecad_cloth.avatar.SkeletonPose import (
    CONTROLLABLE_BONES,
    JointRotation,
    apply_weighted_fk,
    joint_rotation_map,
    joint_rotations_from_json,
    joint_rotations_to_json,
)


def test_joint_rotation_bounds_and_mirror():
    rotation = JointRotation("upperarm01.L", 12.0, 20.0, 30.0).validate()
    mirrored = rotation.mirrored()
    assert mirrored.bone == "upperarm01.R"
    assert mirrored.x == -12.0
    assert mirrored.y == 20.0
    assert mirrored.z == -30.0


def test_joint_rotations_round_trip_is_deterministic():
    rotations = (
        JointRotation("wrist.R", 1.0, 2.0, 3.0),
        JointRotation("upperarm01.L", -10.0, 20.0, -30.0),
    )
    payload = joint_rotations_to_json(rotations)
    restored = joint_rotations_from_json(payload)
    assert restored == (
        JointRotation("upperarm01.L", -10.0, 20.0, -30.0),
        JointRotation("wrist.R", 1.0, 2.0, 3.0),
    )
    assert json.loads(payload)["units"] == "deg"


def test_pose_and_avatar_parameters_persist_manual_joints():
    params = AvatarParameters(
        pose=Pose(
            "standing",
            joint_rotations=(JointRotation("lowerarm01.L", 0.0, 45.0, 0.0),),
        )
    )
    restored = AvatarParameters.from_json(params.to_json())
    assert restored == params
    assert restored.pose.joint_rotations[0].bone == "lowerarm01.L"


def test_joint_map_rejects_unknown_bones():
    with pytest.raises(ValueError, match="unsupported mannequin joint"):
        JointRotation("not-a-bone").validate()


def test_weighted_fk_rotates_a_selected_joint_and_inherits_to_child():
    source = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
    )
    rest = source
    skeleton = {
        "bones": {
            "upperarm01.L": {"head": "h", "parent": None, "tail": "e"},
            "lowerarm01.L": {"head": "e", "parent": "upperarm01.L", "tail": "w"},
        },
        "joints": {
            "h": [0],
            "e": [1],
            "w": [2],
        },
    }
    weights = {
        "lowerarm01.L": ((2, 1.0),),
    }
    posed = apply_weighted_fk(
        source,
        rest,
        skeleton,
        weights,
        lambda point: point,
        (JointRotation("upperarm01.L", z=90.0),),
    )
    assert posed[2] == pytest.approx((0.0, 2.0, 0.0))


def test_controllable_joint_order_is_stable():
    assert CONTROLLABLE_BONES[:4] == ("spine05", "spine03", "neck01", "head")
    assert len(CONTROLLABLE_BONES) == 19
    assert joint_rotation_map((JointRotation("head", z=15.0),))["head"].z == 15.0
