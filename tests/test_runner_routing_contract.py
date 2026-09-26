"""Contract checks for canonical hosted-only PR routing and trusted fallback."""
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
    assert "runs-on: ubuntu-latest" in router
    assert "pull-request-hosted-only" in router
    assert 'runs_on=["ubuntu-latest"]' in router
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" in router

def test_all_substantive_jobs_use_router_output():
    source = WORKFLOW.read_text(encoding="utf-8")
    dynamic = "fromJSON(needs.runner_router.outputs.runs_on)"
    jobs = ["runner_heartbeat","python","sketcher-startup-diagnostic","gui-sewing-creation","gui-sketcher-acceptance","gui-pattern-export","gui-tunic-visual","gui-turntables","gui-visual-examples","publish-readme-turntables","maintenance-cleanup","benchmark"]
    for job in jobs:
        block = _job_block(source, job)
        assert "needs: runner_router" in block or "needs: [runner_router" in block
        assert dynamic in block

def test_runner_discovery_fails_closed():
    source = WORKFLOW.read_text(encoding="utf-8")
    router = _job_block(source, "runner_router")
    assert 'if test -z "${GH_TOKEN:-}"; then' in router
    assert "reason=runner-discovery-token-not-configured" in router
    assert "reason=invalid-runner-api-response" in router
    assert "reason=runner-api-error" in router
    assert "reason=local-runner-unreachable-or-busy" in router

def test_pr_head_checkout_is_immutable_and_credential_free():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source
    assert "refs/pull/{0}/merge" not in source
    assert "persist-credentials: false" in source

def test_no_privileged_pr_broker_or_watchdog_remains():
    source = WORKFLOW.read_text(encoding="utf-8")
    for marker in ("pull_request_broker:", "brokered_hosted_status:", "local_runner_readiness:", "runner_watchdog:"):
        assert marker not in source

def test_stale_run_cleanup_uses_normal_pr_event():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "event=pull_request" in source
    assert "event=pull_request_target" not in source
