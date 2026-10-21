# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the accumulated GitHub Actions artifact budget."""

import pytest

from tools.ci.check_artifact_budget import MAX_ARTIFACT_BYTES, accumulated_size


def _require(*, condition: bool, message: str) -> None:
    """Raise a clear test failure when an artifact-budget expectation is false.

    Args:
        condition: Boolean result of the expectation being checked.
        message: Actionable failure message describing the unmet expectation.

    Raises:
        AssertionError: If the expected test condition is not satisfied.
    """
    if not condition:
        raise AssertionError(message)


def test_accumulated_size_sums_all_artifacts() -> None:
    """Sum byte counts across every artifact in a workflow run."""
    artifacts = [
        {"name": "first", "size_in_bytes": 2_000_000},
        {"name": "second", "size_in_bytes": 3_500_000},
        {"name": "third", "size_in_bytes": 4_000_000},
    ]
    _require(
        condition=accumulated_size(artifacts) == 9_500_000,
        message="artifact sizes should be summed across all records",
    )


def test_ten_mb_budget_boundary_is_allowed() -> None:
    """Allow an accumulated artifact size exactly at the configured limit."""
    artifacts = [{"name": "evidence", "size_in_bytes": MAX_ARTIFACT_BYTES}]
    _require(
        condition=accumulated_size(artifacts) == MAX_ARTIFACT_BYTES,
        message="the exact artifact-budget boundary should be accepted",
    )


def test_over_budget_is_detectable() -> None:
    """Detect artifact collections whose combined size exceeds the limit."""
    artifacts = [
        {"name": "one", "size_in_bytes": 6_000_000},
        {"name": "two", "size_in_bytes": 4_000_001},
    ]
    _require(
        condition=accumulated_size(artifacts) > MAX_ARTIFACT_BYTES,
        message="combined artifact sizes above the limit should be detectable",
    )


def test_invalid_artifact_size_fails_closed() -> None:
    """Reject malformed artifact records instead of undercounting their size."""
    with pytest.raises(ValueError, match="invalid size_in_bytes"):
        accumulated_size([{"name": "broken", "size_in_bytes": None}])
