"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning. This provides the persistent fitting
anchor foundation needed by later CLO-like garment placement interactions.
"""

from __future__ import annotations

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
        Valid known landmarks serialized as name|x,y,z strings in stable name order.
    """
    by_name = {}
    for record in landmarks or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            by_name[name] = f"{name}|{coords}"
    return [by_name[name] for name in ARRANGEMENT_POINT_NAMES if name in by_name]


def arrangement_point_map(records: Iterable[object] | None) -> dict[str, str]:
    """Parse valid arrangement records into a coordinate lookup by point name.

    Args:
        records: Iterable of serialized name-and-coordinate records, if available.

    Returns:
        Mapping from known arrangement-point names to their coordinate strings.
    """
    result = {}
    for record in records or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            result[name] = coords
    return result
