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
        '"cases"',
        '"case_id"',
        '"predecessor_case_id"',
        '"solver"',
        '"collision"',
        '"pre_step"',
        '"checkpoints"',
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
    assert "view.saveImage(str(path), 1280, 720, \"White\")" in SOURCE
    assert 'view.saveImage(str(path), 1280, 720, "White", 1)' not in SOURCE
    assert "app.quit()" in SOURCE
    assert "App.exit()" in SOURCE
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE
    assert "entrypoint __name__=" in SOURCE
    assert '"CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED"' in SOURCE
    assert "QtCore.QTimer.singleShot(0, _scheduled_main)" in SOURCE
    assert "os._exit(status)" in SOURCE
    assert "Gui.activeDocument().activeView()" in SOURCE
    assert "setsid /opt/freecad/AppRun /workspace/tests/freecad_tissu_contact_diagnostics.py" in WORKFLOW
    assert "diagnostic-contact-supervisor=timeout" in WORKFLOW
    assert "artifacts/tissu-contact-diagnostics/app-run.log" in WORKFLOW
    assert "if-no-files-found: warn" in WORKFLOW
    assert "retention-days: 14" in WORKFLOW

def test_diagnostic_freecad_gui_lifecycle_and_screenshot_api_are_bounded():
    assert 'view.saveImage(str(path), 1280, 720, "White")' in SOURCE
    assert 'view.saveImage(str(path), 1280, 720, "White", 1)' not in SOURCE
    assert "QtCore.QTimer.singleShot(0, _run_from_freecad_event_loop)" in SOURCE
    assert "def close_gui():" in SOURCE
    assert "window.close()" in SOURCE
    assert "app.quit()" in SOURCE
