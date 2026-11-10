# Copyright (C) 2026 FreeCAD Cloth contributors
"""Lazy, statically typed access to the Qt binding shipped with FreeCAD.

FreeCAD exposes Qt modules through either the legacy PySide package or PySide2.
Keep those runtime imports lazy so importing a non-GUI workbench module does not
load Qt, while Pyright receives the maintained PySide2 type stubs.
"""

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide2 import QtCore as QtCore
    from PySide2 import QtGui as QtGui
    from PySide2 import QtSvg as QtSvg
    from PySide2 import QtTest as QtTest
    from PySide2 import QtWidgets as QtWidgets

__all__ = ["QtCore", "QtGui", "QtSvg", "QtTest", "QtWidgets"]


def __getattr__(name: str) -> ModuleType:
    """Load one requested Qt submodule from the first supported binding.

    Args:
        name: Qt submodule requested by a FreeCAD GUI caller.

    Returns:
        The requested Qt module from PySide or PySide2.

    Raises:
        AttributeError: If the requested name is not an exported Qt submodule.
        ImportError: If neither supported FreeCAD Qt binding exposes the module.
    """
    if name not in __all__:
        raise AttributeError(name)
    for binding in ("PySide", "PySide2"):
        try:
            return import_module(f"{binding}.{name}")
        except ImportError:
            continue
    msg = f"FreeCAD does not provide a supported Qt module named {name!r}"
    raise ImportError(msg)
