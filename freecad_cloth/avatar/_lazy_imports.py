# Copyright (C) 2026 FreeCAD Cloth contributors
"""Lazy attribute loader for the avatar package's public submodules."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

_AVATAR_SUBMODULES = frozenset(
    {
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
    }
)


def __getattr__(name: str) -> ModuleType:
    """Load one exported avatar submodule on first attribute access.

    Args:
        name: Public avatar submodule attribute requested by the caller.

    Returns:
        The imported module corresponding to an exported name.

    Raises:
        AttributeError: If name is not a public avatar submodule.
    """
    if name not in _AVATAR_SUBMODULES:
        package = __package__ or "freecad_cloth.avatar"
        msg = f"module {package!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return import_module(f".{name}", package=__package__)
