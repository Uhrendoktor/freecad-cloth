# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for explicit failure diagnostics in shared test assertions."""

import pytest

from tests.support.assertions import require


def test_require_preserves_a_descriptive_caller_message() -> None:
    """Expose a caller-supplied invariant description in the assertion failure."""
    message = "The simulation workflow must include the contact audit."

    with pytest.raises(AssertionError, match=message):
        require(condition=False, message=message)
