"""Tests for the accumulated GitHub Actions artifact budget."""

import pytest

from tools.ci.check_artifact_budget import (
    MAX_ARTIFACT_BYTES,
    accumulated_size,
    latest_artifacts_by_name,
)


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


def test_retry_uploads_count_only_the_latest_artifact_with_each_name() -> None:
    artifacts = [
        {
            "id": 10,
            "name": "realtime-preview",
            "size_in_bytes": 3_500,
            "created_at": "2026-11-14T12:24:05Z",
        },
        {
            "id": 20,
            "name": "tunic-audit",
            "size_in_bytes": 2_239_912,
            "created_at": "2026-11-14T12:26:16Z",
        },
        {
            "id": 30,
            "name": "realtime-preview",
            "size_in_bytes": 2_995,
            "created_at": "2026-11-14T12:29:44Z",
        },
        {
            "id": 40,
            "name": "tunic-audit",
            "size_in_bytes": 2_244_914,
            "created_at": "2026-11-14T12:31:47Z",
        },
    ]

    latest = latest_artifacts_by_name(artifacts)

    assert [item["name"] for item in latest] == ["realtime-preview", "tunic-audit"]
    assert accumulated_size(latest) == 2_247_909


def test_duplicate_artifact_name_requires_creation_metadata() -> None:
    artifacts = [
        {"id": 1, "name": "evidence", "size_in_bytes": 100, "created_at": "2026-11-14T12:00:00Z"},
        {"id": 2, "name": "evidence", "size_in_bytes": 200},
    ]
    with pytest.raises(ValueError, match="lacks creation time or artifact ID"):
        latest_artifacts_by_name(artifacts)


def test_invalid_artifact_size_fails_closed():
    with pytest.raises(ValueError):
        accumulated_size([{"name": "broken", "size_in_bytes": None}])
