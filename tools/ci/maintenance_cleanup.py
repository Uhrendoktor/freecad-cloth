# Copyright (C) 2026 FreeCAD Cloth contributors
"""Remove stale unprotected branches, completed runs, and unreferenced PBD images safely."""

from __future__ import annotations

type ApiJsonValue = bool | int | float | str | list[ApiJsonValue] | dict[str, ApiJsonValue] | None
type ApiJsonObject = dict[str, ApiJsonValue]

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import http.client
import json
import os
import string
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

PAGE_SIZE = 100
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 300
HTTP_DETAIL_LENGTH = 240
RUN_RETENTION_DAYS = 30
ACTIVE_RUN_STATUSES = ("queued", "in_progress", "requested", "waiting")
GRAPHQL_ARGUMENT_COUNT = 4
REST_COMMAND_ARGUMENT_COUNT = 2
BRANCH_RETENTION_DAYS = 7
MAX_BRANCH_DELETIONS_PER_RUN = 250
BRANCH_COMMIT_QUERY_BATCH_SIZE = 40
COMMIT_SHA_HEX_LENGTH = 40
MAX_RUN_DELETIONS_PER_RUN = 100
MAX_RUN_CAP_DELETIONS_PER_RUN = 4000
MAX_RUN_DELETE_WORKERS = 12
MAX_RETAINED_WORKFLOW_RUNS = 10
MAX_RUN_RESULTS_PER_API_QUERY = 1000
MAX_RUN_QUERY_SPLITS = 16
MAX_PACKAGE_VERSION_DELETIONS_PER_RUN = 50
DOCKERFILE_TAG_QUERY_BATCH_SIZE = 40
PBD_PACKAGE_SUFFIX = "freecad-cloth/pbd-validation"

# Published documentation assets are long-lived public refs, not disposable work branches.
RESERVED_BRANCH_NAMES = frozenset({"docs/screenshots"})
EVIDENCE_BRANCH_PREFIX = "simulation-evidence/pr-"
GITHUB_API_VERSION = "2022-11-28"


class GitHubApiError(RuntimeError):
    """Represent an unsuccessful authenticated GitHub API request."""


@dataclass(frozen=True, slots=True)
class ClosedPullRequestLookup:
    """Hold verified state used to identify matching closed pull-request heads.

    Attributes:
        repo: Full owner/repository name queried through the API.
        open_heads: Branch names still referenced by open pull requests.
        default_branch: Branch name that must never be selected for deletion.
        activity_epochs: Verified activity timestamps keyed by commit SHA.
        cutoff_epoch: Timestamp boundary for looking up recently active closed PR heads.
    """

    repo: str
    open_heads: set[str]
    default_branch: str
    activity_epochs: dict[str, float]
    cutoff_epoch: float
    open_pr_numbers: set[int]


@dataclass(frozen=True, slots=True)
class BranchRetentionPolicy:
    """Collect verified activity data used to select stale branch refs.

    Attributes:
        activity_epochs: Commit activity timestamps keyed by full SHA.
        cutoff_epoch: Latest timestamp that qualifies as stale.
        closed_pr_head_shas: Exact closed-PR head SHAs allowed through the cutoff.
    """

    activity_epochs: dict[str, float]
    cutoff_epoch: float
    closed_pr_head_shas: dict[str, set[str]]
    open_pr_numbers: set[int]


@dataclass(frozen=True, slots=True)
class PackageCleanupCallbacks:
    """Optional API adapters used to make package retention deterministic in tests.

    Attributes:
        dockerfile_tags_resolver: Callback returning image tags protected by commit SHAs.
        api_items_loader: Callback that lists package versions through pagination.
        delete_resource: Callback that deletes a stale package version.
    """

    dockerfile_tags_resolver: Callable[[str, set[str]], set[str]] | None = None
    api_items_loader: Callable[..., Iterator[ApiJsonObject]] | None = None
    delete_resource: Callable[..., None] | None = None


@dataclass(slots=True)
class PackageCleanupProgress:
    """Track package cleanup results if a deletion fails partway through.

    Attributes:
        result: User-safe counters and status returned by the cleanup API.
        deleted: Number of versions deleted before an operation failed.
        phase: Package cleanup step active when an operation failed.
    """

    result: ApiJsonObject
    deleted: int = 0
    phase: str = "resolve_protected_tags"


def _decode_github_response(connection: http.client.HTTPSConnection) -> ApiJsonValue:
    """Validate an HTTP response and decode its optional JSON payload.

    Args:
        connection: HTTPS connection after its request has been sent.

    Returns:
        Decoded JSON, or None for an empty response body.

    Raises:
        GitHubApiError: If GitHub returns an unsuccessful status or malformed JSON.
    """
    response = connection.getresponse()
    payload = response.read()
    if not HTTP_SUCCESS_MIN <= response.status < HTTP_SUCCESS_MAX:
        detail = payload.decode("utf-8", errors="replace").strip()
        message = f"GitHub API request failed: HTTP {response.status} {response.reason}"
        if detail:
            message = f"{message}: {detail[:HTTP_DETAIL_LENGTH]}"
        raise GitHubApiError(message)
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        msg = "GitHub API returned invalid JSON"
        raise GitHubApiError(msg) from exc


def _request_github_api(
    method: str, endpoint: str, body: dict[str, str] | None = None
) -> ApiJsonValue:
    """Send one authenticated GitHub API request and decode its response.

    Args:
        method: HTTP method used for the API request.
        endpoint: REST or GraphQL endpoint path, without the API host.
        body: Optional JSON body sent to the API.

    Returns:
        Decoded JSON response, or None when the endpoint has no response body.

    Raises:
        GitHubApiError: If authentication, transport, HTTP status, or JSON decoding fails.
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        msg = "GitHub API token is missing from GH_TOKEN and GITHUB_TOKEN"
        raise GitHubApiError(msg)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "FreeCAD-Cloth-CI",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    encoded_body = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        encoded_body = json.dumps(body)
    connection = http.client.HTTPSConnection("api.github.com", timeout=10)
    try:
        connection.request(
            method,
            f"/{endpoint.lstrip('/')}",
            body=encoded_body,
            headers=headers,
        )
        return _decode_github_response(connection)
    except (http.client.HTTPException, OSError) as exc:
        msg = f"GitHub API request failed: {exc}"
        raise GitHubApiError(msg) from exc
    finally:
        connection.close()


def gh_json(*args: str) -> ApiJsonValue:
    """Fetch JSON from the GitHub API using the workflow token.

    Args:
        args: CLI-compatible API arguments; supports REST GET and GraphQL query calls.

    Returns:
        Decoded JSON returned by the API.

    Raises:
        ValueError: If the requested operation is not supported by this helper.
    """
    if len(args) == REST_COMMAND_ARGUMENT_COUNT and args[0] == "api":
        return _request_github_api("GET", args[1])
    if (
        len(args) == GRAPHQL_ARGUMENT_COUNT
        and args[0] == "api"
        and args[1] == "graphql"
        and args[2] == "-f"
        and args[3].startswith("query=")
    ):
        return _request_github_api("POST", "graphql", {"query": args[3][len("query=") :]})
    msg = "Unsupported GitHub API command arguments"
    raise ValueError(msg)


def gh_delete(*args: str) -> None:
    """Delete a GitHub resource through an authenticated API request.

    Args:
        args: CLI-compatible DELETE API arguments.

    Raises:
        ValueError: If the requested operation is not a DELETE API call.
    """
    if len(args) != GRAPHQL_ARGUMENT_COUNT or args[:3] != ("api", "--method", "DELETE"):
        msg = "Only GitHub API DELETE operations are supported by this helper"
        raise ValueError(msg)
    _request_github_api("DELETE", args[3])


def epoch(value: str) -> float:
    """Convert an ISO-8601 timestamp to a Unix epoch.

    Args:
        value: ISO-8601 date and time to convert.

    Returns:
        Unix epoch timestamp representing the supplied date and time.
    """
    return datetime.fromisoformat(value).timestamp()


def is_reserved_branch(name: str, default_branch: str) -> bool:
    """Return whether a ref is the default branch or a deliberately retained documentation ref."""
    return name == default_branch or name in RESERVED_BRANCH_NAMES


def is_open_pr_evidence_branch(name: str, open_pr_numbers: set[int]) -> bool:
    """Return whether an evidence ref belongs to a pull request that is still open."""
    if not name.startswith(EVIDENCE_BRANCH_PREFIX):
        return False
    number_text = name.removeprefix(EVIDENCE_BRANCH_PREFIX)
    return number_text.isdecimal() and int(number_text) in open_pr_numbers


def paginated_api_items(
    endpoint: str,
    *,
    collection_key: str | None = None,
    page_size: int = PAGE_SIZE,
    fetch_json: Callable[..., ApiJsonValue] | None = None,
) -> Iterator[ApiJsonObject]:
    """Yield every item from a paginated GitHub API list endpoint.

    Args:
        endpoint: GitHub API path for the paginated collection.
        collection_key: Optional object key containing the collection.
        page_size: Maximum number of items requested on each page.
        fetch_json: Optional CLI-compatible JSON loader; defaults to the GitHub CLI.

    Yields:
        Individual object records returned by the API.

    Raises:
        ValueError: If the requested page size is not positive.
        TypeError: If an API response has an unexpected type.
    """
    if page_size <= 0:
        msg = "page size must be positive"
        raise ValueError(msg)
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
                msg = f"GitHub API response for {endpoint} must be an object"
                raise TypeError(msg)
            items = payload.get(collection_key)
        if not isinstance(items, list):
            msg = f"GitHub API response for {endpoint} has no item list"
            raise TypeError(msg)
        for item in items:
            if not isinstance(item, dict):
                msg = f"GitHub API response for {endpoint} contains a non-object item"
                raise TypeError(msg)
            yield item
        if len(items) < page_size:
            return
        page += 1


def stale_completed_runs(runs: list[ApiJsonObject], cutoff_epoch: float) -> list[ApiJsonObject]:
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


def branch_activity_epoch(commit_data: ApiJsonObject) -> float | None:
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


def _branch_activity_batch(
    owner: str,
    repository_name: str,
    batch: list[str],
    load_json: Callable[..., ApiJsonValue],
) -> dict[str, float]:
    """Resolve activity timestamps for one validated-size commit batch.

    Args:
        owner: GitHub account or organization that owns the repository.
        repository_name: Repository name under the owner.
        batch: Commit SHAs assigned to this bounded request.
        load_json: API loader compatible with the maintenance test seam.

    Returns:
        Activity timestamps keyed by the commit SHA returned from GitHub.

    Raises:
        RuntimeError: If a SHA is malformed or the GraphQL response reports errors.
        TypeError: If GitHub returns unverified commit activity data.
    """
    aliases: dict[str, str] = {}
    fields: list[str] = []
    for index, sha in enumerate(batch):
        if len(sha) != COMMIT_SHA_HEX_LENGTH or any(char not in string.hexdigits for char in sha):
            msg = f"invalid branch commit SHA: {sha!r}"
            raise RuntimeError(msg)
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
        msg = "GitHub GraphQL returned a non-object branch activity response"
        raise TypeError(msg)
    if payload.get("errors"):
        msg = "GitHub GraphQL could not verify branch activity"
        raise RuntimeError(msg)
    data = payload.get("data")
    repository_data = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository_data, dict):
        msg = "GitHub GraphQL omitted repository branch activity data"
        raise TypeError(msg)

    activity_epochs: dict[str, float] = {}
    for alias, sha in aliases.items():
        commit_data = repository_data.get(alias)
        if not isinstance(commit_data, dict):
            msg = f"commit activity missing for branch head {sha}"
            raise TypeError(msg)
        committed_date = commit_data.get("committedDate")
        authored_date = commit_data.get("authoredDate")
        date = committed_date if isinstance(committed_date, str) else authored_date
        if not isinstance(date, str):
            msg = f"commit activity is unverifiable for branch head {sha}"
            raise TypeError(msg)
        activity_epochs[sha] = epoch(date)
    return activity_epochs


def branch_activity_epochs(
    repo: str,
    commit_shas: set[str],
    *,
    batch_size: int = BRANCH_COMMIT_QUERY_BATCH_SIZE,
    fetch_json: Callable[..., ApiJsonValue] | None = None,
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
    """
    if batch_size <= 0:
        msg = "branch commit query batch size must be positive"
        raise ValueError(msg)
    if not commit_shas:
        return {}

    load_json = gh_json if fetch_json is None else fetch_json
    owner, repository_name = repo.split("/", maxsplit=1)
    ordered_shas = sorted(commit_shas)
    activity_epochs: dict[str, float] = {}
    for offset in range(0, len(ordered_shas), batch_size):
        batch = ordered_shas[offset : offset + batch_size]
        activity_epochs.update(_branch_activity_batch(owner, repository_name, batch, load_json))
    return activity_epochs


def closed_pr_head_shas_by_branch(
    branches: list[ApiJsonObject],
    lookup: ClosedPullRequestLookup,
    *,
    api_items_loader: Callable[..., Iterator[ApiJsonObject]] | None = None,
) -> dict[str, set[str]]:
    """Identify recent branch refs matching a closed pull-request head exactly.

    Long-lived evidence/publication refs, protected refs, the default branch, and
    open pull-request heads are excluded from these lookups.

    Args:
        branches: Branch records containing names, protection flags, and current SHAs.
        lookup: Verified repository, activity, and open-PR state for this search.
        api_items_loader: Optional paginator override used by deterministic tests.

    Returns:
        Eligible branch names mapped to the exact closed-PR head SHAs they match.
    """
    load_api_items = paginated_api_items if api_items_loader is None else api_items_loader
    owner = lookup.repo.split("/", maxsplit=1)[0]
    closed_heads: dict[str, set[str]] = {}
    for branch in branches:
        name = branch.get("name")
        if (
            not isinstance(name, str)
            or is_reserved_branch(name, lookup.default_branch)
            or name.startswith(EVIDENCE_BRANCH_PREFIX)
            or name in lookup.open_heads
            or branch.get("protected") is not False
        ):
            continue
        commit = branch.get("commit")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str):
            continue
        activity = lookup.activity_epochs.get(sha)
        if activity is None or activity < lookup.cutoff_epoch:
            continue

        encoded_head = quote(f"{owner}:{name}", safe=":")
        pulls = list(load_api_items(f"repos/{lookup.repo}/pulls?state=closed&head={encoded_head}"))
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
                and full_name == lookup.repo
            ):
                closed_heads.setdefault(name, set()).add(sha)
                break
    return closed_heads


def stale_unprotected_branches(
    branches: list[ApiJsonObject],
    open_heads: set[str],
    default_branch: str,
    retention: BranchRetentionPolicy,
) -> list[ApiJsonObject]:
    """Return unprotected, non-default branches inactive before the cutoff.

    Reserved evidence/publication refs, open pull-request heads, and branches with
    missing activity evidence are retained. Results are ordered oldest first.

    Args:
        branches: Branch records returned by GitHub for the repository.
        open_heads: Branch names used by currently open pull requests.
        default_branch: Repository's default branch name, which must be retained.
        retention: Verified activity and closed-PR state used for stale selection.

    Returns:
        Unprotected stale branch records sorted by verified commit activity time.
    """
    stale: list[tuple[float, ApiJsonObject]] = []
    for branch in branches:
        name = branch.get("name")
        if (
            not isinstance(name, str)
            or is_reserved_branch(name, default_branch)
            or is_open_pr_evidence_branch(name, retention.open_pr_numbers)
            or name in open_heads
            or branch.get("protected") is not False
        ):
            continue
        commit = branch.get("commit")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str):
            continue
        activity = retention.activity_epochs.get(sha)
        if activity is None:
            continue
        closed_head_shas = retention.closed_pr_head_shas.get(name, set())
        if activity >= retention.cutoff_epoch and sha not in closed_head_shas:
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


def package_version_tags(version: ApiJsonObject) -> set[str] | None:
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


def package_version_activity_epoch(version: ApiJsonObject) -> float | None:
    """Use updated_at when present so a recently republished tag gets a grace period.

    Args:
        version: Container package version metadata from GitHub.

    Returns:
        Unix timestamp for the version's latest activity, or None.
    """
    activity = version.get("updated_at") or version.get("created_at")
    return epoch(activity) if isinstance(activity, str) else None


def stale_package_versions(
    versions: list[ApiJsonObject], protected_tags: set[str], cutoff_epoch: float
) -> list[ApiJsonObject]:
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


def _dockerfile_tag_batch(
    owner: str,
    repository_name: str,
    batch: list[str],
    load_json: Callable[..., ApiJsonValue],
) -> set[str]:
    """Resolve protected image tags for one bounded batch of commit SHAs.

    Args:
        owner: GitHub account or organization that owns the repository.
        repository_name: Repository containing the Dockerfile history.
        batch: Commit SHAs assigned to this bounded request.
        load_json: API loader compatible with the maintenance test seam.

    Returns:
        Image tags derived from the Dockerfile contents returned for the batch.

    Raises:
        RuntimeError: If GraphQL reports query errors or a SHA is malformed.
        TypeError: If GitHub returns protected Dockerfile data with an unexpected type.
    """
    aliases: dict[str, str] = {}
    fields: list[str] = []
    for index, sha in enumerate(batch):
        if len(sha) != COMMIT_SHA_HEX_LENGTH or any(char not in string.hexdigits for char in sha):
            msg = f"invalid protected commit SHA: {sha!r}"
            raise RuntimeError(msg)
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
        msg = "GitHub GraphQL returned a non-object response"
        raise TypeError(msg)
    if payload.get("errors"):
        msg = "GitHub GraphQL could not verify protected Dockerfile contents"
        raise RuntimeError(msg)
    data = payload.get("data")
    repository_data = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository_data, dict):
        msg = "GitHub GraphQL omitted the protected repository data"
        raise TypeError(msg)

    tags: set[str] = set()
    for alias, sha in aliases.items():
        blob = repository_data.get(alias)
        dockerfile_text = blob.get("text") if isinstance(blob, dict) else None
        if not isinstance(dockerfile_text, str):
            msg = f"Dockerfile content missing for protected ref {sha}"
            raise TypeError(msg)
        tags.add(pbd_validation_tag(dockerfile_text.encode("utf-8")))
    return tags


def dockerfile_tags_for_shas(
    repo: str,
    protected_shas: set[str],
    *,
    batch_size: int = DOCKERFILE_TAG_QUERY_BATCH_SIZE,
    fetch_json: Callable[..., ApiJsonValue] | None = None,
) -> set[str]:
    """Resolve protected Dockerfile tags using bounded GraphQL batches.

    Args:
        repo: Owner and repository name containing the Dockerfile history.
        protected_shas: Commit identifiers whose Dockerfile contents are protected.
        batch_size: Maximum number of commit objects queried at once.
        fetch_json: Optional CLI-compatible JSON loader for deterministic tests.

    Returns:
        Image tags derived from Dockerfile contents at all protected commits.

    Raises:
        ValueError: If the GraphQL batch size is not positive.
    """
    if batch_size <= 0:
        msg = "Dockerfile query batch size must be positive"
        raise ValueError(msg)
    if not protected_shas:
        return set()

    load_json = gh_json if fetch_json is None else fetch_json
    owner, repository_name = repo.split("/", maxsplit=1)
    ordered_shas = sorted(protected_shas)
    tags: set[str] = set()
    for offset in range(0, len(ordered_shas), batch_size):
        batch = ordered_shas[offset : offset + batch_size]
        tags.update(_dockerfile_tag_batch(owner, repository_name, batch, load_json))
    return tags


def _perform_package_cleanup(
    repo: str,
    protected_shas: set[str],
    cutoff_epoch: float,
    adapters: PackageCleanupCallbacks,
    progress: PackageCleanupProgress,
) -> ApiJsonObject:
    """Resolve protected tags and delete verified stale package versions.

    Args:
        repo: Owner and repository name containing the PBD package.
        protected_shas: Commit identifiers that keep corresponding image tags in use.
        cutoff_epoch: Unix timestamp marking the image retention boundary.
        adapters: Optional callbacks used for deterministic package-retention tests.
        progress: Mutable state used to preserve safe partial-progress reporting.

    Returns:
        Cleanup counts and a status describing the package-retention outcome.

    Raises:
        TypeError: If a package version has no integer identifier.
    """
    if not protected_shas:
        progress.result["status"] = "skipped_no_protected_refs"
        return progress.result

    resolve_tags = (
        dockerfile_tags_for_shas
        if adapters.dockerfile_tags_resolver is None
        else adapters.dockerfile_tags_resolver
    )
    load_api_items = (
        paginated_api_items if adapters.api_items_loader is None else adapters.api_items_loader
    )
    delete_api_resource = (
        gh_delete if adapters.delete_resource is None else adapters.delete_resource
    )
    protected_tags = resolve_tags(repo, protected_shas)
    progress.result["protected_tags"] = len(protected_tags)

    # The target is fixed by this repository. Encode the slash in the package-name path.
    # Namespace-wide discovery returns HTTP 400 with the workflow installation token.
    progress.phase = "list_package_versions"
    encoded_name = quote(PBD_PACKAGE_SUFFIX, safe="")
    versions = list(load_api_items(f"user/packages/container/{encoded_name}/versions"))
    progress.result["versions_seen"] = len(versions)
    stale = stale_package_versions(versions, protected_tags, cutoff_epoch)
    progress.result["pending"] = len(stale)
    selected = stale[:MAX_PACKAGE_VERSION_DELETIONS_PER_RUN]
    for version in selected:
        version_id = version.get("id")
        if not isinstance(version_id, int):
            msg = "GitHub returned a package version without an integer ID"
            raise TypeError(msg)
        progress.phase = f"delete_package_version_{version_id}"
        delete_api_resource(
            "api",
            "--method",
            "DELETE",
            f"user/packages/container/{encoded_name}/versions/{version_id}",
        )
        progress.deleted += 1
        progress.result["pending"] = len(stale) - progress.deleted

    progress.result["deleted"] = progress.deleted
    progress.result["pending"] = len(stale) - progress.deleted
    progress.result["status"] = "passed"
    return progress.result


def cleanup_pbd_package_versions(
    repo: str,
    protected_shas: set[str],
    cutoff_epoch: float,
    callbacks: PackageCleanupCallbacks | None = None,
) -> ApiJsonObject:
    """Prune old PBD image versions unused by main, open PRs, or retained/active runs.

    Args:
        repo: Owner and repository name containing the PBD package.
        protected_shas: Commit identifiers that keep corresponding image tags in use.
        cutoff_epoch: Unix timestamp marking the image retention boundary.
        callbacks: Optional API adapters for deterministic package-retention testing.

    Returns:
        Cleanup counts and a status describing the package-retention outcome.
    """
    progress = PackageCleanupProgress(
        result={
            "status": "not_started",
            "versions_seen": 0,
            "deleted": 0,
            "pending": 0,
            "protected_tags": 0,
        },
    )
    adapters = callbacks if callbacks is not None else PackageCleanupCallbacks()
    try:
        return _perform_package_cleanup(repo, protected_shas, cutoff_epoch, adapters, progress)
    except GitHubApiError as exc:
        detail = str(exc).strip().replace("\n", " ")[:HTTP_DETAIL_LENGTH]
        progress.result["deleted"] = progress.deleted
        progress.result["status"] = (
            "permission_denied" if "403" in detail or "forbidden" in detail.lower() else "api_error"
        )
        progress.result["error"] = f"{progress.phase}: {detail}"
        return progress.result
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        progress.result["deleted"] = progress.deleted
        progress.result["status"] = "skipped_unverifiable"
        progress.result["error"] = str(exc)[:HTTP_DETAIL_LENGTH]
        return progress.result


def _open_pull_request_refs(repo: str) -> tuple[set[str], set[str], set[int]]:
    """Collect open head refs, commit SHAs, and PR numbers protected by open pull requests.

    Args:
        repo: Full owner/repository name queried through GitHub.

    Returns:
        Open head branch names, head commit SHAs, and open pull-request numbers.
    """
    pull_requests = list(paginated_api_items(f"repos/{repo}/pulls?state=open"))
    open_heads: set[str] = set()
    protected_shas: set[str] = set()
    open_pr_numbers: set[int] = set()
    for pull_request in pull_requests:
        number = pull_request.get("number")
        if isinstance(number, int):
            open_pr_numbers.add(number)
        head = pull_request.get("head")
        if isinstance(head, dict):
            ref, sha = head.get("ref"), head.get("sha")
            if isinstance(ref, str):
                open_heads.add(ref)
            if isinstance(sha, str):
                protected_shas.add(sha)
    return open_heads, protected_shas, open_pr_numbers


def _default_branch_for_repo(repo: str) -> str:
    """Resolve the repository's declared default branch or fail closed.

    Args:
        repo: Full owner/repository name queried through GitHub.

    Returns:
        The verified default branch name.

    Raises:
        TypeError: If the response does not include a string default branch.
    """
    repository_data = gh_json("api", f"repos/{repo}")
    default_branch = (
        repository_data.get("default_branch") if isinstance(repository_data, dict) else None
    )
    if not isinstance(default_branch, str):
        msg = "GitHub repository metadata omitted the default branch"
        raise TypeError(msg)
    return default_branch


def _branch_head_shas(
    branches: list[ApiJsonObject],
    open_heads: set[str],
    open_pr_numbers: set[int],
    default_branch: str,
) -> set[str]:
    """Collect deletable branch head SHAs before querying activity dates.

    Args:
        branches: Branch records returned by GitHub.
        open_heads: Branch names used by open pull requests.
        default_branch: Branch name that must never be selected for deletion.

    Returns:
        Full commit SHAs for unprotected candidate branch heads.
    """
    branch_shas: set[str] = set()
    for branch in branches:
        name = branch.get("name")
        commit = branch.get("commit")
        if (
            not isinstance(name, str)
            or is_reserved_branch(name, default_branch)
            or is_open_pr_evidence_branch(name, open_pr_numbers)
            or name in open_heads
            or branch.get("protected") is not False
        ):
            continue
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if isinstance(sha, str):
            branch_shas.add(sha)
    return branch_shas


def _cleanup_stale_branches(
    repo: str,
    open_heads: set[str],
    open_pr_numbers: set[int],
    default_branch: str,
    branch_cutoff: float,
) -> tuple[int, int, int]:
    """Verify, select, and delete the bounded set of stale branch refs.

    Args:
        repo: Full owner/repository name queried through GitHub.
        open_heads: Branch names used by open pull requests.
        default_branch: Branch name that must never be selected for deletion.
        branch_cutoff: Unix timestamp before which a branch is considered stale.

    Returns:
        Number of branches seen, deleted branches, and stale branches still pending.

    Raises:
        TypeError: If a selected branch is missing its name.
    """
    branches = list(paginated_api_items(f"repos/{repo}/branches"))
    branch_shas = _branch_head_shas(branches, open_heads, open_pr_numbers, default_branch)
    # Resolve all candidate activity before deleting anything; incomplete GraphQL data
    # aborts the branch pass instead of treating an unknown branch as stale.
    activity_epochs = branch_activity_epochs(repo, branch_shas)
    lookup = ClosedPullRequestLookup(
        repo=repo,
        open_heads=open_heads,
        default_branch=default_branch,
        activity_epochs=activity_epochs,
        cutoff_epoch=branch_cutoff,
        open_pr_numbers=open_pr_numbers,
    )
    closed_pr_heads = closed_pr_head_shas_by_branch(branches, lookup)
    retention = BranchRetentionPolicy(
        activity_epochs=activity_epochs,
        cutoff_epoch=branch_cutoff,
        closed_pr_head_shas=closed_pr_heads,
        open_pr_numbers=open_pr_numbers,
    )
    stale_branches = stale_unprotected_branches(branches, open_heads, default_branch, retention)
    selected_branches = stale_branches[:MAX_BRANCH_DELETIONS_PER_RUN]
    removed_branches = 0
    for branch in selected_branches:
        name = branch.get("name")
        if not isinstance(name, str):
            msg = "GitHub returned a stale branch without a name"
            raise TypeError(msg)
        gh_delete("api", "--method", "DELETE", f"repos/{repo}/git/refs/heads/{name}")
        removed_branches += 1
    return len(branches), removed_branches, len(stale_branches) - len(selected_branches)



def stale_completed_workflow_runs(
    repo: str,
    cutoff_epoch: float,
    *,
    api_items_loader: Callable[..., Iterator[ApiJsonObject]] | None = None,
    depth: int = 0,
) -> list[ApiJsonObject]:
    """Collect all completed runs older than a cutoff, splitting below GitHub's 1,000-result cap."""
    if depth > MAX_RUN_QUERY_SPLITS:
        raise RuntimeError("stale workflow-run inventory exceeded the safe date-split depth")
    load_api_items = paginated_api_items if api_items_loader is None else api_items_loader
    cutoff = datetime.fromtimestamp(cutoff_epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    endpoint = f"repos/{repo}/actions/runs?status=completed&created=%3C{cutoff}"
    inventory = list(load_api_items(endpoint, collection_key="workflow_runs"))
    stale = stale_completed_runs(inventory, cutoff_epoch)
    if len(inventory) < MAX_RUN_RESULTS_PER_API_QUERY:
        return stale
    if not stale:
        raise RuntimeError("GitHub returned a capped run page without verifiable creation dates")
    oldest_created_at = stale[0].get("created_at")
    if not isinstance(oldest_created_at, str):
        raise RuntimeError("oldest completed workflow run has no verifiable creation date")
    next_cutoff = epoch(oldest_created_at)
    if next_cutoff >= cutoff_epoch:
        raise RuntimeError("stale workflow-run inventory could not advance its date boundary")
    older = stale_completed_workflow_runs(
        repo, next_cutoff, api_items_loader=load_api_items, depth=depth + 1
    )
    combined_by_id: dict[int, ApiJsonObject] = {}
    for run in older + stale:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise RuntimeError("GitHub returned a workflow run without an integer ID")
        combined_by_id[run_id] = run
    combined = list(combined_by_id.values())
    combined.sort(key=lambda run: epoch(str(run["created_at"])))
    return combined


def cleanup_workflow_runs_to_cap(
    repo: str,
    *,
    keep: int = MAX_RETAINED_WORKFLOW_RUNS,
    now: datetime | None = None,
    total_count_loader: Callable[..., ApiJsonValue] | None = None,
    completed_runs_loader: Callable[[str, float], list[ApiJsonObject]] | None = None,
    delete_resource: Callable[..., None] | None = None,
) -> dict[str, int]:
    """Keep the newest completed runs up to a repository-wide cap; active runs are never deleted."""
    if keep < 0:
        raise ValueError("workflow-run retention cap must be non-negative")
    load_total = gh_json if total_count_loader is None else total_count_loader
    load_candidates = (
        stale_completed_workflow_runs if completed_runs_loader is None else completed_runs_loader
    )
    delete_api_resource = gh_delete if delete_resource is None else delete_resource
    payload = load_total("api", f"repos/{repo}/actions/runs?status=completed&per_page=1")
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned an invalid workflow-run count response")
    total_count = payload.get("total_count")
    if not isinstance(total_count, int) or total_count < 0:
        raise RuntimeError("GitHub returned an invalid total_count for workflow runs")
    needed = max(0, total_count - keep)
    if needed == 0:
        return {
            "total_before": total_count,
            "keep": keep,
            "deleted": 0,
            "remaining_estimate": total_count,
            "pending": 0,
        }
    clock = datetime.now(UTC) if now is None else now.astimezone(UTC)
    candidates = load_candidates(repo, clock.timestamp())
    candidates.sort(key=lambda run: epoch(str(run.get("created_at", ""))))
    if len(candidates) < needed:
        raise RuntimeError(
            f"only {len(candidates)} completed runs are safely enumerable; "
            f"{needed} must be removed to reach the {keep}-run cap"
        )
    delete_count = min(needed, MAX_RUN_CAP_DELETIONS_PER_RUN)
    selected = candidates[:delete_count]
    run_ids: list[int] = []
    for run in selected:
        run_id = run.get("id")
        created_at = run.get("created_at")
        if not isinstance(run_id, int) or not isinstance(created_at, str):
            raise RuntimeError("GitHub returned an unverifiable run deletion candidate")
        run_ids.append(run_id)
    if len(set(run_ids)) != len(run_ids):
        raise RuntimeError("completed workflow-run inventory contains duplicate IDs")

    def delete_run(run_id: int) -> None:
        delete_api_resource("api", "--method", "DELETE", f"repos/{repo}/actions/runs/{run_id}")

    failures: list[tuple[int, str]] = []
    deleted = 0
    with ThreadPoolExecutor(max_workers=MAX_RUN_DELETE_WORKERS) as executor:
        futures = {executor.submit(delete_run, run_id): run_id for run_id in run_ids}
        for future in as_completed(futures):
            run_id = futures[future]
            try:
                future.result()
                deleted += 1
            except Exception as exc:
                failures.append((run_id, str(exc)[:200]))
    if failures:
        sample = "; ".join(f"{run_id}: {error}" for run_id, error in failures[:5])
        raise RuntimeError(
            f"failed to delete {len(failures)} workflow runs after deleting {deleted}: {sample}"
        )
    pending = max(0, needed - deleted)
    return {
        "total_before": total_count,
        "keep": keep,
        "deleted": deleted,
        "remaining_estimate": total_count - deleted,
        "pending": pending,
    }


def _cleanup_stale_completed_runs(
    repo: str, run_cutoff: float
) -> tuple[list[ApiJsonObject], int, int]:
    """Delete a bounded set of old completed workflow runs.

    Args:
        repo: Full owner/repository name queried through GitHub.
        run_cutoff: Unix timestamp before which a completed run is stale.

    Returns:
        All completed runs, deleted-run count, and stale runs still pending.

    Raises:
        TypeError: If a selected completed run is missing its integer ID.
    """
    runs = list(
        paginated_api_items(
            f"repos/{repo}/actions/runs?status=completed", collection_key="workflow_runs"
        )
    )
    stale_runs = stale_completed_runs(runs, run_cutoff)
    selected_runs = stale_runs[:MAX_RUN_DELETIONS_PER_RUN]
    for run in selected_runs:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            msg = "GitHub returned a completed workflow run without an integer ID"
            raise TypeError(msg)
        gh_delete("api", "--method", "DELETE", f"repos/{repo}/actions/runs/{run_id}")
    pending = len(stale_runs) - len(selected_runs)
    return runs, len(selected_runs), pending


def _protected_package_shas(
    repo: str,
    protected_shas: set[str],
    completed_runs: list[ApiJsonObject],
    run_cutoff: float,
) -> set[str]:
    """Collect image tags' protected commits from main and active or retained runs.

    Args:
        repo: Full owner/repository name queried through GitHub.
        protected_shas: Commit SHAs already protected by open pull requests.
        completed_runs: Completed workflow run records used for retention.
        run_cutoff: Unix timestamp for the active completed-run retention window.

    Returns:
        Protected commit SHAs, including main and active or retained run heads.
    """
    protected = set(protected_shas)
    main_ref = gh_json("api", f"repos/{repo}/git/ref/heads/main")
    if isinstance(main_ref, dict):
        main_object = main_ref.get("object")
        main_sha = main_object.get("sha") if isinstance(main_object, dict) else None
        if isinstance(main_sha, str):
            protected.add(main_sha)
    for run in completed_runs:
        created_at, sha = run.get("created_at"), run.get("head_sha")
        if isinstance(created_at, str) and epoch(created_at) >= run_cutoff and isinstance(sha, str):
            protected.add(sha)
    for status in ACTIVE_RUN_STATUSES:
        active_runs = paginated_api_items(
            f"repos/{repo}/actions/runs?status={status}", collection_key="workflow_runs"
        )
        for run in active_runs:
            sha = run.get("head_sha")
            if isinstance(sha, str):
                protected.add(sha)
    return protected


def main() -> int:
    """Run repository retention cleanup and report a non-secret summary.

    GitHub CLI credentials and the repository name come from the workflow environment.
    Branch deletion is fail-closed: all candidate activity is verified before deletion.
    Package cleanup reports unverifiable states instead of deleting possibly active images.

    Returns:
        Zero after the retention pass completes, including recoverable package-cleanup errors.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--branches-and-runs-only",
        action="store_true",
        help="prune stale branches and completed Actions runs without package cleanup",
    )
    args = parser.parse_args()
    repo = os.environ["REPO"]
    now = datetime.now(UTC)
    branch_cutoff = (now - timedelta(days=BRANCH_RETENTION_DAYS)).timestamp()
    run_cutoff = (now - timedelta(days=RUN_RETENTION_DAYS)).timestamp()
    open_heads, protected_shas, open_pr_numbers = _open_pull_request_refs(repo)
    default_branch = _default_branch_for_repo(repo)
    if args.branches_and_runs_only:
        branches_seen, removed_branches, branch_pending = _cleanup_stale_branches(
            repo, open_heads, open_pr_numbers, default_branch, branch_cutoff
        )
        run_result = cleanup_workflow_runs_to_cap(repo)
        sys.stdout.write(
            "maintenance-cleanup=passed mode=branches-and-runs-only "
            f"branches_seen={branches_seen} removed_branches={removed_branches} "
            f"stale_branches_pending={branch_pending} "
            f"completed_runs_before={run_result['total_before']} keep_completed_runs={run_result['keep']} "
            f"removed_runs={run_result['deleted']} "
            f"remaining_completed_runs={run_result['remaining_estimate']} "
            f"runs_pending={run_result['pending']}\n"
        )
        return 0
    branches_seen, removed_branches, stale_branches_pending = _cleanup_stale_branches(
        repo, open_heads, open_pr_numbers, default_branch, branch_cutoff
    )
    completed_runs, removed_runs, stale_runs_pending = _cleanup_stale_completed_runs(
        repo, run_cutoff
    )
    protected_shas = _protected_package_shas(repo, protected_shas, completed_runs, run_cutoff)
    package_result = cleanup_pbd_package_versions(repo, protected_shas, run_cutoff)
    sys.stdout.write(
        "maintenance-cleanup=passed "
        f"branches_seen={branches_seen} "
        f"removed_branches={removed_branches} "
        f"stale_branches_pending={stale_branches_pending} "
        f"removed_runs={removed_runs} stale_runs_pending={stale_runs_pending} "
        f"package_cleanup={package_result['status']} "
        f"package_versions_seen={package_result['versions_seen']} "
        f"removed_package_versions={package_result['deleted']} "
        f"stale_package_versions_pending={package_result['pending']}\n"
    )
    if package_result.get("error"):
        sys.stdout.write(f"package_cleanup_note={package_result['error']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
