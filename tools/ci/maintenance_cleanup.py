"""Remove stale agent branches, completed runs, and unreferenced PBD images safely."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

PAGE_SIZE = 100
MAX_RUN_DELETIONS_PER_RUN = 100
MAX_PACKAGE_VERSION_DELETIONS_PER_RUN = 50
PBD_PACKAGE_SUFFIX = "freecad-cloth/pbd-validation"


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


def pbd_validation_tag(dockerfile_contents: bytes) -> str:
    """Return the immutable image tag used by the canonical workflow."""
    return hashlib.sha256(dockerfile_contents).hexdigest()[:32]


def package_version_tags(version: dict[str, object]) -> set[str] | None:
    """Return container tags, or None when the API omitted tag metadata."""
    metadata = version.get("metadata")
    container = metadata.get("container") if isinstance(metadata, dict) else None
    tags = container.get("tags") if isinstance(container, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        return None
    return set(tags)


def package_version_activity_epoch(version: dict[str, object]) -> float | None:
    """Use updated_at when present so a recently republished tag gets a grace period."""
    activity = version.get("updated_at") or version.get("created_at")
    return epoch(activity) if isinstance(activity, str) else None


def stale_package_versions(
    versions: list[dict[str, object]], protected_tags: set[str], cutoff_epoch: float
) -> list[dict[str, object]]:
    """Return old package versions whose tags are not used by protected refs or runs."""
    stale = []
    for version in versions:
        tags = package_version_tags(version)
        activity = package_version_activity_epoch(version)
        if tags is None or activity is None:
            continue
        if activity >= cutoff_epoch or tags.intersection(protected_tags):
            continue
        stale.append(version)
    stale.sort(key=lambda version: package_version_activity_epoch(version) or float("inf"))
    return stale


def dockerfile_tag_for_sha(repo: str, sha: str) -> str:
    """Resolve the immutable PBD tag for a commit's authoritative Dockerfile."""
    payload = gh_json("api", f"repos/{repo}/contents/docker/freecad-ci/Dockerfile?ref={sha}")
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise RuntimeError(f"could not verify Dockerfile contents for protected ref {sha}")
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        raise RuntimeError(f"Dockerfile content missing for protected ref {sha}")
    try:
        contents = base64.b64decode(encoded)
    except ValueError as exc:
        raise RuntimeError(f"invalid Dockerfile content for protected ref {sha}") from exc
    return pbd_validation_tag(contents)


def cleanup_pbd_package_versions(
    repo: str, protected_shas: set[str], cutoff_epoch: float
) -> dict[str, object]:
    """Prune only old PBD image versions unused by main, open PRs, or retained/active runs."""
    result: dict[str, object] = {
        "status": "not_started",
        "versions_seen": 0,
        "deleted": 0,
        "pending": 0,
        "protected_tags": 0,
    }
    deleted = 0
    try:
        if not protected_shas:
            result["status"] = "skipped_no_protected_refs"
            return result
        protected_tags = {dockerfile_tag_for_sha(repo, sha) for sha in sorted(protected_shas)}
        result["protected_tags"] = len(protected_tags)

        owner = repo.split("/", maxsplit=1)[0]
        packages = list(paginated_api_items(f"users/{owner}/packages?package_type=container"))
        target = next(
            (
                package
                for package in packages
                if isinstance(package.get("name"), str)
                and str(package["name"]).strip("/").lower() == PBD_PACKAGE_SUFFIX
            ),
            None,
        )
        if target is None:
            result["status"] = "package_not_found"
            return result
        package_name = str(target["name"]).strip("/")
        encoded_name = quote(package_name, safe="")
        versions = list(paginated_api_items(f"users/{owner}/packages/container/{encoded_name}/versions"))
        result["versions_seen"] = len(versions)
        stale = stale_package_versions(versions, protected_tags, cutoff_epoch)
        selected = stale[:MAX_PACKAGE_VERSION_DELETIONS_PER_RUN]
        for version in selected:
            version_id = version.get("id")
            if not isinstance(version_id, int):
                raise RuntimeError("GitHub returned a package version without an integer ID")
            gh_delete(
                "api",
                "--method",
                "DELETE",
                f"users/{owner}/packages/container/{encoded_name}/versions/{version_id}",
            )
            deleted += 1
        result["deleted"] = deleted
        result["pending"] = len(stale) - deleted
        result["status"] = "passed"
        return result
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc)).strip().replace("\n", " ")[:240]
        result["deleted"] = deleted
        result["status"] = (
            "permission_denied"
            if "403" in detail or "forbidden" in detail.lower()
            else "api_error"
        )
        result["error"] = detail
        return result
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        result["deleted"] = deleted
        result["status"] = "skipped_unverifiable"
        result["error"] = str(exc)[:240]
        return result


def main() -> int:
    """Remove stale agent branches, runs, and unreferenced PBD image versions."""
    repo = os.environ["REPO"]
    now = datetime.now(UTC)
    branch_cutoff = (now - timedelta(days=14)).timestamp()
    run_cutoff = (now - timedelta(days=30)).timestamp()

    pull_requests = list(paginated_api_items(f"repos/{repo}/pulls?state=open"))
    open_heads: set[str] = set()
    protected_shas: set[str] = set()
    for pull_request in pull_requests:
        head = pull_request.get("head")
        if isinstance(head, dict):
            ref, sha = head.get("ref"), head.get("sha")
            if isinstance(ref, str):
                open_heads.add(ref)
            if isinstance(sha, str):
                protected_shas.add(sha)

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

    # Images used by the current main branch, open PRs, or retained/active runs are protected.
    main_ref = gh_json("api", f"repos/{repo}/git/ref/heads/main")
    if isinstance(main_ref, dict):
        main_object = main_ref.get("object")
        main_sha = main_object.get("sha") if isinstance(main_object, dict) else None
        if isinstance(main_sha, str):
            protected_shas.add(main_sha)
    for run in runs:
        created_at, sha = run.get("created_at"), run.get("head_sha")
        if isinstance(created_at, str) and epoch(created_at) >= run_cutoff and isinstance(sha, str):
            protected_shas.add(sha)
    for status in ("queued", "in_progress", "requested", "waiting"):
        active_runs = paginated_api_items(
            f"repos/{repo}/actions/runs?status={status}", collection_key="workflow_runs"
        )
        for run in active_runs:
            sha = run.get("head_sha")
            if isinstance(sha, str):
                protected_shas.add(sha)

    package_result = cleanup_pbd_package_versions(repo, protected_shas, run_cutoff)
    print(
        "maintenance-cleanup=passed "
        f"removed_branches={removed_branches} "
        f"removed_runs={len(selected)} stale_runs_pending={len(stale) - len(selected)} "
        f"package_cleanup={package_result['status']} "
        f"package_versions_seen={package_result['versions_seen']} "
        f"removed_package_versions={package_result['deleted']} "
        f"stale_package_versions_pending={package_result['pending']}"
    )
    if package_result.get("error"):
        print(f"package_cleanup_note={package_result['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
