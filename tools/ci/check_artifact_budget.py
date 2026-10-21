# Copyright (C) 2026 FreeCAD Cloth contributors
"""Check the accumulated artifact size for the current GitHub Actions run."""

from __future__ import annotations

import http.client
import json
import os
import sys
from typing import TYPE_CHECKING, cast
from urllib.parse import urlencode

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

type JSONValue = str | int | float | bool | list[JSONValue] | dict[str, JSONValue] | None

API_VERSION = "2022-11-28"
MAX_ARTIFACT_BYTES = 10_000_000
PAGE_SIZE = 100


def accumulated_size(artifacts: Iterable[Mapping[str, object]]) -> int:
    """Return the accumulated stored size of workflow artifacts in bytes.

    Args:
        artifacts: Workflow artifact records containing stored byte sizes.

    Returns:
        Total stored artifact size measured in bytes.

    Raises:
        ValueError: Raised when an artifact has an invalid stored byte size.
    """
    total = 0
    for artifact in artifacts:
        size = artifact.get("size_in_bytes")
        if not isinstance(size, int) or size < 0:
            msg = f"artifact has invalid size_in_bytes: {artifact!r}"
            raise ValueError(msg)
        total += size
    return total


def _request_artifact_payload(
    connection: http.client.HTTPSConnection,
    request_path: str,
    headers: Mapping[str, str],
) -> JSONValue:
    """Request and decode one GitHub artifact API response.

    Args:
        connection: Open HTTPS connection to the GitHub API.
        request_path: API path and query string for the requested artifact page.
        headers: Authentication and version headers sent with the request.

    Returns:
        Decoded JSON payload from a successful HTTP response.

    Raises:
        RuntimeError: If the GitHub API returns a non-success HTTP status.
    """
    connection.request("GET", request_path, headers=dict(headers))
    response = connection.getresponse()
    if response.status != http.client.OK:
        msg = f"GitHub artifact API request failed: HTTP {response.status} {response.reason}"
        raise RuntimeError(msg)
    return cast("JSONValue", json.loads(response.read()))


def fetch_artifact_page(
    repository: str, run_id: int, token: str, page: int
) -> list[Mapping[str, object]]:
    """Fetch one paginated workflow-artifact response.

    Args:
        repository: Owner and repository name for the workflow run.
        run_id: Identifier of the workflow run to inspect.
        token: GitHub API token used for authentication.
        page: One-based artifact page number to request.

    Returns:
        Artifact records returned for the requested page.

    Raises:
        RuntimeError: If HTTPS fails or the API returns an error status.
        TypeError: If the JSON response does not have the expected object/list structure.
    """
    query = urlencode({"per_page": PAGE_SIZE, "page": page})
    request_path = f"/repos/{repository}/actions/runs/{run_id}/artifacts?{query}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    connection = http.client.HTTPSConnection("api.github.com", timeout=20)
    try:
        payload = _request_artifact_payload(connection, request_path, headers)
    except (http.client.HTTPException, OSError) as exc:
        msg = f"GitHub artifact API request failed: {exc}"
        raise RuntimeError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = "GitHub artifact API returned invalid JSON"
        raise RuntimeError(msg) from exc
    finally:
        connection.close()

    if not isinstance(payload, dict):
        msg = "GitHub artifact API response must be an object"
        raise TypeError(msg)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        msg = "GitHub artifact API response has no artifact list"
        raise TypeError(msg)
    normalized: list[Mapping[str, object]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            msg = "GitHub artifact API returned a malformed artifact list"
            raise TypeError(msg)
        normalized.append(item)
    return normalized


def fetch_run_artifacts(repository: str, run_id: int, token: str) -> list[Mapping[str, object]]:
    """Fetch every artifact belonging to one workflow run.

    Args:
        repository: Owner and repository name for the workflow run.
        run_id: Identifier of the workflow run to inspect.
        token: GitHub API token used for authentication.

    Returns:
        All artifact records from the workflow run.
    """
    artifacts: list[Mapping[str, object]] = []
    page = 1
    while True:
        batch = fetch_artifact_page(repository, run_id, token, page)
        artifacts.extend(batch)
        if len(batch) < PAGE_SIZE:
            return artifacts
        page += 1


def main() -> int:
    """Enforce the 10 MB accumulated artifact budget.

    Returns:
        Process status indicating whether the artifact budget was satisfied.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    run_id_text = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not repository or not token or not run_id_text:
        sys.stderr.write("GITHUB_REPOSITORY, GITHUB_TOKEN, and GITHUB_RUN_ID are required\n")
        return 2
    try:
        run_id = int(run_id_text)
    except ValueError:
        sys.stderr.write(f"GITHUB_RUN_ID is not an integer: {run_id_text!r}\n")
        return 2

    artifacts = fetch_run_artifacts(repository, run_id, token)
    total = accumulated_size(artifacts)
    sys.stdout.write(
        f"artifact-budget={total}/{MAX_ARTIFACT_BYTES} bytes artifacts={len(artifacts)}\n"
    )
    for artifact in sorted(artifacts, key=lambda item: str(item.get("name", ""))):
        sys.stdout.write(
            f"artifact={artifact.get('name', '<unnamed>')} size={artifact['size_in_bytes']} bytes\n"
        )

    if total > MAX_ARTIFACT_BYTES:
        sys.stderr.write(
            "Accumulated artifact size exceeds the 10 MB limit by "
            f"{total - MAX_ARTIFACT_BYTES} bytes.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
