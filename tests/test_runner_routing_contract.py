"""Contract checks for canonical runner safety and trusted fallback."""

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


def test_pull_request_broker_dispatches_hosted_validation():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target:" in source

    broker = _job_block(source, "pull_request_broker")
    assert "runs-on: ubuntu-latest" in broker
    assert "actions: write" in broker
    assert "contents: read" in broker
    assert "gh workflow run canonical-execution.yml" in broker
    assert "--ref main" in broker
    assert "-f runner_mode=hosted" in broker
    assert "-f pull_request_number=" in broker
    assert "actions/checkout" not in broker
    assert "self-hosted" not in broker


def test_pr_validation_cannot_reach_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    readiness = _job_block(source, "local_runner_readiness")
    assert "github.event_name != 'pull_request_target'" in readiness

    jobs = (
        "python",
        "sketcher-startup-diagnostic",
        "gui-sewing-creation",
        "gui-sketcher-acceptance",
        "gui-pattern-export",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
    )
    for job in jobs:
        block = _job_block(source, job)
        assert "needs: [local_runner_readiness]" in block
        assert "inputs.runner_mode == 'hosted'" in block
        assert "fromJSON('[\"ubuntu-latest\"]')" in block

    sketcher = _job_block(source, "sketcher-startup-diagnostic")
    assert "github.event_name == 'workflow_dispatch'" in sketcher
    assert "inputs.pull_request_number != ''" in sketcher


def test_pr_validation_checks_out_only_the_requested_merge_ref():
    source = WORKFLOW.read_text(encoding="utf-8")
    python = _job_block(source, "python")
    assert "refs/pull/{0}/merge" in python
    assert "persist-credentials: false" in python


def test_trusted_jobs_default_to_local_runner():
    source = WORKFLOW.read_text(encoding="utf-8")
    for job in ("python", "gui-tunic-visual", "gui-turntables", "gui-visual-examples", "benchmark"):
        block = _job_block(source, job)
        assert "self-hosted" in block
        assert "inputs.runner_mode == 'hosted'" in block


def test_watchdog_is_hosted_and_failover_is_bounded():
    source = WORKFLOW.read_text(encoding="utf-8")
    watchdog = _job_block(source, "runner_watchdog")
    assert "runs-on: ubuntu-latest" in watchdog
    assert "grace_seconds=45" in watchdog
    assert "Selected runner readiness" in watchdog
    assert "gh workflow run canonical-execution.yml" in watchdog
    assert "-f runner_mode=hosted" in watchdog
    assert "cancel" in watchdog
    assert "github.event_name != 'pull_request_target'" in watchdog
    assert "/actions/runners" not in source
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in source


def test_only_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 1
    heartbeat = _job_block(source, "runner_heartbeat")
    assert static in heartbeat
