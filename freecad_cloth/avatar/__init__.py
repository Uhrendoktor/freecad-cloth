# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar domain: mannequin models, mesh providers, and GUI commands."""

from importlib import import_module
from typing import TYPE_CHECKING

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
_LAZY_SUBMODULES = frozenset(__all__)


def __getattr__(name: str) -> ModuleType:
    """Load an exported avatar submodule when a caller first requests it.

    Args:
        name: Public avatar submodule attribute requested by the caller.

    Returns:
        The loaded module corresponding to a name in the public export list.

    Raises:
        AttributeError: If name is not an exported avatar submodule.
    """
    if name not in _LAZY_SUBMODULES:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return import_module(f".{name}", package=__name__)
