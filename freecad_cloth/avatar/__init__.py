# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar package — human mannequin and avatar geometry providers."""

from importlib import import_module as _import_module
from types import ModuleType
from typing import TYPE_CHECKING

from ._avatar_compat import AvatarCommands

if TYPE_CHECKING:
    from . import (
        AvatarArrangement,
        AvatarCollision,
        AvatarFitting,
        AvatarGui,
        AvatarModel,
        AvatarProvider,
        AvatarService,
        FittingCommands,
        SkeletonPose,
    )

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
    "SkeletonPose",
]


def __getattr__(name: str) -> ModuleType:
    """Lazily expose an avatar package submodule.

    Args:
        name: Public avatar submodule name requested by the import system.

    Returns:
        ModuleType: The submodule represented by the requested export.

    Raises:
        AttributeError: If name is not a declared avatar package export.
    """
    if name not in __all__:
        raise AttributeError(name)
    module = _import_module(f".{name}", __name__)
    globals()[name] = module
    return module
