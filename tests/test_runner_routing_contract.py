"""Contract checks for the canonical runner topology."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    marker = f"  {job}:\n"
    start = source.index(marker)
    remainder = source[start + len(marker):]
    next_job = remainder.find("\n  ")
    return remainder if next_job < 0 else remainder[:next_job]


def test_one_canonical_workflow():
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))
    assert [path.name for path in workflows] == ["canonical-execution.yml"]


def test_pull_requests_are_hosted_only():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in source
    assert "pull_request_target:" not in source
    assert "pull_request_broker:" not in source
    readiness = _job_block(source, "local_runner_readiness")
    assert "github.event_name == 'pull_request'" in readiness
    assert "'ubuntu-latest'" in readiness

    dynamic = "(github.event_name == 'pull_request' || inputs.runner_mode == 'hosted')"
    for job in (
        "python",
        "gui-sewing-creation",
        "gui-sketcher-acceptance",
        "gui-pattern-export",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
    ):
        block = _job_block(source, job)
        assert "needs: [local_runner_readiness]" in block
        assert dynamic in block


def test_trusted_runs_remain_local_first():
    source = WORKFLOW.read_text(encoding="utf-8")
    for job in ("local_runner_readiness", "python", "gui-tunic-visual", "gui-turntables", "gui-visual-examples", "benchmark"):
        block = _job_block(source, job)
        assert "self-hosted" in block
    assert "inputs.runner_mode == 'hosted'" in source


def test_watchdog_dispatches_hosted_fallback():
    source = WORKFLOW.read_text(encoding="utf-8")
    watchdog = _job_block(source, "runner_watchdog")
    assert "github.event_name != 'pull_request'" in watchdog
    assert "inputs.runner_mode != 'hosted'" in watchdog
    assert "grace_seconds=45" in watchdog
    assert "gh workflow run canonical-execution.yml" in watchdog
    assert "-f runner_mode=hosted" in watchdog
    assert "-f fallback_source_run=" in watchdog
    assert "cancel" in watchdog
    assert "/actions/runners" not in watchdog


def test_no_privileged_runner_discovery_or_second_workflow():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in source
    assert "runner_router:" not in source
    assert "brokered_hosted_status:" not in source
    assert "runner_heartbeat:" not in source
    assert "sketcher-startup-diagnostic:" not in source
    assert "*/5 * * * *" not in source


def test_pr_checkout_is_credential_free_and_uses_head_sha():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source
    assert "persist-credentials: false" in source
