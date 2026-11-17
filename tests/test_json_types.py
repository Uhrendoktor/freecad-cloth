# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for recursive JSON value validation at external data boundaries."""

from typing import cast

import pytest

from freecad_cloth.common.JsonTypes import JsonValue, as_json_value


def test_as_json_value_preserves_nested_json_data() -> None:
    """Preserve valid nested JSON scalars, lists, and objects."""
    source: JsonValue = {
        "items": [True, 4, 2.5, "text", None, {"enabled": False}],
    }

    result: JsonValue = as_json_value(source)

    assert result == source


def test_as_json_value_rejects_python_only_container_values() -> None:
    """Reject tuples rather than silently widening the JSON data contract."""
    with pytest.raises(TypeError, match="unsupported JSON value type"):
        as_json_value(cast("JsonValue", {"items": (1, 2)}))


def test_as_json_value_rejects_non_string_object_keys() -> None:
    """Reject mappings whose keys cannot be represented as JSON object names."""
    with pytest.raises(TypeError, match="keys must be strings"):
        as_json_value(cast("JsonValue", {1: "not a JSON object key"}))
