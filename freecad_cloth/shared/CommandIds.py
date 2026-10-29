# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical command identifiers shared by workbench registration and command providers.

These tuples are declarative UI metadata, not command implementations. Keeping them
in a dependency-neutral module lets workbenches register stable command IDs without
importing another domain's code. The implementation modules expose these tuples as
their public COMMANDS lists, while startup validation checks that registration matches.
"""

AVATAR_COMMANDS = (
    "ClothFitting_CreateAvatar",
    "ClothFitting_EditAvatar",
    "ClothFitting_PoseAvatar",
    "ClothFitting_RebuildAvatar",
    "ClothFitting_SetAvatarMeasurements",
    "ClothFitting_SetAvatarPose",
    "ClothFitting_SetAvatarProvider",
    "ClothFitting_SetAvatarJoint",
    "ClothFitting_SetAvatarSkinOffset",
)
FITTING_COMMANDS = (
    "ClothFitting_CreateScene",
    "ClothFitting_InteractiveArrange",
    "ClothFitting_SetMeasurements",
    "ClothFitting_AssignAvatar",
    "ClothFitting_AddPieces",
    "ClothFitting_CreateArrangementPoint",
    "ClothFitting_SetArrangementPoint",
    "ClothFitting_DeleteArrangementPoint",
    "ClothFitting_CreateBoundingVolume",
    "ClothFitting_DeleteBoundingVolume",
    "ClothFitting_SetSymmetry",
    "ClothFitting_ApplyArrangementPoint",
    "ClothFitting_ResetArrangement",
    "ClothFitting_CreateSimulation",
)
AVATAR_ENTRY_COMMANDS = AVATAR_COMMANDS[:3]
