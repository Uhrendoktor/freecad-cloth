# Copyright (C) 2026 FreeCAD Cloth contributors
"""Prefer the self-hosted runner and dispatch one hosted fallback after 45 seconds."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from subprocess import run


def _gh_executable() -> str:
    """Locate the GitHub CLI without relying on the caller's current directory.

    Returns:
        Absolute path to the GitHub CLI executable.

    Raises:
        FileNotFoundError: If GitHub CLI is unavailable on PATH.
    """
    executable = shutil.which("gh")
    if executable is None:
        msg = "GitHub CLI executable 'gh' was not found on PATH"
        raise FileNotFoundError(msg)
    return executable


def gh(*args: str) -> str:
    """Run a GitHub CLI command and return standard output.

    Args:
        args: GitHub CLI subcommand and arguments, excluding the executable name.

    Returns:
        Standard output emitted by the successful CLI command.
    """
    result = run(
        [_gh_executable(), *args],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout


def main() -> int:
    """Prefer the configured local runner and dispatch the hosted fallback when needed.

    Returns:
        Process status indicating whether runner selection or fallback dispatch completed.
    """
    repo = os.environ["REPO"]
    run_id = os.environ["GITHUB_RUN_ID"]
    ref = os.environ["GITHUB_REF_NAME"]
    executable = _gh_executable()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        jobs = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")).get(
            "jobs", []
        )
        sentinel = next(
            (job for job in jobs if job.get("name") == "Selected runner readiness"), None
        )
        state = sentinel.get("status", "missing") if sentinel else "missing"
        conclusion = sentinel.get("conclusion", "") if sentinel else ""
        if state == "in_progress" or conclusion == "success":
            sys.stdout.write(
                f"runner-watchdog=local-started state={state} conclusion={conclusion}\n"
            )
            return 0
        if state == "completed":
            break
        time.sleep(5)
    run(
        [
            executable,
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
        shell=False,
        timeout=10,
    )
    time.sleep(2)
    run(
        [executable, "api", "--method", "POST", f"repos/{repo}/actions/runs/{run_id}/cancel"],
        check=False,
        shell=False,
        timeout=10,
    )
    sys.stdout.write(f"runner-watchdog=fallback-dispatched source_run={run_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
