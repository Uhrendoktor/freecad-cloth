# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compatibility exports for the historical AvatarArrangement import path."""

from freecad_cloth.avatar.avatar_arrangement import (
    ARRANGEMENT_POINT_COORDINATE_COMPONENT_COUNT,
    ARRANGEMENT_POINT_NAMES,
    ARRANGEMENT_POINT_RECORD_FIELD_COUNT,
    arrangement_point_map,
    arrangement_points_from_landmarks,
)

__all__ = (
    "ARRANGEMENT_POINT_COORDINATE_COMPONENT_COUNT",
    "ARRANGEMENT_POINT_NAMES",
    "ARRANGEMENT_POINT_RECORD_FIELD_COUNT",
    "arrangement_point_map",
    "arrangement_points_from_landmarks",
)
