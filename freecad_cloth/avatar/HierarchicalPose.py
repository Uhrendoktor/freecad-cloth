"""MakeHuman-authored arm posing."""

from __future__ import annotations

import math

from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BODY_VERTEX_COUNT,
    MeshData,
    _authored_arm_rig_points,
    _make_source_fitted_mapper,
    _reoriented_triangles,
    fit_makehuman_mesh,
    load_makehuman_arm_weights,
    load_makehuman_mesh,
    load_makehuman_skeleton,
    load_makehuman_weights,
)
from freecad_cloth.avatar.SkeletonPose import (
    JointRotation,
    apply_weighted_fk,
    build_bone_transforms,
    joint_rotation_map,
)


LANDMARK_BONES = {
    "neck": "neck01",
    "chest": "spine03",
    "waist": "spine04",
    "hip": "spine05",
    "crotch": "spine05",
    "shoulder_left": "clavicle.L",
    "shoulder_right": "clavicle.R",
    "knee_left": "lowerleg01.L",
    "knee_right": "lowerleg01.R",
    "ankle_left": "foot.L",
    "ankle_right": "foot.R",
    "wrist_left": "wrist.L",
    "wrist_right": "wrist.R",
}


def _legacy_arm_rotations(parameters):
    """Return the compatibility arm rotations used by the legacy pose fields."""
    points = _authored_arm_rig_points(parameters)
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(
        parameters.pose.preset, 12.0
    )
    result = []
    for side, bone in ((-1.0, "upperarm01.L"), (1.0, "upperarm01.R")):
        angle_value = (
            parameters.pose.left_arm_angle if side < 0 else parameters.pose.right_arm_angle
        )
        desired = (
            default_angle
            if parameters.pose.preset != "standing" and float(angle_value) == 12.0
            else float(angle_value)
        )
        shoulder = points[side]["shoulder"]
        wrist = points[side]["wrist"]
        radial = max(1e-9, side * (wrist[0] - shoulder[0]))
        downward = max(0.0, shoulder[2] - wrist[2])
        rest_angle = math.degrees(math.atan2(downward, radial))
        result.append(JointRotation(bone, 0.0, side * (desired - rest_angle), 0.0))
    return tuple(result)


def _manual_pose_rotations(parameters):
    """Return explicit joint edits plus the compatibility standing arm baseline."""
    explicit = joint_rotation_map(parameters.pose.joint_rotations)
    result = {item.bone: item for item in _legacy_arm_rotations(parameters)}
    result.update(explicit)
    return tuple(result.values())


def _manual_pose_state(parameters, mesh):
    """Return posed mesh plus baseline/effective transforms for fitting landmarks."""
    source_vertices = _load_source_vertices()
    transform = _make_source_fitted_mapper(
        source_vertices, parameters, float(parameters.skin_offset)
    )
    rest_vertices = tuple(transform(point) for point in mesh.vertices)
    skeleton = load_makehuman_skeleton()
    weights = load_makehuman_weights(len(rest_vertices))
    baseline_transforms = build_bone_transforms(
        source_vertices,
        skeleton,
        transform,
        _legacy_arm_rotations(parameters),
    )
    effective_transforms = build_bone_transforms(
        source_vertices,
        skeleton,
        transform,
        _manual_pose_rotations(parameters),
    )
    posed = apply_weighted_fk(
        source_vertices,
        rest_vertices,
        skeleton,
        weights,
        transform,
        _manual_pose_rotations(parameters),
    )
    return MeshData(posed, _reoriented_triangles(mesh.triangles)).validate(), (
        baseline_transforms,
        effective_transforms,
    )


def _build_manual_mesh(parameters, mesh) -> MeshData:
    """Build a weighted FK pose from the authored MakeHuman skeleton."""
    posed, _transforms = _manual_pose_state(parameters, mesh)
    return posed


def transform_landmarks(landmarks, baseline_transforms, effective_transforms):
    """Transform fitting landmarks from the legacy baseline into the manual pose."""
    result = []
    for landmark in landmarks:
        bone_name = LANDMARK_BONES.get(landmark.name)
        if bone_name is None:
            result.append(landmark)
            continue
        baseline = baseline_transforms.get(bone_name)
        effective = effective_transforms.get(bone_name)
        if baseline is None or effective is None:
            result.append(landmark)
            continue
        rest_point = baseline.inverse().apply(tuple(float(v) for v in landmark.position))
        posed_point = effective.apply(rest_point)
        result.append(type(landmark)(landmark.name, tuple(float(v) for v in posed_point)))
    return tuple(result)


def build_hierarchical_avatar_mesh(parameters) -> MeshData:
    """Build the avatar using the pinned MakeHuman skeleton and weights.

    The old hand/wrist correction layer deliberately does not exist here: the
    source skeleton and source skinning field own the arm, wrist, hand and
    finger deformation.
    """
    mesh = load_makehuman_mesh()
    if parameters.pose.joint_rotations:
        return _build_manual_mesh(parameters, mesh)
    weights = (
        load_makehuman_arm_weights(len(mesh.vertices))
        if len(mesh.vertices) == MAKEHUMAN_BODY_VERTEX_COUNT
        else None
    )
    return fit_makehuman_mesh(mesh, parameters, arm_weights=weights)


def generate_hierarchical_mesh(parameters):
    """Provide the public generate hierarchical mesh operation."""
    mesh = load_makehuman_mesh()
    from freecad_cloth.avatar.AvatarModel import _landmarks

    landmarks = _landmarks(parameters)
    if parameters.pose.joint_rotations:
        mesh, (baseline_transforms, effective_transforms) = _manual_pose_state(parameters, mesh)
        landmarks = transform_landmarks(landmarks, baseline_transforms, effective_transforms)
    else:
        weights = (
            load_makehuman_arm_weights(len(mesh.vertices))
            if len(mesh.vertices) == MAKEHUMAN_BODY_VERTEX_COUNT
            else None
        )
        mesh = fit_makehuman_mesh(mesh, parameters, arm_weights=weights)
    return mesh.vertices, mesh.triangles, landmarks
