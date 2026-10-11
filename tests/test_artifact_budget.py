"""Tests for the accumulated GitHub Actions artifact budget."""

import pytest

from tools.ci.check_artifact_budget import MAX_ARTIFACT_BYTES, accumulated_size


def test_accumulated_size_sums_all_artifacts():
    artifacts = [
        {"name": "first", "size_in_bytes": 2_000_000},
        {"name": "second", "size_in_bytes": 3_500_000},
        {"name": "third", "size_in_bytes": 4_000_000},
    ]
    assert accumulated_size(artifacts) == 9_500_000


def test_ten_mb_budget_boundary_is_allowed():
    artifacts = [{"name": "evidence", "size_in_bytes": MAX_ARTIFACT_BYTES}]
    assert accumulated_size(artifacts) == 10_000_000


def test_over_budget_is_detectable():
    artifacts = [
        {"name": "one", "size_in_bytes": 6_000_000},
        {"name": "two", "size_in_bytes": 4_000_001},
    ]
    assert accumulated_size(artifacts) > MAX_ARTIFACT_BYTES


def test_invalid_artifact_size_fails_closed():
    with pytest.raises(ValueError):
        accumulated_size([{"name": "broken", "size_in_bytes": None}])
