# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical public command IDs for avatar and fitting workbench menus.

This metadata module intentionally does not import command implementations. A
workbench can construct its menu surface without importing domain execution code.
The implementation modules import these tuples as their public COMMANDS lists.
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
