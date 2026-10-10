"""Tests for the repository's single-source CI configuration contracts."""

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
    assert configured > 0
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
    runner = (ROOT / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")

    assert "timeout-seconds:" not in workflow
    assert "timeout-seconds:" not in action
    assert "configured_timeout_seconds()" in runner


def test_timeout_contract_is_documented():
    """The human documentation points to the authoritative configuration."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "CI_CONFIGURATION.md").read_text(encoding="utf-8")

    assert "CI configuration" in docs
    assert "pyproject.toml" in configuration
    assert "freecad_application_timeout_seconds" in configuration


def test_maintenance_cleanup_paginates_until_a_short_page(monkeypatch):
    from tools.ci import maintenance_cleanup

    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}],
    }
    requested_pages = []

    def fake_gh_json(*args):
        endpoint = args[1]
        page = int(endpoint.rsplit("page=", maxsplit=1)[1])
        requested_pages.append(page)
        return {"workflow_runs": pages[page]}

    monkeypatch.setattr(maintenance_cleanup, "gh_json", fake_gh_json)
    items = list(
        maintenance_cleanup.paginated_api_items(
            "repos/example/repo/actions/runs?status=completed",
            collection_key="workflow_runs",
            page_size=2,
        )
    )

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert requested_pages == [1, 2]


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


def test_ruff_and_clone_gates_are_read_only_and_cover_changed_tests():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]

    assert "python -m ruff format --check tools/ci" in quality
    assert "python -m ruff format tools/ci\n" not in quality
    assert "python -m ruff check --fix tools/ci" not in quality
    assert "xargs -r python -m ruff check <" in quality
    assert 'path: "freecad_cloth tests tools/ci"' in workflow
