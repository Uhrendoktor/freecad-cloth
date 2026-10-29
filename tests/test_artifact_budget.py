# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the accumulated GitHub Actions artifact budget."""

import http.client
from unittest.mock import Mock

import pytest

from tests.support.assertions import require as _require
from tools.ci.check_artifact_budget import (
    API_USER_AGENT,
    MAX_ARTIFACT_BYTES,
    accumulated_size,
    request_artifact_payload,
)

EXPECTED_ACCUMULATED_BYTES = 9_500_000
MAX_EXPECTED_ERROR_MESSAGE_LENGTH = 700


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

    request_headers = connection.request.call_args.kwargs["headers"]
    _require(
        condition=request_headers.get("User-Agent") == API_USER_AGENT,
        message="GitHub REST requests must send an explicit User-Agent header",
    )


def test_artifact_api_error_redacts_and_bounds_non_json_body_preview() -> None:
    """Expose useful upstream text without logging common bearer-token formats."""
    connection = Mock()
    response = Mock()
    response.status = http.client.FORBIDDEN
    response.reason = "Forbidden"
    response.read.return_value = (
        b"upstream gateway refused request; Bearer ghp_example_secret_token; "
        b"Authorization: token plain_secret_value"
    )
    response.getheader.return_value = None
    response.getheaders.return_value = [("Content-Type", "text/plain")]
    connection.getresponse.return_value = response

    with pytest.raises(RuntimeError) as error:
        request_artifact_payload(
            connection,
            "/repos/owner/repository/actions/runs/42/artifacts",
            {},
        )

    message = str(error.value)
    _require(
        condition="upstream gateway refused request" in message,
        message="the body preview should explain a non-JSON response",
    )
    _require(
        condition=(
            "ghp_example_secret_token" not in message
            and "plain_secret_value" not in message
            and "[REDACTED]" in message
        ),
        message="the body preview must redact credential-shaped strings",
    )
    _require(
        condition=len(message) < MAX_EXPECTED_ERROR_MESSAGE_LENGTH,
        message="the error report must remain bounded",
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
