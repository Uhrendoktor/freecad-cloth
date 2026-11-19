"""Find validated full-validation artifacts for the exact main publication source tree."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import TypeAlias, TypeGuard

_TRANSIENT_GITHUB_ERROR = re.compile(
    r"HTTP\s+50[234]|Server\s+Error|Bad\s+Gateway|"
    r"connection\s+reset\s+by\s+peer|TLS\s+handshake\s+timeout|timed\s+out",
    re.IGNORECASE,
)
_MAX_ATTEMPTS = 5
_MAX_RUN_PAGES = 4
_RUNS_PER_PAGE = 25
_VALIDATION_SOURCES = (
    ("merge-validation.yml", "merge_group", "Required pre-merge validation"),
    (
        "commit-validation.yml",
        "pull_request",
        "Full validation (explicit request) / Required validation gate",
    ),
    (
        "commit-validation.yml",
        "workflow_dispatch",
        "Full validation / Required validation gate",
    ),
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def run_github_cli(arguments: list[str]) -> str:
    """Run GitHub CLI with bounded retries for transient API and network failures.

    Args:
        arguments: Arguments passed to `gh`, excluding the executable name.

    Returns:
        Standard output from the successful GitHub CLI invocation.

    Raises:
        RuntimeError: If the command fails permanently or all transient retries are exhausted.
    """
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                ["gh", *arguments],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            error = "GitHub CLI request timed out after 30 seconds"
        else:
            if result.returncode == 0:
                return result.stdout
            error = result.stderr.strip() or f"gh exited with status {result.returncode}"
            if not _TRANSIENT_GITHUB_ERROR.search(error):
                raise RuntimeError(error)

        print(
            f"::warning::Transient GitHub API error on attempt {attempt}/{_MAX_ATTEMPTS}: {error}",
            file=sys.stderr,
        )
        if attempt < _MAX_ATTEMPTS:
            time.sleep(attempt)
    command = " ".join(arguments)
    raise RuntimeError(f"GitHub API request failed after {_MAX_ATTEMPTS} attempts: gh {command}")


def _load_json(payload: str) -> JsonValue:
    """Decode a JSON response into the repository's recursive JSON value type."""
    return json.loads(payload)


def _is_json_object(value: JsonValue) -> TypeGuard[dict[str, JsonValue]]:
    """Return whether a decoded JSON value is an object."""
    return isinstance(value, dict)


def _is_workflow_run(value: JsonValue) -> TypeGuard[dict[str, JsonValue]]:
    """Return whether a JSON object contains the required workflow-run fields."""
    return (
        _is_json_object(value)
        and isinstance(value.get("id"), int)
        and not isinstance(value.get("id"), bool)
        and isinstance(value.get("head_sha"), str)
    )


def _workflow_runs(payload: JsonValue) -> list[JsonValue]:
    """Extract workflow-run records from an Actions response, rejecting malformed payloads."""
    if not _is_json_object(payload):
        raise RuntimeError("GitHub Actions returned a non-object workflow-run response")
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise RuntimeError("GitHub Actions response did not contain a workflow_runs array")
    return runs


def _has_exact_successful_gate(payload: JsonValue, required_gate: str) -> bool:
    """Return whether exactly one job has the required name and successful conclusion."""
    if not _is_json_object(payload):
        return False
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return False
    matches = sum(
        1
        for job in jobs
        if _is_json_object(job)
        and job.get("name") == required_gate
        and job.get("conclusion") == "success"
    )
    return matches == 1


def _warn_candidate(run_id: int, error: Exception) -> None:
    """Report why one candidate run could not be used and continue discovery."""
    print(
        f"::warning::Skipping validation run {run_id} after artifact lookup error: {error}",
        file=sys.stderr,
    )


def find_validated_run(repository: str, source_sha: str) -> tuple[int, str]:
    """Find a successful validation run whose required gate and Git tree match.

    Merge-queue validation is preferred, followed by an explicit full pull-request run and
    then a manually dispatched full run (including a manual validation of main). Each source
    requires its own exact successful gate and the identical Git tree.

    Args:
        repository: GitHub repository in owner/name form.
        source_sha: Commit SHA being published on main.

    Returns:
        The validation run ID and the validated commit SHA.

    Raises:
        RuntimeError: If no successful validation run matches the source tree.
    """
    source_tree = run_github_cli(
        ["api", f"repos/{repository}/git/commits/{source_sha}", "--jq", ".tree.sha"]
    ).strip()
    if not source_tree:
        raise RuntimeError(f"Could not resolve Git tree for source commit {source_sha}")

    for workflow, event, required_gate in _VALIDATION_SOURCES:
        for page in range(1, _MAX_RUN_PAGES + 1):
            runs_endpoint = (
                f"repos/{repository}/actions/workflows/{workflow}/runs"
                f"?event={event}&status=success&per_page={_RUNS_PER_PAGE}&page={page}"
            )
            try:
                runs_payload = _load_json(run_github_cli(["api", runs_endpoint]))
            except json.JSONDecodeError as error:
                raise RuntimeError(f"GitHub returned invalid workflow-run JSON: {error}") from error
            run_records = _workflow_runs(runs_payload)

            for candidate in run_records:
                if not _is_workflow_run(candidate):
                    continue
                run_id_value = candidate["id"]
                head_sha_value = candidate["head_sha"]
                if not isinstance(run_id_value, int) or not isinstance(head_sha_value, str):
                    continue
                try:
                    jobs_payload = _load_json(
                        run_github_cli(
                            [
                                "api",
                                f"repos/{repository}/actions/runs/{run_id_value}/jobs?per_page=100",
                            ]
                        )
                    )
                    if not _has_exact_successful_gate(jobs_payload, required_gate):
                        continue
                    candidate_tree = run_github_cli(
                        [
                            "api",
                            f"repos/{repository}/git/commits/{head_sha_value}",
                            "--jq",
                            ".tree.sha",
                        ]
                    ).strip()
                except (RuntimeError, json.JSONDecodeError) as error:
                    _warn_candidate(run_id_value, error)
                    continue
                if candidate_tree and candidate_tree == source_tree:
                    return run_id_value, head_sha_value

            if len(run_records) < _RUNS_PER_PAGE:
                break

    raise RuntimeError(
        f"No successful full-validation run matched source tree {source_tree}; "
        "refusing to publish unvalidated assets."
    )


def main() -> int:
    """Resolve validated artifacts and write run outputs for GitHub Actions."""
    repository = os.environ.get("REPOSITORY", "")
    source_sha = os.environ.get("SOURCE_SHA", "")
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if not repository or not source_sha or not output_path:
        print("::error::REPOSITORY, SOURCE_SHA, and GITHUB_OUTPUT are required", file=sys.stderr)
        return 2
    try:
        run_id, validated_sha = find_validated_run(repository, source_sha)
    except RuntimeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"run_id={run_id}\n")
        output.write(f"validated_sha={validated_sha}\n")
    print(f"validation-artifacts-run={run_id} validated_sha={validated_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
