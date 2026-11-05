# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract checks for the canonical runner topology and trust boundaries."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.ci.pytest_collection_contract import (
    missing_requested_modules,
    validate_collection_contract,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    """Extract one named job block from workflow source text.

    Args:
        source: Full workflow YAML text.
        job: Job identifier whose indented block should be extracted.

    Returns:
        The requested block, including its lines, but excluding the next job.
    """
    marker = f"  {job}:\n"
    start = source.index(marker)
    remainder = source[start + len(marker) :]
    lines = remainder.splitlines(keepends=True)
    block = []
    for line in lines:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            break
        block.append(line)
    return "".join(block)


def test_one_canonical_workflow() -> None:
    """Require the canonical workflow and its three entry-point callers only."""
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = sorted(path.name for path in workflow_dir.glob("*.yml"))
    assert workflows == [
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    ], "Only the canonical workflow and its three callers should exist."
    shared = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in shared, "The canonical workflow must support workflow_call."
    assert "workflow_run:" not in shared, (
        "The canonical workflow must not be triggered by workflow_run."
    )


def test_pull_requests_are_hosted_only() -> None:
    """Keep all pull-request validation jobs on the hosted runner path."""
    workflow_dir = ROOT / ".github" / "workflows"
    entry = (workflow_dir / "commit-validation.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in entry, "PR validation trigger is missing."
    assert "pull_request_target:" not in entry, (
        "PR validation must not use the privileged pull_request_target event."
    )
    fast = _job_block(entry, "fast-feedback")
    full = _job_block(entry, "explicit-full-validation")
    assert "runner_mode: hosted" in fast, "Fast PR feedback must select the hosted runner."
    assert "execution_mode: fast" in fast, "Fast PR feedback must use fast execution mode."
    assert "runner_mode: hosted" in full, "Full PR validation must select the hosted runner."
    assert "execution_mode: full" in full, "Full PR validation must use full execution mode."
    assert "[full-validation]" in entry, "The full-validation title route must remain explicit."

    readiness = _job_block(source, "local_runner_readiness")
    assert "'ubuntu-latest'" in readiness, "Runner readiness must identify the hosted runner."
    assert "self-hosted" in readiness, "Runner readiness must recognize local runners."
    runner_selector = "github.event_name == 'pull_request' || inputs.runner_mode == 'hosted'"
    jobs = (
        "diagnostic-pbd-contact",
        "simulation-ladder",
        "python",
        "gui-simple",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    )
    for job in jobs:
        block = _job_block(source, job)
        assert runner_selector in block, (
            f"{job} must select hosted runners for PRs and hosted mode."
        )
        assert "'ubuntu-latest'" in block, f"{job} must include the hosted runner label."
        assert "self-hosted" in block, (
            f"{job} must preserve the local-runner option for trusted events."
        )


def test_main_publication_uses_main_only_trigger_and_mode_aware_fallback() -> None:
    """Require main-only publication and mode-appropriate fallback routing."""
    workflow_dir = ROOT / ".github" / "workflows"
    publication = (workflow_dir / "main-publication.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in publication, "Main publication must use a push trigger."
    assert "branches: [main]" in publication, "Publication pushes must be restricted to main."
    assert "default: local" in publication, "Publication must default to local execution."

    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in watchdog, (
        "The watchdog may activate only for trusted dispatch or push events."
    )
    assert "inputs.runner_mode != 'hosted'" in watchdog, (
        "The watchdog must check the selected runner mode."
    )
    assert "tools/ci/runner_watchdog.py" in watchdog, (
        "The watchdog job must call the canonical watchdog script."
    )
    fallback_expression = (
        "FALLBACK_WORKFLOW: ${{ inputs.execution_mode == 'publication' && "
        "'main-publication.yml' || 'commit-validation.yml' }}"
    )
    assert fallback_expression in watchdog, (
        "The watchdog must select the fallback workflow for the execution mode."
    )


def test_trusted_runs_remain_local_first() -> None:
    """Keep trusted event runs local-first while allowing explicit hosted fallback."""
    workflow_dir = ROOT / ".github" / "workflows"
    commit = (workflow_dir / "commit-validation.yml").read_text(encoding="utf-8")
    publication = (workflow_dir / "main-publication.yml").read_text(encoding="utf-8")
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "default: local" in commit, "Commit validation must default to local execution."
    assert "default: local" in publication, "Main publication must default to local execution."
    local_selector = 'fromJSON(\'["self-hosted","linux","x64","docker"]\')'
    jobs = (
        "diagnostic-pbd-contact",
        "simulation-ladder",
        "python",
        "gui-simple",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    )
    for job in jobs:
        block = _job_block(source, job)
        assert local_selector in block, f"{job} must preserve the local-first runner selector."
        assert "inputs.runner_mode == 'hosted'" in block, (
            f"{job} must support an explicit hosted runner selection."
        )


def test_watchdog_dispatches_hosted_fallback_only_for_trusted_runs() -> None:
    """Require trusted-event fallback dispatch without runner discovery."""
    source = WORKFLOW.read_text(encoding="utf-8")
    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in watchdog, (
        "Hosted fallback must be limited to trusted push or dispatch events."
    )
    assert "inputs.runner_mode != 'hosted'" in watchdog, (
        "Hosted fallback must respect the requested runner mode."
    )
    assert "Prefer local, otherwise dispatch hosted" in watchdog, (
        "The watchdog job must explain the local-first fallback policy."
    )
    assert "tools/ci/runner_watchdog.py" in watchdog, (
        "The watchdog job must invoke the maintained helper script."
    )
    assert "FALLBACK_WORKFLOW:" in watchdog, (
        "The fallback workflow name must be passed to the watchdog."
    )

    script = (ROOT / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    assert "time.monotonic() + 45" in script, (
        "The watchdog wait must use the bounded monotonic deadline."
    )
    assert 'os.environ.get("FALLBACK_WORKFLOW", "commit-validation.yml")' in script, (
        "The watchdog must preserve the default fallback workflow."
    )
    assert '"runner_mode=hosted"' in script, "The hosted fallback must request hosted runner mode."
    assert 'f"fallback_source_run={run_id}"' in script, (
        "The hosted fallback must identify its source run."
    )
    assert 'f"repos/{repo}/actions/runs/{run_id}/cancel"' in script, (
        "The watchdog must cancel the stale source run after dispatch."
    )
    assert "/actions/runners" not in source + script, (
        "Runner discovery must not query privileged runner inventory."
    )


def test_no_privileged_runner_discovery_or_second_workflow() -> None:
    """Forbid privileged runner discovery and duplicate workflow entry points."""
    workflow_dir = ROOT / ".github" / "workflows"
    sources = {path.name: path.read_text(encoding="utf-8") for path in workflow_dir.glob("*.yml")}
    assert set(sources) == {
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    }, "The workflow directory must contain only the four canonical workflows."
    assert all("workflow_run:" not in source for source in sources.values()), (
        "No workflow may be triggered by the privileged workflow_run event."
    )
    shared = sources["canonical-execution.yml"]
    forbidden_markers = (
        "CLOTH_RUNNER_DISCOVERY_TOKEN",
        "runner_router:",
        "brokered_hosted_status:",
        "runner_heartbeat:",
        "sketcher-startup-diagnostic:",
        "*/5 * * * *",
    )
    for marker in forbidden_markers:
        assert marker not in shared, (
            f"The canonical workflow must not contain forbidden marker {marker!r}."
        )
    maintenance = _job_block(shared, "maintenance-cleanup")
    assert "runs-on: ubuntu-latest" in maintenance, (
        "Repository maintenance must run on the hosted runner."
    )
    assert "github.event_name == 'schedule'" in maintenance, (
        "Maintenance cleanup must be restricted to scheduled events."
    )
    assert "RUN MAINTENANCE CLEANUP" in maintenance, (
        "Maintenance cleanup must require its explicit event marker."
    )


def test_pr_checkout_is_credential_free_and_uses_head_sha() -> None:
    """Keep pull-request checkout pinned to the head SHA without persisted credentials."""
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source, (
        "PR validation must use the source branch head SHA."
    )
    assert "persist-credentials: false" in source, (
        "PR checkout must not persist repository credentials."
    )


def test_collection_contract_passes_when_every_requested_module_collects() -> None:
    """Accept the collection contract when each requested test module is present."""
    result = missing_requested_modules(
        ("tests/test_one.py", "tests/test_two.py"),
        ("tests/test_one.py", "tests/test_two.py", "tests/test_two.py"),
    )
    assert result == (), "Collection must pass when all requested modules have collected tests."


def test_collection_contract_rejects_a_requested_module_with_zero_items() -> None:
    """Reject a requested test module when collection produces no items from it."""
    expected = (ROOT / "tests" / "test_one.py", ROOT / "tests" / "test_empty.py")
    collected = SimpleNamespace(path=expected[0])
    with pytest.raises(pytest.UsageError, match=r"tests/test_empty\.py"):
        validate_collection_contract(
            [collected],
            environ={"CLOTH_EXPECTED_TEST_MODULES": os.pathsep.join(map(str, expected))},
        )
