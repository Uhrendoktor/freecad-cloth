# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the strict, repository-wide Python documentation contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tests.support.assertions import require as _require

from tools.check_documentation_contract import check_source, suppression_violations


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


def test_ruff_selects_all_rules_with_only_formatter_conflicts_ignored() -> None:
    """Protect the full lint policy from silent rule or exemption removal."""
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    config = tomllib.loads(project.read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    allowed_ignores = {
        "missing-trailing-comma",
        "prohibited-trailing-comma",
        "incorrect-blank-line-before-class",
        "docstring-tab-indentation",
        "triple-single-quotes",
        "indentation-with-invalid-multiple",
        "indentation-with-invalid-multiple-comment",
        "over-indented",
        "bad-quotes-inline-string",
        "bad-quotes-multiline-string",
        "bad-quotes-docstring",
        "avoidable-escaped-quote",
        "unnecessary-escaped-quote",
        "tab-indentation",
    }
    _require(
        condition=lint["select"] == ["ALL"],
        message=f"Ruff must select ALL rules: {lint['select']!r}",
    )
    _require(condition=lint["preview"] is True, message="Ruff preview rules must remain enabled")
    _require(
        condition=set(lint.get("ignore", [])) == allowed_ignores,
        message="Only formatter-conflicting rules may be ignored",
    )
    expected_per_file_ignores = {
        "freecad_cloth/bootstrap.py": ["PLC0415"],
        "freecad_cloth/avatar/AvatarCommands.py": ["PLC0415"],
        "freecad_cloth/avatar/AvatarGui.py": ["PLC0415"],
        "freecad_cloth/avatar/AvatarPoseGui.py": ["PLC0415"],
        "freecad_cloth/simulation/FittingHandoff.py": ["PLC0415"],
        "freecad_cloth/simulation/DrapeCommands.py": ["PLC0415"],
        "freecad_cloth/simulation/SimulationCommands.py": ["PLC0415"],
        "freecad_cloth/simulation/SimulationQualityGui.py": ["PLC0415"],
        "freecad_cloth/pattern/PatternMesh.py": ["PLC0415"],
        "tests/freecad_*.py": ["PLC0415"],
        "tests/support/pbd_contact_helpers.py": ["PLC0415"],
        "tests/test_avatar_fitting.py": ["PLC0415"],
    }
    _require(
        condition=lint.get("per-file-ignores", {}) == expected_per_file_ignores,
        message="Only the documented local-import boundaries may ignore PLC0415",
    )


def _inventory_entries(path: Path) -> tuple[tuple[str, str], ...]:
    """Read listed repository paths and their goal/usefulness descriptions.

    Args:
        path: Repository-relative inventory document to inspect.

    Returns:
        Inventory paths and their complete description text in document order.
    """
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- `"):
            continue
        path_end = line.find("`", 3)
        separator = line.find(" — ", path_end)
        if path_end < 0 or separator < 0:
            continue
        entries.append((line[3:path_end], line[separator + 3 :]))
    return tuple(entries)


def test_tool_and_test_inventories_have_unique_descriptions_and_existing_paths() -> None:
    """Prevent duplicate inventory descriptions and stale file references."""
    repository_root = Path(__file__).resolve().parents[1]
    inventory_paths = (
        repository_root / "docs" / "developers" / "TOOL_INVENTORY.md",
        repository_root / "docs" / "developers" / "TEST_INVENTORY.md",
    )
    for inventory_path in inventory_paths:
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
