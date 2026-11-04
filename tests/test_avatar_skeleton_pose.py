# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the manual mannequin skeleton pose contract."""

import json
from typing import TYPE_CHECKING

import pytest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Landmark, Pose
from freecad_cloth.avatar.HierarchicalPose import pose_world_state, transform_landmarks
from freecad_cloth.avatar.SkeletonPose import (
    CONTROLLABLE_BONES,
    IDENTITY,
    AffineTransform,
    JointRotation,
    apply_weighted_fk,
    compose_transforms,
    joint_rotation_map,
    joint_rotations_from_json,
    joint_rotations_to_json,
)

if TYPE_CHECKING:
    from freecad_cloth.avatar.SkeletonTypes import SkeletonData

MIRROR_EXPECTED_X = 12.0
MIRROR_EXPECTED_Y = -20.0
MIRROR_EXPECTED_Z = -30.0
CONTROLLABLE_JOINT_COUNT = 18
HEAD_ROTATION_DEGREES = 15.0


def test_skeleton_fit_ignores_skin_padding_and_unrelated_hip_changes() -> None:
    """Keep skeleton fitting invariant to unrelated hip and skin-padding changes."""
    baseline = AvatarParameters()
    hip_changed = baseline.with_measurements(hip=baseline.measurement("hip") + 120.0)
    padded = AvatarParameters(skin_offset=8.0)
    source, skeleton, _baseline_mapper, baseline_transforms = pose_world_state(baseline)

    for variant in (hip_changed, padded):
        variant_source, variant_skeleton, _variant_mapper, variant_transforms = pose_world_state(
            variant
        )
        assert (
            variant_skeleton == skeleton
        ), "regression contract"
        unchanged_bones = (
            ("head", "neck01", "clavicle.L")
            if variant is hip_changed
            else ("head", "neck01", "spine05", "clavicle.L")
        )
        for bone_name in unchanged_bones:
            assert (
                baseline_transforms[bone_name] == variant_transforms[bone_name]
            ), f"{bone_name} transform is unchanged"
        assert (
            variant_source == source
        ), "regression contract"


def test_joint_rotation_bounds_and_mirror() -> None:
    """Validate mirrored joint rotations and their coordinate signs."""
    rotation = JointRotation("upperarm01.L", 12.0, 20.0, 30.0).validate()
    mirrored = rotation.mirrored()
    assert (
        mirrored.bone == "upperarm01.R"
    ), "regression contract"
    assert (
        mirrored.x == pytest.approx(MIRROR_EXPECTED_X)
    ), "mirrored X rotation is preserved"
    assert (
        mirrored.y == pytest.approx(MIRROR_EXPECTED_Y)
    ), "mirrored Y rotation changes sign"
    assert (
        mirrored.z == pytest.approx(MIRROR_EXPECTED_Z)
    ), "mirrored Z rotation changes sign"


def test_joint_rotations_round_trip_is_deterministic() -> None:
    """Preserve stable, normalized JSON serialization for joint rotations."""
    rotations = (
        JointRotation("wrist.R", 1.0, 2.0, 3.0),
        JointRotation("upperarm01.L", -10.0, 20.0, -30.0),
    )
    payload = joint_rotations_to_json(rotations)
    restored = joint_rotations_from_json(payload)
    assert (
        (
        restored
        == (
        JointRotation("upperarm01.L", -10.0, 20.0, -30.0),
        JointRotation("wrist.R", 1.0, 2.0, 3.0),
        )
        )
    ), "regression contract"
    assert (
        json.loads(payload)["units"] == "deg"
    ), "serialized rotations record degree units"


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{}",
        json.dumps({"upperarm01.L": {"x": 15.0}}),
        json.dumps({"schema_version": 1, "units": "rad", "joints": {}}),
    ],
)
def test_joint_rotation_parser_rejects_unversioned_payloads(payload: str) -> None:
    """Reject empty, unversioned, raw-map, and wrong-unit pose JSON.

    Args:
        payload: Versioned-pose JSON candidate that should fail validation.
    """
    with pytest.raises((ValueError, TypeError)):
        joint_rotations_from_json(payload)


def test_pose_and_avatar_parameters_persist_manual_joints() -> None:
    """Round-trip manually authored joint rotations with avatar parameters."""
    params = AvatarParameters(
        pose=Pose(
            "standing",
            joint_rotations=(JointRotation("lowerarm01.L", 0.0, 45.0, 0.0),),
        )
    )
    restored = AvatarParameters.from_json(params.to_json())
    assert (
        restored == params
    ), "manual joints survive persistence"
    assert (
        (restored.pose.joint_rotations[0].bone == "lowerarm01.L")
    ), "regression contract"


def test_manual_pose_moves_fitting_landmark_from_baseline() -> None:
    """Verify manual posing moves the selected fitting landmark."""
    landmarks = (
        Landmark("shoulder_left", (1.0, 0.0, 0.0)),
        Landmark("waist", (0.0, 1.0, 0.0)),
    )
    rotation = AffineTransform(
        (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
    )
    posed = transform_landmarks(
        landmarks,
        {"clavicle.L": IDENTITY, "spine04": IDENTITY},
        {"clavicle.L": rotation, "spine04": IDENTITY},
    )
    assert (
        (posed[0].position == pytest.approx((1.0, 1.0, 0.0)))
    ), "regression contract"
    assert (
        posed[1] == landmarks[1]
    ), "unaffected landmarks remain unchanged"


def test_affine_transform_inverse_round_trips_rigid_points() -> None:
    """Verify inverse affine transforms restore a rigid point."""
    transform = AffineTransform(
        (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (4.0, -3.0, 2.0),
    )
    point = (1.25, -2.5, 9.0)
    assert (
        (transform.inverse().apply(transform.apply(point)) == pytest.approx(point))
    ), "regression contract"


def test_affine_transform_composition_matches_sequential_application() -> None:
    """Keep composed affine transformations equivalent to sequential transforms."""
    first = AffineTransform(
        (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (4.0, -3.0, 2.0),
    )
    second = AffineTransform(
        (1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0),
        (-2.0, 5.0, 1.0),
    )
    point = (1.25, -2.5, 9.0)
    assert (
        (
        compose_transforms(first, second).apply(point)
        == pytest.approx(first.apply(second.apply(point)))
        )
    ), "regression contract"


def test_joint_map_rejects_unknown_bones() -> None:
    """Reject unsupported mannequin joint identifiers."""
    with pytest.raises(ValueError, match="unsupported mannequin joint"):
        JointRotation("not-a-bone").validate()


def test_weighted_fk_rotates_a_selected_joint_and_inherits_to_child() -> None:
    """Propagate a selected joint rotation to its child joint."""
    source = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
    )
    rest = source
    skeleton: SkeletonData = {
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
    assert (
        posed[2] == pytest.approx((0.0, 2.0, 0.0))
    ), "child joint inherits the upper-arm rotation"


def test_controllable_joint_order_is_stable() -> None:
    """Keep the controllable joint order and head rotation mapping stable."""
    assert (
        (CONTROLLABLE_BONES[:4] == ("spine05", "spine03", "neck01", "head"))
    ), "regression contract"
    assert (
        (len(CONTROLLABLE_BONES) == CONTROLLABLE_JOINT_COUNT)
    ), "regression contract"
    assert (
        (
        joint_rotation_map((JointRotation("head", z=HEAD_ROTATION_DEGREES),))["head"].z
        == pytest.approx(HEAD_ROTATION_DEGREES)
        )
    ), "regression contract"


def test_weighted_fk_vectorizes_sparse_weights_and_preserves_blend_contract() -> None:
    """Preserve duplicate-weight accumulation, normalization, and untouched vertices."""
    source = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
    )
    skeleton: SkeletonData = {
        "bones": {
            "upperarm01.L": {"head": "h", "tail": "t", "parent": None},
            "lowerarm01.L": {"head": "h", "tail": "t", "parent": None},
        },
        "joints": {"h": [0], "t": [0]},
    }
    weights = {
        "upperarm01.L": ((1, 0.25), (1, 0.25), (2, 2.0), (-1, 5.0), (99, 5.0)),
        "lowerarm01.L": ((1, 0.5), (2, 1.0)),
    }
    posed = apply_weighted_fk(
        source,
        source,
        skeleton,
        weights,
        lambda point: point,
        (JointRotation("upperarm01.L", z=90.0),),
    )
    assert (
        posed[0] == pytest.approx(source[0])
    ), "unweighted vertices remain unchanged"
    assert (
        posed[1] == pytest.approx((0.5, 0.5, 0.0))
    ), "overlapping weights are normalized"
    assert (
        (posed[2] == pytest.approx((2.0 / 3.0, 4.0 / 3.0, 0.0)))
    ), "regression contract"
