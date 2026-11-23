# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for collision-aware layered-outfit support selection."""

import pytest

from tests.support.layered_outfit_support import (
    select_landmark_supports,
    select_top_boundary_supports,
)


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
            dict.fromkeys(range(1, 6), True),
            dict.fromkeys(range(1, 6), 6.0),
            minimum_clearance_mm=5.0,
        )


def test_landmark_supports_choose_nearest_bounded_exterior_particle() -> None:
    """Choose one support near each anatomical target and reject excessive stand-off."""
    chains = {"left_shoulder": (0, 1, 2), "right_shoulder": (3, 4, 5)}
    positions = (
        (-100.0, 0.0, 150.0),
        (-100.0, 28.0, 150.0),
        (-100.0, 85.0, 150.0),
        (100.0, 0.0, 150.0),
        (100.0, -25.0, 150.0),
        (100.0, -90.0, 150.0),
    )
    exterior = dict.fromkeys(range(6), True)
    exterior[0] = False
    exterior[3] = False
    clearance = {0: 20.0, 1: 28.0, 2: 85.0, 3: 30.0, 4: 25.0, 5: 90.0}

    selected = select_landmark_supports(
        chains,
        {"left_shoulder": (-100.0, 0.0, 150.0), "right_shoulder": (100.0, 0.0, 150.0)},
        positions,
        exterior,
        clearance,
        minimum_clearance_mm=5.0,
        maximum_clearance_mm=40.0,
    )

    assert selected == {"left_shoulder": 1, "right_shoulder": 4}


def test_landmark_supports_reject_targets_without_nearby_safe_particles() -> None:
    """A distant edge point must not be accepted merely because it is outside the body."""
    with pytest.raises(ValueError, match="no exterior particle within"):
        select_landmark_supports(
            {"waist-front": (0, 1)},
            {"waist-front": (0.0, 0.0, 100.0)},
            ((0.0, 0.0, 100.0), (0.0, 80.0, 100.0)),
            {0: True, 1: True},
            {0: 4.0, 1: 80.0},
            minimum_clearance_mm=5.0,
            maximum_clearance_mm=45.0,
        )


def test_landmark_supports_reject_particle_reused_by_two_targets() -> None:
    """One native particle cannot be registered as two distinct body supports."""
    with pytest.raises(ValueError, match="reused by multiple anatomical targets"):
        select_landmark_supports(
            {"waist-front": (0,), "waist-back": (0,)},
            {"waist-front": (0.0, 0.0, 100.0), "waist-back": (0.0, 0.0, 100.0)},
            ((0.0, 0.0, 100.0),),
            {0: True},
            {0: 10.0},
            minimum_clearance_mm=5.0,
            maximum_clearance_mm=45.0,
        )
