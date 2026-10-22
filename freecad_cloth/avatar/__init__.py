# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar package — human mannequin and avatar geometry providers."""

from importlib import import_module as _import_module
from sys import modules as _modules
from types import ModuleType
from typing import TYPE_CHECKING

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
        avatar_commands as AvatarCommands,
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

    Raises:
        AttributeError: If name is not a declared avatar package export.

    Returns:
        ModuleType: The submodule represented by the requested export.
    """
    if name not in __all__:
        raise AttributeError(name)
    module_name = "avatar_commands" if name == "AvatarCommands" else name
    module = _import_module(f".{module_name}", __name__)
    globals()[name] = module
    if name == "AvatarCommands":
        _modules.setdefault(f"{__name__}.AvatarCommands", module)
    return module
