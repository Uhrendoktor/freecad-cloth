"""MakeHuman-authored arm posing."""

from __future__ import annotations

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
    joint_rotation_map,
)


def _manual_pose_rotations(parameters):
    """Return explicit joint edits plus the compatibility standing arm baseline."""
    explicit = joint_rotation_map(parameters.pose.joint_rotations)
    points = _authored_arm_rig_points(parameters)
    default_angle = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}.get(
        parameters.pose.preset, 12.0
    )
    result = dict(explicit)
    for side, bone in ((-1.0, "upperarm01.L"), (1.0, "upperarm01.R")):
        if bone in result:
            continue
        angle_value = (
            parameters.pose.left_arm_angle
            if side < 0
            else parameters.pose.right_arm_angle
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
        result[bone] = JointRotation(bone, 0.0, side * (desired - rest_angle), 0.0)
    return tuple(result.values())


def _build_manual_mesh(parameters, mesh) -> MeshData:
    """Build a weighted FK pose from the authored MakeHuman skeleton."""
    source_vertices = tuple(mesh.vertices)
    transform = _make_source_fitted_mapper(
        source_vertices, parameters, float(parameters.skin_offset)
    )
    rest_vertices = tuple(transform(point) for point in source_vertices)
    skeleton = load_makehuman_skeleton()
    weights = load_makehuman_weights(len(rest_vertices))
    rotations = _manual_pose_rotations(parameters)
    posed = apply_weighted_fk(
        source_vertices, rest_vertices, skeleton, weights, transform, rotations
    )
    return MeshData(posed, _reoriented_triangles(mesh.triangles)).validate()


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
    mesh = build_hierarchical_avatar_mesh(parameters)
    from freecad_cloth.avatar.AvatarModel import _landmarks

    return mesh.vertices, mesh.triangles, _landmarks(parameters)
