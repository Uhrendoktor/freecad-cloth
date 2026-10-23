# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for default failure diagnostics in shared test assertions."""

import pytest

from tests.support.assertions import require

_DEFAULT_MESSAGE_FRAGMENT = "originating test call in the traceback"


def test_require_default_message_identifies_the_failure_location() -> None:
    """Direct omitted-message failures to pytest's report of the call site."""
    with pytest.raises(AssertionError, match=_DEFAULT_MESSAGE_FRAGMENT):
        require(condition=False)


def test_require_preserves_a_descriptive_caller_message() -> None:
    """Keep a caller-supplied invariant description unchanged."""
    message = "The simulation workflow must include the contact audit."

    with pytest.raises(AssertionError, match=message):
        require(condition=False, message=message)
