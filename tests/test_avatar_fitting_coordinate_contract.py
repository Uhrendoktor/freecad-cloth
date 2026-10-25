# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for fixed three-dimensional fitting-coordinate parsing."""

import pytest

from freecad_cloth.avatar.AvatarFitting import BoundingVolume, PiecePlacement


@pytest.mark.parametrize(
    "serialized_placement",
    (
        "front|1,2|90",
        "front|1,2,3,4|90",
    ),
)
def test_piece_placement_rejects_invalid_coordinate_counts(
    serialized_placement: str,
) -> None:
    """Reject serialized placements with other than three position coordinates.

    Args:
        serialized_placement: Placement record with an invalid coordinate count.
    """
    with pytest.raises(
        ValueError,
        match="^position must contain three coordinates$",
    ):
        PiecePlacement.from_string(serialized_placement)


@pytest.mark.parametrize(
    "serialized_volume",
    (
        "body|1,2|1,2,3",
        "body|1,2,3,4|1,2,3",
        "body|1,2,3|1,2",
        "body|1,2,3|1,2,3,4",
    ),
)
def test_bounding_volume_rejects_invalid_coordinate_counts(
    serialized_volume: str,
) -> None:
    """Reject serialized volumes with malformed center or size coordinates.

    Args:
        serialized_volume: Volume record whose center or size is not 3D.
    """
    with pytest.raises(
        ValueError,
        match="^bounding volume center and size require three coordinates$",
    ):
        BoundingVolume.from_string(serialized_volume)
