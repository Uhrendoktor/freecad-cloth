# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared assertion helpers for strict, descriptive regression tests."""

_DEFAULT_REQUIRE_MESSAGE = (
    "Required predicate evaluated to false. See the originating test call in the traceback; "
    "pass `message=` to name the expected invariant."
)


def require(*, condition: bool, message: str | None = None) -> None:
    """Raise an explicit assertion error when a required predicate is false.

    Args:
        condition: Boolean predicate that must hold for the test to pass.
        message: Optional failure detail; the default points readers to the test call site.

    Raises:
        AssertionError: If the required condition is false.
    """
    __tracebackhide__ = True
    if not condition:
        raise AssertionError(_DEFAULT_REQUIRE_MESSAGE if message is None else message)


def require_contains(*, source: str, fragment: str, message: str) -> None:
    """Require a source string to contain a contract fragment.

    Args:
        source: Text inspected by the contract test.
        fragment: Required literal fragment within the source.
        message: Descriptive failure explanation when the fragment is absent.

    """
    __tracebackhide__ = True
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
    __tracebackhide__ = True
    if value is None:
        raise AssertionError(message)
    return value
