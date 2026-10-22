# Copyright (C) 2026 FreeCAD Cloth contributors
"""Lazy compatibility for the historical avatar command module path."""

from importlib import import_module
from sys import modules
from types import ModuleType


class _LegacyAvatarCommands(ModuleType):
    """Lazy proxy for the retired CamelCase avatar command module."""

    def __getattr__(self, name: str) -> object:
        """Resolve a command attribute from the canonical implementation.

        Args:
            name: Attribute requested from the legacy module path.

        Returns:
            object: The requested attribute from the canonical module.
        """
        package_name = self.__name__.rpartition(".")[0]
        command_module = import_module(".avatar_commands", package_name)
        modules[self.__name__] = command_module
        package = modules[package_name]
        package.AvatarCommands = command_module
        return getattr(command_module, name)


_PACKAGE_NAME = __name__.rpartition(".")[0]
_LEGACY_MODULE_NAME = f"{_PACKAGE_NAME}.AvatarCommands"
_LEGACY_MODULE = _LegacyAvatarCommands(_LEGACY_MODULE_NAME)
modules[_LEGACY_MODULE_NAME] = _LEGACY_MODULE


def __getattr__(name: str) -> ModuleType:
    """Export the lazy proxy for legacy package-level imports.

    Args:
        name: Name requested from the compatibility module.

    Returns:
        ModuleType: The registered legacy proxy.

    Raises:
        AttributeError: If the requested export is not declared.
    """
    if name != "AvatarCommands":
        raise AttributeError(name)
    return _LEGACY_MODULE
