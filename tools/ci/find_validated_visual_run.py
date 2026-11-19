"""Find full-validation artifacts whose Git tree matches the main publication source."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

_TRANSIENT_GITHUB_ERROR = re.compile(
    r"HTTP\s+50[234]|Server\s+Error|Bad\s+Gateway|"
    r"connection\s+reset\s+by\s+peer|TLS\s+handshake\s+timeout"
)
_MAX_ATTEMPTS = 5
_VALIDATION_SOURCES = (
    ("merge-validation.yml", "merge_group", "Required pre-merge validation"),
    (
        "commit-validation.yml",
        "pull_request",
        "Full validation (explicit request) / Required validation gate",
    ),
)


def run_github_cli(arguments: list[str]) -> str:
    """Run GitHub CLI with bounded retries for transient API/network errors.

    Args:
        arguments: Arguments passed to the `gh` executable, excluding the executable name.

    Returns:
        Standard output from the successful GitHub CLI invocation.

    Raises:
        RuntimeError: If the command fails permanently or all transient retries are exhausted.
    """
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result = subprocess.run(
            ["gh", *arguments],
            capture_output=True,
            check=False,
            text=True,
        )
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


def find_validated_run(repository: str, source_sha: str) -> tuple[int, str]:
    """Find a successful full-validation run whose required gate and Git tree match.

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
        runs_payload = json.loads(
            run_github_cli(
                [
                    "run",
                    "list",
                    "--repo",
                    repository,
                    "--workflow",
                    workflow,
                    "--event",
                    event,
                    "--status",
                    "success",
                    "--limit",
                    "100",
                    "--json",
                    "databaseId,headSha",
                ]
            )
        )
        if not isinstance(runs_payload, list):
            continue
        for candidate in runs_payload:
            if not isinstance(candidate, dict):
                continue
            run_id = candidate.get("databaseId")
            head_sha = candidate.get("headSha")
            if not isinstance(run_id, int) or not isinstance(head_sha, str):
                continue
            try:
                jobs_payload = json.loads(
                    run_github_cli(
                        ["api", f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"]
                    )
                )
                if not isinstance(jobs_payload, dict):
                    continue
                jobs_value = jobs_payload.get("jobs", [])
                if not isinstance(jobs_value, list) or not any(
                    isinstance(job, dict)
                    and job.get("name") == required_gate
                    and job.get("conclusion") == "success"
                    for job in jobs_value
                ):
                    continue
                candidate_tree = run_github_cli(
                    [
                        "api",
                        f"repos/{repository}/git/commits/{head_sha}",
                        "--jq",
                        ".tree.sha",
                    ]
                ).strip()
            except (RuntimeError, json.JSONDecodeError) as error:
                print(
                    f"::warning::Skipping validation run {run_id} after artifact lookup error: {error}",
                    file=sys.stderr,
                )
                continue
            if candidate_tree and candidate_tree == source_tree:
                return run_id, head_sha

    raise RuntimeError(
        f"No successful full-validation run matched source tree {source_tree}; "
        "refusing to publish unvalidated assets."
    )


def main() -> int:
    """Resolve the validated run and write outputs for the GitHub Actions workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("REPOSITORY", ""))
    parser.add_argument("--source-sha", default=os.environ.get("SOURCE_SHA", ""))
    parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args()
    if not args.repository or not args.source_sha or not args.output:
        parser.error("repository, source SHA, and GITHUB_OUTPUT are required")
    try:
        run_id, validated_sha = find_validated_run(args.repository, args.source_sha)
    except RuntimeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    with open(args.output, "a", encoding="utf-8") as output:
        output.write(f"run_id={run_id}\n")
        output.write(f"validated_sha={validated_sha}\n")
    print(f"validation-artifacts-run={run_id} validated_sha={validated_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
