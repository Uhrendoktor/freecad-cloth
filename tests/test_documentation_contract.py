# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the strict, repository-wide Python documentation contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.check_documentation_contract import check_source, suppression_violations


def _require(condition: bool, message: str) -> None:
    """Raise a useful test failure when a documentation invariant is not met.

    Args:
        condition: Whether the requirement has been satisfied.
        message: Failure explanation displayed by the test runner.
    """
    if not condition:
        raise AssertionError(message)


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
    _require(check_source(source) == [], "complete Google-style docstrings should pass")


def test_missing_symbol_docstrings_are_reported() -> None:
    """Reject undocumented classes and functions even when they are private."""
    source = '''"""Documentation checker fixture module."""

class Undocumented:
    pass

def _calculate(value: int, scale: float) -> float:
    return value * scale
'''
    errors = "\n".join(check_source(source))
    _require("missing class docstring" in errors, errors)
    _require("_calculate: missing docstring" in errors, errors)


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
    _require("missing parameter descriptions for radix" in errors, errors)
    _require("missing descriptive Returns section" in errors, errors)
    _require("missing descriptive Raises section" in errors, errors)


def test_ruff_suppression_comments_are_rejected() -> None:
    """Reject noqa comments without matching the token inside ordinary strings."""
    source = 'value = 1  # noqa: F841\ncaption = "noqa"\n'
    errors = suppression_violations(source, "sample.py")
    _require(len(errors) == 1, str(errors))
    _require("sample.py:1" in errors[0], str(errors))


def test_syntax_errors_fail_closed() -> None:
    """Report invalid source rather than treating it as documented."""
    errors = check_source('"""Module documentation."""\ndef broken(:\n    pass\n')
    _require(any("cannot parse Python source" in error for error in errors), str(errors))


def test_ruff_selects_all_rules_with_only_formatter_conflicts_ignored() -> None:
    """Protect the full lint policy from silent rule or exemption removal."""
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    config = tomllib.loads(project.read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    allowed_ignores = {
        "COM812",
        "COM819",
        "D203",
        "D206",
        "D300",
        "E111",
        "E114",
        "E117",
        "Q000",
        "Q001",
        "Q002",
        "Q003",
        "Q004",
        "W191",
    }
    _require(lint["select"] == ["ALL"], f"Ruff must select ALL rules: {lint['select']!r}")
    _require(lint["preview"] is True, "Ruff preview rules must remain enabled")
    _require(
        set(lint.get("ignore", [])) == allowed_ignores,
        "Only formatter-conflicting rules may be ignored",
    )
    _require("per-file-ignores" not in lint, "Per-file lint exemptions are prohibited")
