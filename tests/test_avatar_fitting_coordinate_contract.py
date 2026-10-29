# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for fixed three-dimensional fitting-coordinate parsing."""

import pytest

from freecad_cloth.avatar.AvatarFitting import BoundingVolume, PiecePlacement
from tests.support.assertions import require


@pytest.mark.parametrize(
    "serialized_placement",
    [
        "front|1,2|90",
        "front|1,2,3,4|90",
    ],
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
        match=r"^position must contain three coordinates$",
    ):
        PiecePlacement.from_string(serialized_placement)


@pytest.mark.parametrize(
    "serialized_volume",
    [
        "body|1,2|1,2,3",
        "body|1,2,3,4|1,2,3",
        "body|1,2,3|1,2",
        "body|1,2,3|1,2,3,4",
    ],
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
        match=r"^bounding volume center and size require three coordinates$",
    ):
        BoundingVolume.from_string(serialized_volume)


def test_valid_fitting_records_round_trip() -> None:
    """Preserve valid placement and bounding-volume records through serialization."""
    placement = PiecePlacement("front", (1.5, -2.0, 3.25), 90.0)
    restored_placement = PiecePlacement.from_string(placement.to_string())
    require(
        condition=restored_placement == placement,
        message="A valid placement must survive serialization and parsing.",
    )
    volume = BoundingVolume("torso", (1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
    restored_volume = BoundingVolume.from_string(volume.to_string())
    require(
        condition=restored_volume == volume,
        message="A valid bounding volume must survive serialization and parsing.",
    )
