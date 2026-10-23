# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the repository's single-source CI configuration contracts."""

import json
import re
import tomllib
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path

from tests.support.assertions import require, require_not_none
from tools.ci import maintenance_cleanup
from tools.ci.run_freecad import configured_timeout_seconds

ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_FREECAD_APPLICATION_TIMEOUT_SECONDS = 120
_EXPECTED_GRAPHQL_BATCH_COUNT = 3


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
        message='Expected "case: simulation-quality" in gui_matrix.',
    )
    require(
        condition="tests/freecad_simulation_quality_acceptance.py" in gui_matrix,
        message='Expected "tests/freecad_simulation_quality_acceptance.py" in gui_matrix.',
    )
    require(
        condition="python3 tools/ci/validate_acceptance.py simulation-quality" in gui_matrix,
        message=(
            "Expected \"python3 tools/ci/validate_acceptance.py simulation-quality\" in "
            "gui_matrix."
        ),
    )
    require(
        condition=(
            '"simulation-quality": Path("artifacts/simulation-quality-readiness.png")' in validator
        ),
        message=(
            "Expected ( '\"simulation-quality\": "
            "Path(\"artifacts/simulation-quality-readiness.png\")' in validator )."
        ),
    )
    stale_image_contract = (
        '"simulation-quality": (Path("artifacts/simulation-quality-stale-target.png"),)'
    )
    require(
        condition=stale_image_contract in validator,
        message="Expected stale_image_contract in validator.",
    )
    require(
        condition="simulation-quality-readiness.png" in acceptance,
        message="Expected \"simulation-quality-readiness.png\" in acceptance.",
    )
    require(
        condition="simulation-quality-stale-target.png" in acceptance,
        message="Expected \"simulation-quality-stale-target.png\" in acceptance.",
    )
    require(
        condition='property("workflowState") != "blocked"' in acceptance,
        message="Expected 'property(\"workflowState\") != \"blocked\"' in acceptance.",
    )
    require(
        condition='if __name__ == "__main__"' not in acceptance,
        message="Expected 'if __name__ == \"__main__\"' not in acceptance.",
    )
    require(
        condition='_progress("entrypoint-entered")' in acceptance,
        message="Expected '_progress(\"entrypoint-entered\")' in acceptance.",
    )
    require(
        condition="os._exit(0)" in acceptance,
        message="Expected \"os._exit(0)\" in acceptance.",
    )
    require(
        condition="os._exit(1)" in acceptance,
        message="Expected \"os._exit(1)\" in acceptance.",
    )


def test_freecad_timeout_is_positive_and_declared_once() -> None:
    """The application timeout comes from the project configuration."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    configured = tomllib.loads(pyproject)["tool"]["freecad_cloth"]["ci"][
        "freecad_application_timeout_seconds"
    ]
    require(
        condition=configured == _EXPECTED_FREECAD_APPLICATION_TIMEOUT_SECONDS,
        message="Expected configured == _EXPECTED_FREECAD_APPLICATION_TIMEOUT_SECONDS.",
    )
    require(
        condition=configured_timeout_seconds() == configured,
        message="Expected configured_timeout_seconds() == configured.",
    )
    require(
        condition=pyproject.count("freecad_application_timeout_seconds") == 1,
        message="Expected pyproject.count(\"freecad_application_timeout_seconds\") == 1.",
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
        message="Expected workflow.count(\"timeout-seconds:\") == 1.",
    )
    require(
        condition='timeout-seconds: "360"' in simulation_ladder,
        message="Expected 'timeout-seconds: \"360\"' in simulation_ladder.",
    )
    require(
        condition="freecad_application_timeout_seconds" not in workflow,
        message="Expected \"freecad_application_timeout_seconds\" not in workflow.",
    )
    require(
        condition='default: "120"' in action,
        message="Expected 'default: \"120\"' in action.",
    )
    require(
        condition="timeout-seconds: ${{ inputs.timeout-seconds }}" in action,
        message="Expected \"timeout-seconds: ${{ inputs.timeout-seconds }}\" in action.",
    )
    require(
        condition="FREECAD_APPLICATION_TIMEOUT_SECONDS=" in action,
        message="Expected \"FREECAD_APPLICATION_TIMEOUT_SECONDS=\" in action.",
    )
    require(
        condition='default: "120"' in container_action,
        message="Expected 'default: \"120\"' in container_action.",
    )
    require(
        condition="maximum 360 seconds" in container_action,
        message="Expected \"maximum 360 seconds\" in container_action.",
    )
    require(
        condition='if [ "$timeout_seconds" -gt 360 ]; then' in container_action,
        message="Expected 'if [ \"$timeout_seconds\" -gt 360 ]; then' in container_action.",
    )
    require(
        condition="FREECAD_APPLICATION_TIMEOUT_SECONDS" in runner,
        message="Expected \"FREECAD_APPLICATION_TIMEOUT_SECONDS\" in runner.",
    )
    require(
        condition="420" not in container_action,
        message="Expected \"420\" not in container_action.",
    )
    require(
        condition="--no-deps -e ." in action,
        message="Expected \"--no-deps -e .\" in action.",
    )
    require(
        condition='"numpy>=1.26,<3"' in action,
        message="Expected '\"numpy>=1.26,<3\"' in action.",
    )
    require(
        condition='"pydantic>=2.11,<3"' in action,
        message="Expected '\"pydantic>=2.11,<3\"' in action.",
    )
    require(
        condition='"Pillow>=11,<13"' in action,
        message="Expected '\"Pillow>=11,<13\"' in action.",
    )
    require(
        condition="install --disable-pip-version-check -e ." not in action,
        message="Expected \"install --disable-pip-version-check -e .\" not in action.",
    )
    require(
        condition="configured_timeout_seconds()" in runner,
        message="Expected \"configured_timeout_seconds()\" in runner.",
    )
    require(
        condition="--extra-index-url https://download.pytorch.org/whl/cpu" in workflow,
        message=(
            "Expected \"--extra-index-url https://download.pytorch.org/whl/cpu\" in "
            "workflow."
        ),
    )
    require(
        condition='"torch==2.8.0+cpu"' in workflow,
        message="Expected '\"torch==2.8.0+cpu\"' in workflow.",
    )


def test_timeout_contract_is_documented() -> None:
    """The human documentation points to the authoritative configuration."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "developers" / "CI_CONFIGURATION.md").read_text(
        encoding="utf-8"
    )

    require(
        condition="CI configuration" in docs,
        message="Expected \"CI configuration\" in docs.",
    )
    require(
        condition="pyproject.toml" in configuration,
        message="Expected \"pyproject.toml\" in configuration.",
    )
    require(
        condition="freecad_application_timeout_seconds" in configuration,
        message="Expected \"freecad_application_timeout_seconds\" in configuration.",
    )


def test_maintenance_cleanup_receives_github_cli_token() -> None:
    """The scheduled cleanup has the token needed for gh API reads and deletes."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    cleanup = workflow.split("  maintenance-cleanup:", 1)[1].split("  artifact-budget:", 1)[0]

    require(
        condition="GH_TOKEN: ${{ github.token }}" in cleanup,
        message="Expected \"GH_TOKEN: ${{ github.token }}\" in cleanup.",
    )
    require(
        condition="actions: write" in cleanup,
        message="Expected \"actions: write\" in cleanup.",
    )
    require(
        condition="contents: write" in cleanup,
        message="Expected \"contents: write\" in cleanup.",
    )
    require(
        condition="packages: write" in cleanup,
        message="Expected \"packages: write\" in cleanup.",
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
        message=f"Expected `!({activation})` in readiness.",
    )
    require(
        condition=f"!({activation})" in watchdog,
        message=f"Expected `!({activation})` in watchdog.",
    )
    require(
        condition=f"!({activation})" in image,
        message=f"Expected `!({activation})` in image.",
    )
    require(
        condition=(
            "!startsWith(github.event.head_commit.message, 'RUN MAINTENANCE CLEANUP')"
            in artifact_budget
        ),
        message=(
            "Expected ( \"!startsWith(github.event.head_commit.message, 'RUN MAINTENANCE "
            "CLEANUP')\" in artifact_budget )."
        ),
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
        message="Expected \"python tools/check_dead_code.py\" in quality.",
    )
    require(
        condition="xargs -r python tools/check_dead_code.py" not in quality,
        message="Expected \"xargs -r python tools/check_dead_code.py\" not in quality.",
    )
    require(
        condition="changed-python.txt" not in quality,
        message="Expected \"changed-python.txt\" not in quality.",
    )


def test_pbd_validation_tag_matches_workflow_dockerfile_hash() -> None:
    """Verify the PBD validation image tag matches the Dockerfile content hash."""
    contents = b"FROM freecad:stable\n"
    require(
        condition=(
            maintenance_cleanup.pbd_validation_tag(contents) == sha256(contents).hexdigest()[:32]
        ),
        message=(
            "Expected maintenance_cleanup.pbd_validation_tag(contents) == "
            "sha256(contents).hexdigest()[:32]."
        ),
    )


def test_dockerfile_tags_for_shas_batches_graphql_queries() -> None:
    """Verify protected Dockerfile tags are resolved in bounded GraphQL batches."""
    contents_by_sha = {
        "1" * 40: b"FROM freecad:one\n",
        "2" * 40: b"FROM freecad:two\n",
        "3" * 40: b"FROM freecad:three\n",
        "4" * 40: b"FROM freecad:four\n",
        "5" * 40: b"FROM freecad:five\n",
    }
    queries = []

    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return a mock GraphQL response for protected Dockerfile blobs.

        Args:
            args: GitHub CLI request arguments, including the GraphQL query.

        Returns:
            Mapping containing the protected repository blob contents.
        """
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="Expected args[:3] == (\"api\", \"graphql\", \"-f\").",
        )
        query_arg = args[3]
        require(
            condition=query_arg.startswith("query="),
            message="Expected query_arg.startswith(\"query=\").",
        )
        query = query_arg.removeprefix("query=")
        aliases = re.findall(
            r'(file\d+): object\(expression: "([0-9a-f]{40}):docker/freecad-ci/Dockerfile"\)',
            query,
        )
        require(
            condition=bool(aliases),
            message="Expected bool(aliases).",
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
        message=(
            "Expected ( tags == {sha256(contents).hexdigest()[:32] for contents in "
            "contents_by_sha.values()} )."
        ),
    )
    require(
        condition=len(queries) == _EXPECTED_GRAPHQL_BATCH_COUNT,
        message="Expected len(queries) == _EXPECTED_GRAPHQL_BATCH_COUNT.",
    )


def test_dockerfile_tags_fail_closed_when_graphql_omits_a_protected_blob() -> None:
    """Reject cleanup when a protected Dockerfile blob is missing.

    Raises:
        AssertionError: If cleanup accepts a missing protected Dockerfile blob.
    """
    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return a mock GraphQL response for a missing protected Dockerfile blob.

        Args:
            args: GitHub CLI request arguments, including the GraphQL query.

        Returns:
            Response mapping with the queried protected blob.
        """
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="Expected args[:3] == (\"api\", \"graphql\", \"-f\").",
        )
        return {"data": {"repository": {"file0": None}}}

    try:
        maintenance_cleanup.dockerfile_tags_for_shas(
            "owner/repo", {"1" * 40}, fetch_json=fake_gh_json
        )
    except RuntimeError as exc:
        require(
            condition="Dockerfile content missing" in str(exc),
            message="Expected \"Dockerfile content missing\" in str(exc).",
        )
    else:
        msg = "missing protected Dockerfile content must fail closed"
        raise AssertionError(msg)


def test_package_cleanup_uses_configured_authenticated_user_package_endpoint() -> None:
    """Use the authenticated user's package endpoint for image cleanup."""
    requested_endpoints: list[str] = []
    deleted_arguments: list[tuple[str, ...]] = []

    def fake_resolve_tags(repo_name: str, protected_shas: set[str]) -> set[str]:
        """Return protected Dockerfile tags for the requested repository state.

        Args:
            repo_name: Repository whose protected Dockerfiles are resolved.
            protected_shas: Commit SHAs that must remain protected.

        Returns:
            Set of tags that identify protected Dockerfile contents.
        """
        require(
            condition=repo_name == "Uhrendoktor/freecad-cloth",
            message="Expected repo_name == \"Uhrendoktor/freecad-cloth\".",
        )
        require(
            condition=protected_shas == {"1" * 40},
            message="Expected protected_shas == {\"1\" * 40}.",
        )
        return {"protected-dockerfile-tag"}

    def fake_load_items(endpoint: str) -> Iterator[dict[str, object]]:
        """Return mocked API records for the requested endpoint.

        Args:
            endpoint: GitHub API collection endpoint to emulate.

        Returns:
            Iterator over package records from the requested endpoint.

        Raises:
            AssertionError: If the cleanup requests an unexpected package endpoint.
        """
        requested_endpoints.append(endpoint)
        if endpoint == "user/packages/container/freecad-cloth%2Fpbd-validation/versions":
            return iter([])
        msg = f"unexpected package API endpoint: {endpoint}"
        raise AssertionError(msg)

    def fake_delete(*args: str) -> None:
        """Record an attempted GitHub API deletion.

        Args:
            args: Resource deletion arguments supplied by the cleanup routine.
        """
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
        message="Expected result[\"status\"] == \"passed\".",
    )
    require(
        condition=result["versions_seen"] == 0,
        message="Expected result[\"versions_seen\"] == 0.",
    )
    require(
        condition=result["deleted"] == 0,
        message="Expected result[\"deleted\"] == 0.",
    )
    require(
        condition=(
            requested_endpoints == [
                "user/packages/container/freecad-cloth%2Fpbd-validation/versions"
            ]
        ),
        message=(
            "Expected ( requested_endpoints == [ "
            "\"user/packages/container/freecad-cloth%2Fpbd-validation/versions\" ] )."
        ),
    )
    require(
        condition=deleted_arguments == [],
        message="Expected deleted_arguments == [].",
    )


def test_stale_package_versions_keep_protected_recent_and_unverifiable_versions() -> None:
    """Keep protected, recent and unverifiable package versions out of deletion candidates."""
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

    stale = maintenance_cleanup.stale_package_versions(
        versions, {"protected-dockerfile-tag"}, cutoff
    )

    require(
        condition=[version["id"] for version in stale] == [1],
        message="Expected [version[\"id\"] for version in stale] == [1].",
    )


def test_package_cleanup_queries_configured_pbd_versions_without_namespace_listing() -> None:
    """Delete stale package versions using only the configured package endpoint."""
    endpoint = "user/packages/container/freecad-cloth%2Fpbd-validation/versions"
    endpoints: list[str] = []
    deleted: list[tuple[str, ...]] = []

    def fake_resolve_tags(_repo_name: str, _protected_shas: set[str]) -> set[str]:
        """Return a stable protected tag set for this package-cleanup test.

        Args:
            _repo_name: Repository name ignored by this controlled fake.
            _protected_shas: Protected commits ignored by this controlled fake.

        Returns:
            Set containing the single tag kept by the test.
        """
        return {"current-tag"}

    def fake_load_items(requested_endpoint: str) -> Iterator[dict[str, object]]:
        """Record a request and provide the configured stale package version.

        Args:
            requested_endpoint: API endpoint requested by the cleanup routine.

        Returns:
            Iterator containing the configured stale package version.

        Raises:
            AssertionError: If the cleanup requests an unexpected package endpoint.
        """
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
            args: Resource deletion arguments supplied by the cleanup routine.
        """
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
        message="Expected endpoints == [endpoint].",
    )
    require(
        condition=result["status"] == "passed",
        message="Expected result[\"status\"] == \"passed\".",
    )
    require(
        condition=result["versions_seen"] == 1,
        message="Expected result[\"versions_seen\"] == 1.",
    )
    require(
        condition=result["deleted"] == 1,
        message="Expected result[\"deleted\"] == 1.",
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
        message=(
            "Expected ( deleted == [ ( \"api\", \"--method\", \"DELETE\", "
            "\"user/packages/container/freecad-cloth%2Fpbd-validation/versions/11\", ) ] )."
        ),
    )


def test_maintenance_cleanup_paginates_until_a_short_page() -> None:
    """Read all cleanup API pages and stop on the first short page."""
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
            Mapping containing the requested page of integer-ID records.
        """
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
        message="Expected items == [{\"id\": 1}, {\"id\": 2}, {\"id\": 3}].",
    )
    require(
        condition=requested_pages == [1, 2],
        message="Expected requested_pages == [1, 2].",
    )


def test_maintenance_cleanup_prefers_committer_date_for_branch_activity() -> None:
    """Prefer a commit's committer date when determining branch activity age."""
    commit_data = {
        "author": {"date": "2020-01-01T00:00:00Z"},
        "committer": {"date": "2026-10-01T00:00:00Z"},
    }

    activity = maintenance_cleanup.branch_activity_epoch(commit_data)
    cutoff = maintenance_cleanup.epoch("2026-09-26T00:00:00Z")

    activity = require_not_none(
        activity,
        message="Expected activity to be present.",
    )
    require(
        condition=activity > cutoff,
        message="Expected activity > cutoff.",
    )


def test_maintenance_cleanup_falls_back_to_author_date_when_needed() -> None:
    """Use the author date when the committer date cannot be parsed."""
    commit_data = {"author": {"date": "2026-10-01T00:00:00Z"}}

    require(
        condition=(
            maintenance_cleanup.branch_activity_epoch(commit_data) == maintenance_cleanup.epoch(
                "2026-10-01T00:00:00Z"
            )
        ),
        message=(
            "Expected ( maintenance_cleanup.branch_activity_epoch(commit_data) == "
            "maintenance_cleanup.epoch( \"2026-10-01T00:00:00Z\" ) )."
        ),
    )


def test_branch_activity_epochs_resolve_unique_heads_in_bounded_batches() -> None:
    """Resolve unique commit heads in bounded GraphQL batches."""
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
            Mapping from query aliases to commit date objects.
        """
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="Expected args[:3] == (\"api\", \"graphql\", \"-f\").",
        )
        query_arg = args[3]
        require(
            condition=query_arg.startswith("query="),
            message="Expected query_arg.startswith(\"query=\").",
        )
        query = query_arg.removeprefix("query=")
        aliases = re.findall(r'(commit\d+): object\(expression: "([0-9a-f]{40})"\)', query)
        require(
            condition=bool(aliases),
            message="Expected bool(aliases).",
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
        message=(
            "Expected ( activities == { \"1\" * 40: "
            "maintenance_cleanup.epoch(\"2026-07-01T00:00:00Z\"), \"2\" * 40: "
            "maintenance_cleanup.epoch(\"2026-08-01T00:00:00Z\"), \"3\" * 40: "
            "maintenance_cleanup.epoch(\"2026-09-01T00:00:00Z\"), \"4\" * 40: "
            "maintenance_cleanup.epoch(\"2026-10-01T00:00:00Z\"), \"5\" * 40: "
            "maintenance_cleanup.epoch(\"2026-10-05T00:00:00Z\"), } )."
        ),
    )
    require(
        condition=len(query_batches) == _EXPECTED_GRAPHQL_BATCH_COUNT,
        message="Expected len(query_batches) == _EXPECTED_GRAPHQL_BATCH_COUNT.",
    )


def test_branch_activity_epochs_fail_closed_when_a_commit_is_missing() -> None:
    """Fail closed when a requested branch commit has no activity record.

    Raises:
        AssertionError: If missing commit activity is accepted.
    """
    def fake_gh_json(*args: str) -> dict[str, object]:
        """Return a mock response that omits a requested commit object.

        Args:
            args: GitHub CLI command and GraphQL query arguments.

        Returns:
            Mapping whose queried alias does not contain commit data.
        """
        require(
            condition=args[:3] == ("api", "graphql", "-f"),
            message="Expected args[:3] == (\"api\", \"graphql\", \"-f\").",
        )
        return {"data": {"repository": {"commit0": None}}}

    try:
        maintenance_cleanup.branch_activity_epochs(
            "owner/repo", {"1" * 40}, fetch_json=fake_gh_json
        )
    except RuntimeError as exc:
        require(
            condition="commit activity missing" in str(exc),
            message="Expected \"commit activity missing\" in str(exc).",
        )
    else:
        msg = "missing branch activity must fail closed"
        raise AssertionError(msg)


def test_closed_pr_head_lookup_matches_only_unchanged_same_repo_heads() -> None:
    """Match closed pull requests only to unchanged heads in the same repository."""
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
            Iterator over mock pull-request records.
        """
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
        message="Expected matched == {\"fix/closed-pr-head\": {\"1\" * 40}}.",
    )
    require(
        condition=(
            endpoints == [
                "repos/owner/repo/pulls?state=closed&head=owner:fix%2Fclosed-pr-head",
                "repos/owner/repo/pulls?state=closed&head=owner:fix%2Frecent-unsubmitted-work",
            ]
        ),
        message=(
            "Expected ( endpoints == [ "
            "\"repos/owner/repo/pulls?state=closed&head=owner:fix%2Fclosed-pr-head\", "
            "\"repos/owner/repo/pulls?state=closed&head=owner:fix%2Frecent-unsubmitted-wor"
            "k\", ] )."
        ),
    )


def test_stale_unprotected_branches_cover_all_namespaces_and_preserve_live_refs() -> None:
    """Keep live and protected references while selecting stale unprotected branches."""
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
        message=(
            "Expected ( [branch[\"name\"] for branch in stale] == [ "
            "\"maintenance/old-closed-work\", \"fix/old-closed-work\", ] )."
        ),
    )


def test_maintenance_cleanup_filters_and_orders_runs_before_cutoff() -> None:
    """Filter completed workflow runs by cutoff and preserve chronological ordering."""
    runs = [
        {"id": 3, "created_at": "2026-10-01T00:00:00Z"},
        {"id": 1, "created_at": "2026-08-01T00:00:00Z"},
        {"id": 2, "created_at": "2026-09-01T00:00:00Z"},
    ]
    cutoff = maintenance_cleanup.epoch("2026-09-15T00:00:00Z")

    stale = maintenance_cleanup.stale_completed_runs(runs, cutoff)

    require(
        condition=[run["id"] for run in stale] == [1, 2],
        message="Expected [run[\"id\"] for run in stale] == [1, 2].",
    )


def test_ruff_covers_every_tracked_python_file_without_auto_fixing() -> None:
    """Require Ruff format and lint checks over every tracked Python source file."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]

    require(
        condition="git ls-files -z -- '*.py' '*.pyi'" in quality,
        message="Expected \"git ls-files -z -- '*.py' '*.pyi'\" in quality.",
    )
    require(
        condition=(
            (
                'xargs -0 -r python -m ruff format --check < '
                '"$RUNNER_TEMP/python-files.zlist"'
            ) in quality
        ),
        message=(
            "Expected ( ( 'xargs -0 -r python -m ruff format --check < ' "
            "'\"$RUNNER_TEMP/python-files.zlist\"' ) in quality )."
        ),
    )
    require(
        condition='xargs -0 -r python -m ruff check < "$RUNNER_TEMP/python-files.zlist"' in quality,
        message=(
            "Expected 'xargs -0 -r python -m ruff check < "
            "\"$RUNNER_TEMP/python-files.zlist\"' in quality."
        ),
    )
    require(
        condition="python -m ruff check --fix" not in quality,
        message="Expected \"python -m ruff check --fix\" not in quality.",
    )
    require(
        condition="xargs -r python -m ruff check <" not in quality,
        message="Expected \"xargs -r python -m ruff check <\" not in quality.",
    )
    require(
        condition="pyright -p pyrightconfig.agent-strict.json" not in quality,
        message="Expected \"pyright -p pyrightconfig.agent-strict.json\" not in quality.",
    )
    require(
        condition="python tools/ci/check_pydantic_models.py" in quality,
        message="Expected \"python tools/ci/check_pydantic_models.py\" in quality.",
    )
    require(
        condition='path: "freecad_cloth tests tools/ci"' in workflow,
        message="Expected 'path: \"freecad_cloth tests tools/ci\"' in workflow.",
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
        message="Expected config[\"typeCheckingMode\"] == \"standard\".",
    )
    require(
        condition=config["include"] == ["."],
        message="Expected config[\"include\"] == [\".\"].",
    )
    require(
        condition=not config.get("exclude"),
        message="Expected not config.get(\"exclude\").",
    )
    require(
        condition=not (ROOT / "pyrightconfig.agent-strict.json").exists(),
        message="Expected not (ROOT / \"pyrightconfig.agent-strict.json\").exists().",
    )
    require(
        condition=quality.count("pyright -p ") == 1,
        message="Expected quality.count(\"pyright -p \") == 1.",
    )
    require(
        condition=config["strict"] == list(strict_core),
        message="Expected config[\"strict\"] == list(strict_core).",
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
        message="Expected \"CLOTH_AVATAR_SCREENSHOT_MODE=documentation\" in gallery_invocation.",
    )
    require(
        condition=(
            "FREECAD_CLOTH_ANNY_FIT_STEPS=${{ env."
            "CLOTH_DOC_AVATAR_FIT_STEPS }}" in gallery_invocation
        ),
        message=(
            "Expected `FREECAD_CLOTH_ANNY_FIT_STEPS=${{ env."
            "CLOTH_DOC_AVATAR_FIT_STEPS }}` in gallery_invocation."
        ),
    )
    require(
        condition="CLOTH_DOC_AVATAR_FIT_STEPS:" in workflow,
        message="Expected \"CLOTH_DOC_AVATAR_FIT_STEPS:\" in workflow.",
    )
    require(
        condition="FREECAD_CLOTH_ANNY_FIT_STEPS=18" not in gallery_invocation,
        message="Expected \"FREECAD_CLOTH_ANNY_FIT_STEPS=18\" not in gallery_invocation.",
    )
    require(
        condition="freecad_application_timeout_seconds" not in gallery_job,
        message="Expected \"freecad_application_timeout_seconds\" not in gallery_job.",
    )
    require(
        condition="timeout-minutes: 12" in gallery_job,
        message="Expected \"timeout-minutes: 12\" in gallery_job.",
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
        message="Expected publisher_job.count(checkout) == 1.",
    )
    require(
        condition=publisher_job.index(checkout) < publisher_job.index(local_action),
        message="Expected publisher_job.index(checkout) < publisher_job.index(local_action).",
    )
    require(
        condition='ref: "${{ github.sha }}"' in publisher_job,
        message="Expected 'ref: \"${{ github.sha }}\"' in publisher_job.",
    )
    require(
        condition="persist-credentials: false" in publisher_job,
        message="Expected \"persist-credentials: false\" in publisher_job.",
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
        message="Expected \"artifact-path: docs/images/generated/**\" in blanket_job.",
    )
    require(
        condition="artifact-path: docs/images/generated/blanket-example/**" not in blanket_job,
        message=(
            "Expected \"artifact-path: docs/images/generated/blanket-example/**\" not in "
            "blanket_job."
        ),
    )
