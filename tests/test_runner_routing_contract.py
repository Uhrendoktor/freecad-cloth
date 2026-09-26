"""Contract checks for canonical runner safety and local-first fallback."""
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
    for job in ("python", "gui-sewing-creation", "gui-sketcher-acceptance", "gui-pattern-export", "gui-tunic-visual", "gui-turntables", "gui-visual-examples", "publish-readme-turntables", "benchmark"):
        block = _job_block(source, job)
        assert "github.event_name == 'pull_request'" in block
        assert "ubuntu-latest" in block
        assert "self-hosted" in block


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
    assert "Python and FreeCAD non-GUI tests" in watchdog
    assert "gh workflow run canonical-execution.yml" in watchdog
    assert "-f runner_mode=hosted" in watchdog
    assert "cancel" in watchdog
    assert "/actions/runners" not in watchdog
    assert "CLOTH_RUNNER_DISCOVERY_TOKEN" not in watchdog
    assert "pull_request_target" not in source


def test_only_heartbeat_is_static_self_hosted():
    source = WORKFLOW.read_text(encoding="utf-8")
    static = "runs-on: [self-hosted, linux, x64, docker]"
    assert source.count(static) == 1
    assert static in _job_block(source, "runner_heartbeat")


def test_blanket_evidence_validates_after_docker_restore():
    source = WORKFLOW.read_text(encoding="utf-8")
    block = source.split("  gui-visual-examples:", 1)[1].split("  publish-readme-turntables:", 1)[0]
    restore = block.index("name: Restore workspace from Docker volume")
    validate = block.index("name: Validate blanket visual evidence")
    assert restore < validate
