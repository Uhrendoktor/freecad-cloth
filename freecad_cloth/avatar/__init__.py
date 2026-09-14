"""Cloth Avatar package — human mannequin and avatar geometry providers."""

__all__ = [
    "AvatarArrangement",
    "AvatarCollision",
    "AvatarCommands",
    "AvatarFitting",
    "AvatarGui",
    "AvatarModel",
    "AvatarProvider",
    "AvatarService",
    "FittingCommands",
]

from dataclasses import replace as _replace

from . import AvatarModel as _AvatarModel
from . import HierarchicalPose as _HierarchicalPose
from .MeshSanity import compact_mesh as _compact_mesh


def _standing_visual_parameters(params):
    """Convert the legacy 12° standing sentinel into a neutral arm-down pose."""
    pose = params.pose
    if pose.preset != "standing":
        return params
    if float(pose.left_arm_angle) != 12.0 or float(pose.right_arm_angle) != 12.0:
        return params
    neutral_pose = _replace(pose, left_arm_angle=70.0, right_arm_angle=70.0)
    return _replace(params, pose=neutral_pose)


_original_generate_mesh = _AvatarModel.generate_mesh
if not getattr(_original_generate_mesh, "_cloth_avatar_mesh_sane", False):
    def _generate_mesh_sane(params):
        visual_params = _standing_visual_parameters(params)
        vertices, triangles, landmarks = _HierarchicalPose.generate_hierarchical_mesh(visual_params)
        vertices, triangles = _compact_mesh(vertices, triangles)
        return vertices, triangles, landmarks

    _generate_mesh_sane._cloth_avatar_mesh_sane = True
    _AvatarModel.generate_mesh = _generate_mesh_sane
