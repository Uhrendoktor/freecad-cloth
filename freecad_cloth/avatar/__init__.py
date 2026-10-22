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
    )


class AvatarCommands(ModuleType):
    """Lazy compatibility module for the historical CamelCase import path."""

    def __getattr__(self, name: str) -> object:
        """Resolve a member from the compliant lowercase command module.

        Args:
            name: Public or private command member requested by the importer.

        Returns:
            object: The requested command member.

        Raises:
            AttributeError: If the lowercase command module does not expose the member.
        """
        package_name = self.__name__.rpartition(".")[0]
        command_module = _import_module(".avatar_commands", package_name)
        _modules[self.__name__] = command_module
        package = _modules[package_name]
        setattr(package, "AvatarCommands", command_module)
        return getattr(command_module, name)


_legacy_module_name = f"{__name__}.AvatarCommands"
_legacy_module = _modules.get(_legacy_module_name)
if _legacy_module is None:
    _legacy_module = AvatarCommands(_legacy_module_name)
    _modules[_legacy_module_name] = _legacy_module
globals()["AvatarCommands"] = _legacy_module

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
    if name == "AvatarCommands":
        module = _modules[_legacy_module_name]
    else:
        module = _import_module(f".{name}", __name__)
    globals()[name] = module
    return module
