"""Contract tests for the diagnostic contact controls.

These assertions protect the diagnostic scope and the shared manifest contract without
making the diagnostic artifact a release gate.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests" / "freecad_tissu_contact_diagnostics.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")


def test_diagnostic_controls_are_static_and_one_step():
    assert '"control-0-cube"' in SOURCE
    assert '"control-0a-avatar"' in SOURCE
    assert "scene.Steps = 1" in SOURCE
    assert '"diagnostic-only-contact-controls"' in SOURCE
    assert '"release_gate_effect": "none"' in SOURCE
    assert "GravityZ = 0.0" in SOURCE


def test_diagnostic_manifest_contains_shared_schema_fields():
    for needle in (
        '"schema": 1',
        '"solver_settings_frozen"',
        '"particle_distance_mm"',
        '"iterations"',
        '"substeps"',
        '"timestep_s"',
        '"gravity_mm_s2"',
        '"cases"',
        '"contact_state"',
        '"images"',
        '"release_gate_effect"',
    ):
        assert needle in SOURCE


def test_canonical_workflow_uses_single_opt_in_dispatch_job():
    assert "diagnostic_controls:" in WORKFLOW
    assert "diagnostic-tissu-contact:" in WORKFLOW
    assert "github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls" in WORKFLOW
    job = WORKFLOW.split("diagnostic-tissu-contact:", 1)[1].split("\n  ", 1)[0]
    assert "needs: [local_runner_readiness]" in WORKFLOW
    assert "needs: [diagnostic-tissu-contact]" not in WORKFLOW
    assert "release_gate_effect" not in job


def test_diagnostic_entrypoint_and_failure_evidence_are_explicit():
    assert 'CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1' in WORKFLOW
    assert 'os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1"' in SOURCE
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE
    assert "entrypoint __name__=" in SOURCE
    assert "setsid /opt/freecad/AppRun /workspace/tests/freecad_tissu_contact_diagnostics.py" in WORKFLOW
    assert "diagnostic-contact-supervisor=timeout" in WORKFLOW
    assert "artifacts/tissu-contact-diagnostics/app-run.log" in WORKFLOW
    assert "if-no-files-found: warn" in WORKFLOW
    assert "retention-days: 14" in WORKFLOW
