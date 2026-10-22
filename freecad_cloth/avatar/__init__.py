# Copyright (C) 2026 FreeCAD Cloth contributors
"""Cloth Avatar package — human mannequin and avatar geometry providers."""


from importlib import import_module
from importlib.machinery import ModuleSpec
from sys import modules
from types import ModuleType


class _LegacyAvatarCommandModule(ModuleType):
    """Compatibility view of the former camel-case avatar command module."""

    def __getattr__(self, name: str) -> object:
        """Resolve an attribute from the canonical snake-case module."""
        module = import_module(".avatar_commands", __name__)
        return getattr(module, name)


def _install_legacy_avatar_commands_module() -> None:
    """Keep historical direct imports working without retaining a noncompliant filename."""
    legacy_name = f"{__name__}.AvatarCommands"
    legacy_module = _LegacyAvatarCommandModule(legacy_name)
    legacy_module.__package__ = __name__
    legacy_module.__spec__ = ModuleSpec(legacy_name, loader=None)
    modules.setdefault(legacy_name, legacy_module)
    globals()["AvatarCommands"] = modules[legacy_name]


_install_legacy_avatar_commands_module()

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
