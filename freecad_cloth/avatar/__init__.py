# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar domain: mannequin models, mesh providers, and GUI commands."""

from typing import TYPE_CHECKING

from ._lazy_imports import __getattr__ as __getattr__

if TYPE_CHECKING:
    from types import ModuleType

    AvatarArrangement: ModuleType
    AvatarCommands: ModuleType
    AvatarFitting: ModuleType
    AvatarGui: ModuleType
    AvatarModel: ModuleType
    AvatarProperties: ModuleType
    AvatarProvider: ModuleType
    AvatarService: ModuleType
    FittingCommands: ModuleType
    SkeletonPose: ModuleType

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
