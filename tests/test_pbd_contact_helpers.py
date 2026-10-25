# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the import-safe shared PBD diagnostic helpers."""

from math import ceil
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
    _pbd_collision_resolution,
    _pbd_collision_voxel_mm,
)
from tests.support.assertions import require
from tests.support.pbd_contact_helpers import events, nearest_surface_distance

if TYPE_CHECKING:
    from tests.support.pbd_contact_helpers import _EventApplication


def test_surface_distance_fallback_uses_spatial_index() -> None:
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args: object, **_kwargs: object) -> NoReturn:
        """Simulate an unavailable query so spatial-index fallback behavior is tested.

        Args:
            _args: Positional query arguments, intentionally ignored.
            _kwargs: Keyword query options, intentionally ignored.

        Raises:
            RuntimeError: Always, to force the spatial-index fallback path.
        """
        msg = "surface query backend unavailable"
        raise RuntimeError(msg)

    vertices = tuple((float(index), 0.0, 0.0) for index in range(5000))
    garment_points = tuple((float(index), 0.0, 5.0) for index in range(5000))
    surface = SimpleNamespace(vertices=vertices, triangles=((0, 1, 2),))
    actual_distance = nearest_surface_distance(
        garment_points, surface, surface_clearance_fn=unavailable
    )

    require(
        condition=actual_distance == pytest.approx(5.0),
        message="the spatial-index fallback should find the five-millimetre separation",
    )


def test_events_processes_qt_events_after_one_gui_refresh() -> None:
    """Avoid a second synchronous FreeCAD refresh during each simulation checkpoint."""
    calls: list[str] = []
    gui = ModuleType("FreeCADGui")
    gui.__dict__["updateGui"] = lambda: calls.append("gui-update")
    application = cast(
        "_EventApplication",
        SimpleNamespace(processEvents=lambda: calls.append("qt-events")),
    )

    events(gui=gui, application=application)

    require(
        condition=calls == ["gui-update", "qt-events"],
        message="GUI refresh must precede Qt event processing exactly once",
    )


def test_pbd_collision_resolution_uses_axis_spans_and_handles_empty_surfaces() -> None:
    """Preserve bounded per-axis grid sizing while calculating spans in NumPy."""
    surface = CollisionSurface(
        vertices=((-10.0, 1.0, 2.0), (10.0, 51.0, 4.0), (0.0, 20.0, 3.0)),
        triangles=((0, 1, 2),),
    )
    voxel_mm = _pbd_collision_voxel_mm()
    expected = [max(16, min(256, ceil((span + 200.0) / voxel_mm))) for span in (20.0, 50.0, 2.0)]
    require(
        condition=_pbd_collision_resolution(surface) == expected,
        message="collision-grid resolution must reflect each axis span and stay within bounds.",
    )
    empty_resolution = _pbd_collision_resolution(CollisionSurface(vertices=(), triangles=()))
    require(
        condition=empty_resolution == [16, 16, 16],
        message="empty collision surfaces must retain the minimum grid resolution.",
    )
