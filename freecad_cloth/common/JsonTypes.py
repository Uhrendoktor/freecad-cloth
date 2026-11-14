# Copyright (C) 2026 FreeCAD Cloth contributors
"""Recursive JSON value types shared by persistence and validation boundaries.

These aliases describe data decoded from or encoded to JSON. Native FreeCAD
objects and numerical geometry values use their own structural protocols.
"""

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]
