# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for avatar pose-angle defaults and landmark behavior."""

import json

import pytest

from freecad_cloth.avatar.AvatarModel import (
    AVATAR_SCHEMA_VERSION,
    DEFAULT_POSE_ARM_ANGLES,
    AvatarParameters,
    Pose,
    generate_mesh,
)
from tests.support.assertions import require

_POSE_PRESETS = tuple(DEFAULT_POSE_ARM_ANGLES)
_EXPLICIT_ARM_ANGLE_CASES = (
    ("t_pose", -24.0, 32.0),
    ("standing", -31.0, 27.0),
    ("sewing", -41.0, 16.0),
    ("sitting", -12.0, 36.0),
)
_WRIST_LANDMARK_NAMES = frozenset({"wrist_left", "wrist_right"})


def _parameters_with_omitted_arm_angles(preset: str) -> AvatarParameters:
    """Load avatar JSON with omitted arm angles for a given pose preset.

    Args:
        preset: Supported pose preset to encode in the parameter document.

    Returns:
        Validated avatar parameters with the preset's default arm angles.
    """
    payload = {
        "schema_version": AVATAR_SCHEMA_VERSION,
        "units": "mm",
        "measurements": {},
        "pose": {"preset": preset},
    }
    return AvatarParameters.from_json(json.dumps(payload))


@pytest.mark.parametrize("preset", _POSE_PRESETS)
def test_omitted_arm_angles_use_preset_defaults(preset: str) -> None:
    """Resolve omitted JSON arm angles to the configured preset defaults.

    Args:
        preset: Supported avatar pose preset under test.
    """
    default_pose = Pose(preset)
    recovered = _parameters_with_omitted_arm_angles(preset)
    expected_angle = DEFAULT_POSE_ARM_ANGLES[preset]
    require(
        condition=(
            default_pose.left_arm_angle == expected_angle
            and default_pose.right_arm_angle == expected_angle
            and recovered.pose.left_arm_angle == expected_angle
            and recovered.pose.right_arm_angle == expected_angle
        ),
        message=f"Omitted arm angles must resolve to the {preset} default.",
    )


@pytest.mark.parametrize(
    ("preset", "left_angle", "right_angle"),
    _EXPLICIT_ARM_ANGLE_CASES,
)
def test_explicit_arm_angles_survive_json_round_trip(
    preset: str,
    left_angle: float,
    right_angle: float,
) -> None:
    """Preserve explicit left and right arm angles through serialization.

    Args:
        preset: Supported avatar pose preset under test.
        left_angle: Explicit left arm angle in degrees.
        right_angle: Explicit right arm angle in degrees.
    """
    parameters = AvatarParameters(pose=Pose(preset, left_angle, right_angle))
    restored = AvatarParameters.from_json(parameters.to_json())
    require(
        condition=(
            restored == parameters
            and restored.pose.left_arm_angle == left_angle
            and restored.pose.right_arm_angle == right_angle
        ),
        message=f"Explicit arm angles must survive the {preset} JSON round-trip.",
    )


def _generated_wrist_positions(
    parameters: AvatarParameters,
) -> tuple[tuple[str, tuple[float, float, float]], ...]:
    """Return generated wrist landmark coordinates for an avatar pose.

    Args:
        parameters: Validated parameters controlling the generated avatar.

    Returns:
        Named wrist landmark coordinates from the generated body mesh.
    """
    return tuple(
        (landmark.name, landmark.position)
        for landmark in generate_mesh(parameters)[2]
        if landmark.name in _WRIST_LANDMARK_NAMES
    )


def test_explicit_arm_angles_change_generated_wrist_landmarks() -> None:
    """Ensure explicit arm angles change generated wrist coordinates."""
    baseline = AvatarParameters(pose=Pose("sewing"))
    posed = AvatarParameters(pose=Pose("sewing", -41.0, 16.0))
    require(
        condition=(_generated_wrist_positions(baseline) != _generated_wrist_positions(posed)),
        message="Explicit sewing angles must alter generated wrist landmarks.",
    )
