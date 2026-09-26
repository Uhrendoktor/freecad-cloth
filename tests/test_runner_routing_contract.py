"""Contract checks for the canonical GitHub Actions runner router."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    marker = "  %s:\n" % job
    start = source.index(marker)
    remainder = source[start + len(marker):]
    next_job = remainder.find("\n  ")
    return remainder if next_job < 0 else remainder[:next_job]


def test_repository_keeps_one_canonical_workflow():
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))
    assert [path.name for path in workflows] == ["canonical-execution.yml"]


def test_runner_router_is_hosted_and_pr_safe():
    source = WORKFLOW.read_text(encoding="utf-8")
    router = _job_block(source, "runner_router")
    assert "runs-on: ubuntu-latest" in router
    assert 'if test "${{ github.event_name }}" = "pull_request"' in router
    assert "pull-request-hosted-only" in router
    assert "GH_TOKEN: ${{" + " secrets.CLOTH_RUNNER_DISCOVERY_TOKEN }}" in router
    assert "runs_on=[" + "\"ubuntu-latest\"" + "]" in router


def test_only_local_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 1
    heartbeat = _job_block(source, "runner_heartbeat")
    assert static in heartbeat


def test_normal_self_hosted_jobs_depend_on_router():
    source = WORKFLOW.read_text(encoding="utf-8")
    jobs = [
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
    ]
    dynamic_runs_on = "runs-on: ${{" + " fromJSON(needs.runner_router.outputs.runs_on) }}"
    for job in jobs:
        block = _job_block(source, job)
        assert "needs: runner_router" in block or "needs: [runner_router," in block
        assert dynamic_runs_on in block
