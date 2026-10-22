# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the repository's single-source CI configuration contracts."""

import json
import tomllib
from pathlib import Path

from tests.support.assertions import require, require_not_none
from tools.ci.run_freecad import configured_timeout_seconds

ROOT = Path(__file__).resolve().parents[1]


def test_simulation_quality_readiness_has_native_gui_and_screenshot_gates() -> None:
    """The readiness checklist is exercised in FreeCAD and both rendered states are validated."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    validator = (ROOT / "tools" / "ci" / "validate_acceptance.py").read_text(encoding="utf-8")
    acceptance = (ROOT / "tests" / "freecad_simulation_quality_acceptance.py").read_text(
        encoding="utf-8"
    )
    gui_matrix = workflow.split("  gui-simple:", 1)[1].split("  gui-tunic-visual:", 1)[0]

    require(
        condition="case: simulation-quality" in gui_matrix,
        message="simulation quality readiness failed at line 24.",
    )
    require(
        condition="tests/freecad_simulation_quality_acceptance.py" in gui_matrix,
        message="simulation quality readiness failed at line 25.",
    )
    require(
        condition="python3 tools/ci/validate_acceptance.py simulation-quality" in gui_matrix,
        message="simulation quality readiness failed at line 26.",
    )
    require(
        condition=(
            '"simulation-quality": Path("artifacts/simulation-quality-readiness.png")' in validator
        ),
        message="simulation quality readiness failed at line 27.",
    )
    stale_image_contract = (
        '"simulation-quality": (Path("artifacts/simulation-quality-stale-target.png"),)'
    )
    require(
        condition=stale_image_contract in validator,
        message="simulation quality readiness failed at line 31.",
    )
    require(
        condition="simulation-quality-readiness.png" in acceptance,
        message="simulation quality readiness failed at line 32.",
    )
    require(
        condition="simulation-quality-stale-target.png" in acceptance,
        message="simulation quality readiness failed at line 33.",
    )
    require(
        condition='property("workflowState") != "blocked"' in acceptance,
        message="simulation quality readiness failed at line 34.",
    )
    require(
        condition='if __name__ == "__main__"' not in acceptance,
        message="simulation quality readiness failed at line 35.",
    )
    require(
        condition='_progress("entrypoint-entered")' in acceptance,
        message="simulation quality readiness failed at line 36.",
    )
    require(
        condition="os._exit(0)" in acceptance,
        message="simulation quality readiness failed at line 37.",
    )
    require(
        condition="os._exit(1)" in acceptance,
        message="simulation quality readiness failed at line 38.",
    )


def test_freecad_timeout_is_positive_and_declared_once() -> None:
    """The application timeout comes from the project configuration."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    configured = tomllib.loads(pyproject)["tool"]["freecad_cloth"]["ci"][
        "freecad_application_timeout_seconds"
    ]
    require(
        condition=configured == 120,
        message="freecad timeout is positive  failed at line 48.",
    )
    require(
        condition=configured_timeout_seconds() == configured,
        message="freecad timeout is positive  failed at line 49.",
    )
    require(
        condition=pyproject.count("freecad_application_timeout_seconds") == 1,
        message="freecad timeout is positive  failed at line 50.",
    )


def test_ci_consumers_do_not_duplicate_the_application_timeout() -> None:
    """Workflow and action surfaces delegate to the project configuration."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    action = (ROOT / ".github" / "actions" / "freecad-test" / "action.yml").read_text(
        encoding="utf-8"
    )
    container_action = (
        ROOT / ".github" / "actions" / "freecad-container" / "action.yml"
    ).read_text(encoding="utf-8")
    runner = (ROOT / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")

    simulation_ladder = workflow.split("  simulation-ladder:", 1)[1].split("  python:", 1)[0]
    require(
        condition=workflow.count("timeout-seconds:") == 1,
        message="ci consumers do not duplicat failed at line 67.",
    )
    require(
        condition='timeout-seconds: "360"' in simulation_ladder,
        message="ci consumers do not duplicat failed at line 68.",
    )
    require(
        condition="freecad_application_timeout_seconds" not in workflow,
        message="ci consumers do not duplicat failed at line 69.",
    )
    require(
        condition='default: "120"' in action,
        message="ci consumers do not duplicat failed at line 70.",
    )
    require(
        condition="timeout-seconds: ${{ inputs.timeout-seconds }}" in action,
        message="ci consumers do not duplicat failed at line 71.",
    )
    require(
        condition="FREECAD_APPLICATION_TIMEOUT_SECONDS=" in action,
        message="ci consumers do not duplicat failed at line 72.",
    )
    require(
        condition='default: "120"' in container_action,
        message="ci consumers do not duplicat failed at line 73.",
    )
    require(
        condition="maximum 360 seconds" in container_action,
        message="ci consumers do not duplicat failed at line 74.",
    )
    require(
        condition='if [ "$timeout_seconds" -gt 360 ]; then' in container_action,
        message="ci consumers do not duplicat failed at line 75.",
    )
    require(
        condition="FREECAD_APPLICATION_TIMEOUT_SECONDS" in runner,
        message="ci consumers do not duplicat failed at line 76.",
    )
    require(
        condition="420" not in container_action,
        message="ci consumers do not duplicat failed at line 77.",
    )
    require(
        condition="--no-deps -e ." in action,
        message="ci consumers do not duplicat failed at line 78.",
    )
    require(
        condition='"numpy>=1.26,<3"' in action,
        message="ci consumers do not duplicat failed at line 79.",
    )
    require(
        condition='"pydantic>=2.11,<3"' in action,
        message="ci consumers do not duplicat failed at line 80.",
    )
    require(
        condition='"Pillow>=11,<13"' in action,
        message="ci consumers do not duplicat failed at line 81.",
    )
    require(
        condition="install --disable-pip-version-check -e ." not in action,
        message="ci consumers do not duplicat failed at line 82.",
    )
    require(
        condition="configured_timeout_seconds()" in runner,
        message="ci consumers do not duplicat failed at line 83.",
    )
    require(
        condition="--extra-index-url https://download.pytorch.org/whl/cpu" in workflow,
        message="ci consumers do not duplicat failed at line 84.",
    )
    require(
        condition='"torch==2.8.0+cpu"' in workflow,
        message="ci consumers do not duplicat failed at line 85.",
    )


def test_timeout_contract_is_documented() -> None:
    """The human documentation points to the authoritative configuration."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "developers" / "CI_CONFIGURATION.md").read_text(
        encoding="utf-8"
    )

    require(
        condition="CI configuration" in docs,
        message="timeout contract is document failed at line 95.",
    )
    require(
        condition="pyproject.toml" in configuration,
        message="timeout contract is document failed at line 96.",
    )
    require(
        condition="freecad_application_timeout_seconds" in configuration,
        message="timeout contract is document failed at line 97.",
    )


def test_maintenance_cleanup_receives_github_cli_token() -> None:
    """The scheduled cleanup has the token needed for gh API reads and deletes."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    cleanup = workflow.split("  maintenance-cleanup:", 1)[1].split("  artifact-budget:", 1)[0]

    require(
        condition="GH_TOKEN: ${{ github.token }}" in cleanup,
        message="maintenance cleanup receives failed at line 107.",
    )
    require(
        condition="actions: write" in cleanup,
        message="maintenance cleanup receives failed at line 108.",
    )
    require(
        condition="contents: write" in cleanup,
        message="maintenance cleanup receives failed at line 109.",
    )
    require(
        condition="packages: write" in cleanup,
        message="maintenance cleanup receives failed at line 110.",
    )


def test_one_shot_retention_run_bypasses_runner_fallback() -> None:
    """Retention can finish on GitHub-hosted runners without watchdog cancellation."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    activation = (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' && "
        "startsWith(github.event.head_commit.message, 'RUN MAINTENANCE CLEANUP')"
    )
    readiness = workflow.split("  local_runner_readiness:", 1)[1].split("  runner_watchdog:", 1)[0]
    watchdog = workflow.split("  runner_watchdog:", 1)[1].split("  pbd_validation_image:", 1)[0]
    image = workflow.split("  pbd_validation_image:", 1)[1].split("  diagnostic-pbd-contact:", 1)[0]
    artifact_budget = workflow.split("  artifact-budget:", 1)[1].split("  benchmark:", 1)[0]

    require(
        condition=f"!({activation})" in readiness,
        message="one shot retention run bypas failed at line 127.",
    )
    require(
        condition=f"!({activation})" in watchdog,
        message="one shot retention run bypas failed at line 128.",
    )
    require(
        condition=f"!({activation})" in image,
        message="one shot retention run bypas failed at line 129.",
    )
    require(
        condition=(
            "!startsWith(github.event.head_commit.message, 'RUN MAINTENANCE CLEANUP')"
            in artifact_budget
        ),
        message="one shot retention run bypasses the runner fallback failed at line 130.",
    )


def test_dead_code_gate_scans_the_full_static_core_inventory() -> None:
    """The dead-code gate must include unchanged modules, not only PR diffs."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("      - name: Python and architecture checks", 1)[1].split(
        "      - name: Workflow linters", 1
    )[0]

    require(
        condition="python tools/check_dead_code.py" in quality,
        message="dead code gate scans the ful failed at line 145.",
    )
    require(
        condition="xargs -r python tools/check_dead_code.py" not in quality,
        message="dead code gate scans the ful failed at line 146.",
    )
    require(
        condition="changed-python.txt" not in quality,
        message="dead code gate scans the ful failed at line 147.",
    )


def test_pbd_validation_tag_matches_workflow_dockerfile_hash() -> None:
    """Verify the PBD validation image tag matches the Dockerfile content hash."""
    from hashlib import sha256

    from tools.ci.maintenance_cleanup import pbd_validation_tag

    contents = b"FROM freecad:stable\n"
    require(
        condition=pbd_validation_tag(contents) == sha256(contents).hexdigest()[:32],
        message="pbd validation tag matches w failed at line 156.",
    )


def test_dockerfile_tags_for_shas_batches_graphql_queries() -> None:
    """Verify protected Dockerfile tags are resolved in bounded GraphQL batches."""
    import re
    from hashlib import sha256

    from tools.ci import maintenance_cleanup

    contents_by_sha = {
        "1" * 40: b"FROM freecad:one\n",
        "2" * 40: b"FROM freecad:two\n",
        "3" * 40: b"FROM freecad:three\n",
        "4" * 40: b"FROM freecad:four\n",
        "5" * 40: b"FROM freecad:five\n",
    }
    queries = []

    def fake_gh_json(*args: str) -> dict[str, object]:
        """Fail closed if GitHub omits a requested commit activity object.
        Resolve distinct branch commit timestamps in bounded GraphQL batches.
        Return a mock GraphQL response for protected Dockerfile blobs.
        
        Args:
            args: GitHub CLI request arguments, including the GraphQL query.
        """
        Returns:
            Response mapping with protected repository blob contents.
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="fake gh json failed at line 175.",
        )
        query_arg = args[3]
        require(
            condition=query_arg.startswith("query="),
            message="fake gh json failed at line 177.",
        )
        query = query_arg.removeprefix("query=")
        aliases = re.findall(
            r'(file\d+): object\(expression: "([0-9a-f]{40}):docker/freecad-ci/Dockerfile"\)',
            query,
        )
        require(
            condition=bool(aliases),
            message="fake gh json failed at line 183.",
        )
        queries.append(query)
        return {
            "data": {
                "repository": {
                    alias: {"text": contents_by_sha[sha].decode("utf-8")} for alias, sha in aliases
                }
            }
        }

    tags = maintenance_cleanup.dockerfile_tags_for_shas(
        "owner/repo", set(contents_by_sha), batch_size=2, fetch_json=fake_gh_json
    )

    require(
        condition=(
            tags == {sha256(contents).hexdigest()[:32] for contents in contents_by_sha.values()}
        ),
        message="dockerfile tags for shas bat failed at line 197.",
    )
    require(
        condition=len(queries) == 3,
        message="dockerfile tags for shas bat failed at line 198.",
    )


def test_dockerfile_tags_fail_closed_when_graphql_omits_a_protected_blob() -> None:
    """Reject cleanup when a protected Dockerfile blob is missing."""
    from tools.ci import maintenance_cleanup

    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return a mock GraphQL response for a missing protected Dockerfile blob.
        
        Args:
            args: GitHub CLI request arguments, including the GraphQL query.
        
        Returns:
            Response mapping with the queried protected blob."""
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="fake gh json failed at line 205.",
        )
        return {"data": {"repository": {"file0": None}}}

    try:
        maintenance_cleanup.dockerfile_tags_for_shas(
            "owner/repo", {"1" * 40}, fetch_json=fake_gh_json
        )
    except RuntimeError as exc:
        require(
            condition="Dockerfile content missing" in str(exc),
            message="dockerfile tags fail closed  failed at line 213.",
        )
    else:
        msg = "missing protected Dockerfile content must fail closed"
        raise AssertionError(msg)


def test_package_cleanup_uses_configured_authenticated_user_package_endpoint() -> None:
    """Use the authenticated user's package endpoint for image cleanup."""
    from collections.abc import Iterator

    from tools.ci import maintenance_cleanup

    requested_endpoints: list[str] = []
    deleted_arguments: list[tuple[str, ...]] = []

    def fake_resolve_tags(repo_name: str, protected_shas: set[str]) -> set[str]:
        """Return protected Dockerfile tags for the requested repository state.
        
        Args:
            repo_name: Repository whose protected Dockerfiles are resolved.
            protected_shas: Commit SHAs that must remain protected.
        
        Returns:
            Set of tags that identify protected Dockerfile contents."""
        require(
            condition=repo_name == "Uhrendoktor/freecad-cloth",
            message="fake resolve tags failed at line 228.",
        )
        require(
            condition=protected_shas == {"1" * 40},
            message="fake resolve tags failed at line 229.",
        )
        return {"protected-dockerfile-tag"}

    def fake_load_items(endpoint: str) -> Iterator[dict[str, object]]:
        """Return mocked API records for the requested endpoint.
        
        Args:
            endpoint: GitHub API collection endpoint to emulate.
        
        Returns:
            Iterator over package records from the requested endpoint."""
        requested_endpoints.append(endpoint)
        if endpoint == "user/packages/container/freecad-cloth%2Fpbd-validation/versions":
            return iter([])
        msg = f"unexpected package API endpoint: {endpoint}"
        raise AssertionError(msg)

    def fake_delete(*args: str) -> None:
        """Record an attempted GitHub API deletion.
        
        Args:
            args: Resource deletion arguments supplied by the cleanup routine."""
        deleted_arguments.append(args)

    result = maintenance_cleanup.cleanup_pbd_package_versions(
        "Uhrendoktor/freecad-cloth",
        {"1" * 40},
        maintenance_cleanup.epoch("2026-09-15T00:00:00Z"),
        dockerfile_tags_resolver=fake_resolve_tags,
        api_items_loader=fake_load_items,
        delete_resource=fake_delete,
    )

    require(
        condition=result["status"] == "passed",
        message="package cleanup uses configu failed at line 251.",
    )
    require(
        condition=result["versions_seen"] == 0,
        message="package cleanup uses configu failed at line 252.",
    )
    require(
        condition=result["deleted"] == 0,
        message="package cleanup uses configu failed at line 253.",
    )
    require(
        condition=(
            requested_endpoints == [
                "user/packages/container/freecad-cloth%2Fpbd-validation/versions"
            ]
        ),
        message="package cleanup uses configu failed at line 254.",
    )
    require(
        condition=deleted_arguments == [],
        message="package cleanup uses configu failed at line 257.",
    )


def test_stale_package_versions_keep_protected_recent_and_unverifiable_versions() -> None:
    """Keep protected, recent and unverifiable package versions out of deletion candidates."""
    from tools.ci.maintenance_cleanup import stale_package_versions

    versions = [
        {
            "id": 1,
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-01T00:00:00Z",
            "metadata": {"container": {"tags": ["old-dockerfile-tag"]}},
        },
        {
            "id": 2,
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-01T00:00:00Z",
            "metadata": {"container": {"tags": ["protected-dockerfile-tag"]}},
        },
        {
            "id": 3,
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-10-01T00:00:00Z",
            "metadata": {"container": {"tags": ["recently-updated-tag"]}},
        },
        {"id": 4, "created_at": "2026-08-01T00:00:00Z"},
    ]
    cutoff = 1_789_430_400  # 2026-09-15T00:00:00Z

    stale = stale_package_versions(versions, {"protected-dockerfile-tag"}, cutoff)

    require(
        condition=[version["id"] for version in stale] == [1],
        message="stale package versions keep  failed at line 288.",
    )


def test_package_cleanup_queries_configured_pbd_versions_without_namespace_listing() -> None:
    """Delete stale package versions using only the configured package endpoint."""
    from collections.abc import Iterator

    from tools.ci import maintenance_cleanup

    endpoint = "user/packages/container/freecad-cloth%2Fpbd-validation/versions"
    endpoints: list[str] = []
    deleted: list[tuple[str, ...]] = []

    def fake_resolve_tags(_repo_name: str, _protected_shas: set[str]) -> set[str]:
        """Return a stable protected tag set for this package-cleanup test.
        
        Args:
            _repo_name: Repository name ignored by this controlled fake.
            _protected_shas: Protected commits ignored by this controlled fake.
        
        Returns:
            Set containing the single tag kept by the test."""
        return {"current-tag"}

    def fake_load_items(requested_endpoint: str) -> Iterator[dict[str, object]]:
        """Record a request and provide the configured stale package version.
        
        Args:
            requested_endpoint: API endpoint requested by the cleanup routine.
        
        Returns:
            Iterator containing the configured stale package version."""
        endpoints.append(requested_endpoint)
        if requested_endpoint != endpoint:
            msg = f"unexpected package API endpoint: {requested_endpoint}"
            raise AssertionError(msg)
        return iter(
            [
                {
                    "id": 11,
                    "created_at": "2026-08-01T00:00:00Z",
                    "updated_at": "2026-08-01T00:00:00Z",
                    "metadata": {"container": {"tags": ["old-unreferenced-tag"]}},
                }
            ]
        )

    def fake_delete(*args: str) -> None:
        """Record an attempted deletion of a stale package version.
        
        Args:
            args: Resource deletion arguments supplied by the cleanup routine."""
        deleted.append(args)

    result = maintenance_cleanup.cleanup_pbd_package_versions(
        "example-owner/repo",
        {"protected-sha"},
        maintenance_cleanup.epoch("2026-09-15T00:00:00Z"),
        dockerfile_tags_resolver=fake_resolve_tags,
        api_items_loader=fake_load_items,
        delete_resource=fake_delete,
    )

    require(
        condition=endpoints == [endpoint],
        message="package cleanup queries conf failed at line 331.",
    )
    require(
        condition=result["status"] == "passed",
        message="package cleanup queries conf failed at line 332.",
    )
    require(
        condition=result["versions_seen"] == 1,
        message="package cleanup queries conf failed at line 333.",
    )
    require(
        condition=result["deleted"] == 1,
        message="package cleanup queries conf failed at line 334.",
    )
    require(
        condition=(
            deleted == [
                (
                    "api",
                    "--method",
                    "DELETE",
                    "user/packages/container/freecad-cloth%2Fpbd-validation/versions/11",
                )
            ]
        ),
        message="package cleanup queries conf failed at line 335.",
    )


def test_maintenance_cleanup_paginates_until_a_short_page() -> None:
    """Read all cleanup API pages and stop on the first short page."""
    from tools.ci import maintenance_cleanup

    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}],
    }
    requested_pages = []

    def fake_gh_json(*args: str) -> dict[str, list[dict[str, int]]]:
        """Return mock paginated GitHub API responses.
        
        Args:
            args: GitHub CLI command and endpoint arguments.
        
        Returns:
            Mapping containing the requested page of integer-ID records."""
        endpoint = args[1]
        page = int(endpoint.rsplit("page=", maxsplit=1)[1])
        requested_pages.append(page)
        return {"workflow_runs": pages[page]}

    items = list(
        maintenance_cleanup.paginated_api_items(
            "repos/example/repo/actions/runs?status=completed",
            collection_key="workflow_runs",
            page_size=2,
            fetch_json=fake_gh_json,
        )
    )

    require(
        condition=items == [{"id": 1}, {"id": 2}, {"id": 3}],
        message="maintenance cleanup paginate failed at line 369.",
    )
    require(
        condition=requested_pages == [1, 2],
        message="maintenance cleanup paginate failed at line 370.",
    )


def test_maintenance_cleanup_prefers_committer_date_for_branch_activity() -> None:
    """Prefer a commit's committer date when determining branch activity age."""
    from tools.ci import maintenance_cleanup

    commit_data = {
        "author": {"date": "2020-01-01T00:00:00Z"},
        "committer": {"date": "2026-10-01T00:00:00Z"},
    }

    activity = maintenance_cleanup.branch_activity_epoch(commit_data)
    cutoff = maintenance_cleanup.epoch("2026-09-26T00:00:00Z")

    activity = require_not_none(
        activity,
        message="maintenance cleanup prefers  failed at line 384.",
    )
    require(
        condition=activity > cutoff,
        message="maintenance cleanup prefers  failed at line 385.",
    )


def test_maintenance_cleanup_falls_back_to_author_date_when_needed() -> None:
    """Use the author date when the committer date cannot be parsed."""
    from tools.ci import maintenance_cleanup

    commit_data = {"author": {"date": "2026-10-01T00:00:00Z"}}

    require(
        condition=(
            maintenance_cleanup.branch_activity_epoch(commit_data) == maintenance_cleanup.epoch(
                "2026-10-01T00:00:00Z"
            )
        ),
        message="maintenance cleanup falls ba failed at line 393.",
    )


def test_branch_activity_epochs_resolve_unique_heads_in_bounded_batches() -> None:
    """import re"""

    from tools.ci import maintenance_cleanup

    dates_by_sha: dict[str, dict[str, str | None]] = {
        "1" * 40: {
            "committedDate": "2026-07-01T00:00:00Z",
            "authoredDate": "2026-06-30T00:00:00Z",
        },
        "2" * 40: {
            "committedDate": "2026-08-01T00:00:00Z",
            "authoredDate": "2026-07-31T00:00:00Z",
        },
        "3" * 40: {
            "committedDate": "2026-09-01T00:00:00Z",
            "authoredDate": "2026-08-31T00:00:00Z",
        },
        "4" * 40: {
            "committedDate": "2026-10-01T00:00:00Z",
            "authoredDate": "2026-09-30T00:00:00Z",
        },
        "5" * 40: {
            "committedDate": None,
            "authoredDate": "2026-10-05T00:00:00Z",
        },
    }
    query_batches: list[str] = []

    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return mocked commit activity data for a batch query.
        
        Args:
            args: GitHub CLI command and GraphQL query arguments.
        
        Returns:
            Mapping from query aliases to commit date objects."""
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="fake gh json failed at line 428.",
        )
        query_arg = args[3]
        require(
            condition=query_arg.startswith("query="),
            message="fake gh json failed at line 430.",
        )
        query = query_arg.removeprefix("query=")
        aliases = re.findall(r'(commit\d+): object\(expression: "([0-9a-f]{40})"\)', query)
        require(
            condition=bool(aliases),
            message="fake gh json failed at line 433.",
        )
        query_batches.append(query)
        repository_data: dict[str, object] = {alias: dates_by_sha[sha] for alias, sha in aliases}
        return {"data": {"repository": repository_data}}

    shas = set(dates_by_sha)
    activities = maintenance_cleanup.branch_activity_epochs(
        "owner/repo", shas, batch_size=2, fetch_json=fake_gh_json
    )

    require(
        condition=(
            activities == {
                "1" * 40: maintenance_cleanup.epoch("2026-07-01T00:00:00Z"),
                "2" * 40: maintenance_cleanup.epoch("2026-08-01T00:00:00Z"),
                "3" * 40: maintenance_cleanup.epoch("2026-09-01T00:00:00Z"),
                "4" * 40: maintenance_cleanup.epoch("2026-10-01T00:00:00Z"),
                "5" * 40: maintenance_cleanup.epoch("2026-10-05T00:00:00Z"),
            }
        ),
        message="branch activity epochs resol failed at line 443.",
    )
    require(
        condition=len(query_batches) == 3,
        message="branch activity epochs resol failed at line 450.",
    )


def test_branch_activity_epochs_fail_closed_when_a_commit_is_missing() -> None:
    """from tools.ci import maintenance_cleanup"""

    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return a mock response that omits a requested commit object.
        
        Args:
            args: GitHub CLI command and GraphQL query arguments.
        
        Returns:
            Mapping whose queried alias does not contain commit data."""
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="fake gh json failed at line 457.",
        )
        return {"data": {"repository": {"commit0": None}}}

    try:
        maintenance_cleanup.branch_activity_epochs(
            "owner/repo", {"1" * 40}, fetch_json=fake_gh_json
        )
    except RuntimeError as exc:
        require(
            condition="commit activity missing" in str(exc),
            message="branch activity epochs fail  failed at line 465.",
        )
    else:
        msg = "missing branch activity must fail closed"
        raise AssertionError(msg)


def test_closed_pr_head_lookup_matches_only_unchanged_same_repo_heads() -> None:
    """Match closed pull requests only to unchanged heads in the same repository."""
    from collections.abc import Iterator

    from tools.ci import maintenance_cleanup

    cutoff = maintenance_cleanup.epoch("2026-10-01T00:00:00Z")
    activity = {
        "1" * 40: maintenance_cleanup.epoch("2026-10-10T00:00:00Z"),
        "2" * 40: maintenance_cleanup.epoch("2026-10-10T00:00:00Z"),
        "3" * 40: maintenance_cleanup.epoch("2026-10-10T00:00:00Z"),
    }
    branches: list[dict[str, object]] = [
        {"name": "main", "protected": True, "commit": {"sha": "1" * 40}},
        {
            "name": "simulation-evidence/pr-2500",
            "protected": False,
            "commit": {"sha": "2" * 40},
        },
        {
            "name": "fix/closed-pr-head",
            "protected": False,
            "commit": {"sha": "1" * 40},
        },
        {
            "name": "fix/recent-unsubmitted-work",
            "protected": False,
            "commit": {"sha": "3" * 40},
        },
    ]
    endpoints: list[str] = []

    def fake_load_items(endpoint: str) -> Iterator[dict[str, object]]:
        """Return mock closed pull requests for the supplied API endpoint.
        
        Args:
            endpoint: GitHub pull-request listing endpoint to emulate.
        
        Returns:
            Iterator over mock pull-request records."""
        endpoints.append(endpoint)
        if endpoint.endswith("head=owner:fix%2Fclosed-pr-head"):
            return iter(
                [
                    {
                        "state": "closed",
                        "head": {
                            "ref": "fix/closed-pr-head",
                            "sha": "1" * 40,
                            "repo": {"full_name": "owner/repo"},
                        },
                    }
                ]
            )
        return iter([])

    matched = maintenance_cleanup.closed_pr_head_shas_by_branch(
        "owner/repo",
        branches,
        set(),
        "main",
        activity,
        cutoff,
        api_items_loader=fake_load_items,
    )

    require(
        condition=matched == {"fix/closed-pr-head": {"1" * 40}},
        message="closed pr head lookup matche failed at line 529.",
    )
    require(
        condition=(
            endpoints == [
                "repos/owner/repo/pulls?state=closed&head=owner:fix%2Fclosed-pr-head",
                "repos/owner/repo/pulls?state=closed&head=owner:fix%2Frecent-unsubmitted-work",
            ]
        ),
        message="closed pr head lookup matche failed at line 530.",
    )


def test_stale_unprotected_branches_cover_all_namespaces_and_preserve_live_refs() -> None:
    """Keep live and protected references while selecting stale unprotected branches."""
    from tools.ci import maintenance_cleanup

    cutoff = maintenance_cleanup.epoch("2026-10-01T00:00:00Z")
    branches: list[dict[str, object]] = [
        {
            "name": "main",
            "protected": True,
            "commit": {"sha": "1" * 40},
        },
        {
            "name": "simulation-evidence/pr-2500",
            "protected": False,
            "commit": {"sha": "2" * 40},
        },
        {
            "name": "fix/old-closed-work",
            "protected": False,
            "commit": {"sha": "3" * 40},
        },
        {
            "name": "agent/open-pr",
            "protected": False,
            "commit": {"sha": "4" * 40},
        },
        {
            "name": "fix/recent-work",
            "protected": False,
            "commit": {"sha": "5" * 40},
        },
        {
            "name": "release/protected-by-github",
            "protected": True,
            "commit": {"sha": "6" * 40},
        },
        {
            "name": "docs/unverifiable",
            "protected": False,
            "commit": {"sha": "7" * 40},
        },
        {
            "name": "maintenance/old-closed-work",
            "protected": False,
            "commit": {"sha": "8" * 40},
        },
    ]
    activity = {
        "2" * 40: maintenance_cleanup.epoch("2026-07-01T00:00:00Z"),
        "3" * 40: maintenance_cleanup.epoch("2026-08-01T00:00:00Z"),
        "4" * 40: maintenance_cleanup.epoch("2026-08-15T00:00:00Z"),
        "5" * 40: maintenance_cleanup.epoch("2026-10-10T00:00:00Z"),
        "6" * 40: maintenance_cleanup.epoch("2026-06-01T00:00:00Z"),
        "8" * 40: maintenance_cleanup.epoch("2026-06-15T00:00:00Z"),
    }

    stale = maintenance_cleanup.stale_unprotected_branches(
        branches, {"agent/open-pr"}, "main", activity, cutoff
    )

    require(
        condition=(
            [branch["name"] for branch in stale] == [
                "maintenance/old-closed-work",
                "fix/old-closed-work",
            ]
        ),
        message="stale unprotected branches c failed at line 595.",
    )


def test_maintenance_cleanup_filters_and_orders_runs_before_cutoff() -> None:
    """Filter completed workflow runs by cutoff and preserve chronological ordering."""
    from tools.ci import maintenance_cleanup

    runs = [
        {"id": 3, "created_at": "2026-10-01T00:00:00Z"},
        {"id": 1, "created_at": "2026-08-01T00:00:00Z"},
        {"id": 2, "created_at": "2026-09-01T00:00:00Z"},
    ]
    cutoff = maintenance_cleanup.epoch("2026-09-15T00:00:00Z")

    stale = maintenance_cleanup.stale_completed_runs(runs, cutoff)

    require(
        condition=[run["id"] for run in stale] == [1, 2],
        message="maintenance cleanup filters  failed at line 613.",
    )


def test_ruff_covers_every_tracked_python_file_without_auto_fixing() -> None:
    """Require Ruff format and lint checks over every tracked Python source file."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]

    require(
        condition="git ls-files -z -- '*.py' '*.pyi'" in quality,
        message="ruff covers every tracked py failed at line 622.",
    )
    require(
        condition=(
            (
                'xargs -0 -r python -m ruff format --check < '
                '"$RUNNER_TEMP/python-files.zlist"'
            ) in quality
        ),
        message="ruff covers every tracked py failed at line 623.",
    )
    require(
        condition='xargs -0 -r python -m ruff check < "$RUNNER_TEMP/python-files.zlist"' in quality,
        message="ruff covers every tracked py failed at line 626.",
    )
    require(
        condition="python -m ruff check --fix" not in quality,
        message="ruff covers every tracked py failed at line 627.",
    )
    require(
        condition="xargs -r python -m ruff check <" not in quality,
        message="ruff covers every tracked py failed at line 628.",
    )
    require(
        condition="pyright -p pyrightconfig.agent-strict.json" not in quality,
        message="ruff covers every tracked py failed at line 629.",
    )
    require(
        condition="python tools/ci/check_pydantic_models.py" in quality,
        message="ruff covers every tracked py failed at line 630.",
    )
    require(
        condition='path: "freecad_cloth tests tools/ci"' in workflow,
        message="ruff covers every tracked py failed at line 631.",
    )


def test_pyright_keeps_broad_inventory_with_explicit_strict_core() -> None:
    """One profile covers the broad inventory and makes strict core scope explicit."""
    config = json.loads((ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]
    strict_core = (
        "freecad_cloth/simulation/DrapeFailureClassifier.py",
        "freecad_cloth/simulation/ClothBackend.py",
        "freecad_cloth/simulation/ClothSolver.py",
    )

    require(
        condition=config["typeCheckingMode"] == "standard",
        message="pyright keeps broad inventor failed at line 647.",
    )
    require(
        condition=config["include"] == ["."],
        message="pyright keeps broad inventor failed at line 648.",
    )
    require(
        condition=not config.get("exclude"),
        message="pyright keeps broad inventor failed at line 649.",
    )
    require(
        condition=not (ROOT / "pyrightconfig.agent-strict.json").exists(),
        message="pyright keeps broad inventor failed at line 650.",
    )
    require(
        condition=quality.count("pyright -p ") == 1,
        message="pyright keeps broad inventor failed at line 651.",
    )
    require(
        condition=config["strict"] == list(strict_core),
        message="pyright keeps broad inventor failed at line 652.",
    )


def test_readme_gallery_uses_bounded_fit_steps_without_raising_freecad_timeout() -> None:
    """The main-only gallery generation uses a bounded fit budget."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gallery_job = workflow.split("  gui-documentation-assets:", maxsplit=1)[1].split(
        "  publish-readme-turntables:", maxsplit=1
    )[0]
    gallery_invocation = gallery_job.split(
        "log-file: artifacts/avatar-documentation-progress.log", maxsplit=1
    )[1].split("      - uses:", maxsplit=1)[0]

    require(
        condition="CLOTH_AVATAR_SCREENSHOT_MODE=documentation" in gallery_invocation,
        message="readme gallery uses bounded  failed at line 667.",
    )
    require(
        condition=(
            (
                "FREECAD_CLOTH_ANNY_FIT_STEPS=${{ env."
                "CLOTH_DOC_AVATAR_FIT_STEPS }}" in gallery_invocation
            )
        ),
        message="readme gallery uses bounded  failed at line 668.",
    )
    require(
        condition="CLOTH_DOC_AVATAR_FIT_STEPS:" in workflow,
        message="readme gallery uses bounded  failed at line 671.",
    )
    require(
        condition="FREECAD_CLOTH_ANNY_FIT_STEPS=18" not in gallery_invocation,
        message="readme gallery uses bounded  failed at line 672.",
    )
    require(
        condition="freecad_application_timeout_seconds" not in gallery_job,
        message="readme gallery uses bounded  failed at line 673.",
    )
    require(
        condition="timeout-minutes: 12" in gallery_job,
        message="readme gallery uses bounded  failed at line 674.",
    )


def test_main_publication_checks_out_source_before_local_publisher_action() -> None:
    """The runner must have the local composite action before it can resolve the action."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    publisher_job = workflow.split("  publish-readme-turntables:\n", maxsplit=1)[1].split(
        "\n  maintenance-cleanup:", maxsplit=1
    )[0]
    checkout = "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    local_action = "uses: ./.github/actions/publish-visual-evidence"

    require(
        condition=publisher_job.count(checkout) == 1,
        message="main publication checks out  failed at line 688.",
    )
    require(
        condition=publisher_job.index(checkout) < publisher_job.index(local_action),
        message="main publication checks out  failed at line 689.",
    )
    require(
        condition='ref: "${{ github.sha }}"' in publisher_job,
        message="main publication checks out  failed at line 690.",
    )
    require(
        condition="persist-credentials: false" in publisher_job,
        message="main publication checks out  failed at line 691.",
    )


def test_blanket_artifact_preserves_example_directory_for_gif_publisher() -> None:
    """The publisher rebuilds the blanket GIF from frames under blanket-example/."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    blanket_job = workflow.split("  gui-visual-examples:\n", maxsplit=1)[1].split(
        "\n  publish-pr-simulation-evidence:", maxsplit=1
    )[0]

    # Keep the generated-directory prefix outside the upload wildcard so the
    # artifact ZIP retains blanket-example/motion-*.png rather than flattening it.
    require(
        condition="artifact-path: docs/images/generated/**" in blanket_job,
        message="blanket artifact preserves e failed at line 705.",
    )
    require(
        condition="artifact-path: docs/images/generated/blanket-example/**" not in blanket_job,
        message="blanket artifact preserves e failed at line 706.",
    )
