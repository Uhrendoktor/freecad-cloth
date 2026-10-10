"""Shared, domain-neutral parser for persisted named 3D arrangement anchors.

Accepted forms are:
    name|x,y,z
    name|x,y,z|wrap|rotation|symmetry

This module has no FreeCAD, avatar, or simulation dependency so both domains can
interpret the same document record without importing each other.
"""
from math import isfinite


def parse_arrangement_point_record(value: str) -> tuple[str, tuple[float, float, float], str, float, str]:
    """Parse a serialized named 3D point into normalized primitive values."""
    parts = str(value).split("|")
    if len(parts) == 2:
        name, position = parts
        wrap, rotation, symmetry = "front", "0", ""
    elif len(parts) == 5:
        name, position, wrap, rotation, symmetry = parts
    else:
        raise ValueError(
            "arrangement point requires name|x,y,z or name|x,y,z|wrap|rotation|symmetry"
        )
    name = name.strip()
    if not name:
        raise ValueError("arrangement point name must not be empty")
    try:
        coords = tuple(float(component) for component in position.split(","))
        rotation_value = float(rotation)
    except ValueError as exc:
        raise ValueError("arrangement point coordinates and rotation must be numeric") from exc
    if len(coords) != 3:
        raise ValueError("arrangement point position requires x, y, and offset")
    if any(not isfinite(component) for component in coords) or not isfinite(rotation_value):
        raise ValueError("arrangement point coordinates and rotation must be finite")
    return name, coords, str(wrap), rotation_value, str(symmetry)
