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
    assert "scene.GravityZ = 0.0" in SOURCE


def test_diagnostic_manifest_contains_shared_schema_fields():
    for needle in (
        '"schema": 1',
        '"cases"',
        '"case_id"',
        '"predecessor_case_id"',
        '"case":',
        '"rung"',
        '"solver"',
        '"collision"',
        '"source_triangles"',
        '"solver_triangles"',
        '"pre_step"',
        '"piece_bounds"',
        '"checkpoints"',
        '"contact_state"',
        '"first_contact_step"',
        '"control"',
        '"release_gate_effect"',
    ):
        assert needle in SOURCE


def test_canonical_workflow_uses_single_opt_in_dispatch_job():
    assert "diagnostic_controls:" in WORKFLOW
    assert "diagnostic-tissu-contact:" in WORKFLOW
    assert "github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls" in WORKFLOW
    assert "needs: [local_runner_readiness]" in WORKFLOW
    assert "needs: [diagnostic-tissu-contact]" not in WORKFLOW


def test_diagnostic_entrypoint_and_failure_evidence_are_explicit():
    assert 'CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1' in WORKFLOW
    assert 'os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1"' in SOURCE
    assert 'CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED' in SOURCE
    assert "QtCore.QTimer.singleShot(0, _scheduled_main)" in SOURCE
    assert "os._exit(status)" in SOURCE
    assert "Gui.activeDocument().activeView()" in SOURCE
    assert "solver_collision_surface" in SOURCE
    assert "penetration_shift_mm = 16.0" in SOURCE
    assert "def _point_inside_mesh(point, vertices, triangles):" in SOURCE
    assert "def _shutdown_gui():" in SOURCE
    assert "app.quit()" in SOURCE
    assert "App.exit()" not in SOURCE
    assert "gui-shutdown-requested" in SOURCE
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE
    assert "entrypoint __name__=" in SOURCE
    assert "setsid /opt/freecad/AppRun /workspace/tests/freecad_tissu_contact_diagnostics.py" in WORKFLOW
    assert "Shape.CenterOfMass" in SOURCE
    assert "width=72.0" in SOURCE
    assert 'did not create a true interior pre-step state' in SOURCE
    assert 'tissu-env: collision_mode=' in SOURCE
    assert "diagnostic-contact-supervisor=timeout" in WORKFLOW
    assert "artifacts/tissu-contact-diagnostics/app-run.log" in WORKFLOW
    assert "if-no-files-found: warn" in WORKFLOW
    assert "retention-days: 14" in WORKFLOW


def test_workflow_validator_matches_shared_manifest():
    assert 'assert data["schema"] == 1, data' in WORKFLOW
    assert 'assert data["release_gate_effect"] == "none", data' in WORKFLOW
    assert 'case["case"]["id"]' in WORKFLOW
    assert 'case["solver"]["backend"]' in WORKFLOW
    assert 'case["collision"]["solver_triangles"]' in WORKFLOW
    assert 'case["checkpoints"]' in WORKFLOW
