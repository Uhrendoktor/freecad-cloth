"""Cloth Avatar package — human mannequin and avatar geometry providers."""

# Enforce the authored HM08 geometry convention at the package boundary. The
# pinned MakeHuman OBJ is Z-up; older code mapped Y into the FreeCAD height axis,
# which produced a horizontal mannequin. Compacting removes unused canonical
# vertices that otherwise distort FreeCAD Mesh bounds and collision centroids.
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

from . import HumanoidMesh as _HumanoidMesh


def _map_hm08_z_up(vertices):
    zmin = min(float(v[2]) for v in vertices)
    zmax = max(float(v[2]) for v in vertices)
    span = max(1e-9, zmax - zmin)
    return [(float(x), float(y), (float(z) - zmin) / span) for x, y, z in vertices]


_HumanoidMesh._map_makehuman_axes = _map_hm08_z_up

from . import AvatarModel as _AvatarModel
from .MeshSanity import compact_mesh as _compact_mesh

_original_generate_mesh = _AvatarModel.generate_mesh
if not getattr(_original_generate_mesh, "_cloth_avatar_mesh_sane", False):
    def _generate_mesh_sane(params):
        vertices, triangles, landmarks = _original_generate_mesh(params)
        vertices, triangles = _compact_mesh(vertices, triangles)
        return vertices, triangles, landmarks

    _generate_mesh_sane._cloth_avatar_mesh_sane = True
    _AvatarModel.generate_mesh = _generate_mesh_sane
