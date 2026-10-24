# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning. This provides the persistent fitting
anchor foundation needed by later CLO-like garment placement interactions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

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


def arrangement_points_from_landmarks(landmarks: Iterable[object] | None) -> list[str]:
    """Normalize landmark records into the stable public arrangement-point order.

    Args:
        landmarks: Iterable of serialized name-and-coordinate records, if available.

    Returns:
        Known landmarks serialized in the current five-field arrangement-point format.
    """
    by_name = {}
    for record in landmarks or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            by_name[name] = f"{name}|{coords}|front|0|"
    return [by_name[name] for name in ARRANGEMENT_POINT_NAMES if name in by_name]


def arrangement_point_map(records: Iterable[object] | None) -> dict[str, str]:
    """Return current-format arrangement coordinates indexed by point name.

    Args:
        records: Iterable of serialized five-field arrangement-point records.

    Returns:
        Mapping from known arrangement-point names to their coordinate strings.
    """
    result = {}
    for record in records or ():
        parts = str(record).split("|")
        if len(parts) != 5:
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
        if len(values) == 3:
            result[name] = coordinates
    return result
