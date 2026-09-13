"""Cloth Avatar package — human mannequin and avatar geometry providers."""

# Individual avatar modules import each other and the simulation layer, so keep
# the package dependency-light while normalizing the public generated mesh at
# the provider boundary. HM08's coordinate convention remains owned by
# HumanoidMesh; this wrapper only removes unreferenced vertices from generated
# topology so FreeCAD bounds and collision centroids reflect authored faces.
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

from . import AvatarModel as _AvatarModel
from .HierarchicalPose import generate_hierarchical_mesh as _generate_hierarchical_mesh
from .MeshSanity import compact_mesh as _compact_mesh

_original_generate_mesh = _AvatarModel.generate_mesh
if not getattr(_original_generate_mesh, "_cloth_avatar_mesh_sane", False):
    def _generate_mesh_sane(params):
        vertices, triangles, landmarks = _generate_hierarchical_mesh(params)
        vertices, triangles = _compact_mesh(vertices, triangles)
        return vertices, triangles, landmarks

    _generate_mesh_sane._cloth_avatar_mesh_sane = True
    _AvatarModel.generate_mesh = _generate_mesh_sane
