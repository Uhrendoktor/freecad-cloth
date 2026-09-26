"""Contract checks for canonical runner safety and local-first fallback."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    marker = f"  {job}:\n"
    start = source.index(marker)
    remainder = source[start + len(marker):]
    next_job = remainder.find("\n  ")
    return remainder if next_job < 0 else remainder[:next_job]



def _job_blocks(source: str) -> dict[str, str]:
    jobs = source.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\n", jobs, re.MULTILINE))
    return {
        match.group(1): jobs[match.start() : (matches[index + 1].start() if index + 1 < len(matches) else len(jobs))]
        for index, match in enumerate(matches)
    }


def test_no_pull_request_path_can_select_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    trigger_section = source.split("\njobs:\n", 1)[0]
    assert "\n  pull_request:\n" not in trigger_section
    assert "\n  pull_request_target:\n" in trigger_section

    trusted_event_gates = (
        "github.event_name != 'pull_request_target'",
        "github.event_name == 'push'",
        "github.event_name == 'schedule'",
        "github.event_name == 'workflow_dispatch'",
    )
    for job, block in _job_blocks(source).items():
        if "self-hosted" not in block:
            continue
        assert any(gate in block for gate in trusted_event_gates), (
            f"{job} exposes a self-hosted runner without a trusted-event gate"
        )


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
    assert "-f pull_request_sha=" in broker
    assert "actions/checkout" not in broker
    assert "self-hosted" not in broker

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
        assert "github.event_name != 'pull_request_target'" in block
        assert "fromJSON('[\"ubuntu-latest\"]')" in block

    sketcher = _job_block(source, "sketcher-startup-diagnostic")
    assert "github.event_name == 'workflow_dispatch'" in sketcher
    assert "inputs.pull_request_number != ''" in sketcher


def test_trusted_jobs_default_to_local_runner():
    source = WORKFLOW.read_text(encoding="utf-8")
    for job in ("python", "gui-tunic-visual", "gui-turntables", "gui-visual-examples", "benchmark"):
        block = _job_block(source, job)
        assert "self-hosted" in block
        assert "inputs.runner_mode == 'hosted'" in block


def test_pr_validation_checks_out_only_the_requested_pr_head_sha():
    source = WORKFLOW.read_text(encoding="utf-8")
    python = _job_block(source, "python")
    assert "inputs.pull_request_number != ''" in python
    assert "inputs.pull_request_sha != ''" in python
    assert "persist-credentials: false" in python
    assert "inputs.runner_mode == 'hosted'" in python

    watchdog = _job_block(source, "runner_watchdog")
    assert "runs-on: ubuntu-latest" in watchdog
    assert "grace_seconds=45" in watchdog
    assert "Python and FreeCAD non-GUI tests" in watchdog
    assert "gh workflow run canonical-execution.yml" in watchdog
    assert "-f runner_mode=hosted" in watchdog
    assert "cancel" in watchdog
    assert "/actions/runners" not in watchdog
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in watchdog
    assert "/actions/runners" not in source
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in source


def test_only_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 1
    assert static in _job_block(source, "runner_heartbeat")


def test_hosted_fallback_preserves_main_publication():
    source = WORKFLOW.read_text(encoding="utf-8")
    publish = _job_block(source, "publish-readme-turntables")
    assert "github.event_name == 'workflow_dispatch'" in publish
    assert "inputs.runner_mode == 'hosted'" in publish
    assert "inputs.fallback_source_run != ''" in publish
    assert "refs/heads/main" in publish
    assert "inputs.pull_request_number != ''" in publish


def test_broker_dispatches_immutable_pr_head_sha_and_checkout_avoids_ephemeral_merge_ref():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert 'pull_request_sha="${{ github.event.pull_request.head.sha }}"' in source
    assert "inputs.pull_request_sha" in source
    assert "refs/pull/{0}/merge" not in source


def test_stale_run_cleanup_tolerates_only_completed_run_409():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "HTTP 409" in source
    assert 'exit "$cancel_status"' in source
