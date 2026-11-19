"""Tests for exact-tree validated artifact discovery and transient API retries."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from tools.ci import find_validated_visual_run as lookup


def test_run_github_cli_retries_transient_api_failure() -> None:
    """A transient HTTP 502 is retried and the successful output is returned."""
    results = [
        subprocess.CompletedProcess(["gh", "api"], 1, "", "gh: Server Error (HTTP 502)"),
        subprocess.CompletedProcess(["gh", "api"], 0, "ok\n", ""),
    ]
    with (
        patch.object(lookup.subprocess, "run", side_effect=results),
        patch.object(lookup.time, "sleep") as sleep,
    ):
        assert lookup.run_github_cli(["api", "repos/example/repo"]) == "ok\n"
    sleep.assert_called_once_with(1)


def test_find_validated_run_requires_successful_gate_and_exact_tree() -> None:
    """The publisher selects a validation run only when the required gate and tree match."""
    responses = [
        "source-tree\n",
        "[]",
        '[{"databaseId": 1234, "headSha": "validated-sha"}]',
        (
            '{"jobs": [{"name": "Full validation (explicit request) / Required validation gate", '
            '"conclusion": "success"}]}'
        ),
        '{"tree": {"sha": "source-tree"}}\n',
    ]
    with patch.object(lookup, "run_github_cli", side_effect=responses):
        assert lookup.find_validated_run("example/repo", "main-sha") == (
            1234,
            "validated-sha",
        )


def test_find_validated_run_rejects_a_different_git_tree() -> None:
    """A successful gate on a different tree cannot authorize publication."""
    responses = [
        "source-tree\n",
        "[]",
        '[{"databaseId": 1234, "headSha": "validated-sha"}]',
        (
            '{"jobs": [{"name": "Full validation (explicit request) / Required validation gate", '
            '"conclusion": "success"}]}'
        ),
        '{"tree": {"sha": "different-tree"}}\n',
    ]
    with patch.object(lookup, "run_github_cli", side_effect=responses):
        with pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"):
            lookup.find_validated_run("example/repo", "main-sha")


def test_find_validated_run_rejects_a_missing_required_gate() -> None:
    """A matching tree without the exact successful required-gate job is insufficient."""
    responses = [
        "source-tree\n",
        "[]",
        '[{"databaseId": 1234, "headSha": "validated-sha"}]',
        '{"jobs": [{"name": "Other check", "conclusion": "success"}]}',
    ]
    with patch.object(lookup, "run_github_cli", side_effect=responses):
        with pytest.raises(RuntimeError, match="refusing to publish unvalidated assets"):
            lookup.find_validated_run("example/repo", "main-sha")
