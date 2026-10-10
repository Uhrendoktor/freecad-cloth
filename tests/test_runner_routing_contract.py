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
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))
    assert [path.name for path in workflows] == ["canonical-execution.yml"]


def test_pull_requests_are_hosted_only():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in source
    assert "pull_request_target:" not in source
    readiness = _job_block(source, "local_runner_readiness")
    assert "github.event_name == 'pull_request'" in readiness
    assert "'ubuntu-latest'" in readiness
    assert "self-hosted" in readiness

    # All validation jobs use the same explicit trust-boundary runner selector.
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
        assert "needs: [agent-quality, local_runner_readiness, pbd_validation_image]" in block
        assert "(github.event_name == 'pull_request' || inputs.runner_mode == 'hosted')" in block
        assert "'ubuntu-latest'" in block


def test_trusted_runs_remain_local_first():
    source = WORKFLOW.read_text(encoding="utf-8")
    for job in (
        "local_runner_readiness",
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
        assert "self-hosted" in block
        assert "inputs.runner_mode == 'hosted'" in block


def test_watchdog_dispatches_hosted_fallback_only_for_trusted_runs():
    source = WORKFLOW.read_text(encoding="utf-8")
    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in watchdog
    assert "inputs.runner_mode != 'hosted'" in watchdog
    assert "Prefer local, otherwise dispatch hosted" in watchdog
    assert "tools/ci/runner_watchdog.py" in watchdog

    script = (ROOT / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    assert "time.monotonic() + 45" in script
    assert '"canonical-execution.yml"' in script
    assert '"runner_mode=hosted"' in script
    assert 'f"fallback_source_run={run_id}"' in script
    assert 'f"repos/{repo}/actions/runs/{run_id}/cancel"' in script
    assert "/actions/runners" not in source + script


def test_no_privileged_runner_discovery_or_second_workflow():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in source
    assert "runner_router:" not in source
    assert "brokered_hosted_status:" not in source
    assert "runner_heartbeat:" not in source
    assert "sketcher-startup-diagnostic:" not in source
    assert "*/5 * * * *" not in source
    maintenance = _job_block(source, "maintenance-cleanup")
    assert "runs-on: ubuntu-latest" in maintenance
    assert "needs: [agent-quality]" in maintenance
    assert "github.event_name == 'schedule'" in maintenance


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


def test_collection_contract_rejects_a_requested_module_with_zero_items(monkeypatch):
    import os
    from types import SimpleNamespace

    import pytest

    from tools.ci.pytest_collection_contract import pytest_collection_modifyitems

    expected = (ROOT / "tests" / "test_one.py", ROOT / "tests" / "test_empty.py")
    monkeypatch.setenv("CLOTH_EXPECTED_TEST_MODULES", os.pathsep.join(map(str, expected)))
    collected = SimpleNamespace(path=expected[0])
    with pytest.raises(pytest.UsageError, match="tests/test_empty.py"):
        pytest_collection_modifyitems([collected])
