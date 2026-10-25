# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for avatar parameter validation and mesh generation."""

import json
import math

import pytest

from freecad_cloth.avatar.AvatarModel import (
    AVATAR_SCHEMA_VERSION,
    DEFAULT_MEASUREMENTS,
    DEFAULT_POSE_ARM_ANGLES,
    AvatarParameters,
    Pose,
    generate_mesh,
)
from tests.support.assertions import require

_MIN_MESH_ELEMENT_COUNT = 100
_MEASUREMENT_CHANGE_MM = 100.0
_HIP_CHANGE_MM = 120.0
_SKIN_OFFSET_TEST_MM = 8.0
_POSE_ENVELOPE_MARGIN_MM = 100.0


def test_default_avatar_is_valid_and_deterministic() -> None:
    """Generate a stable, populated avatar mesh from default parameters."""
    params = AvatarParameters()
    first = generate_mesh(params)
    second = generate_mesh(params)
    require(
        condition=first == second,
        message="Repeated default mesh generation must be deterministic.",
    )
    require(
        condition=len(first[0]) > _MIN_MESH_ELEMENT_COUNT,
        message="The generated avatar needs a nontrivial vertex set.",
    )
    require(
        condition=len(first[1]) > _MIN_MESH_ELEMENT_COUNT,
        message="The generated avatar needs a nontrivial face set.",
    )
    require(
        condition={landmark.name for landmark in first[2]}
        >= {
            "neck",
            "chest",
            "waist",
            "hip",
            "shoulder_left",
            "shoulder_right",
        },
        message="The generated avatar must expose its standard body landmarks.",
    )


def test_measurement_change_changes_geometry_without_mutating_source() -> None:
    """Keep source parameters stable while a chest-measurement edit changes geometry."""
    params = AvatarParameters()
    wider = params.with_measurements(
        chest=params.measurement("chest") + _MEASUREMENT_CHANGE_MM
    )
    require(
        condition=math.isclose(
            params.measurement("chest"),
            DEFAULT_MEASUREMENTS["chest"],
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="Editing a copy must not mutate the source chest measurement.",
    )
    require(
        condition=math.isclose(
            wider.measurement("chest"),
            DEFAULT_MEASUREMENTS["chest"] + _MEASUREMENT_CHANGE_MM,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="The updated chest measurement must be retained.",
    )
    require(
        condition=generate_mesh(params)[0] != generate_mesh(wider)[0],
        message="A wider chest measurement must alter generated geometry.",
    )


def test_hip_circumference_does_not_change_leg_stance_landmarks() -> None:
    """Preserve the leg stance when only hip circumference changes."""
    params = AvatarParameters()
    wider_hip = params.with_measurements(
        hip=params.measurement("hip") + _HIP_CHANGE_MM
    )
    baseline_landmarks = {item.name: item.position for item in generate_mesh(params)[2]}
    wider_landmarks = {item.name: item.position for item in generate_mesh(wider_hip)[2]}
    for name in ("knee_left", "knee_right", "ankle_left", "ankle_right"):
        require(
            condition=wider_landmarks[name] == baseline_landmarks[name],
            message=f"Hip circumference must not move the {name} landmark.",
        )


def test_gender_and_breast_controls_persist_and_change_geometry() -> None:
    """Persist morphology controls and verify that they change the mesh."""
    neutral = AvatarParameters()
    feminine = AvatarParameters(gender=0.0)
    masculine = AvatarParameters(gender=1.0)
    fuller = AvatarParameters(breast_size=1.0)
    require(
        condition=AvatarParameters.from_json(feminine.to_json()) == feminine,
        message="The feminine morphology controls must survive JSON round-trips.",
    )
    require(
        condition=AvatarParameters.from_json(fuller.to_json()) == fuller,
        message="The breast-size control must survive JSON round-trips.",
    )
    edited = neutral.with_measurements(waist=780.0)
    require(
        condition=math.isclose(edited.gender, neutral.gender, rel_tol=0.0, abs_tol=0.0),
        message="A measurement edit must preserve the gender blend.",
    )
    require(
        condition=math.isclose(
            edited.breast_size,
            neutral.breast_size,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="A measurement edit must preserve the breast-size control.",
    )
    require(
        condition=generate_mesh(feminine)[0] != generate_mesh(masculine)[0],
        message="Different gender blends must change generated geometry.",
    )
    require(
        condition=generate_mesh(neutral)[0] != generate_mesh(fuller)[0],
        message="The breast-size control must change generated geometry.",
    )


@pytest.mark.parametrize(
    ("gender", "breast_size"),
    [
        (-0.01, 0.0),
        (1.01, 0.0),
        (0.5, -0.01),
        (0.5, 1.01),
    ],
)
def test_invalid_shape_values_are_rejected(gender: float, breast_size: float) -> None:
    """Reject body-shape controls outside their normalized ranges.

    Args:
        gender: Gender blend value to validate.
        breast_size: Breast-size value to validate.
    """
    with pytest.raises(ValueError):
        AvatarParameters(gender=gender, breast_size=breast_size)


def test_advanced_anny_overrides_round_trip_and_survive_measurement_edits() -> None:
    """Persist advanced Anny overrides when avatar measurements are edited."""
    parameters = AvatarParameters(
        phenotype_overrides={"age": 0.41, "weight": 0.67},
        local_change_overrides={"measure-waist-circ-incr": 0.2},
        mass_target_kg=68.5,
    )
    restored = AvatarParameters.from_json(parameters.to_json())
    edited = parameters.with_measurements(waist=780.0)
    require(
        condition=parameters.schema_version == AVATAR_SCHEMA_VERSION,
        message="The parameter record must use the current schema version.",
    )
    require(condition=restored == parameters, message="JSON round-trip must be stable.")
    require(
        condition=edited.phenotype_overrides == parameters.phenotype_overrides,
        message="Measurement edits must preserve phenotype overrides.",
    )
    require(
        condition=edited.local_change_overrides == parameters.local_change_overrides,
        message="Measurement edits must preserve local morph overrides.",
    )
    require(
        condition=math.isclose(restored.mass_target_kg or 0.0, 68.5, rel_tol=0.0, abs_tol=0.0),
        message="JSON round-trip must preserve the mass target.",
    )
    require(
        condition=math.isclose(edited.mass_target_kg or 0.0, 68.5, rel_tol=0.0, abs_tol=0.0),
        message="Measurement edits must preserve the mass target.",
    )


@pytest.mark.parametrize(
    ("phenotype_overrides", "local_change_overrides", "mass_target_kg"),
    [
        ({"age": -0.01}, {}, None),
        ({"age": 1.01}, {}, None),
        ({}, {"waist-shape": -1.01}, None),
        ({}, {"waist-shape": 1.01}, None),
        ({"gender": 0.1}, {}, None),
        ({}, {"breast-volume-vert-up": 0.5}, None),
        ({}, {}, 24.9),
        ({}, {}, 250.1),
    ],
)
def test_advanced_anny_overrides_are_range_checked_and_do_not_shadow_primary_controls(
    phenotype_overrides: dict[str, float],
    local_change_overrides: dict[str, float],
    mass_target_kg: float | None,
) -> None:
    """Reject out-of-range advanced overrides and conflicts with primary controls.

    Args:
        phenotype_overrides: Phenotype values to validate.
        local_change_overrides: Local morphology values to validate.
        mass_target_kg: Optional mass target to validate.
    """
    with pytest.raises(ValueError):
        AvatarParameters(
            phenotype_overrides=phenotype_overrides,
            local_change_overrides=local_change_overrides,
            mass_target_kg=mass_target_kg,
        )


def test_skin_offset_changes_collision_geometry() -> None:
    """Ensure skin offset influences the generated collision geometry."""
    base = AvatarParameters(skin_offset=0.0)
    padded = AvatarParameters(skin_offset=_SKIN_OFFSET_TEST_MM)
    require(
        condition=generate_mesh(base)[0] != generate_mesh(padded)[0],
        message="A larger skin offset must change the generated geometry.",
    )


def test_pose_round_trip_is_persistent_and_validated() -> None:
    """Preserve a pose through JSON and reject unsupported presets."""
    params = AvatarParameters(pose=Pose("sewing"))
    restored = AvatarParameters.from_json(params.to_json())
    require(condition=restored == params, message="Pose settings must survive JSON round-trips.")
    with pytest.raises(ValueError, match="unsupported avatar pose"):
        Pose("invalid").validate()


def _mesh_x_bounds(params: AvatarParameters) -> tuple[float, float]:
    """Return the horizontal vertex bounds for an avatar pose.

    Args:
        params: Avatar parameters to generate.

    Returns:
        Minimum and maximum horizontal coordinates in millimetres.
    """
    xs = [float(point[0]) for point in generate_mesh(params)[0]]
    return min(xs), max(xs)


def test_t_pose_preset_round_trips_and_has_a_horizontal_arm_envelope() -> None:
    """Keep the T-pose arm angles and its broader horizontal mesh envelope."""
    t_pose = AvatarParameters(pose=Pose("t_pose"))
    standing = AvatarParameters(pose=Pose("standing"))
    require(
        condition=math.isclose(
            t_pose.pose.left_arm_angle or 0.0,
            DEFAULT_POSE_ARM_ANGLES["t_pose"],
            rel_tol=0.0,
            abs_tol=0.0,
        )
        and math.isclose(
            t_pose.pose.right_arm_angle or 0.0,
            DEFAULT_POSE_ARM_ANGLES["t_pose"],
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="The T-pose must use the configured horizontal arm defaults.",
    )
    require(
        condition=AvatarParameters.from_json(t_pose.to_json()) == t_pose,
        message="The T-pose settings must survive JSON round-trips.",
    )
    horizontal = _mesh_x_bounds(t_pose)
    relaxed = _mesh_x_bounds(standing)
    require(
        condition=horizontal[0] < relaxed[0] - _POSE_ENVELOPE_MARGIN_MM,
        message="The T-pose must extend farther on the left.",
    )
    require(
        condition=horizontal[1] > relaxed[1] + _POSE_ENVELOPE_MARGIN_MM,
        message="The T-pose must extend farther on the right.",
    )


def test_invalid_measurements_are_rejected() -> None:
    """Reject anthropometric combinations that violate body geometry constraints."""
    with pytest.raises(ValueError, match="underbust"):
        AvatarParameters().with_measurements(underbust=1200.0, chest=1000.0)


def test_avatar_parameter_loading_rejects_pre_release_schema_versions() -> None:
    """Reject pre-release parameter schemas rather than retaining migration branches."""
    for schema_version in (1, 2, 3, 5):
        payload = json.dumps({"schema_version": schema_version, "units": "mm"})
        with pytest.raises(ValueError, match="unsupported avatar schema version"):
            AvatarParameters.from_json(payload)
