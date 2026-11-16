# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the import-safe shared PBD diagnostic helpers."""

from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Never, NoReturn, cast

import pytest

from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.PositionBasedDynamicsBackend import pbd_collision_resolution
from freecad_cloth.simulation.InterClothContact import project_inter_cloth_contacts
from tests.support.pbd_contact_helpers import (
    LADDER_STITCH_SAMPLES,
    append_optional_ladder_piece,
    configure_ladder_scene,
    events,
    nearest_surface_distance,
    position_bounds,
)

PBD_COLLISION_AXIS_COUNT = 3
PBD_COLLISION_MIN_CELLS = 16
PBD_COLLISION_MAX_CELLS = 256

if TYPE_CHECKING:
    from tests.support.pbd_contact_helpers import _EventApplication


def test_surface_distance_fallback_uses_spatial_index() -> None:
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args: Never, **_kwargs: Never) -> NoReturn:
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

    assert actual_distance == pytest.approx(5.0), (
        "the spatial-index fallback should find the five-millimetre separation"
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

    assert calls == ["gui-update", "qt-events"], (
        "GUI refresh must precede Qt event processing exactly once"
    )


def test_pbd_collision_resolution_uses_axis_spans_and_handles_empty_surfaces() -> None:
    """Preserve bounded per-axis grid sizing while calculating spans in NumPy."""
    surface = CollisionSurface(
        vertices=((-10.0, 1.0, 2.0), (10.0, 51.0, 4.0), (0.0, 20.0, 3.0)),
        triangles=((0, 1, 2),),
    )
    resolution = pbd_collision_resolution(surface)
    assert len(resolution) == PBD_COLLISION_AXIS_COUNT and all(
        PBD_COLLISION_MIN_CELLS <= cells <= PBD_COLLISION_MAX_CELLS for cells in resolution
    ), "collision-grid resolution must remain bounded on each axis."
    assert resolution[1] >= resolution[0] >= resolution[2], (
        "larger coordinate spans must not receive smaller grid resolutions."
    )
    empty_resolution = pbd_collision_resolution(CollisionSurface(vertices=(), triangles=()))
    assert empty_resolution == [PBD_COLLISION_MIN_CELLS] * PBD_COLLISION_AXIS_COUNT, (
        "empty collision surfaces must retain the minimum grid resolution."
    )


def test_ladder_scene_helpers_add_only_requested_pieces_and_keep_scene_state_coherent() -> None:
    """Configure common cloth state and add a second panel only for two-piece cases."""
    left = SimpleNamespace()
    right = SimpleNamespace()
    pieces = [left]
    seams: list[tuple[SimpleNamespace, SimpleNamespace]] = []
    append_optional_ladder_piece(
        spec={"piece_count": 2, "seam_mode": "large"},
        pieces=pieces,
        create_right_piece=lambda: right,
        add_seam=lambda first, second: seams.append((first, second)),
    )
    scene = SimpleNamespace()
    configure_ladder_scene(scene, pieces, {"pin_mode": "hem"})
    assert pieces == [left, right] and seams == [(left, right)], (
        "the shared ladder helper must add a right panel and seam only as requested"
    )
    assert (
        scene.ClothPieces is pieces
        and scene.SeamSelection == []
        and scene.PinMode == "hem"
        and scene.PinSelection == []
        and scene.StitchSamples == LADDER_STITCH_SAMPLES
        and scene.Steps == 0
    ), "the shared ladder helper must initialize common scene controls consistently"


def test_position_bounds_uses_vectorized_axis_reductions() -> None:
    """Compute all six particle bounds from one coordinate array."""
    actual = position_bounds(((-2.0, 1.0, 5.0), (4.0, -3.0, 9.0)))
    assert actual == {
        "x_min": -2.0,
        "x_max": 4.0,
        "y_min": -3.0,
        "y_max": 1.0,
        "z_min": 5.0,
        "z_max": 9.0,
    }, "axis bounds must match the full particle coordinate set"
    with pytest.raises(ValueError, match="empty PBD position set"):
        position_bounds(())


def _parallel_cloth_groups(offset_mm: float = 0.25):
    """Create two independent, identically triangulated square cloth surfaces."""
    positions = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, offset_mm),
        (10.0, 0.0, offset_mm),
        (10.0, 10.0, offset_mm),
        (0.0, 10.0, offset_mm),
    )
    triangles = ((0, 1, 2), (0, 2, 3))
    return positions, {
        "shirt": triangles,
        "skirt": tuple(tuple(index + 4 for index in triangle) for triangle in triangles),
    }


def test_inter_cloth_projection_separates_parallel_independent_surfaces() -> None:
    """Two garment groups must separate by the requested clearance, not by sewing."""
    positions, groups = _parallel_cloth_groups()
    corrected, directions, metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=4,
    )

    assert metrics.contact_count > 0
    assert metrics.corrected_particle_count == len(positions)
    assert metrics.remaining_contact_count == 0
    assert metrics.max_penetration_after_mm <= 1e-7
    assert all(abs(float(value[2])) > 0.0 for value in directions)
    assert all(corrected[index][2] < 0.0 for index in range(4))
    assert all(corrected[index][2] > 0.25 for index in range(4, 8))


def test_inter_cloth_projection_preserves_pins_and_leaves_separated_surfaces_alone() -> None:
    """Pinned garment particles stay fixed and non-contacting layers are unchanged."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    pinned, _directions, _metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
        clearance_mm=1.0,
        iterations=4,
    )
    assert pinned[:4] == positions[:4]
    assert any(pinned[index] != positions[index] for index in range(4, 8))

    separated_positions, separated_groups = _parallel_cloth_groups(offset_mm=20.0)
    untouched, _directions, separated_metrics = project_inter_cloth_contacts(
        separated_positions,
        separated_groups,
        (1.0,) * len(separated_positions),
        clearance_mm=1.0,
    )
    assert untouched == separated_positions
    assert separated_metrics.contact_count == 0
    assert separated_metrics.corrected_particle_count == 0


def test_inter_cloth_samples_detect_an_edge_piercing_an_opposing_face() -> None:
    """Mid-edge samples must detect face intersections that have no close vertices."""
    positions = (
        (-10.0, -10.0, 0.0),
        (10.0, -10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, -10.0, -10.0),
        (0.0, 10.0, -10.0),
        (0.0, 0.0, 10.0),
    )
    corrected, _directions, metrics = project_inter_cloth_contacts(
        positions,
        {
            "horizontal": ((0, 1, 2),),
            "vertical": ((3, 4, 5),),
        },
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=4,
    )

    assert metrics.contact_count > 0, "crossing edge/face samples must be observed"
    assert corrected != positions, "the detected surface crossing must change solver particles"


def test_inter_cloth_projection_rejects_shared_particles_and_invalid_clearance() -> None:
    """Independent garments cannot alias solver particles or request invalid clearance."""
    positions, groups = _parallel_cloth_groups()
    shared = {
        "outer": ((0, 1, 2),),
        "inner": ((0, 2, 3),),
    }
    with pytest.raises(ValueError, match="must not share solver particles"):
        project_inter_cloth_contacts(
            positions,
            shared,
            (1.0,) * len(positions),
            clearance_mm=1.0,
        )
    with pytest.raises(ValueError, match="positive and finite"):
        project_inter_cloth_contacts(
            positions,
            groups,
            (1.0,) * len(positions),
            clearance_mm=0.0,
        )
