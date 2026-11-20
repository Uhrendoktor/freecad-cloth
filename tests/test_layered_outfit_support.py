# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for collision-aware layered-outfit support selection."""

import pytest

from tests.support.layered_outfit_support import select_top_boundary_supports


def test_support_selection_skips_interior_and_too_close_particles() -> None:
    """Choose three distributed supports per edge only from safe candidates."""
    top_chains = {
        "front": (0, 1, 2, 3, 4, 5),
        "right": (6, 7, 8, 9, 10, 11),
    }
    exterior = {index: True for chain in top_chains.values() for index in chain}
    exterior[2] = False
    exterior[8] = False
    clearance = {index: 6.0 for chain in top_chains.values() for index in chain}
    clearance[1] = 4.9
    clearance[10] = 4.0

    selected = select_top_boundary_supports(
        top_chains,
        exterior,
        clearance,
        minimum_clearance_mm=5.0,
    )

    assert selected == {
        "front": (0, 4, 5),
        "right": (6, 9, 11),
    }


def test_support_selection_rejects_top_edge_without_enough_safe_particles() -> None:
    """Do not silently pin an intersecting or under-clearance shoulder edge."""
    with pytest.raises(ValueError, match="only 1 exterior particle"):
        select_top_boundary_supports(
            {"right": (1, 2, 3, 4)},
            {1: True, 2: False, 3: True, 4: False},
            {1: 6.0, 2: 8.0, 3: 4.0, 4: 8.0},
            minimum_clearance_mm=5.0,
        )


def test_support_selection_rejects_particles_shared_by_panel_boundaries() -> None:
    """Every selected support must belong to one authored panel edge only."""
    with pytest.raises(ValueError, match="reused by multiple panel boundaries"):
        select_top_boundary_supports(
            {"front": (1, 2, 3), "right": (3, 4, 5)},
            {index: True for index in range(1, 6)},
            {index: 6.0 for index in range(1, 6)},
            minimum_clearance_mm=5.0,
        )
