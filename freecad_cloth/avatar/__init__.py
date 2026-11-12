# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar domain: mannequin models, mesh providers, and GUI commands."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import (
        AvatarArrangement,
        AvatarCommands,
        AvatarFitting,
        AvatarGui,
        AvatarModel,
        AvatarProperties,
        AvatarProvider,
        AvatarService,
        FittingCommands,
        SkeletonPose,
    )

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
