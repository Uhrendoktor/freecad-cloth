"""Contract checks for canonical runner routing security."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'canonical-execution.yml'

def _job_block(source: str, job: str) -> str:
    marker = '  %s:\n' % job
    start = source.index(marker)
    remainder = source[start + len(marker):]
    next_job = remainder.find('\n  ')
    return remainder if next_job < 0 else remainder[:next_job]

def test_one_canonical_workflow():
    workflows = sorted((ROOT / '.github' / 'workflows').glob('*.yml'))
    workflows += sorted((ROOT / '.github' / 'workflows').glob('*.yaml'))
    assert [path.name for path in workflows] == ['canonical-execution.yml']

def test_pull_requests_are_hosted_only():
    source = WORKFLOW.read_text(encoding='utf-8')
    assert 'runner_router:' in source
    router = _job_block(source, 'runner_router')
    assert 'runs-on: ubuntu-latest' in router
    assert 'pull-request-hosted-only' in router
    assert 'CLOTH_RUNNER_DISCOVERY_TOKEN' in router
    assert 'runs_on=' + '["ubuntu-latest"]' in router

def test_only_router_can_emit_self_hosted_labels():
    source = WORKFLOW.read_text(encoding='utf-8')
    static = 'runs-on: [self-hosted, linux, x64, docker]'
    assert static not in source
    assert 'required=["self-hosted","linux","x64","docker"]' in source

def test_normal_jobs_depend_on_router():
    source = WORKFLOW.read_text(encoding='utf-8')
    jobs = ['python','sketcher-startup-diagnostic','gui-sewing-creation','gui-sketcher-acceptance','gui-pattern-export','gui-tunic-visual','gui-turntables','gui-visual-examples','publish-readme-turntables','maintenance-cleanup','benchmark']
    assert 'fromJSON(needs.runner_router.outputs.runs_on)' in source
    for job in jobs:
        block = _job_block(source, job)
        assert 'needs: runner_router' in block or 'needs: [runner_router,' in block
        assert 'fromJSON(needs.runner_router.outputs.runs_on)' in block

def test_fail_closed_diagnostics_are_credential_safe():
    source = WORKFLOW.read_text(encoding='utf-8')
    router = _job_block(source, 'runner_router')
    for reason in (
        'pull-request-hosted-only',
        'runner-discovery-token-not-configured',
        'invalid-runner-api-response',
        'runner-api-error',
        'local-runner-unreachable-or-busy',
    ):
        assert reason in router
    assert 'sed -n' not in router
    assert 'echo "$GH_TOKEN"' not in router

def test_runner_scope_and_absent_configuration_are_documented():
    docs = (ROOT / 'docs' / 'DEVELOPMENT.md').read_text(encoding='utf-8')
    assert 'CLOTH_RUNNER_DISCOVERY_TOKEN' in docs
    assert 'Administration: read' in docs
    assert 'absent configuration intentionally selects hosted execution' in docs

def test_publish_and_heartbeat_have_single_needs_key():
    source = WORKFLOW.read_text(encoding='utf-8')
    publish = _job_block(source, 'publish-readme-turntables')
    heartbeat = _job_block(source, 'runner_heartbeat')
    assert 'needs: [runner_router, gui-tunic-visual, gui-turntables, gui-visual-examples]' in publish
    assert 'needs: runner_router' in heartbeat
