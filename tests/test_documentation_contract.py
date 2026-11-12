# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the strict, repository-wide Python documentation contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tests.support.assertions import require as _require
from tools.check_documentation_contract import (
    check_source,
    object_annotation_violations,
    suppression_violations,
)

_EXPECTED_DIRECT_OBJECT_ANNOTATION_COUNT = 4
_EXPECTED_ALIASED_OBJECT_ANNOTATION_COUNT = 10


def test_complete_google_docstrings_pass() -> None:
    """Accept complete descriptions of inputs, results, and failure behavior."""
    source = '''"""Documentation checker fixture module."""

class Renderer:
    """Render untrusted text into a display-safe representation."""

    def render(self, text: str) -> str:
        """Escape plain text before inserting it into the display.

        Args:
            text: Untrusted plain text that must be escaped.

        Returns:
            Text escaped for safe insertion into the display.
        """
        return text

def parse_count(value: str) -> int:
    """Parse a non-negative item count from text.

    Args:
        value: Text containing a base-10 integer.

    Returns:
        The parsed item count, provided it is non-negative.

    Raises:
        ValueError: If the input is not a non-negative integer.
    """
    count = int(value)
    if count < 0:
        raise ValueError("count must be non-negative")
    return count
'''
    _require(
        condition=check_source(source) == [],
        message="complete Google-style docstrings should pass",
    )


def test_stub_modules_do_not_require_module_docstrings() -> None:
    """Accept declaration-only stubs without prose module docstrings."""
    source = "from PySide2 import QtCore as QtCore\n"
    errors = check_source(source, "typings/PySide/__init__.pyi")
    _require(
        condition=not any("missing module docstring" in error for error in errors),
        message=str(errors),
    )


def test_missing_symbol_docstrings_are_reported() -> None:
    """Reject undocumented classes and functions even when they are private."""
    source = '''"""Documentation checker fixture module."""

class Undocumented:
    pass

def _calculate(value: int, scale: float) -> float:
    return value * scale
'''
    errors = "\n".join(check_source(source))
    _require(condition="missing class docstring" in errors, message=errors)
    _require(condition="_calculate: missing docstring" in errors, message=errors)


def test_missing_parameter_result_and_exception_prose_is_reported() -> None:
    """Reject incomplete Args, Returns, and Raises sections."""
    source = '''"""Documentation checker fixture module."""

def parse(value: str, radix: int) -> int:
    """Parse numeric text.

    Args:
        value: Text that contains a number.
    """
    raise ValueError(value)
'''
    errors = "\n".join(check_source(source))
    _require(condition="missing parameter descriptions for radix" in errors, message=errors)
    _require(condition="missing descriptive Returns section" in errors, message=errors)
    _require(condition="missing descriptive Raises section" in errors, message=errors)


def test_placeholder_and_name_only_descriptions_are_rejected() -> None:
    """Reject placeholder prose even when all required docstring sections exist."""
    source = '''"""Documentation checker fixture module."""

def parse(value: str, radix: int) -> int:
    """Parse numeric text.

    Args:
        value: value
        radix: TODO

    Returns:
        TODO

    Raises:
        ValueError: FIXME
    """
    if not value:
        raise ValueError("value cannot be empty")
    return int(value, radix)
'''
    errors = "\n".join(check_source(source))
    _require(
        condition="non-descriptive parameter descriptions for radix, value" in errors,
        message=errors,
    )
    _require(
        condition="Returns description is too vague or contains a placeholder" in errors,
        message=errors,
    )
    _require(
        condition="non-descriptive Raises entries for ValueError" in errors,
        message=errors,
    )


def test_generic_object_annotations_are_rejected() -> None:
    """Reject object annotations in parameter, result, field, and alias positions."""
    source = '''"""Documentation checker fixture module."""

import builtins
from typing import TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def consume(value: object) -> dict[str, object]:
    """Encode one supplied value into a JSON-compatible mapping.

    Args:
        value: Value to encode into the resulting mapping.

    Returns:
        A mapping containing the supplied value.
    """
    return {"value": value}


def consume_builtin(value: builtins.object) -> "object":
    """Return the supplied value through a legacy binding annotation.

    Args:
        value: Value received from the dynamic binding.

    Returns:
        The unchanged value supplied by the caller.
    """
    return value
'''
    errors = list(object_annotation_violations(source, "sample.py"))
    violations = [
        error for error in errors if "generic object type annotations are prohibited" in error
    ]
    _require(
        condition=len(violations) == _EXPECTED_DIRECT_OBJECT_ANNOTATION_COUNT,
        message="\n".join(errors),
    )


def test_object_annotations_cannot_hide_behind_aliases_or_typing_helpers() -> None:
    """Reject aliased, nested, type-comment, and typing-constructor object escapes."""
    source = '''"""Typing escape-hatch fixture module."""

import builtins as native_builtins
from builtins import object as NativeObject
from typing import Annotated, Literal, NewType, TypeVar, cast

NativeObjectAlias = native_builtins.object
ChainedObjectAlias = NativeObjectAlias
Bounded = TypeVar("Bounded", bound=object)
LegacyEntity = NewType("LegacyEntity", object)


def imported_aliases(
    value: NativeObject,
    native: native_builtins.object,
    nested: list["object"],
) -> None:
    """Inspect values that use aliased native object types.

    Args:
        value: Value received through the imported built-in alias.
        native: Value received through the qualified builtins module.
        nested: Nested values whose forward reference must be inspected.
    """
    object.__setattr__(native, "value", value)


def assignment_alias(value: ChainedObjectAlias) -> None:
    """Reject ordinary assignments used as hidden type aliases.

    Args:
        value: Value declared through a chained alias of builtins.object.
    """



def metadata_is_not_a_type(
    value: Literal["object"],
    details: Annotated[str, object],
) -> str:
    """Keep literal values and Annotated metadata outside the type scan.

    Args:
        value: Literal string whose contents happen to name a built-in.
        details: String value with runtime metadata attached.

    Returns:
        The literal value unchanged.
    """
    return value


def legacy_comment(value):  # type: (object) -> object
    """Reject function type comments that widen values to every Python object.

    Args:
        value: Value passed through a legacy unannotated declaration.

    Returns:
        The unchanged input value.
    """
    return value


legacy_value = None  # type: object


def cast_target(value: str) -> str:
    """Reject cast targets that erase the caller's value type.

    Args:
        value: Text value whose declared type should remain precise.

    Returns:
        The same text after the cast expression.
    """
    return cast(object, value)
'''
    errors = list(object_annotation_violations(source, "sample.py"))
    violations = [
        error for error in errors if "generic object type annotations are prohibited" in error
    ]
    _require(
        condition=len(violations) == _EXPECTED_ALIASED_OBJECT_ANNOTATION_COUNT,
        message="\n".join(errors),
    )


def test_structural_protocols_and_json_value_unions_are_accepted() -> None:
    """Accept structural protocols and recursive JSON types as precise alternatives."""
    source = '''"""Documentation checker fixture module."""

from typing import Protocol, TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class SketchProtocol(Protocol):
    """Expose the native sketch geometry consumed by the adapter."""

    Geometry: tuple[tuple[float, float], ...]


def inspect_sketch(sketch: SketchProtocol) -> dict[str, JsonValue]:
    """Describe the supplied sketch using a JSON-compatible payload.

    Args:
        sketch: Sketch exposing its native two-dimensional geometry.

    Returns:
        A JSON-compatible mapping containing the geometry count.
    """
    return {"geometry_count": len(sketch.Geometry)}
'''
    errors = check_source(source, "sample.py")
    violations = [
        error for error in errors if "generic object type annotations are prohibited" in error
    ]
    _require(condition=not violations, message="\n".join(violations))


def test_ruff_suppression_comments_are_rejected() -> None:
    """Reject noqa comments without matching the token inside ordinary strings."""
    source = 'value = 1  # noqa: F841\ncaption = "noqa"\n'
    errors = suppression_violations(source, "sample.py")
    _require(condition=bool(errors) and not errors[1:], message=str(errors))
    _require(condition="sample.py:1" in errors[0], message=str(errors))


def test_syntax_errors_fail_closed() -> None:
    """Report invalid source rather than treating it as documented."""
    errors = check_source('"""Module documentation."""\ndef broken(:\n    pass\n')
    _require(
        condition=any("cannot parse Python source" in error for error in errors),
        message=str(errors),
    )


def test_ruff_uses_the_reviewed_rule_set_and_documented_exceptions() -> None:
    """Protect the reviewed production-oriented Ruff rules and narrow callback exceptions."""
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    config = tomllib.loads(project.read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    allowed_select = {
        "E",
        "F",
        "W",
        "I",
        "A",
        "ANN401",
        "B",
        "BLE",
        "C4",
        "DTZ",
        "FURB",
        "G",
        "LOG",
        "PERF",
        "PGH",
        "PIE",
        "RET",
        "RUF",
        "SIM",
        "UP",
        "YTT",
    }
    allowed_ignores = {
        "E402",
        "E501",
        "UP031",
        "RUF007",
        "RUF046",
        "RUF005",
        "RET501",
        "RET503",
        "RET504",
        "SIM105",
        "C401",
        "C408",
        "C416",
        "FURB162",
        "FURB192",
        "PIE810",
        "RUF043",
        "UP017",
        "UP040",
    }
    allowed_per_file = {
        "tests/**/*.py": ["S101"],
        "freecad_cloth/pattern/PatternCommands.py": ["BLE001"],
        "freecad_cloth/pattern/PatternTopologyRepairGui.py": ["BLE001"],
        "freecad_cloth/simulation/RealtimePreview.py": ["BLE001"],
        "freecad_cloth/simulation/SimulationQualityGui.py": ["BLE001"],
        "tests/freecad_*.py": ["BLE001"],
        "tests/support/pbd_contact_helpers.py": ["BLE001"],
        "tools/benchmark_workbenches.py": ["BLE001"],
        "tools/ci/python_validation.py": ["BLE001"],
    }
    _require(
        condition=set(lint["select"]) == allowed_select,
        message="Ruff rule selection differs from the reviewed project contract",
    )
    _require(
        condition=not lint.get("preview", False),
        message="Ruff preview rules must not be enabled as a blanket migration policy",
    )
    _require(
        condition=set(lint.get("ignore", [])) == allowed_ignores,
        message="Ruff global ignores differ from the reviewed project contract",
    )
    _require(
        condition=lint.get("per-file-ignores") == allowed_per_file,
        message="Ruff per-file exceptions differ from reviewed host/test boundaries",
    )


def _inventory_entries(path: Path) -> tuple[tuple[str, str], ...]:
    """Read listed repository paths and their goal/usefulness descriptions.

    Args:
        path: Repository-relative inventory document to inspect.

    Returns:
        Inventory paths and their complete description text in document order.
    """
    entries: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- `"):
            continue
        path_end = line.find("`", 3)
        separator = line.find(" — ", path_end)
        if path_end < 0 or separator < 0:
            continue
        entries.append((line[3:path_end], line[separator + 3 :]))
    return tuple(entries)


def test_tool_inventory_has_unique_descriptions_and_existing_paths() -> None:
    """Prevent duplicate tool entries and stale file references."""
    repository_root = Path(__file__).resolve().parents[1]
    inventory_path = repository_root / "docs" / "developers" / "TOOL_INVENTORY.md"
    entries = _inventory_entries(inventory_path)
    listed_paths = [path for path, _ in entries]
    descriptions = [description for _, description in entries]
    _require(
        condition=len(listed_paths) == len(set(listed_paths)),
        message=f"{inventory_path.name} contains duplicate paths",
    )
    _require(
        condition=len(descriptions) == len(set(descriptions)),
        message=f"{inventory_path.name} contains duplicate descriptions",
    )
    for relative_path, description in entries:
        _require(
            condition=(repository_root / relative_path).is_file(),
            message=f"{inventory_path.name} references missing file {relative_path}",
        )
        _require(
            condition="**Goal:**" in description and "**Why useful:**" in description,
            message=f"{inventory_path.name} has incomplete description for {relative_path}",
        )
