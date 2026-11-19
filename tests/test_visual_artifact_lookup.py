"""Tests for exact-tree validated artifact discovery and transient API retries."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from tools.ci import find_validated_visual_run as lookup

_REQUIRED_GATE = "Full validation (explicit request) / Required validation gate"
_DISPATCH_GATE = "Full validation / Required validation gate"


@pytest.mark.parametrize(
    ("failure", "expected_delay"),
    [
        ("gh: Server Error (HTTP 502)", 1),
        ("gh: Server Error (HTTP 503)", 1),
        ("gh: Server Error (HTTP 504)", 1),
        ("TLS handshake timeout", 1),
    ],
)
def test_run_github_cli_retries_transient_api_failures(
    failure: str,
    expected_delay: int,
) -> None:
    """Transient HTTP and connection failures are retried before returning success."""
    results = [
        subprocess.CompletedProcess(["gh", "api"], 1, "", failure),
        subprocess.CompletedProcess(["gh", "api"], 0, "ok\n", ""),
    ]
    with (
        patch.object(lookup.subprocess, "run", side_effect=results),
        patch.object(lookup.time, "sleep") as sleep,
    ):
        assert lookup.run_github_cli(["api", "repos/example/repo"]) == "ok\n"
    sleep.assert_called_once_with(expected_delay)


def test_run_github_cli_does_not_retry_permanent_errors() -> None:
    """Permanent permission and query errors fail immediately."""
    result = subprocess.CompletedProcess(["gh", "api"], 1, "", "HTTP 403: Resource not accessible")
    with (
        patch.object(lookup.subprocess, "run", return_value=result) as run,
        patch.object(lookup.time, "sleep") as sleep,
        pytest.raises(RuntimeError, match="HTTP 403"),
    ):
        lookup.run_github_cli(["api", "repos/example/repo"])
    run.assert_called_once()
    sleep.assert_not_called()


def test_find_validated_run_requires_exact_gate_and_identical_git_tree() -> None:
    """A matching validation run must pass the exact required gate on the same Git tree."""
    responses = [
        "source-tree\n",
        json.dumps({"workflow_runs": []}),
        json.dumps({"workflow_runs": [{"id": 1234, "head_sha": "validated-sha"}]}),
        json.dumps({"jobs": [{"name": _REQUIRED_GATE, "conclusion": "success"}]}),
        "source-tree\n",
    ]
    with patch.object(lookup, "run_github_cli", side_effect=responses):
        assert lookup.find_validated_run("example/repo", "main-sha") == (1234, "validated-sha")


def test_find_validated_run_accepts_a_successful_main_workflow_dispatch() -> None:
    """A manually dispatched full validation can authorize the identical main Git tree."""
    calls: list[list[str]] = []

    def response(arguments: list[str]) -> str:
        calls.append(arguments)
        if "git/commits/main-sha" in arguments[1]:
            return "source-tree\n"
        if "event=merge_group" in arguments[1] or "event=pull_request" in arguments[1]:
            return json.dumps({"workflow_runs": []})
        if "event=workflow_dispatch" in arguments[1]:
            return json.dumps({"workflow_runs": [{"id": 2345, "head_sha": "main-validation-sha"}]})
        if "actions/runs/2345/jobs" in arguments[1]:
            return json.dumps({"jobs": [{"name": _DISPATCH_GATE, "conclusion": "success"}]})
        if "git/commits/main-validation-sha" in arguments[1]:
            return "source-tree\n"
        raise AssertionError(f"Unexpected GitHub CLI request: {arguments}")

    with patch.object(lookup, "run_github_cli", side_effect=response):
        assert lookup.find_validated_run("example/repo", "main-sha") == (
            2345,
            "main-validation-sha",
        )
    dispatch_requests = [
        arguments[1]
        for arguments in calls
        if len(arguments) > 1 and "event=workflow_dispatch" in arguments[1]
    ]
    assert len(dispatch_requests) == 1
    assert "commit-validation.yml" in dispatch_requests[0]


def test_find_validated_run_rejects_the_fast_feedback_gate() -> None:
    """Fast-feedback checks must never authorize full-validation documentation publication."""
    responses = [
        "source-tree\\n",
        json.dumps({"workflow_runs": []}),
        json.dumps({"workflow_runs": [{"id": 1235, "head_sha": "fast-feedback-sha"}]}),
        json.dumps(
            {
                "jobs": [
                    {
                        "name": "Explicit full validation / Required validation gate",
                        "conclusion": "success",
                    }
                ]
            }
        ),
        json.dumps({"workflow_runs": []}),
    ]
    with (
        patch.object(lookup, "run_github_cli", side_effect=responses),
        pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"),
    ):
        lookup.find_validated_run("example/repo", "main-sha")


def test_find_validated_run_discovers_runs_on_later_pages() -> None:
    """The bounded pagination reaches later pages instead of checking only the first page."""
    first_page = [{"unusable": index} for index in range(lookup._RUNS_PER_PAGE)]
    calls: list[list[str]] = []

    def response(arguments: list[str]) -> str:
        calls.append(arguments)
        if arguments[0] == "api" and "git/commits/source-sha" in arguments[1]:
            return "source-tree\n"
        if "merge-validation.yml" in arguments[1] and "page=2" in arguments[1]:
            return json.dumps({"workflow_runs": [{"id": 88, "head_sha": "later-sha"}]})
        if "merge-validation.yml" in arguments[1]:
            return json.dumps({"workflow_runs": first_page})
        if "actions/runs/88/jobs" in arguments[1]:
            return json.dumps(
                {"jobs": [{"name": "Required pre-merge validation", "conclusion": "success"}]}
            )
        if "git/commits/later-sha" in arguments[1]:
            return "source-tree\n"
        raise AssertionError(f"Unexpected GitHub CLI request: {arguments}")

    with patch.object(lookup, "run_github_cli", side_effect=response):
        # First page has exactly 25 entries, so the next page must be queried.
        assert lookup.find_validated_run("example/repo", "source-sha") == (88, "later-sha")
    assert any("page=2" in arguments[1] for arguments in calls if len(arguments) > 1)


def test_find_validated_run_rejects_a_different_git_tree() -> None:
    """A successful required gate on another tree cannot authorize publication."""
    responses = [
        "source-tree\n",
        json.dumps({"workflow_runs": []}),
        json.dumps({"workflow_runs": [{"id": 1234, "head_sha": "validated-sha"}]}),
        json.dumps({"jobs": [{"name": _REQUIRED_GATE, "conclusion": "success"}]}),
        "different-tree\n",
        json.dumps({"workflow_runs": []}),
    ]
    with (
        patch.object(lookup, "run_github_cli", side_effect=responses),
        pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"),
    ):
        lookup.find_validated_run("example/repo", "main-sha")


def test_find_validated_run_rejects_a_missing_required_gate() -> None:
    """A matching tree without the required successful gate is insufficient."""
    responses = [
        "source-tree\n",
        json.dumps({"workflow_runs": []}),
        json.dumps({"workflow_runs": [{"id": 1234, "head_sha": "validated-sha"}]}),
        json.dumps({"jobs": [{"name": "Other check", "conclusion": "success"}]}),
        json.dumps({"workflow_runs": []}),
    ]
    with (
        patch.object(lookup, "run_github_cli", side_effect=responses),
        pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"),
    ):
        lookup.find_validated_run("example/repo", "main-sha")


def test_find_validated_run_rejects_duplicate_successful_required_gates() -> None:
    """Ambiguous duplicate required-gate jobs are not accepted as validation evidence."""
    responses = [
        "source-tree\n",
        json.dumps({"workflow_runs": []}),
        json.dumps({"workflow_runs": [{"id": 1234, "head_sha": "validated-sha"}]}),
        json.dumps(
            {
                "jobs": [
                    {"name": _REQUIRED_GATE, "conclusion": "success"},
                    {"name": _REQUIRED_GATE, "conclusion": "success"},
                ]
            }
        ),
        json.dumps({"workflow_runs": []}),
    ]
    with (
        patch.object(lookup, "run_github_cli", side_effect=responses),
        pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"),
    ):
        lookup.find_validated_run("example/repo", "main-sha")
