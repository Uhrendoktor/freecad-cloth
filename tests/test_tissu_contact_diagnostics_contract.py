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
    assert "def _point_inside_mesh(point, vertices, triangles):" in SOURCE
    assert "def _shutdown_gui():" in SOURCE
    assert "app.quit()" in SOURCE
    assert "App.exit()" not in SOURCE
    assert "gui-shutdown-requested" in SOURCE
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE
    assert "entrypoint __name__=" in SOURCE
    assert "setsid /opt/freecad/AppRun /workspace/tests/freecad_tissu_contact_diagnostics.py" in WORKFLOW
    assert "ArrangementPoint.from_string" in SOURCE
    assert '_inside_outside(((float(candidate.x), float(candidate.y), float(candidate.z)),), avatar)' in SOURCE
    assert "interior_seed_source" in SOURCE
    assert "float(center.y) + 120.0" in SOURCE
    assert "width=72.0" in SOURCE
    assert "mesh_is_inside = getattr(mesh, \"isInside\", None)" in SOURCE
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


def test_cube_ladder_diagnostic_job_has_scoped_branch_trigger():
    assert "contains(github.event.pull_request.head.ref, 'cube-ladder-2481')" in WORKFLOW



def test_cube_ladder_caches_collision_proximity_mesh():
    source = (ROOT / "tests" / "freecad_tissu_cube_ladder.py").read_text(encoding="utf-8")
    assert "proximity_mesh = trimesh.Trimesh(" in source
    assert "proximity_mesh.nearest.on_surface" in source
    assert "_surface_signed_clearance(" in source
    assert "source_shape," in source
    assert "collision_surface," in source
    assert "proximity_mesh," in source
    assert "for step in CHECKPOINTS:" in source
    assert "scene.Steps = int(step)" in source


def test_cube_ladder_bootstrap_faulthandler_is_freecad_safe():
    source = (ROOT / "tests" / "freecad_tissu_cube_ladder.py").read_text(encoding="utf-8")
    assert "import freecad_tissu_contact_diagnostics as _contact" in source
    assert "App = _contact.App" in source
    assert "Gui = _contact.Gui" in source
    assert "Part = _contact.Part" in source
    assert "_TRACE_HANDLE = _BOOT_LOG.open(" in source
    assert "faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)" in source
    assert "faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)" in source
    assert "file=sys.stderr" not in source
