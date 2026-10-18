# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract checks for the canonical runner topology and trust boundaries."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    marker = f"  {job}:\n"
    start = source.index(marker)
    remainder = source[start + len(marker) :]
    lines = remainder.splitlines(True)
    block = []
    for line in lines:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            break
        block.append(line)
    return "".join(block)


def test_one_canonical_workflow():
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = sorted(path.name for path in workflow_dir.glob("*.yml"))
    assert workflows == [
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    ]
    shared = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in shared
    assert "workflow_run:" not in shared


def test_pull_requests_are_hosted_only():
    workflow_dir = ROOT / ".github" / "workflows"
    entry = (workflow_dir / "commit-validation.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in entry
    assert "pull_request_target:" not in entry
    fast = _job_block(entry, "fast-feedback")
    full = _job_block(entry, "explicit-full-validation")
    assert "runner_mode: hosted" in fast
    assert "execution_mode: fast" in fast
    assert "runner_mode: hosted" in full
    assert "execution_mode: full" in full
    assert "[full-validation]" in entry

    readiness = _job_block(source, "local_runner_readiness")
    assert "'ubuntu-latest'" in readiness
    assert "self-hosted" in readiness
    runner_selector = "github.event_name == 'pull_request' || inputs.runner_mode == 'hosted'"
    for job in (
        "diagnostic-pbd-contact",
        "simulation-ladder",
        "python",
        "gui-simple",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    ):
        block = _job_block(source, job)
        assert runner_selector in block
        assert "'ubuntu-latest'" in block
        assert "self-hosted" in block


def test_main_publication_uses_main_only_trigger_and_mode_aware_fallback() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    publication = (workflow_dir / "main-publication.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in publication
    assert "branches: [main]" in publication
    assert "default: local" in publication

    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in watchdog
    assert "inputs.runner_mode != 'hosted'" in watchdog
    assert "tools/ci/runner_watchdog.py" in watchdog
    assert (
        "FALLBACK_WORKFLOW: ${{ inputs.execution_mode == 'publication' && 'main-publication.yml' || 'commit-validation.yml' }}"
        in watchdog
    )


def test_trusted_runs_remain_local_first():
    workflow_dir = ROOT / ".github" / "workflows"
    commit = (workflow_dir / "commit-validation.yml").read_text(encoding="utf-8")
    publication = (workflow_dir / "main-publication.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "default: local" in commit
    assert "default: local" in publication
    local_selector = 'fromJSON(\'["self-hosted","linux","x64","docker"]\')'
    for job in (
        "diagnostic-pbd-contact",
        "simulation-ladder",
        "python",
        "gui-simple",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    ):
        block = _job_block(source, job)
        assert local_selector in block
        assert "inputs.runner_mode == 'hosted'" in block


def test_watchdog_dispatches_hosted_fallback_only_for_trusted_runs():
    source = WORKFLOW.read_text(encoding="utf-8")
    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in watchdog
    assert "inputs.runner_mode != 'hosted'" in watchdog
    assert "Prefer local, otherwise dispatch hosted" in watchdog
    assert "tools/ci/runner_watchdog.py" in watchdog
    assert "FALLBACK_WORKFLOW:" in watchdog

    script = (ROOT / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    assert "time.monotonic() + 45" in script
    assert 'os.environ.get("FALLBACK_WORKFLOW", "commit-validation.yml")' in script
    assert '"runner_mode=hosted"' in script
    assert 'f"fallback_source_run={run_id}"' in script
    assert 'f"repos/{repo}/actions/runs/{run_id}/cancel"' in script
    assert "/actions/runners" not in source + script


def test_no_privileged_runner_discovery_or_second_workflow():
    workflow_dir = ROOT / ".github" / "workflows"
    sources = {path.name: path.read_text(encoding="utf-8") for path in workflow_dir.glob("*.yml")}
    assert set(sources) == {
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    }
    assert all("workflow_run:" not in source for source in sources.values())
    shared = sources["canonical-execution.yml"]
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in shared
    assert "runner_router:" not in shared
    assert "brokered_hosted_status:" not in shared
    assert "runner_heartbeat:" not in shared
    assert "sketcher-startup-diagnostic:" not in shared
    assert "*/5 * * * *" not in shared
    maintenance = _job_block(shared, "maintenance-cleanup")
    assert "runs-on: ubuntu-latest" in maintenance
    assert "github.event_name == 'schedule'" in maintenance
    assert "RUN MAINTENANCE CLEANUP" in maintenance


def test_pr_checkout_is_credential_free_and_uses_head_sha():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source
    assert "persist-credentials: false" in source


def test_collection_contract_passes_when_every_requested_module_collects():
    from tools.ci.pytest_collection_contract import missing_requested_modules

    assert (
        missing_requested_modules(
            ("tests/test_one.py", "tests/test_two.py"),
            ("tests/test_one.py", "tests/test_two.py", "tests/test_two.py"),
        )
        == ()
    )


def test_collection_contract_rejects_a_requested_module_with_zero_items():
    import os
    from types import SimpleNamespace

    import pytest

    from tools.ci.pytest_collection_contract import validate_collection_contract

    expected = (ROOT / "tests" / "test_one.py", ROOT / "tests" / "test_empty.py")
    collected = SimpleNamespace(path=expected[0])
    with pytest.raises(pytest.UsageError, match="tests/test_empty.py"):
        validate_collection_contract(
            [collected],
            environ={"CLOTH_EXPECTED_TEST_MODULES": os.pathsep.join(map(str, expected))},
        )
