# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression coverage for persistent avatar arrangement-point metadata."""

import freecad_cloth.avatar as avatar_package
import freecad_cloth.avatar.avatar_arrangement as implementation_module
from freecad_cloth.avatar.avatar_arrangement import (
    arrangement_point_map,
    arrangement_points_from_landmarks,
)
from tests.support.assertions import require


class _StringRecord:
    """Represent arrangement metadata with an explicit string conversion."""

    def __init__(self, value: str) -> None:
        """Store one serialized metadata record.

        Args:
            value: Serialized arrangement record returned by the string conversion.
        """
        self.value = value

    def __str__(self) -> str:
        """Return the serialized arrangement record.

        Returns:
            The exact metadata string stored by the fixture.
        """
        return self.value


def test_landmarks_preserve_canonical_order_and_persisted_format() -> None:
    """Normalize string-convertible landmarks into the stable point order."""
    records = (
        _StringRecord("shoulder_right|11,12,13"),
        _StringRecord("unknown|99,99,99"),
        _StringRecord("neck|1,2,3"),
    )
    normalized = arrangement_points_from_landmarks(records)
    require(
        condition=normalized
        == [
            "neck|1,2,3|front|0|",
            "shoulder_right|11,12,13|front|0|",
        ],
        message="Landmarks must be normalized in the stable canonical point order.",
    )


def test_arrangement_map_rejects_invalid_record_shapes_and_values() -> None:
    """Accept only records with five fields, three coordinates, and valid metadata."""
    records = (
        _StringRecord("neck|1,2,3|front|0|"),
        _StringRecord("chest|1,2|front|0|"),
        _StringRecord("waist|1,2,3|up|0|"),
        _StringRecord("hip|1,2,3|front|not-a-number|"),
        _StringRecord("knee_left|1,2,3|front|0"),
    )
    mapped = arrangement_point_map(records)
    require(
        condition=mapped == {"neck": "1,2,3"},
        message="Malformed arrangement metadata must be omitted from the point map.",
    )


def test_legacy_import_path_reexports_the_lowercase_implementation() -> None:
    """Keep historical PascalCase imports bound to the lowercase implementation."""
    legacy_module = avatar_package.AvatarArrangement
    require(
        condition=(
            legacy_module.arrangement_point_map is implementation_module.arrangement_point_map
            and legacy_module.arrangement_points_from_landmarks
            is implementation_module.arrangement_points_from_landmarks
        ),
        message="The historical AvatarArrangement path must re-export canonical functions.",
    )
