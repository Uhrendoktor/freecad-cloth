"""Remove stale unprotected branches, completed runs, and unreferenced PBD images safely."""

from __future__ import annotations

import hashlib
import json
import os
import string
import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

PAGE_SIZE = 100
BRANCH_RETENTION_DAYS = 7
MAX_BRANCH_DELETIONS_PER_RUN = 250
BRANCH_COMMIT_QUERY_BATCH_SIZE = 40
MAX_RUN_DELETIONS_PER_RUN = 100
MAX_PACKAGE_VERSION_DELETIONS_PER_RUN = 50
DOCKERFILE_TAG_QUERY_BATCH_SIZE = 40
PBD_PACKAGE_SUFFIX = "freecad-cloth/pbd-validation"


def gh_json(*args: str) -> object:
    """Run a GitHub CLI command and parse its JSON output.

    Args:
        args: Arguments passed to the GitHub CLI invocation.

    Returns:
        Parsed JSON value written to standard output.
    """
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)


def gh_delete(*args: str) -> None:
    """Delete a GitHub resource through the GitHub CLI.

    Args:
        args: Arguments identifying the GitHub resource to delete.
    """
    subprocess.run(["gh", *args], check=True, timeout=10)


def epoch(value: str) -> float:
    """Convert an ISO-8601 timestamp to a Unix epoch.

    Args:
        value: ISO-8601 date and time to convert.

    Returns:
        Unix epoch timestamp representing the supplied date and time.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def paginated_api_items(
    endpoint: str,
    *,
    collection_key: str | None = None,
    page_size: int = PAGE_SIZE,
    fetch_json: Callable[..., object] | None = None,
) -> Iterator[dict[str, object]]:
    """Yield every item from a paginated GitHub API list endpoint.

    Args:
        endpoint: GitHub API path for the paginated collection.
        collection_key: Optional object key containing the collection.
        page_size: Maximum number of items requested on each page.
        fetch_json: Optional CLI-compatible JSON loader; defaults to the GitHub CLI.

    Yields:
        Individual object records returned by the API.

    Raises:
        ValueError: Raised when the requested page size is not positive.
        RuntimeError: Raised when an API response has an invalid collection shape.
    """
    if page_size <= 0:
        raise ValueError("page size must be positive")
    load_json = gh_json if fetch_json is None else fetch_json
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}per_page={page_size}&page={page}"
        payload = load_json("api", url)
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
    """Return runs older than the retention cutoff, oldest first.

    Args:
        runs: Workflow-run records to filter by creation time.
        cutoff_epoch: Unix timestamp marking the retention boundary.

    Returns:
        Expired run records sorted from oldest to newest.
    """
    stale = [
        run
        for run in runs
        if isinstance(run.get("created_at"), str) and epoch(str(run["created_at"])) < cutoff_epoch
    ]
    stale.sort(key=lambda run: epoch(str(run["created_at"])))
    return stale


def branch_activity_epoch(commit_data: dict[str, object]) -> float | None:
    """Return commit activity time, preferring commit creation over original authorship.

    Args:
        commit_data: Commit metadata containing author and committer timestamps.

    Returns:
        Unix timestamp for the best available commit activity date, or None.
    """
    committer = commit_data.get("committer")
    date = committer.get("date") if isinstance(committer, dict) else None
    if not isinstance(date, str):
        author = commit_data.get("author")
        date = author.get("date") if isinstance(author, dict) else None
    return epoch(date) if isinstance(date, str) else None


def branch_activity_epochs(
    repo: str,
    commit_shas: set[str],
    *,
    batch_size: int = BRANCH_COMMIT_QUERY_BATCH_SIZE,
    fetch_json: Callable[..., object] | None = None,
) -> dict[str, float]:
    """Resolve commit activity timestamps in bounded GraphQL batches.

    Missing or unverifiable commit data raises before the caller can select any
    branch for deletion, so a partial GitHub response cannot turn into cleanup.

    Args:
        repo: Owner and repository name whose commit objects are queried.
        commit_shas: Full commit SHA values whose activity dates must be verified.
        batch_size: Maximum number of commit objects included in one GraphQL request.
        fetch_json: Optional CLI-compatible JSON loader for deterministic tests.

    Returns:
        Mapping from each verified commit SHA to its Unix activity timestamp.

    Raises:
        ValueError: If batch_size is not positive.
        RuntimeError: If a SHA is malformed or GitHub omits verifiable commit data.
    """
    if batch_size <= 0:
        raise ValueError("branch commit query batch size must be positive")
    if not commit_shas:
        return {}

    load_json = gh_json if fetch_json is None else fetch_json
    owner, repository_name = repo.split("/", maxsplit=1)
    ordered_shas = sorted(commit_shas)
    activity_epochs: dict[str, float] = {}
    for offset in range(0, len(ordered_shas), batch_size):
        batch = ordered_shas[offset : offset + batch_size]
        aliases: dict[str, str] = {}
        fields: list[str] = []
        for index, sha in enumerate(batch):
            if len(sha) != 40 or any(char not in "0123456789abcdefABCDEF" for char in sha):
                raise RuntimeError(f"invalid branch commit SHA: {sha!r}")
            alias = f"commit{index}"
            aliases[alias] = sha
            fields.append(
                f'{alias}: object(expression: "{sha}") '
                "{ ... on Commit { committedDate authoredDate } }"
            )

        query = (
            "query { repository("
            f'owner: "{owner}", name: "{repository_name}"'
            f") {{ {' '.join(fields)} }} }}"
        )
        payload = load_json("api", "graphql", "-f", f"query={query}")
        if not isinstance(payload, dict):
            raise RuntimeError("GitHub GraphQL returned a non-object branch activity response")
        if payload.get("errors"):
            raise RuntimeError("GitHub GraphQL could not verify branch activity")
        data = payload.get("data")
        repository_data = data.get("repository") if isinstance(data, dict) else None
        if not isinstance(repository_data, dict):
            raise RuntimeError("GitHub GraphQL omitted branch activity repository data")

        for alias, sha in aliases.items():
            commit_data = repository_data.get(alias)
            if not isinstance(commit_data, dict):
                raise RuntimeError(f"commit activity missing for branch head {sha}")
            committed_date = commit_data.get("committedDate")
            authored_date = commit_data.get("authoredDate")
            date = committed_date if isinstance(committed_date, str) else authored_date
            if not isinstance(date, str):
                raise RuntimeError(f"commit activity is unverifiable for branch head {sha}")
            activity_epochs[sha] = epoch(date)
    return activity_epochs


def closed_pr_head_shas_by_branch(
    repo: str,
    branches: list[dict[str, object]],
    open_heads: set[str],
    default_branch: str,
    activity_epochs: dict[str, float],
    cutoff_epoch: float,
    *,
    api_items_loader: Callable[..., Iterator[dict[str, object]]] | None = None,
) -> dict[str, set[str]]:
    """Identify recent branch refs that still match a closed PR head exactly.

    Args:
        repo: Full owner/repository name used to query pull requests.
        branches: Branch records containing names, protection flags, and current SHAs.
        open_heads: Branch names currently referenced by open pull requests.
        default_branch: Repository default branch, which must always be retained.
        activity_epochs: Commit SHA to most-recent-activity epoch mapping.
        cutoff_epoch: Earliest activity epoch recent enough to inspect for closed PRs.
        api_items_loader: Optional paginator override used by deterministic API tests.

    Returns:
        Eligible branch names mapped to the exact closed-PR head SHAs they match.
    """
    load_api_items = paginated_api_items if api_items_loader is None else api_items_loader
    owner = repo.split("/", maxsplit=1)[0]
    closed_heads: dict[str, set[str]] = {}
    for branch in branches:
        name = branch.get("name")
        if (
            not isinstance(name, str)
            or name.startswith("simulation-evidence/")
            or name == default_branch
            or name in open_heads
            or branch.get("protected") is not False
        ):
            continue
        commit = branch.get("commit")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str):
            continue
        activity = activity_epochs.get(sha)
        if activity is None or activity < cutoff_epoch:
            continue

        encoded_head = quote(f"{owner}:{name}", safe=":")
        pulls = list(load_api_items(f"repos/{repo}/pulls?state=closed&head={encoded_head}"))
        for pull_request in pulls:
            head = pull_request.get("head")
            head_repo = head.get("repo") if isinstance(head, dict) else None
            ref, head_sha = (
                (head.get("ref"), head.get("sha")) if isinstance(head, dict) else (None, None)
            )
            full_name = head_repo.get("full_name") if isinstance(head_repo, dict) else None
            if (
                pull_request.get("state") == "closed"
                and ref == name
                and head_sha == sha
                and full_name == repo
            ):
                closed_heads.setdefault(name, set()).add(sha)
                break
    return closed_heads


def stale_unprotected_branches(
    branches: list[dict[str, object]],
    open_heads: set[str],
    default_branch: str,
    activity_epochs: dict[str, float],
    cutoff_epoch: float,
    closed_pr_head_shas: dict[str, set[str]] | None = None,
) -> list[dict[str, object]]:
    """Return unprotected, non-default branches inactive before the cutoff.

    Open pull-request heads and branches with missing activity evidence are
    retained. Results are ordered oldest first for predictable bounded cleanup.

    Args:
        branches: Branch records returned by GitHub for the repository.
        open_heads: Branch names used by currently open pull requests.
        default_branch: Repository's default branch name, which must be retained.
        activity_epochs: Verified commit activity times keyed by full commit SHA.
        cutoff_epoch: Unix timestamp before which a branch is considered stale.

    Returns:
        Unprotected stale branch records sorted by verified commit activity time.
    """
    stale: list[tuple[float, dict[str, object]]] = []
    for branch in branches:
        name = branch.get("name")
        if (
            not isinstance(name, str)
            or name.startswith("simulation-evidence/")
            or name == default_branch
            or name in open_heads
            or branch.get("protected") is not False
        ):
            continue
        commit = branch.get("commit")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str):
            continue
        activity = activity_epochs.get(sha)
        if activity is None:
            continue
        closed_head_shas = (
            closed_pr_head_shas.get(name, set()) if closed_pr_head_shas is not None else set()
        )
        if activity >= cutoff_epoch and sha not in closed_head_shas:
            continue
        stale.append((activity, branch))
    stale.sort(key=lambda item: (item[0], str(item[1].get("name", ""))))
    return [branch for _, branch in stale]


def pbd_validation_tag(dockerfile_contents: bytes) -> str:
    """Return the immutable image tag used by the canonical workflow.

    Args:
        dockerfile_contents: Exact Dockerfile bytes used to build the image.

    Returns:
        Stable hexadecimal tag derived from the Dockerfile contents.
    """
    return hashlib.sha256(dockerfile_contents).hexdigest()[:32]


def package_version_tags(version: dict[str, object]) -> set[str] | None:
    """Return container tags, or None when the API omitted tag metadata.

    Args:
        version: Container package version record returned by GitHub.

    Returns:
        Set of string tags, or None when tag metadata is missing or malformed.
    """
    metadata = version.get("metadata")
    container = metadata.get("container") if isinstance(metadata, dict) else None
    tags = container.get("tags") if isinstance(container, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        return None
    return set(tags)


def package_version_activity_epoch(version: dict[str, object]) -> float | None:
    """Use updated_at when present so a recently republished tag gets a grace period.

    Args:
        version: Container package version metadata from GitHub.

    Returns:
        Unix timestamp for the version's latest activity, or None.
    """
    activity = version.get("updated_at") or version.get("created_at")
    return epoch(activity) if isinstance(activity, str) else None


def stale_package_versions(
    versions: list[dict[str, object]], protected_tags: set[str], cutoff_epoch: float
) -> list[dict[str, object]]:
    """Return old package versions whose tags are not used by protected refs or runs.

    Args:
        versions: Container package versions examined for retention.
        protected_tags: Image tags still referenced by protected commits or runs.
        cutoff_epoch: Unix timestamp marking the package retention boundary.

    Returns:
        Unprotected package versions older than the retention cutoff.
    """
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


def dockerfile_tags_for_shas(
    repo: str,
    protected_shas: set[str],
    *,
    batch_size: int = DOCKERFILE_TAG_QUERY_BATCH_SIZE,
    fetch_json: Callable[..., object] | None = None,
) -> set[str]:
    """Resolve protected Dockerfile tags with batched GraphQL queries instead of one REST call per SHA.

    Args:
        repo: Owner and repository name containing the Dockerfile history.
        protected_shas: Commit identifiers whose Dockerfile contents are protected.
        batch_size: Maximum number of commit objects queried at once.
        fetch_json: Optional CLI-compatible JSON loader for deterministic tests.

    Returns:
        Image tags derived from Dockerfile contents at all protected commits.

    Raises:
        ValueError: Raised when the GraphQL batch size is not positive.
        RuntimeError: Raised when a protected commit cannot be verified.
    """
    if batch_size <= 0:
        raise ValueError("Dockerfile query batch size must be positive")
    if not protected_shas:
        return set()

    load_json = gh_json if fetch_json is None else fetch_json
    owner, repository_name = repo.split("/", maxsplit=1)
    ordered_shas = sorted(protected_shas)
    tags: set[str] = set()
    for offset in range(0, len(ordered_shas), batch_size):
        batch = ordered_shas[offset : offset + batch_size]
        aliases: dict[str, str] = {}
        fields: list[str] = []
        for index, sha in enumerate(batch):
            if len(sha) != 40 or any(char not in string.hexdigits for char in sha):
                raise RuntimeError(f"invalid protected commit SHA: {sha!r}")
            alias = f"file{index}"
            aliases[alias] = sha
            fields.append(
                f'{alias}: object(expression: "{sha}:docker/freecad-ci/Dockerfile") '
                "{ ... on Blob { text } }"
            )

        query = (
            "query { repository("
            f'owner: "{owner}", name: "{repository_name}"'
            f") {{ {' '.join(fields)} }} }}"
        )
        payload = load_json("api", "graphql", "-f", f"query={query}")
        if not isinstance(payload, dict):
            raise RuntimeError("GitHub GraphQL returned a non-object response")
        if payload.get("errors"):
            raise RuntimeError("GitHub GraphQL could not verify protected Dockerfile contents")
        data = payload.get("data")
        repository_data = data.get("repository") if isinstance(data, dict) else None
        if not isinstance(repository_data, dict):
            raise RuntimeError("GitHub GraphQL omitted the protected repository data")

        for alias, sha in aliases.items():
            blob = repository_data.get(alias)
            dockerfile_text = blob.get("text") if isinstance(blob, dict) else None
            if not isinstance(dockerfile_text, str):
                raise RuntimeError(f"Dockerfile content missing for protected ref {sha}")
            tags.add(pbd_validation_tag(dockerfile_text.encode("utf-8")))
    return tags


def cleanup_pbd_package_versions(
    repo: str,
    protected_shas: set[str],
    cutoff_epoch: float,
    *,
    dockerfile_tags_resolver: Callable[[str, set[str]], set[str]] | None = None,
    api_items_loader: Callable[..., Iterator[dict[str, object]]] | None = None,
    delete_resource: Callable[..., None] | None = None,
) -> dict[str, object]:
    """Prune only old PBD image versions unused by main, open PRs, or retained/active runs.

    Args:
        repo: Owner and repository name containing the PBD package.
        protected_shas: Commit identifiers that keep corresponding image tags in use.
        cutoff_epoch: Unix timestamp marking the image retention boundary.
        dockerfile_tags_resolver: Optional callback that returns tags protected by commit SHAs.
        api_items_loader: Optional paginated API iterator used to list package versions.
        delete_resource: Optional CLI-compatible callback for deleting stale versions.

    Returns:
        Cleanup counts and a status describing the package-retention outcome.

    Raises:
        RuntimeError: Raised when a required package version identifier is invalid.
    """
    result: dict[str, object] = {
        "status": "not_started",
        "versions_seen": 0,
        "deleted": 0,
        "pending": 0,
        "protected_tags": 0,
    }
    deleted = 0
    resolve_tags = (
        dockerfile_tags_for_shas if dockerfile_tags_resolver is None else dockerfile_tags_resolver
    )
    load_api_items = paginated_api_items if api_items_loader is None else api_items_loader
    delete_api_resource = gh_delete if delete_resource is None else delete_resource
    phase = "resolve_protected_tags"
    try:
        if not protected_shas:
            result["status"] = "skipped_no_protected_refs"
            return result
        protected_tags = resolve_tags(repo, protected_shas)
        result["protected_tags"] = len(protected_tags)

        # The target is fixed by this repository. Encode its slash as part of the package-name path parameter.
        # Skip namespace-wide discovery, which returns HTTP 400 with the workflow installation token.
        phase = "list_package_versions"
        encoded_name = quote(PBD_PACKAGE_SUFFIX, safe="")
        versions = list(load_api_items(f"user/packages/container/{encoded_name}/versions"))
        result["versions_seen"] = len(versions)
        stale = stale_package_versions(versions, protected_tags, cutoff_epoch)
        result["pending"] = len(stale)
        selected = stale[:MAX_PACKAGE_VERSION_DELETIONS_PER_RUN]
        for version in selected:
            version_id = version.get("id")
            if not isinstance(version_id, int):
                raise RuntimeError("GitHub returned a package version without an integer ID")
            phase = f"delete_package_version_{version_id}"
            delete_api_resource(
                "api",
                "--method",
                "DELETE",
                f"user/packages/container/{encoded_name}/versions/{version_id}",
            )
            deleted += 1
            result["pending"] = len(stale) - deleted
        result["deleted"] = deleted
        result["pending"] = len(stale) - deleted
        result["status"] = "passed"
        return result
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc)).strip().replace("\n", " ")[:240]
        result["deleted"] = deleted
        result["status"] = (
            "permission_denied" if "403" in detail or "forbidden" in detail.lower() else "api_error"
        )
        result["error"] = f"{phase}: {detail}"
        return result
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        result["deleted"] = deleted
        result["status"] = "skipped_unverifiable"
        result["error"] = str(exc)[:240]
        return result


def main() -> int:
    """Run repository retention cleanup and report a non-secret summary.

    GitHub CLI credentials and the repository name come from the workflow environment.
    Branch deletion is fail-closed: all candidate activity is verified before deletion.
    Package cleanup reports unverifiable states instead of deleting possibly active images.

    Returns:
        Zero after the retention pass completes, including recoverable package-cleanup errors.

    Raises:
        KeyError: If the required REPO environment variable is absent.
        RuntimeError: If repository metadata, branch activity, or a resource identifier is invalid.
        subprocess.CalledProcessError: If a required GitHub CLI request fails.
    """
    repo = os.environ["REPO"]
    now = datetime.now(UTC)
    branch_cutoff = (now - timedelta(days=BRANCH_RETENTION_DAYS)).timestamp()
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

    repository_data = gh_json("api", f"repos/{repo}")
    default_branch = (
        repository_data.get("default_branch") if isinstance(repository_data, dict) else None
    )
    if not isinstance(default_branch, str):
        raise RuntimeError("GitHub repository metadata omitted the default branch")

    branches = list(paginated_api_items(f"repos/{repo}/branches"))
    branch_shas: set[str] = set()
    for branch in branches:
        name = branch.get("name")
        commit = branch.get("commit")
        if (
            not isinstance(name, str)
            or name.startswith("simulation-evidence/")
            or name == default_branch
            or name in open_heads
            or branch.get("protected") is not False
        ):
            continue
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if isinstance(sha, str):
            branch_shas.add(sha)

    # Resolve all candidate activity before deleting anything; incomplete GraphQL data
    # aborts the branch pass instead of treating an unknown branch as stale.
    activity_epochs = branch_activity_epochs(repo, branch_shas)
    closed_pr_heads = closed_pr_head_shas_by_branch(
        repo, branches, open_heads, default_branch, activity_epochs, branch_cutoff
    )
    stale_branches = stale_unprotected_branches(
        branches, open_heads, default_branch, activity_epochs, branch_cutoff, closed_pr_heads
    )
    selected_branches = stale_branches[:MAX_BRANCH_DELETIONS_PER_RUN]
    removed_branches = 0
    for branch in selected_branches:
        name = branch.get("name")
        if not isinstance(name, str):
            raise RuntimeError("GitHub returned a stale branch without a name")
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
        f"branches_seen={len(branches)} "
        f"removed_branches={removed_branches} "
        f"stale_branches_pending={len(stale_branches) - len(selected_branches)} "
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
