"""Check the accumulated artifact size for the current GitHub Actions run."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_VERSION = "2022-11-28"
MAX_ARTIFACT_BYTES = 10_000_000
PAGE_SIZE = 100


def accumulated_size(artifacts: Iterable[Mapping[str, object]]) -> int:
    """Return the accumulated stored size of workflow artifacts in bytes."""
    total = 0
    for artifact in artifacts:
        size = artifact.get("size_in_bytes")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"artifact has invalid size_in_bytes: {artifact!r}")
        total += size
    return total


def fetch_artifact_page(
    repository: str, run_id: int, token: str, page: int
) -> list[Mapping[str, object]]:
    """Fetch one paginated workflow-artifact response."""
    query = urlencode({"per_page": PAGE_SIZE, "page": page})
    url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?{query}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload: Any = json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"GitHub artifact API request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub artifact API returned invalid JSON") from exc

    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(artifacts, list):
        raise RuntimeError("GitHub artifact API response has no artifact list")
    if not all(isinstance(item, Mapping) for item in artifacts):
        raise RuntimeError("GitHub artifact API returned a malformed artifact list")
    return artifacts


def fetch_run_artifacts(repository: str, run_id: int, token: str) -> list[Mapping[str, object]]:
    """Fetch every artifact belonging to one workflow run."""
    artifacts: list[Mapping[str, object]] = []
    page = 1
    while True:
        batch = fetch_artifact_page(repository, run_id, token, page)
        artifacts.extend(batch)
        if len(batch) < PAGE_SIZE:
            return artifacts
        page += 1


def main() -> int:
    """Enforce the 10 MB accumulated artifact budget."""
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    run_id_text = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not repository or not token or not run_id_text:
        print("GITHUB_REPOSITORY, GITHUB_TOKEN, and GITHUB_RUN_ID are required", file=sys.stderr)
        return 2
    try:
        run_id = int(run_id_text)
    except ValueError:
        print(f"GITHUB_RUN_ID is not an integer: {run_id_text!r}", file=sys.stderr)
        return 2

    artifacts = fetch_run_artifacts(repository, run_id, token)
    total = accumulated_size(artifacts)
    print(f"artifact-budget={total}/{MAX_ARTIFACT_BYTES} bytes artifacts={len(artifacts)}")
    for artifact in sorted(artifacts, key=lambda item: str(item.get("name", ""))):
        print(
            f"artifact={artifact.get('name', '<unnamed>')} size={artifact['size_in_bytes']} bytes"
        )

    if total > MAX_ARTIFACT_BYTES:
        print(
            f"Accumulated artifact size exceeds the 10 MB limit by "
            f"{total - MAX_ARTIFACT_BYTES} bytes.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
