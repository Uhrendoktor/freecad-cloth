# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the strict, repository-wide Python documentation contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.check_documentation_contract import check_source, suppression_violations


def _require(*, condition: bool, message: str) -> None:
    """Raise a test failure when a documentation invariant is not met.

    Args:
        condition: Whether the requirement has been satisfied.
        message: Failure explanation displayed by the test runner.

    Raises:
        AssertionError: When the requirement is not satisfied.
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
    _require(
        condition="per-file-ignores" not in lint,
        message="Per-file lint exemptions are prohibited",
    )
