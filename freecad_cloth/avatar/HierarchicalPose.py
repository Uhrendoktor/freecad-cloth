"""MakeHuman-authored arm posing."""
from __future__ import annotations

from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BODY_VERTEX_COUNT,
    MeshData,
    fit_makehuman_mesh,
    load_makehuman_arm_weights,
    load_makehuman_mesh,
)


def build_hierarchical_avatar_mesh(parameters) -> MeshData:
    """Build the avatar using the pinned MakeHuman skeleton and weights.

    The old hand/wrist correction layer deliberately does not exist here: the
    source skeleton and source skinning field own the arm, wrist, hand and
    finger deformation.
    """
    mesh = load_makehuman_mesh()
    weights = load_makehuman_arm_weights(len(mesh.vertices)) if len(mesh.vertices) == MAKEHUMAN_BODY_VERTEX_COUNT else None
    return fit_makehuman_mesh(mesh, parameters, arm_weights=weights)


def generate_hierarchical_mesh(parameters):
    mesh = build_hierarchical_avatar_mesh(parameters)
    from freecad_cloth.avatar.AvatarModel import _landmarks
    return mesh.vertices, mesh.triangles, _landmarks(parameters)
