"""Remove stale agent branches and completed workflow runs."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone


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


def main() -> int:
    """Remove stale agent branches and completed workflow runs."""
    repo = os.environ["REPO"]
    now = datetime.now(timezone.utc)
    branch_cutoff = (now - timedelta(days=14)).timestamp()
    run_cutoff = (now - timedelta(days=30)).timestamp()
    open_heads = {
        item["headRefName"]
        for item in gh_json(
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "headRefName",
        )
    }
    for item in gh_json("api", f"repos/{repo}/branches?per_page=100"):
        name = item["name"]
        if not name.startswith("agent/") or name in open_heads:
            continue
        data = gh_json("api", f"repos/{repo}/commits/{item['commit']['sha']}")
        date = data["commit"]["author"].get("date") or data["commit"]["committer"]["date"]
        if epoch(date) < branch_cutoff:
            gh_delete("api", "--method", "DELETE", f"repos/{repo}/git/refs/heads/{name}")
    runs = gh_json("api", f"repos/{repo}/actions/runs?per_page=100&status=completed")
    for run in runs.get("workflow_runs", []):
        if epoch(run["created_at"]) < run_cutoff:
            gh_delete("api", "--method", "DELETE", f"repos/{repo}/actions/runs/{run['id']}")
    print("maintenance-cleanup=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
