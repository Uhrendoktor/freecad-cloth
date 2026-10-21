# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared assertion helpers for strict, descriptive regression tests."""

from typing import TypeVar

_T = TypeVar("_T")


def require(*, condition: bool, message: str) -> None:
    """Raise an explicit assertion error when a required predicate is false.

    Args:
        condition: Boolean predicate that must hold for the test to pass.
        message: Descriptive failure explanation for a violated predicate.

    Raises:
        AssertionError: If the required condition is false.
    """
    if not condition:
        raise AssertionError(message)


def require_contains(*, source: str, fragment: str, message: str) -> None:
    """Require a source string to contain a contract fragment.

    Args:
        source: Text inspected by the contract test.
        fragment: Required literal fragment within the source.
        message: Descriptive failure explanation when the fragment is absent.

    """
    require(condition=fragment in source, message=message)


def require_not_none(value: _T | None, *, message: str) -> _T:
    """Return a value only when it is not None.

    Args:
        value: Optional result that must be present for the next operation.
        message: Human-readable failure reason when the value is absent.

    Returns:
        The original value narrowed to its non-None type.

    Raises:
        AssertionError: If the required value is None.
    """
    if value is None:
        raise AssertionError(message)
    return value
