"""Contract checks for the canonical runner safety boundary."""
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
    router = _job_block(source, "runner_router")
    assert "github.event_name" + " == \"pull_request\"" in router
    assert "pull-request-hosted-only" in router
    assert "runs_on=[\"ubuntu-latest\"]" in router

def test_trusted_events_use_router_outputs():
    source = WORKFLOW.read_text(encoding="utf-8")
    dynamic = "fromJSON(needs.runner_router.outputs.runs_on)"
    jobs = ["runner_heartbeat", "python", "gui-tunic-visual", "gui-turntables", "gui-visual-examples", "publish-readme-turntables", "maintenance-cleanup", "benchmark"]
    for job in jobs:
        block = _job_block(source, job)
        assert "needs: runner_router" in block or "needs: [runner_router," in block
        assert dynamic in block

def test_runner_discovery_fails_closed():
    source = WORKFLOW.read_text(encoding="utf-8")
    router = _job_block(source, "runner_router")
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" in router
    assert "reason=runner-discovery-token-not-configured" in router
    assert "reason=invalid-runner-api-response" in router
    assert "reason=runner-api-error" in router
    assert "reason=local-runner-unreachable-or-busy" in router

def test_no_privileged_pr_broker_or_watchdog():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_broker:" not in source
    assert "runner_watchdog:" not in source
    assert "local_runner_readiness:" not in source

def test_only_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 0
    assert "fromJSON(needs.runner_router.outputs.runs_on)" in _job_block(source, "runner_heartbeat")
