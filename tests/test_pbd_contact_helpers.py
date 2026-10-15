"""Tests for the import-safe shared PBD diagnostic helpers."""

from types import SimpleNamespace

import pytest

from tests.support.pbd_contact_helpers import nearest_surface_distance


def test_surface_distance_fallback_uses_spatial_index():
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("surface query backend unavailable")

    vertices = tuple((float(index), 0.0, 0.0) for index in range(5000))
    garment_points = tuple((float(index), 0.0, 5.0) for index in range(5000))
    surface = SimpleNamespace(vertices=vertices, triangles=((0, 1, 2),))

    assert nearest_surface_distance(
        garment_points, surface, surface_clearance_fn=unavailable
    ) == pytest.approx(5.0)


def test_events_processes_qt_events_after_one_gui_refresh() -> None:
    """Avoid a second synchronous FreeCAD refresh during each simulation checkpoint."""
    calls = []
    gui = SimpleNamespace(updateGui=lambda: calls.append("gui-update"))
    application = SimpleNamespace(processEvents=lambda: calls.append("qt-events"))

    from tests.support.pbd_contact_helpers import events

    events(gui=gui, application=application)

    assert calls == ["gui-update", "qt-events"]
