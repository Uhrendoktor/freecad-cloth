"""Single weighted-FK pipeline for the MakeHuman mannequin and Pose Mode."""

from __future__ import annotations

import math
from collections.abc import Callable

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Landmark, _landmarks
from freecad_cloth.avatar.HumanoidMesh import (
    MeshData,
    _bone_source_endpoints,
    _joint_point,
    _load_source_vertices,
    _make_source_fitted_mapper,
    _reoriented_triangles,
    load_makehuman_mesh,
    load_makehuman_skeleton,
    load_makehuman_weights,
)
from freecad_cloth.avatar.SkeletonPose import (
    AffineTransform,
    JointRotation,
    apply_weighted_fk,
    build_bone_transforms,
    joint_rotation_map,
)

Point = tuple[float, float, float]
Mapper = Callable[[Point], Point]

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


def _arm_pose_configuration(
    parameters: AvatarParameters,
    source_vertices: tuple[Point, ...],
    skeleton: dict,
    mapper: Mapper,
) -> tuple[tuple[JointRotation, ...], dict[str, Point]]:
    """Express arm fields as rotations in the same fitted skeleton space."""
    rotations: list[JointRotation] = []
    pivots: dict[str, Point] = {}
    shoulder_z = float(parameters.measurement("height")) * 0.76
    for bone_name, wrist_bone in (
        ("upperarm01.L", "wrist.L"),
        ("upperarm01.R", "wrist.R"),
    ):
        shoulder_source, _ = _bone_source_endpoints(source_vertices, skeleton, bone_name)
        wrist_source, _ = _bone_source_endpoints(source_vertices, skeleton, wrist_bone)
        shoulder = mapper(shoulder_source)
        wrist = mapper(wrist_source)
        side = -1.0 if shoulder[0] < 0.0 else 1.0
        desired = float(
            parameters.pose.left_arm_angle
            if side < 0.0
            else parameters.pose.right_arm_angle
        )
        radial = max(1e-9, side * (wrist[0] - shoulder[0]))
        downward = max(0.0, shoulder[2] - wrist[2])
        rest_angle = math.degrees(math.atan2(downward, radial))
        rotations.append(JointRotation(bone_name, 0.0, side * (desired - rest_angle), 0.0))
        # Preserve the established fitted shoulder pivot in the common FK path.
        pivots[bone_name] = (shoulder[0], 0.0, shoulder_z)

    for bone_name, angle, side in (
        ("lowerarm01.L", float(parameters.pose.left_elbow_angle), -1.0),
        ("lowerarm01.R", float(parameters.pose.right_elbow_angle), 1.0),
    ):
        if abs(angle) > 1e-12:
            rotations.append(JointRotation(bone_name, 0.0, side * angle, 0.0))
    return tuple(rotations), pivots


def _effective_pose_configuration(
    parameters: AvatarParameters,
    source_vertices: tuple[Point, ...],
    skeleton: dict,
    mapper: Mapper,
) -> tuple[
    tuple[JointRotation, ...],
    dict[str, Point],
    tuple[JointRotation, ...],
    dict[str, Point],
]:
    base_rotations, base_pivots = _arm_pose_configuration(
        parameters, source_vertices, skeleton, mapper
    )
    effective = {rotation.bone: rotation for rotation in base_rotations}
    pivots = dict(base_pivots)
    for rotation in joint_rotation_map(parameters.pose.joint_rotations).values():
        effective[rotation.bone] = rotation
        # A manually edited joint rotates about its actual rest joint.
        pivots.pop(rotation.bone, None)
    return tuple(effective.values()), pivots, base_rotations, base_pivots


def pose_world_state(
    parameters: AvatarParameters,
) -> tuple[
    tuple[Point, ...],
    dict,
    Mapper,
    dict[str, AffineTransform],
]:
    """Return the exact rig transforms used to deform the visible mannequin."""
    source_vertices = _load_source_vertices()
    mapper = _make_source_fitted_mapper(
        source_vertices, parameters, float(parameters.skin_offset)
    )
    skeleton = load_makehuman_skeleton()
    rotations, pivots, _base_rotations, _base_pivots = _effective_pose_configuration(
        parameters, source_vertices, skeleton, mapper
    )
    transforms = build_bone_transforms(
        source_vertices, skeleton, mapper, rotations, rotation_pivots=pivots
    )
    return source_vertices, skeleton, mapper, transforms


def _manual_pose_state(
    parameters: AvatarParameters,
    mesh: MeshData,
) -> tuple[
    MeshData,
    tuple[dict[str, AffineTransform], dict[str, AffineTransform]],
]:
    """Generate mesh and landmark transforms through one weighted-FK pipeline."""
    source_vertices = _load_source_vertices()
    mapper = _make_source_fitted_mapper(
        source_vertices, parameters, float(parameters.skin_offset)
    )
    skeleton = load_makehuman_skeleton()
    effective_rotations, effective_pivots, base_rotations, base_pivots = (
        _effective_pose_configuration(parameters, source_vertices, skeleton, mapper)
    )
    baseline_transforms = build_bone_transforms(
        source_vertices, skeleton, mapper, base_rotations, rotation_pivots=base_pivots
    )
    effective_transforms = build_bone_transforms(
        source_vertices,
        skeleton,
        mapper,
        effective_rotations,
        rotation_pivots=effective_pivots,
    )
    rest_vertices = tuple(mapper(point) for point in mesh.vertices)
    weights = load_makehuman_weights(len(rest_vertices))
    posed_vertices = apply_weighted_fk(
        source_vertices,
        rest_vertices,
        skeleton,
        weights,
        mapper,
        effective_rotations,
        rotation_pivots=effective_pivots,
    )
    from freecad_cloth.avatar.MeshSanity import compact_mesh

    vertices, triangles = compact_mesh(posed_vertices, _reoriented_triangles(mesh.triangles))
    posed = MeshData(vertices, triangles).validate()
    return posed, (baseline_transforms, effective_transforms)


def _build_manual_mesh(parameters: AvatarParameters, mesh: MeshData) -> MeshData:
    """Build the mannequin with the same FK system used by Pose Mode."""
    posed, _transforms = _manual_pose_state(parameters, mesh)
    return posed


def transform_landmarks(
    landmarks: tuple[Landmark, ...],
    baseline_transforms: dict[str, AffineTransform],
    effective_transforms: dict[str, AffineTransform],
) -> tuple[Landmark, ...]:
    """Transform parameter landmarks between the base and effective FK poses."""
    result: list[Landmark] = []
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
        rest_point = baseline.inverse().apply(tuple(float(value) for value in landmark.position))
        posed_point = effective.apply(rest_point)
        result.append(
            Landmark(landmark.name, tuple(float(value) for value in posed_point))
        )
    return tuple(result)


def build_hierarchical_avatar_mesh(parameters: AvatarParameters) -> MeshData:
    """Build the mannequin with the shared weighted-FK deformation system."""
    return _build_manual_mesh(parameters, load_makehuman_mesh())


def generate_hierarchical_mesh(
    parameters: AvatarParameters,
) -> tuple[
    tuple[Point, ...],
    tuple[tuple[int, int, int], ...],
    tuple[Landmark, ...],
]:
    """Return the compact mesh and landmarks from the authoritative FK state."""
    mesh, (baseline_transforms, effective_transforms) = _manual_pose_state(
        parameters, load_makehuman_mesh()
    )
    return (
        mesh.vertices,
        mesh.triangles,
        transform_landmarks(_landmarks(parameters), baseline_transforms, effective_transforms),
    )
