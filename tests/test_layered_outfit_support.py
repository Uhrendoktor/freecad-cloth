# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for collision-aware layered-outfit support selection."""

import pytest

from tests.support.layered_outfit_support import (
    boundary_bounds_mm,
    outer_shell_front_back_targets,
    panel_depth_profile_placement_y,
    sample_local_torso_depth,
    select_landmark_supports,
    select_top_boundary_supports,
)


def test_local_torso_depth_uses_only_the_requested_height_band() -> None:
    """Do not let a lower-body maximum define the upper-back shirt plane."""
    vertices = [
        (x, y, z)
        for z, front_y, back_y in (
            (900.0, -150.0, 180.0),
            (1277.5, -92.0, 128.0),
        )
        for x in (-40.0, -20.0, 0.0, 20.0, 40.0)
        for y in (front_y, back_y)
    ]

    front_y, back_y, count = sample_local_torso_depth(
        vertices,
        center_x_mm=0.0,
        center_z_mm=1277.5,
        half_width_mm=60.0,
        half_height_mm=35.0,
        minimum_samples=10,
    )

    assert (front_y, back_y, count) == (-92.0, 128.0, 10)


def test_local_torso_depth_rejects_insufficient_and_degenerate_bands() -> None:
    """A local section must be measured, not silently replaced by a global bound."""
    with pytest.raises(ValueError, match="has 2 samples"):
        sample_local_torso_depth(
            ((0.0, -10.0, 100.0), (0.0, 10.0, 100.0)),
            center_x_mm=0.0,
            center_z_mm=100.0,
            half_width_mm=20.0,
            half_height_mm=10.0,
            minimum_samples=3,
        )
    with pytest.raises(ValueError, match="positive front/back extent"):
        sample_local_torso_depth(
            ((0.0, 4.0, 100.0), (1.0, 4.0, 101.0)),
            center_x_mm=0.5,
            center_z_mm=100.5,
            half_width_mm=20.0,
            half_height_mm=10.0,
            minimum_samples=2,
        )


def test_semantic_hem_bounds_ignore_lower_non_hem_panel_vertices() -> None:
    """A side/seam vertex must not be misreported as the authored hem's drift."""
    positions = (
        (-100.0, -90.0, 980.0),
        (0.0, -90.0, 982.0),
        (100.0, -90.0, 980.0),
        (150.0, -85.0, 869.0),
    )

    minimum, maximum = boundary_bounds_mm(positions, (0, 1, 2))

    assert minimum == (-100.0, -90.0, 980.0)
    assert maximum == (100.0, -90.0, 982.0)
    assert min(point[2] for point in positions) == 869.0


def test_boundary_bounds_reject_invalid_indices_and_duplicate_samples() -> None:
    """Semantic boundary telemetry requires an exact, non-empty particle chain."""
    positions = ((0.0, 0.0, 980.0), (1.0, 0.0, 980.0))
    with pytest.raises(ValueError, match="must not be empty"):
        boundary_bounds_mm(positions, ())
    with pytest.raises(ValueError, match="duplicate indices"):
        boundary_bounds_mm(positions, (0, 0))
    with pytest.raises(ValueError, match="invalid particle index"):
        boundary_bounds_mm(positions, (2,))


def test_outer_shirt_hem_stays_outside_the_waistband_envelope() -> None:
    """The outer shirt hem must preserve the requested front/back shell gap."""
    front_y, back_y = outer_shell_front_back_targets(
        inner_front_y_mm=-82.9,
        inner_back_y_mm=177.3,
        clearance_mm=8.0,
    )

    assert front_y == pytest.approx(-90.9)
    assert back_y == pytest.approx(185.3)
    assert -82.9 - front_y == pytest.approx(8.0)
    assert back_y - 177.3 == pytest.approx(8.0)


def test_outer_shell_front_back_targets_reject_invalid_envelopes() -> None:
    """Do not build a nested garment shell from malformed or negative dimensions."""
    with pytest.raises(ValueError, match="positive depth"):
        outer_shell_front_back_targets(10.0, 10.0, 8.0)
    with pytest.raises(ValueError, match="clearance must be positive"):
        outer_shell_front_back_targets(-10.0, 10.0, 0.0)


def test_panel_depth_profile_interpolates_hip_and_upper_torso_sections() -> None:
    """The tilted panel origin must interpolate the two measured body sections."""
    origin_y, slope = panel_depth_profile_placement_y(
        reference_y_mm=-90.0,
        reference_z_mm=920.0,
        support_y_mm=-113.0,
        support_z_mm=1277.5,
        panel_origin_z_mm=835.0,
    )

    assert slope == pytest.approx(-23.0 / 357.5)
    assert origin_y == pytest.approx(-90.0 + slope * (835.0 - 920.0))
    assert origin_y + slope * (920.0 - 835.0) == pytest.approx(-90.0)
    assert origin_y + slope * (1277.5 - 835.0) == pytest.approx(-113.0)


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


def test_support_selection_can_distribute_five_tucked_hem_anchors() -> None:
    """A wide shirt hem needs five safe anchors per panel rather than three."""
    chain = {"front": tuple(range(11))}
    exterior = dict.fromkeys(range(11), True)
    clearances = dict.fromkeys(range(11), 14.0)

    selected = select_top_boundary_supports(
        chain,
        exterior,
        clearances,
        minimum_clearance_mm=5.0,
        samples_per_chain=5,
    )

    assert len(selected["front"]) == 5
    assert len(set(selected["front"])) == 5
    assert selected["front"] == (0, 2, 5, 8, 10)


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
