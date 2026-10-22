# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared assertion helpers for strict, descriptive regression tests."""


def require(*, condition: bool, message: str = "Required condition was false.") -> None:
    """Raise an explicit assertion error when a required predicate is false.

    Args:
        condition: Boolean predicate that must hold for the test to pass.
        message: Optional failure detail; the default is used for simple predicates.

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


def require_not_none[T](value: T | None, *, message: str = "Expected a non-None value.") -> T:
    """Return a value only when it is not None.

    Args:
        value: Optional result that must be present for the next operation.
        message: Failure detail when the value is absent; defaults to a concise explanation.

    Returns:
        The original value narrowed to its non-None type.

    Raises:
        AssertionError: If the required value is None.
    """
    if value is None:
        raise AssertionError(message)
    return value
