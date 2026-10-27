# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the accumulated GitHub Actions artifact budget."""

import http.client
from unittest.mock import Mock

import pytest

from tests.support.assertions import require as _require
from tools.ci.check_artifact_budget import (
    accumulated_size,
    MAX_ARTIFACT_BYTES,
    request_artifact_payload,
)

EXPECTED_ACCUMULATED_BYTES = 9_500_000


def test_accumulated_size_sums_all_artifacts() -> None:
    """Sum byte counts across every artifact in a workflow run."""
    artifacts = [
        {"name": "first", "size_in_bytes": 2_000_000},
        {"name": "second", "size_in_bytes": 3_500_000},
        {"name": "third", "size_in_bytes": 4_000_000},
    ]
    _require(
        condition=accumulated_size(artifacts) == EXPECTED_ACCUMULATED_BYTES,
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


def test_artifact_api_permission_error_includes_github_message() -> None:
    """Expose GitHub's safe error message so permission failures are diagnosable."""
    connection = Mock()
    response = Mock()
    response.status = http.client.FORBIDDEN
    response.reason = "Forbidden"
    response.read.return_value = b'{"message":"Resource not accessible by integration"}'
    response.getheader.side_effect = {
        "X-GitHub-Request-Id": "GH-REQUEST-123",
        "X-Accepted-GitHub-Permissions": "actions=read",
    }.get
    response.getheaders.return_value = [
        ("X-GitHub-Request-Id", "GH-REQUEST-123"),
        ("X-Accepted-GitHub-Permissions", "actions=read"),
        ("Content-Type", "application/json"),
    ]
    connection.getresponse.return_value = response

    with pytest.raises(
        RuntimeError,
        match=r"GH-REQUEST-123.*actions=read.*Resource not accessible by integration",
    ):
        request_artifact_payload(
            connection,
            "/repos/owner/repository/actions/runs/42/artifacts",
            {},
        )


def test_artifact_api_error_reports_empty_response_metadata() -> None:
    """Expose empty response metadata when GitHub returns a bodyless HTTP failure."""
    connection = Mock()
    response = Mock()
    response.status = http.client.FORBIDDEN
    response.reason = "Forbidden"
    response.read.return_value = b""
    response.getheader.return_value = None
    response.getheaders.return_value = []
    connection.getresponse.return_value = response

    with pytest.raises(
        RuntimeError,
        match=r"response_header_names=\[\].*error_body_bytes_read=0",
    ):
        request_artifact_payload(
            connection,
            "/repos/owner/repository/actions/runs/42/artifacts",
            {},
        )
