# Copyright (C) 2026 FreeCAD Cloth contributors
"""Recursive JSON value types shared by persistence and validation boundaries.

These aliases describe data decoded from or encoded to JSON. Native FreeCAD
objects and numerical geometry values use their own structural protocols.
"""

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]


def as_json_value(value: object) -> JsonValue:
    """Validate and normalize one value at a recursive JSON boundary.

    Args:
        value: Decoded or externally supplied value to validate as JSON data.

    Returns:
        The same scalar or a recursively normalized list or dictionary.

    Raises:
        TypeError: If the value contains non-JSON objects or non-string mapping keys.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [as_json_value(item) for item in value]
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                msg = "JSON object keys must be strings"
                raise TypeError(msg)
            result[key] = as_json_value(item)
        return result
    msg = f"unsupported JSON value type: {type(value).__name__}"
    raise TypeError(msg)
