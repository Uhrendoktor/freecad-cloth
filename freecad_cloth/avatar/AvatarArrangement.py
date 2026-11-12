# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning. This provides the persistent fitting
anchor foundation needed by later CLO-like garment placement interactions.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class _StringConvertible(Protocol):
    """Record values whose string representation carries serialized metadata."""

    def __str__(self) -> str:
        """Return the serialized representation of the record.

        Returns:
            The serialized arrangement metadata text.
        """

ARRANGEMENT_POINT_RECORD_FIELD_COUNT = 5
ARRANGEMENT_POINT_COORDINATE_COMPONENT_COUNT = 3

ARRANGEMENT_POINT_NAMES = (
    "neck",
    "chest",
    "waist",
    "hip",
    "shoulder_left",
    "shoulder_right",
    "knee_left",
    "knee_right",
)


def arrangement_points_from_landmarks(landmarks: Iterable[_StringConvertible] | None) -> list[str]:
    """Normalize landmark records into the stable public arrangement-point order.

    Args:
        landmarks: Iterable of serialized name-and-coordinate records, if available.

    Returns:
        Known landmarks serialized in the current five-field arrangement-point format.
    """
    by_name: dict[str, str] = {}
    for record in landmarks or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            by_name[name] = f"{name}|{coords}|front|0|"
    return [by_name[name] for name in ARRANGEMENT_POINT_NAMES if name in by_name]


def arrangement_point_map(records: Iterable[_StringConvertible] | None) -> dict[str, str]:
    """Return current-format arrangement coordinates indexed by point name.

    Args:
        records: Iterable of serialized five-field arrangement-point records.

    Returns:
        Mapping from known arrangement-point names to their coordinate strings.
    """
    result: dict[str, str] = {}
    for record in records or ():
        parts = str(record).split("|")
        if len(parts) != ARRANGEMENT_POINT_RECORD_FIELD_COUNT:
            continue
        name, coordinates, wrap_direction, rotation, symmetry_group = parts
        if (
            name not in ARRANGEMENT_POINT_NAMES
            or wrap_direction not in {"front", "back", "left", "right"}
            or (symmetry_group and not symmetry_group.strip())
        ):
            continue
        try:
            values = tuple(float(value) for value in coordinates.split(","))
            float(rotation)
        except ValueError:
            continue
        if len(values) == ARRANGEMENT_POINT_COORDINATE_COMPONENT_COUNT:
            result[name] = coordinates
    return result
