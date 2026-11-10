# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for lazy Qt binding selection."""

from types import ModuleType

import pytest

from freecad_cloth.common import qt_compat
from tests.support.assertions import require


def test_qt_compat_prefers_the_legacy_pyside_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer PySide when FreeCAD provides the legacy binding.

    Args:
        monkeypatch: Fixture used to isolate the binding import operation.
    """
    expected = ModuleType("PySide.QtCore")
    imports: list[str] = []

    def import_module(name: str) -> ModuleType:
        """Return the fake PySide submodule requested by the compatibility layer.

        Args:
            name: Fully-qualified binding and submodule name.

        Returns:
            Fake Qt submodule standing in for FreeCAD's runtime binding.
        """
        imports.append(name)
        return expected

    monkeypatch.setattr(qt_compat, "import_module", import_module)
    actual = qt_compat.__getattr__("QtCore")

    require(condition=actual is expected, message="The legacy PySide Qt module must be returned.")
    require(
        condition=imports == ["PySide.QtCore"],
        message="PySide2 must not be imported when the legacy binding is available.",
    )


def test_qt_compat_falls_back_to_pyside2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use PySide2 when the legacy PySide package is unavailable.

    Args:
        monkeypatch: Fixture used to isolate the binding import operation.
    """
    expected = ModuleType("PySide2.QtWidgets")
    imports: list[str] = []

    def import_module(name: str) -> ModuleType:
        """Fail the legacy import and provide the PySide2 widget module.

        Args:
            name: Fully-qualified binding and submodule name.

        Returns:
            Fake QtWidgets module for the supported PySide2 fallback.
        """
        imports.append(name)
        if name == "PySide.QtWidgets":
            raise ImportError(name)
        return expected

    monkeypatch.setattr(qt_compat, "import_module", import_module)
    actual = qt_compat.__getattr__("QtWidgets")

    require(condition=actual is expected, message="The PySide2 fallback module must be returned.")
    require(
        condition=imports == ["PySide.QtWidgets", "PySide2.QtWidgets"],
        message="The compatibility layer must try PySide2 only after PySide fails.",
    )


def test_qt_compat_rejects_unknown_submodule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject names outside the explicit Qt submodule surface.

    Args:
        monkeypatch: Fixture proving no runtime import occurs for unknown names.
    """
    def import_module(name: str) -> ModuleType:
        """Fail if an unknown name unexpectedly starts importing a Qt binding.

        Args:
            name: Fully-qualified module that the test must never request.

        Returns:
            No value, because unknown Qt names must fail before importing.
        """
        msg = f"Unexpected Qt import: {name}"
        raise RuntimeError(msg)

    monkeypatch.setattr(qt_compat, "import_module", import_module)
    with pytest.raises(AttributeError, match="QApplication"):
        qt_compat.__getattr__("QApplication")
