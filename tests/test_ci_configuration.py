"""Tests for the repository's single-source CI configuration contracts."""

import json
import tomllib
from pathlib import Path

from tools.ci.run_freecad import configured_timeout_seconds

ROOT = Path(__file__).resolve().parents[1]


def test_freecad_timeout_is_positive_and_declared_once():
    """The application timeout comes from the project configuration."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    configured = tomllib.loads(pyproject)["tool"]["freecad_cloth"]["ci"][
        "freecad_application_timeout_seconds"
    ]
    assert configured == 120
    assert configured_timeout_seconds() == configured
    assert pyproject.count("freecad_application_timeout_seconds") == 1


def test_ci_consumers_do_not_duplicate_the_application_timeout():
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

    assert "timeout-seconds:" not in workflow
    assert "freecad_application_timeout_seconds" not in workflow
    assert "timeout-seconds:" not in action
    assert 'default: "120"' in container_action
    assert "maximum 120 seconds" in container_action
    assert 'if [ "$timeout_seconds" -gt 120 ]; then' in container_action
    assert "420" not in container_action
    assert "--no-deps -e ." in action
    assert '"numpy>=1.26,<3"' in action
    assert '"pydantic>=2.11,<3"' in action
    assert '"Pillow>=11,<13"' in action
    assert "install --disable-pip-version-check -e ." not in action
    assert "configured_timeout_seconds()" in runner
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in workflow
    assert '"torch==2.8.0+cpu"' in workflow


def test_timeout_contract_is_documented():
    """The human documentation points to the authoritative configuration."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "developers" / "CI_CONFIGURATION.md").read_text(
        encoding="utf-8"
    )

    assert "CI configuration" in docs
    assert "pyproject.toml" in configuration
    assert "freecad_application_timeout_seconds" in configuration


def test_maintenance_cleanup_receives_github_cli_token() -> None:
    """The scheduled cleanup has the token needed for gh API reads and deletes."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    cleanup = workflow.split("  maintenance-cleanup:", 1)[1].split("  artifact-budget:", 1)[0]

    assert "GH_TOKEN: ${{ github.token }}" in cleanup
    assert "actions: write" in cleanup
    assert "contents: write" in cleanup
    assert "packages: write" in cleanup


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

    assert f"!({activation})" in readiness
    assert f"!({activation})" in watchdog
    assert f"!({activation})" in image
    assert (
        "!startsWith(github.event.head_commit.message, 'RUN MAINTENANCE CLEANUP')"
        in artifact_budget
    )


def test_dead_code_gate_scans_the_full_static_core_inventory() -> None:
    """The dead-code gate must include unchanged modules, not only PR diffs."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("      - name: Python and architecture checks", 1)[1].split(
        "      - name: Workflow linters", 1
    )[0]

    assert "python tools/check_dead_code.py" in quality
    assert "xargs -r python tools/check_dead_code.py" not in quality
    assert "changed-python.txt" not in quality


def test_pbd_validation_tag_matches_workflow_dockerfile_hash() -> None:
    from hashlib import sha256

    from tools.ci.maintenance_cleanup import pbd_validation_tag

    contents = b"FROM freecad:stable\n"
    assert pbd_validation_tag(contents) == sha256(contents).hexdigest()[:32]


def test_dockerfile_tags_for_shas_batches_graphql_queries() -> None:
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
        assert args[:3] == ("api", "graphql", "-f")
        query_arg = args[3]
        assert query_arg.startswith("query=")
        query = query_arg.removeprefix("query=")
        aliases = re.findall(
            r'(file\d+): object\(expression: "([0-9a-f]{40}):docker/freecad-ci/Dockerfile"\)',
            query,
        )
        assert aliases
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

    assert tags == {sha256(contents).hexdigest()[:32] for contents in contents_by_sha.values()}
    assert len(queries) == 3


def test_dockerfile_tags_fail_closed_when_graphql_omits_a_protected_blob() -> None:
    from tools.ci import maintenance_cleanup

    def fake_gh_json(*args: str) -> dict[str, object]:
        assert args[:3] == ("api", "graphql", "-f")
        return {"data": {"repository": {"file0": None}}}

    try:
        maintenance_cleanup.dockerfile_tags_for_shas(
            "owner/repo", {"1" * 40}, fetch_json=fake_gh_json
        )
    except RuntimeError as exc:
        assert "Dockerfile content missing" in str(exc)
    else:
        raise AssertionError("missing protected Dockerfile content must fail closed")


def test_package_cleanup_uses_configured_authenticated_user_package_endpoint() -> None:
    from collections.abc import Iterator

    from tools.ci import maintenance_cleanup

    requested_endpoints: list[str] = []
    deleted_arguments: list[tuple[str, ...]] = []

    def fake_resolve_tags(repo_name: str, protected_shas: set[str]) -> set[str]:
        assert repo_name == "Uhrendoktor/freecad-cloth"
        assert protected_shas == {"1" * 40}
        return {"protected-dockerfile-tag"}

    def fake_load_items(endpoint: str) -> Iterator[dict[str, object]]:
        requested_endpoints.append(endpoint)
        if endpoint == "user/packages/container/freecad-cloth/pbd-validation/versions":
            return iter([])
        raise AssertionError(f"unexpected package API endpoint: {endpoint}")

    def fake_delete(*args: str) -> None:
        deleted_arguments.append(args)

    result = maintenance_cleanup.cleanup_pbd_package_versions(
        "Uhrendoktor/freecad-cloth",
        {"1" * 40},
        maintenance_cleanup.epoch("2026-09-15T00:00:00Z"),
        dockerfile_tags_resolver=fake_resolve_tags,
        api_items_loader=fake_load_items,
        delete_resource=fake_delete,
    )

    assert result["status"] == "passed"
    assert result["versions_seen"] == 0
    assert result["deleted"] == 0
    assert requested_endpoints == [
        "user/packages/container/freecad-cloth/pbd-validation/versions"
    ]
    assert deleted_arguments == []


def test_stale_package_versions_keep_protected_recent_and_unverifiable_versions() -> None:
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

    assert [version["id"] for version in stale] == [1]


def test_package_cleanup_queries_configured_pbd_versions_without_namespace_listing() -> None:
    from collections.abc import Iterator

    from tools.ci import maintenance_cleanup

    endpoint = "user/packages/container/freecad-cloth/pbd-validation/versions"
    endpoints: list[str] = []
    deleted: list[tuple[str, ...]] = []

    def fake_resolve_tags(_repo_name: str, _protected_shas: set[str]) -> set[str]:
        return {"current-tag"}

    def fake_load_items(requested_endpoint: str) -> Iterator[dict[str, object]]:
        endpoints.append(requested_endpoint)
        if requested_endpoint != endpoint:
            raise AssertionError(f"unexpected package API endpoint: {requested_endpoint}")
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
        deleted.append(args)

    result = maintenance_cleanup.cleanup_pbd_package_versions(
        "example-owner/repo",
        {"protected-sha"},
        maintenance_cleanup.epoch("2026-09-15T00:00:00Z"),
        dockerfile_tags_resolver=fake_resolve_tags,
        api_items_loader=fake_load_items,
        delete_resource=fake_delete,
    )

    assert endpoints == [endpoint]
    assert result["status"] == "passed"
    assert result["versions_seen"] == 1
    assert result["deleted"] == 1
    assert deleted == [
        (
            "api",
            "--method",
            "DELETE",
            "user/packages/container/freecad-cloth/pbd-validation/versions/11",
        )
    ]


def test_maintenance_cleanup_paginates_until_a_short_page() -> None:
    from tools.ci import maintenance_cleanup

    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}],
    }
    requested_pages = []

    def fake_gh_json(*args: str) -> dict[str, list[dict[str, int]]]:
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

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert requested_pages == [1, 2]


def test_maintenance_cleanup_prefers_committer_date_for_branch_activity():
    from tools.ci import maintenance_cleanup

    commit_data = {
        "author": {"date": "2020-01-01T00:00:00Z"},
        "committer": {"date": "2026-10-01T00:00:00Z"},
    }

    activity = maintenance_cleanup.branch_activity_epoch(commit_data)
    cutoff = maintenance_cleanup.epoch("2026-09-26T00:00:00Z")

    assert activity is not None
    assert activity > cutoff


def test_maintenance_cleanup_falls_back_to_author_date_when_needed():
    from tools.ci import maintenance_cleanup

    commit_data = {"author": {"date": "2026-10-01T00:00:00Z"}}

    assert maintenance_cleanup.branch_activity_epoch(commit_data) == maintenance_cleanup.epoch(
        "2026-10-01T00:00:00Z"
    )


def test_maintenance_cleanup_filters_and_orders_runs_before_cutoff():
    from tools.ci import maintenance_cleanup

    runs = [
        {"id": 3, "created_at": "2026-10-01T00:00:00Z"},
        {"id": 1, "created_at": "2026-08-01T00:00:00Z"},
        {"id": 2, "created_at": "2026-09-01T00:00:00Z"},
    ]
    cutoff = maintenance_cleanup.epoch("2026-09-15T00:00:00Z")

    stale = maintenance_cleanup.stale_completed_runs(runs, cutoff)

    assert [run["id"] for run in stale] == [1, 2]


def test_ruff_covers_every_tracked_python_file_without_auto_fixing():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]

    assert "git ls-files -z -- '*.py' '*.pyi'" in quality
    assert (
        'xargs -0 -r python -m ruff format --check < "$RUNNER_TEMP/python-files.zlist"' in quality
    )
    assert 'xargs -0 -r python -m ruff check < "$RUNNER_TEMP/python-files.zlist"' in quality
    assert "python -m ruff check --fix" not in quality
    assert "xargs -r python -m ruff check <" not in quality
    assert "pyright -p pyrightconfig.agent-strict.json" not in quality
    assert "python tools/ci/check_pydantic_models.py" in quality
    assert 'path: "freecad_cloth tests tools/ci"' in workflow


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

    assert config["typeCheckingMode"] == "standard"
    assert set(strict_core).issubset(config["include"])
    assert not (ROOT / "pyrightconfig.agent-strict.json").exists()
    assert quality.count("pyright -p ") == 1
    assert config["strict"] == list(strict_core)


def test_readme_gallery_uses_bounded_fit_steps_without_raising_freecad_timeout() -> None:
    """The seven-profile README gallery must finish inside the unchanged FreeCAD cap."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gallery_job = workflow.split("  gui-turntables:", maxsplit=1)[1].split(
        "  gui-visual-examples:", maxsplit=1
    )[0]
    gallery_invocation = gallery_job.split(
        "log-file: artifacts/avatar-gallery-progress.log", maxsplit=1
    )[1].split("       - uses:", maxsplit=1)[0]

    assert "CLOTH_AVATAR_SCREENSHOT_MODE=gallery" in gallery_invocation
    assert "FREECAD_CLOTH_ANNY_FIT_STEPS=10" in gallery_invocation
    assert "FREECAD_CLOTH_ANNY_FIT_STEPS=18" not in gallery_invocation
    assert "freecad_application_timeout_seconds" not in gallery_job
    assert "timeout-minutes: &ten_minute_timeout 10" in workflow
    assert workflow.count("timeout-minutes: &ten_minute_timeout 10") == 1
    assert "timeout-minutes: *ten_minute_timeout" in gallery_job
