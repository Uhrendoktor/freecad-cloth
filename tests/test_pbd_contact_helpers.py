# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the import-safe shared PBD diagnostic helpers."""

from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.PositionBasedDynamicsBackend import pbd_collision_resolution
from tests.support.assertions import require
from tests.support.pbd_contact_helpers import events, nearest_surface_distance

PBD_COLLISION_AXIS_COUNT = 3
PBD_COLLISION_MIN_CELLS = 16
PBD_COLLISION_MAX_CELLS = 256

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
    resolution = pbd_collision_resolution(surface)
    require(
        condition=len(resolution) == PBD_COLLISION_AXIS_COUNT
        and all(
            PBD_COLLISION_MIN_CELLS <= cells <= PBD_COLLISION_MAX_CELLS
            for cells in resolution
        ),
        message="collision-grid resolution must remain bounded on each axis.",
    )
    require(
        condition=resolution[1] >= resolution[0] >= resolution[2],
        message="larger coordinate spans must not receive smaller grid resolutions.",
    )
    empty_resolution = pbd_collision_resolution(CollisionSurface(vertices=(), triangles=()))
    require(
        condition=empty_resolution == [PBD_COLLISION_MIN_CELLS] * PBD_COLLISION_AXIS_COUNT,
        message="empty collision surfaces must retain the minimum grid resolution.",
    )
