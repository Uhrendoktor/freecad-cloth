"""Safely rebase a requested same-repository pull request onto main."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYRIGHT_LIST_KEYS = {"include", "exclude", "strict"}


def merge_pyright_config(ours: dict[str, object], theirs: dict[str, object]) -> dict[str, object]:
    """Merge reviewed path lists, preserving main-side settings and both branches' paths."""
    merged = dict(ours)
    for key, incoming in theirs.items():
        if key in PYRIGHT_LIST_KEYS and isinstance(incoming, list):
            current = merged.get(key, [])
            if not isinstance(current, list):
                raise ValueError(f"Expected a list for pyrightconfig.json key {key!r}")
            if any(not isinstance(item, str) for item in [*current, *incoming]):
                raise ValueError(f"Expected string entries in pyrightconfig.json key {key!r}")
            merged[key] = list(dict.fromkeys([*current, *incoming]))
        elif key not in merged:
            merged[key] = incoming
    return merged


def _run(
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command from the repository root."""
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture_output,
        env=env,
    )


def _output(args: list[str]) -> str:
    return _run(args, capture_output=True).stdout.strip()


def _rebase_in_progress() -> bool:
    """Return whether Git has an active rebase state directory."""
    return any(
        (ROOT / _output(["git", "rev-parse", "--git-path", state])).is_dir()
        for state in ("rebase-merge", "rebase-apply")
    )


def _resolve_pyrightconfig_conflict() -> None:
    """Resolve only pyrightconfig.json, using the index's base/branch versions."""
    conflicts = _output(["git", "diff", "--name-only", "--diff-filter=U"]).splitlines()
    if conflicts != ["pyrightconfig.json"]:
        raise RuntimeError(f"Refusing unsupported rebase conflicts: {conflicts!r}")

    ours = json.loads(_output(["git", "show", ":2:pyrightconfig.json"]))
    theirs = json.loads(_output(["git", "show", ":3:pyrightconfig.json"]))
    if not isinstance(ours, dict) or not isinstance(theirs, dict):
        raise ValueError("Both conflicted Pyright configurations must be JSON objects")

    merged = merge_pyright_config(ours, theirs)
    serialized = json.dumps(merged, indent=2) + "\n"
    json.loads(serialized)
    (ROOT / "pyrightconfig.json").write_text(serialized, encoding="utf-8")
    _run(["git", "add", "pyrightconfig.json"])


def _active_pr(repo: str, number: int) -> tuple[str, str]:
    """Validate PR state and return its branch and current head SHA."""
    pr = json.loads(_output(["gh", "api", f"repos/{repo}/pulls/{number}"]))
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    head_repo = head.get("repo") or {}
    branch = head.get("ref")
    expected_head = head.get("sha")
    if (
        pr.get("state") != "open"
        or base.get("ref") != "main"
        or head_repo.get("full_name") != repo
        or not branch
        or branch == "main"
        or not expected_head
    ):
        raise RuntimeError(
            "PR must be open, based on main, and have a branch in this repository"
        )
    _run(["git", "check-ref-format", "--branch", branch])
    return branch, expected_head


def _rebase_and_push(
    repo: str, number: int, branch: str, expected_head: str, token: str
) -> str:
    """Rebase, resolve only the known JSON-list conflict, and push with a lease."""
    _run(["git", "config", "user.name", "github-actions[bot]"])
    _run(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ]
    )
    remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    _run(["git", "remote", "set-url", "origin", remote_url])
    _run(["git", "fetch", "origin", "main"])
    _run(
        [
            "git",
            "fetch",
            "origin",
            f"refs/heads/{branch}:refs/remotes/origin/{branch}",
        ]
    )

    fetched_head = _output(["git", "rev-parse", f"refs/remotes/origin/{branch}"])
    if fetched_head != expected_head:
        raise RuntimeError(
            "PR head changed during inspection; refusing to rebase a stale revision"
        )

    _run(["git", "checkout", "-B", branch, f"refs/remotes/origin/{branch}"])
    result = _run(
        ["git", "-c", "rerere.enabled=true", "rebase", "origin/main"],
        check=False,
    )
    if result.returncode and not _rebase_in_progress():
        raise RuntimeError("Git rebase failed without an inspectable conflict state")

    while _rebase_in_progress():
        conflicts = _output(["git", "diff", "--name-only", "--diff-filter=U"]).splitlines()
        if conflicts != ["pyrightconfig.json"]:
            _run(["git", "status", "--short"], check=False)
            raise RuntimeError(f"Rebase stopped on unsupported conflict(s): {conflicts!r}")
        print(
            "::notice::Merging pyrightconfig.json path lists while preserving main's strict "
            "targets.",
            flush=True,
        )
        _resolve_pyrightconfig_conflict()
        continue_env = {**os.environ, "GIT_EDITOR": "true"}
        continued = _run(
            ["git", "-c", "rerere.enabled=true", "rebase", "--continue"],
            check=False,
            env=continue_env,
        )
        if continued.returncode and not _rebase_in_progress():
            raise RuntimeError("git rebase --continue failed outside a rebase conflict")

    _run(["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"])
    rebased_head = _output(["git", "rev-parse", "HEAD"])
    print(f"Rebased PR #{number} head: {rebased_head}", flush=True)
    _run(["git", "log", "-5", "--oneline", "--decorate"])
    _run(
        [
            "git",
            "push",
            f"--force-with-lease=refs/heads/{branch}:{expected_head}",
            "origin",
            f"HEAD:refs/heads/{branch}",
        ]
    )
    return rebased_head


def _dispatch_validation(repo: str, branch: str, rebased_head: str) -> None:
    """Dispatch canonical checks and confirm a run exists for the exact rebased SHA."""
    _run(
        [
            "gh",
            "workflow",
            "run",
            "canonical-execution.yml",
            "--repo",
            repo,
            "--ref",
            branch,
            "-f",
            "runner_mode=hosted",
        ]
    )
    for attempt in range(1, 31):
        print(f"validation-dispatch-wait={attempt}/30", flush=True)
        result = _run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                "Canonical execution",
                "--branch",
                branch,
                "--event",
                "workflow_dispatch",
                "--limit",
                "20",
                "--json",
                "databaseId,headSha,status,url",
                "--jq",
                f'.[] | select(.headSha == "{rebased_head}")',
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            print(result.stdout.strip(), flush=True)
            return
        time.sleep(2)
    raise RuntimeError(f"Dispatched validation but could not find a run for {rebased_head}")


def main() -> int:
    """Run the guarded rebase requested by the activation commit title."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    title_lines = os.environ.get("ACTIVATION_TITLE", "").splitlines()
    match = (
        re.fullmatch(r"RUN REBASE: PR #([0-9]+)", title_lines[0].strip())
        if title_lines
        else None
    )
    if not repo or not token or not match:
        raise RuntimeError("Missing repository/token or invalid rebase activation title")
    number = int(match.group(1))
    branch, expected_head = _active_pr(repo, number)
    rebased_head = _rebase_and_push(repo, number, branch, expected_head, token)
    _dispatch_validation(repo, branch, rebased_head)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", flush=True)
        raise SystemExit(1) from error
