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

import json
import math

from . import AvatarModel as _AvatarModel
from . import HumanoidMesh as _HumanoidMesh

_original_shoulder_pivots = _HumanoidMesh._estimate_shoulder_pivots


def _weighted_medial_root(samples, shoulder_half):
    """Return the proximal upper-arm root from lateral surface samples."""
    if not samples:
        return None
    ordered = sorted(samples, key=lambda item: item[0])
    count = max(1, int(math.ceil(len(ordered) * 0.08)))
    proximal = ordered[:count]
    total = sum(max(0.0, weight) for _lateral, _z, weight in proximal)
    if total <= 1e-12:
        return None
    lateral = sum(lateral * max(0.0, weight) for lateral, _z, weight in proximal) / total
    return max(shoulder_half * 0.55, min(shoulder_half * 0.95, lateral))


def _estimate_shoulder_pivots_from_upperarm(vertices, shoulder_half, shoulder_z, height_mm):
    """Anchor each arm at the authored MakeHuman upper-arm root."""
    fallback = _original_shoulder_pivots(vertices, shoulder_half, shoulder_z, height_mm)
    # Only the pinned HM08 mesh has a matching authored weight field.
    if len(vertices) != _HumanoidMesh.MAKEHUMAN_BODY_VERTEX_COUNT:
        return fallback
    try:
        source = _HumanoidMesh.ensure_makehuman_weights()
        payload = json.loads(source.read_text(encoding="utf-8", errors="strict"))
        raw = payload["weights"]
        upperarm = {"-1": [0.0] * len(vertices), "1": [0.0] * len(vertices)}
        for bone_name, entries in raw.items():
            if not bone_name.endswith((".L", ".R")):
                continue
            base = bone_name[:-2]
            if not base.startswith("upperarm"):
                continue
            side_key = "-1" if bone_name.endswith(".L") else "1"
            target = upperarm[side_key]
            for index, weight in entries:
                index = int(index)
                if 0 <= index < len(target):
                    target[index] = min(1.0, target[index] + max(0.0, float(weight)))

        result = dict(fallback)
        for side in (-1.0, 1.0):
            weights = upperarm[str(int(side))]
            samples = [
                (side * x, z, weights[index])
                for index, (x, _y, z) in enumerate(vertices)
                if weights[index] >= 0.35
                and side * x > 0.0
                and 0.64 <= z / max(1.0, height_mm) <= 0.82
            ]
            root = _weighted_medial_root(samples, shoulder_half)
            if root is not None:
                result[side] = side * root
        return result
    except (KeyError, OSError, UnicodeError, ValueError, TypeError):
        return fallback


# HierarchicalPose imports this symbol directly, so patch the provider before
# that module is imported. The geometric implementation remains the fallback.
_HumanoidMesh._estimate_shoulder_pivots = _estimate_shoulder_pivots_from_upperarm

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
