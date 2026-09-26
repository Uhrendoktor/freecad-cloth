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


def test_pull_request_broker_is_trusted_and_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target:" in source
    assert "\n  pull_request:\n" not in source

    broker = _job_block(source, "pull_request_broker")
    assert "if: ${{ github.event_name == 'pull_request_target' }}" in broker
    assert "runs-on: ubuntu-latest" in broker
    assert "actions: write" in broker
    assert "contents: read" in broker
    assert "gh workflow run canonical-execution.yml" in broker
    assert "--ref main" in broker
    assert "-f runner_mode=hosted" in broker
    assert "-f pull_request_number=" in broker
    assert "actions/checkout" not in broker
    assert "self-hosted" not in broker
    assert "/actions/runners" not in broker


def test_pr_broker_cannot_start_substantive_work():
    source = WORKFLOW.read_text(encoding="utf-8")
    router = _job_block(source, "runner_router")
    assert "github.event_name != 'pull_request_target'" in router

    for job in (
        "python",
        "sketcher-startup-diagnostic",
        "gui-sewing-creation",
        "gui-sketcher-acceptance",
        "gui-pattern-export",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "publish-readme-turntables",
        "maintenance-cleanup",
        "benchmark",
    ):
        block = _job_block(source, job)
        assert "needs: runner_router" in block or "needs: [runner_router," in block

    sketcher = _job_block(source, "sketcher-startup-diagnostic")
    assert "github.event_name == 'workflow_dispatch'" in sketcher
    assert "inputs.pull_request_number != ''" in sketcher


def test_pr_validation_forced_hosted_on_trusted_dispatch():
    source = WORKFLOW.read_text(encoding="utf-8")
    router = _job_block(source, "runner_router")
    assert "inputs.runner_mode" in router
    assert 'fallback "explicit-hosted"' in router
    assert "secrets.CLOTH_RUNNER_DISCOVERY_TOKEN" in router
    assert "repos/$REPO/actions/runners?per_page=100" in router
    assert "runner-api-error" in router
    assert "local-runner-unreachable-or-busy" in router


def test_pr_dispatch_checks_out_only_the_requested_merge_ref():
    source = WORKFLOW.read_text(encoding="utf-8")
    for job in (
        "python",
        "sketcher-startup-diagnostic",
        "gui-sewing-creation",
        "gui-sketcher-acceptance",
        "gui-pattern-export",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    ):
        block = _job_block(source, job)
        assert "refs/pull/{0}/merge" in block
        assert "persist-credentials: false" in block


def test_only_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 1
    heartbeat = _job_block(source, "runner_heartbeat")
    assert static in heartbeat


def test_time_budgets_remain_unchanged():
    source = WORKFLOW.read_text(encoding="utf-8")
    for timeout in (
        "timeout-minutes: 20",
        "timeout-minutes: 5",
        "timeout-minutes: 10",
        "timeout-minutes: 25",
        "timeout-minutes: 12",
    ):
        assert timeout in source
