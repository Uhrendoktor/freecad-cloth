"""Remove stale agent branches and completed workflow runs safely."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

PAGE_SIZE = 100
MAX_RUN_DELETIONS_PER_RUN = 100


def gh_json(*args: str) -> object:
    """Run a GitHub CLI command and parse its JSON output."""
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)


def gh_delete(*args: str) -> None:
    """Delete a GitHub resource through the GitHub CLI."""
    subprocess.run(["gh", *args], check=True, timeout=10)


def epoch(value: str) -> float:
    """Convert an ISO-8601 timestamp to a Unix epoch."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def paginated_api_items(
    endpoint: str, *, collection_key: str | None = None, page_size: int = PAGE_SIZE
) -> Iterator[dict[str, object]]:
    """Yield every item from a paginated GitHub API list endpoint."""
    if page_size <= 0:
        raise ValueError("page size must be positive")
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}per_page={page_size}&page={page}"
        payload = gh_json("api", url)
        if collection_key is None:
            items = payload
        else:
            if not isinstance(payload, dict):
                raise RuntimeError(f"GitHub API response for {endpoint} must be an object")
            items = payload.get(collection_key)
        if not isinstance(items, list):
            raise RuntimeError(f"GitHub API response for {endpoint} has no item list")
        for item in items:
            if not isinstance(item, dict):
                raise RuntimeError(f"GitHub API response for {endpoint} contains a non-object item")
            yield item
        if len(items) < page_size:
            return
        page += 1


def stale_completed_runs(
    runs: list[dict[str, object]], cutoff_epoch: float
) -> list[dict[str, object]]:
    """Return runs older than the retention cutoff, oldest first."""
    stale = [
        run
        for run in runs
        if isinstance(run.get("created_at"), str) and epoch(str(run["created_at"])) < cutoff_epoch
    ]
    stale.sort(key=lambda run: epoch(str(run["created_at"])))
    return stale


def branch_activity_epoch(commit_data: dict[str, object]) -> float | None:
    """Return commit activity time, preferring commit creation over original authorship."""
    committer = commit_data.get("committer")
    date = committer.get("date") if isinstance(committer, dict) else None
    if not isinstance(date, str):
        author = commit_data.get("author")
        date = author.get("date") if isinstance(author, dict) else None
    return epoch(date) if isinstance(date, str) else None


def main() -> int:
    """Remove old agent branches and retain bounded workflow-run cleanup work."""
    repo = os.environ["REPO"]
    now = datetime.now(timezone.utc)
    branch_cutoff = (now - timedelta(days=14)).timestamp()
    run_cutoff = (now - timedelta(days=30)).timestamp()

    open_heads: set[str] = set()
    for pull_request in paginated_api_items(f"repos/{repo}/pulls?state=open"):
        head = pull_request.get("head")
        if isinstance(head, dict) and isinstance(head.get("ref"), str):
            open_heads.add(str(head["ref"]))

    removed_branches = 0
    for branch in paginated_api_items(f"repos/{repo}/branches"):
        name = branch.get("name")
        commit = branch.get("commit")
        if not isinstance(name, str) or not name.startswith("agent/") or name in open_heads:
            continue
        if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str):
            continue
        data = gh_json("api", f"repos/{repo}/commits/{commit['sha']}")
        if not isinstance(data, dict):
            continue
        commit_data = data.get("commit")
        if not isinstance(commit_data, dict):
            continue
        activity_epoch = branch_activity_epoch(commit_data)
        if activity_epoch is not None and activity_epoch < branch_cutoff:
            gh_delete("api", "--method", "DELETE", f"repos/{repo}/git/refs/heads/{name}")
            removed_branches += 1

    runs = list(
        paginated_api_items(
            f"repos/{repo}/actions/runs?status=completed", collection_key="workflow_runs"
        )
    )
    stale = stale_completed_runs(runs, run_cutoff)
    selected = stale[:MAX_RUN_DELETIONS_PER_RUN]
    for run in selected:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise RuntimeError("GitHub returned a completed workflow run without an integer ID")
        gh_delete("api", "--method", "DELETE", f"repos/{repo}/actions/runs/{run_id}")

    print(
        "maintenance-cleanup=passed "
        f"removed_branches={removed_branches} removed_runs={len(selected)} "
        f"stale_runs_pending={len(stale) - len(selected)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
