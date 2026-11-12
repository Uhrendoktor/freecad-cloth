# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar domain: mannequin models, mesh providers, and GUI commands."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import freecad_cloth.avatar.AvatarArrangement as AvatarArrangement


__all__ = [
    "AvatarArrangement",
    "AvatarCommands",
    "AvatarFitting",
    "AvatarGui",
    "AvatarModel",
    "AvatarProperties",
    "AvatarProvider",
    "AvatarService",
    "FittingCommands",
    "SkeletonPose",
]
