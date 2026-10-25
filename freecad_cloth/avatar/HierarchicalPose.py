# Copyright (C) 2026 FreeCAD Cloth contributors
"""Single weighted-FK pipeline for the MakeHuman mannequin and Pose Mode."""

from __future__ import annotations

import math

import numpy as np
from collections.abc import Callable

from freecad_cloth.avatar.AnnyAvatarBackend import (
    build_avatar_rig_vertices,
    build_avatar_shape_mesh,
)
from freecad_cloth.avatar.AvatarModel import (
    DEFAULT_POSE_ARM_ANGLES,
    AvatarParameters,
    Landmark,
    _landmarks,
)
from freecad_cloth.avatar.HumanoidMesh import (
    HumanoidMeshError,
    MeshData,
    _bone_source_endpoints,
    _load_source_vertices,
    load_makehuman_skeleton,
    load_makehuman_weights,
)
from freecad_cloth.avatar.SkeletonTypes import SkeletonData
from freecad_cloth.avatar.SkeletonPose import (
    AffineTransform,
    JointRotation,
    apply_weighted_fk,
    build_bone_transforms,
    joint_rotation_map,
)

Point = tuple[float, float, float]
Mapper = Callable[[Point], Point]


def _identity_point(point: Point) -> Point:
    """Normalize a fitted point to FreeCAD's millimetre coordinate frame.

    Args:
        point: Coordinate triple returned by the avatar fitting library.

    Returns:
        The same coordinates converted to Python floats.
    """
    return (float(point[0]), float(point[1]), float(point[2]))


def _make_anny_rig_mapper(
    source_vertices: tuple[Point, ...],
    rig_vertices: tuple[Point, ...],
    skeleton: SkeletonData,
) -> Mapper:
    """Build a point mapper from the source rig to fitted Anny coordinates.

    Args:
        source_vertices: Original MakeHuman rig points in their stable index order.
        rig_vertices: Fitted Anny rig points aligned with the source vertex indices.
        skeleton: Skeleton joint definitions used to preserve fitted joint centres.

    Returns:
        Callable that maps known source vertices and joint centres to fitted points.

    Raises:
        HumanoidMeshError: If the source and fitted rigs have different vertex counts.
    """
    if len(source_vertices) != len(rig_vertices):
        msg = "Anny's fitted vertices do not match the original MakeHuman rig index space."
        raise HumanoidMeshError(msg)

    def average(points: list[Point]) -> Point:
        """Compute the centroid of a non-empty list of 3D points.

        Args:
            points: Coordinates whose component-wise mean is required.

        Returns:
            The component-wise mean point.
        """
        mean = np.mean(np.asarray(points, dtype=np.float64), axis=0)
        return (float(mean[0]), float(mean[1]), float(mean[2]))

    vertices_by_point: dict[Point, list[Point]] = {}
    for source_point, fitted_point in zip(source_vertices, rig_vertices, strict=True):
        key = _identity_point(source_point)
        vertices_by_point.setdefault(key, []).append(_identity_point(fitted_point))
    mapped_vertices = {
        point: average(fitted_points) for point, fitted_points in vertices_by_point.items()
    }

    joint_centres: dict[Point, list[Point]] = {}
    for indices in skeleton["joints"].values():
        source_points = [
            source_vertices[int(index)]
            for index in indices
            if 0 <= int(index) < len(source_vertices)
        ]
        fitted_points = [
            rig_vertices[int(index)] for index in indices if 0 <= int(index) < len(rig_vertices)
        ]
        if source_points and fitted_points:
            source_centre = average(source_points)
            fitted_centre = average(fitted_points)
            joint_centres.setdefault(source_centre, []).append(fitted_centre)
    mapped_joint_centres = {
        point: average(fitted_points) for point, fitted_points in joint_centres.items()
    }

    def map_point(point: Point) -> Point:
        """Map a source joint centre or vertex into fitted Anny space.

        Args:
            point: Point expressed in the original MakeHuman coordinate frame.

        Returns:
            Fitted coordinate when the point has a mapping, otherwise the input point.
        """
        key = _identity_point(point)
        if key in mapped_joint_centres:
            return mapped_joint_centres[key]
        return mapped_vertices.get(key, key)

    return map_point


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
    skeleton: SkeletonData,
    mapper: Mapper,
) -> tuple[tuple[JointRotation, ...], dict[str, Point]]:
    """Compute baseline arm rotations and their pivots in fitted skeleton space.

    Args:
        parameters: Validated measurements and pose fields for the avatar.
        source_vertices: Rest coordinates for the source mannequin rig.
        skeleton: Loaded joint hierarchy and vertex memberships.
        mapper: Mapping from source points into fitted Anny coordinates.

    Returns:
        Joint rotations and the pivot coordinates associated with those rotations.
    """
    rotations: list[JointRotation] = []
    pivots: dict[str, Point] = {}
    shoulder_z = float(parameters.measurement("height")) * 0.76
    for bone_name, wrist_bone in (
        ("upperarm01.L", "wrist.L"),
        ("upperarm01.R", "wrist.R"),
    ):
        shoulder, _ = _bone_source_endpoints(source_vertices, skeleton, bone_name, mapper=mapper)
        wrist, _ = _bone_source_endpoints(source_vertices, skeleton, wrist_bone, mapper=mapper)
        side = -1.0 if shoulder[0] < 0.0 else 1.0
        desired_angle = (
            parameters.pose.left_arm_angle
            if side < 0.0
            else parameters.pose.right_arm_angle
        )
        if desired_angle is None:
            desired_angle = DEFAULT_POSE_ARM_ANGLES.get(
                parameters.pose.preset,
                DEFAULT_POSE_ARM_ANGLES["standing"],
            )
        desired = float(desired_angle)
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
    skeleton: SkeletonData,
    mapper: Mapper,
) -> tuple[
    tuple[JointRotation, ...],
    dict[str, Point],
    tuple[JointRotation, ...],
    dict[str, Point],
]:
    """Combine the preset arm pose with explicit manual joint rotations.

    Args:
        parameters: Validated avatar measurements and current pose settings.
        source_vertices: Rest coordinates for the source mannequin rig.
        skeleton: Loaded joint hierarchy and vertex memberships.
        mapper: Mapping from source points into fitted Anny coordinates.

    Returns:
        Effective rotations and pivots, followed by their baseline counterparts.
    """
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
    SkeletonData,
    Mapper,
    dict[str, AffineTransform],
]:
    """Build the fitted coordinate mapper and transforms for the current avatar pose.

    Args:
        parameters: Validated measurements, shape settings, and pose rotations.

    Returns:
        Source rig vertices, skeleton data, point mapper, and effective bone transforms.
    """
    source_vertices = _load_source_vertices()
    rig_vertices = build_avatar_rig_vertices(parameters)
    skeleton = load_makehuman_skeleton()
    mapper = _make_anny_rig_mapper(source_vertices, rig_vertices, skeleton)
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
    """Generate the posed mesh and baseline/effective landmark transforms together.

    Args:
        parameters: Validated measurements, shape settings, and pose rotations.
        mesh: Base topology to retain while replacing its vertices with posed coordinates.

    Returns:
        Posed mesh and paired baseline/effective bone-transform dictionaries.
    """
    source_mesh = mesh
    source_vertices = _load_source_vertices()
    rig_vertices = build_avatar_rig_vertices(parameters)
    padded_mesh = build_avatar_shape_mesh(parameters, include_skin_offset=True)
    skeleton = load_makehuman_skeleton()
    mapper = _make_anny_rig_mapper(source_vertices, rig_vertices, skeleton)
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
    rest_vertices = padded_mesh.vertices
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

    vertices, triangles = compact_mesh(posed_vertices, source_mesh.triangles)
    posed = MeshData(vertices, triangles).validate()
    return posed, (baseline_transforms, effective_transforms)


def _build_manual_mesh(parameters: AvatarParameters, mesh: MeshData) -> MeshData:
    """Build the mannequin with the shared weighted-forward-kinematics system.

    Args:
        parameters: Validated measurements, shape settings, and pose rotations.
        mesh: Base mesh whose topology will be retained.

    Returns:
        Validated mesh with vertices transformed by the effective pose.
    """
    posed, _transforms = _manual_pose_state(parameters, mesh)
    return posed


def transform_landmarks(
    landmarks: tuple[Landmark, ...],
    baseline_transforms: dict[str, AffineTransform],
    effective_transforms: dict[str, AffineTransform],
) -> tuple[Landmark, ...]:
    """Transform parameter landmarks from the base pose into the effective pose.

    Args:
        landmarks: Named points originally expressed in the base mannequin frame.
        baseline_transforms: Bone transforms for the pose before manual joint edits.
        effective_transforms: Bone transforms after applying manual joint edits.

    Returns:
        Landmarks with applicable points transformed into the effective pose.
    """
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
        result.append(Landmark(landmark.name, tuple(float(value) for value in posed_point)))
    return tuple(result)


def build_hierarchical_avatar_mesh(parameters: AvatarParameters) -> MeshData:
    """Build the mannequin using the shared weighted-forward-kinematics system.

    Args:
        parameters: Validated avatar measurements, shape settings, and pose rotations.

    Returns:
        Validated mannequin mesh in the effective pose.
    """
    return _build_manual_mesh(
        parameters, build_avatar_shape_mesh(parameters, include_skin_offset=False)
    )


def generate_hierarchical_mesh(
    parameters: AvatarParameters,
) -> tuple[
    tuple[Point, ...],
    tuple[tuple[int, int, int], ...],
    tuple[Landmark, ...],
]:
    """Generate mesh coordinates and transformed landmarks from the authoritative FK state.

    Args:
        parameters: Validated avatar measurements, shape settings, and pose rotations.

    Returns:
        Compact vertices, triangular faces, and landmarks in the effective pose.
    """
    mesh, (baseline_transforms, effective_transforms) = _manual_pose_state(
        parameters, build_avatar_shape_mesh(parameters, include_skin_offset=False)
    )
    return (
        mesh.vertices,
        mesh.triangles,
        transform_landmarks(_landmarks(parameters), baseline_transforms, effective_transforms),
    )
