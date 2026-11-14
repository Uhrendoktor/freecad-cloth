# Copyright (C) 2026 FreeCAD Cloth contributors
"""Lazy compatibility for the historical cloth backend module path."""

from importlib import import_module
from sys import modules
from types import ModuleType

_PACKAGE_NAME = __name__.rpartition(".")[0]
_LEGACY_MODULE_NAME = f"{_PACKAGE_NAME}.ClothBackend"


def __getattr__(name: str) -> ModuleType:
    """Resolve the legacy package export to the canonical backend module.

    Args:
        name: Requested compatibility export.

    Returns:
        The canonical cloth backend module registered under its legacy path.

    Raises:
        AttributeError: If the requested compatibility export is not supported.
    """
    if name != "ClothBackend":
        raise AttributeError(name)
    backend_module = import_module(".cloth_backend", _PACKAGE_NAME)
    modules[_LEGACY_MODULE_NAME] = backend_module
    modules[_PACKAGE_NAME].__dict__["ClothBackend"] = backend_module
    return backend_module
