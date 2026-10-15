"""Tests for the import-safe shared PBD diagnostic helpers."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from freecad_cloth.common import MeshValidation
from tests.support.pbd_contact_helpers import nearest_surface_distance


def test_surface_distance_fallback_uses_spatial_index(monkeypatch):
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("surface query backend unavailable")

    monkeypatch.setattr(MeshValidation, "nearest_surface_clearance", unavailable)
    vertices = tuple((float(index), 0.0, 0.0) for index in range(5000))
    garment_points = tuple((float(index), 0.0, 5.0) for index in range(5000))
    surface = SimpleNamespace(vertices=vertices, triangles=((0, 1, 2),))

    assert nearest_surface_distance(garment_points, surface) == pytest.approx(5.0)


def test_events_processes_qt_events_after_one_gui_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid a second synchronous FreeCAD refresh during each simulation checkpoint."""
    calls = []
    gui = ModuleType("FreeCADGui")

    def update_gui() -> None:
        calls.append("gui-update")

    gui.updateGui = update_gui
    application = SimpleNamespace(processEvents=lambda: calls.append("qt-events"))
    widgets = SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: application))
    pyside = ModuleType("PySide")
    pyside.QtWidgets = widgets
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", pyside)

    from tests.support.pbd_contact_helpers import events

    events()

    assert calls == ["gui-update", "qt-events"]
