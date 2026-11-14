"""Prefer the self-hosted runner and dispatch one hosted fallback after 45 seconds."""

from __future__ import annotations

import json
import os
import subprocess
import time


def gh(*args: str) -> str:
    """Run a GitHub CLI command and return standard output."""
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=10
    ).stdout


def find_runner_readiness_job(
    jobs: list[dict[str, object]],
) -> dict[str, object] | None:
    """Find the readiness sentinel with or without its reusable-workflow prefix."""
    suffix = " / Selected runner readiness"
    for job in jobs:
        name = job.get("name")
        if isinstance(name, str) and (name == "Selected runner readiness" or name.endswith(suffix)):
            return job
    return None


def main() -> int:
    """Wait for local-runner readiness and dispatch the hosted fallback when needed."""
    repo = os.environ["REPO"]
    run_id = os.environ["GITHUB_RUN_ID"]
    ref = os.environ["GITHUB_REF_NAME"]
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        jobs = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")).get(
            "jobs", []
        )
        sentinel = find_runner_readiness_job(jobs)
        state = sentinel.get("status", "missing") if sentinel else "missing"
        conclusion = sentinel.get("conclusion", "") if sentinel else ""
        if conclusion == "success":
            print(f"runner-watchdog=local-ready state={state} conclusion={conclusion}")
            return 0
        if state == "completed":
            print(f"runner-watchdog=local-not-ready conclusion={conclusion or 'unknown'}")
            break
        time.sleep(5)
    subprocess.run(
        [
            "gh",
            "workflow",
            "run",
            os.environ.get("FALLBACK_WORKFLOW", "commit-validation.yml"),
            "--repo",
            repo,
            "--ref",
            ref,
            "-f",
            "runner_mode=hosted",
            "-f",
            f"fallback_source_run={run_id}",
        ],
        check=True,
        timeout=10,
    )
    time.sleep(2)
    subprocess.run(
        ["gh", "api", "--method", "POST", f"repos/{repo}/actions/runs/{run_id}/cancel"],
        check=False,
        timeout=10,
    )
    print(f"runner-watchdog=fallback-dispatched source_run={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
