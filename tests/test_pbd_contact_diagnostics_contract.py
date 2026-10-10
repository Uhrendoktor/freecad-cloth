"""Contract tests for the diagnostic contact controls.

These assertions protect the diagnostic scope and the shared manifest contract without
making the diagnostic artifact a release gate.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests" / "freecad_pbd_contact_diagnostics.py").read_text(encoding="utf-8")
HELPERS = (ROOT / "tests" / "support" / "pbd_contact_helpers.py").read_text(encoding="utf-8")
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
    assert "diagnostic-pbd-contact:" in WORKFLOW
    assert "github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls" in WORKFLOW
    assert "needs: [agent-quality, local_runner_readiness, pbd_validation_image]" in WORKFLOW
    assert "needs: [diagnostic-pbd-contact]" not in WORKFLOW


def test_diagnostic_entrypoint_and_failure_evidence_are_explicit():
    assert "CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1" in WORKFLOW
    assert 'os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1"' in SOURCE
    assert "CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED" in SOURCE
    assert "schedule_freecad_main(_scheduled_main)" in SOURCE
    assert "QtCore.QTimer.singleShot(0, callback)" in HELPERS
    assert "os._exit(status)" in SOURCE
    assert "Gui.activeDocument().activeView()" in SOURCE
    assert "solver_collision_surface" in SOURCE
    assert "point_inside_closed_mesh" in HELPERS
    assert (
        "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh" in HELPERS
    )
    assert "make_shutdown_gui(_progress)" in SOURCE
    assert "app.quit()" in HELPERS
    assert "App.exit()" not in SOURCE
    assert "gui-shutdown-requested" in HELPERS
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE
    assert "diagnostic contact controls start" in SOURCE
    assert "test-script: tests/freecad_pbd_contact_diagnostics.py" in WORKFLOW
    assert "ArrangementPoint.from_string" in SOURCE
    assert "state = _inside_outside(" in SOURCE
    assert "float(candidate.x)" in SOURCE
    assert "float(candidate.y)" in SOURCE
    assert "float(candidate.z)" in SOURCE
    assert "interior_seed_source" in SOURCE
    assert "float(center.y) + 120.0" in SOURCE
    assert "width=72.0" in SOURCE
    assert 'mesh_is_inside = getattr(mesh, "isInside", None)' in HELPERS
    assert "did not create a true interior pre-step state" in SOURCE
    assert "pbd-env: collision_mode=" in SOURCE
    assert "diagnostic-pbd-contact:" in WORKFLOW
    assert "artifacts/pbd-contact-diagnostics/app-run.log" in WORKFLOW
    diagnostic = WORKFLOW.split("  diagnostic-pbd-contact:", 1)[1].split("  simulation-ladder:", 1)[
        0
    ]
    assert "artifact-name: pbd-contact-diagnostics" in diagnostic
    assert "artifact-path: artifacts/pbd-contact-diagnostics/**" in diagnostic


def test_workflow_validator_matches_shared_manifest():
    assert "tools/ci/validate_manifests.py" in WORKFLOW
    assert "simulation-ladder" in WORKFLOW
    assert "artifact" in WORKFLOW.lower()
    assert "test-script: tests/freecad_pbd_contact_diagnostics.py" in WORKFLOW
    assert "simulation-ladder" in WORKFLOW
    assert "validate_manifests.py" in WORKFLOW


def test_cube_ladder_diagnostic_job_has_scoped_branch_trigger():
    assert "contains(github.event.pull_request.head.ref, 'cube-ladder-2481')" in WORKFLOW


def test_cube_ladder_caches_collision_proximity_mesh():
    source = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    assert "proximity_mesh = trimesh.Trimesh(" in source
    assert "proximity_mesh.nearest.on_surface" in source
    assert "_surface_signed_clearance(" in source
    assert "source_shape," in source
    assert "collision_surface," in source
    assert "proximity_mesh," in source
    assert "for step in CHECKPOINTS:" in source
    assert "scene.Steps = int(step)" in source


def test_cube_ladder_bootstrap_faulthandler_is_freecad_safe():
    source = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    assert "runpy.run_path(" not in source
    assert "from tests.support.pbd_contact_helpers import" in source
    assert "before-support-helper-import" in source
    assert "_TRACE_HANDLE = _BOOT_LOG.open(" in source
    assert "faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)" in source
    assert "faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)" in source
    assert "file=sys.stderr" not in source
    assert '_boot("script-start")' in source
    assert "_freecad_entrypoint_name = Path(__file__).stem" in source
    assert '_freecad_gui_hosted = bool(getattr(App, "GuiUp", False))' in source
    assert "def _schedule_freecad_main():" in source
    assert "schedule_freecad_main(_run_and_shutdown)" in source
    assert "QtCore.QTimer.singleShot(0, callback)" in HELPERS
    assert '_boot("freecad-hosted-entrypoint")' in source
    assert "__name__ == _freecad_entrypoint_name" in source
    assert '_boot("direct-entrypoint")' in source


def test_progressive_collision_ladder_is_a_normal_gate():
    assert "simulation-ladder:" in WORKFLOW
    block = WORKFLOW.split("  simulation-ladder:", 1)[1]
    assert "if: ${{ github.event_name != 'schedule' }}" in WORKFLOW
    assert "CLOTH_PBD_SUBSTEPS: 8" in WORKFLOW
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 2" in WORKFLOW
    assert "test-script: tests/freecad_pbd_cube_ladder.py" in block
    assert "validate_manifests.py simulation" in block
    assert "artifact-name: simulation-collision-ladder" in block
    assert "artifact-name: simulation-collision-ladder" in block
    assert "artifact-path: artifacts/simulation-ladder/**" in block


def test_shared_pbd_helpers_are_import_safe_and_keep_ladder_contracts_explicit():
    cube = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    avatar = (ROOT / "tests" / "freecad_pbd_avatar_ladder.py").read_text(encoding="utf-8")
    assert "runpy.run_path(" not in cube + avatar
    assert "from tests.support.pbd_contact_helpers import" in cube
    assert "from tests.support.pbd_contact_helpers import" in avatar
    assert 'if __name__ == "__main__"' not in HELPERS
    assert "def build_scene(" in HELPERS
    assert "def checkpoint_record(" in HELPERS


def test_shared_checkpoint_builder_preserves_case_specific_contact_labels():
    from types import SimpleNamespace

    from tests.support.pbd_contact_helpers import (
        checkpoint_record,
        connected_components,
        seam_geometry,
    )

    backend = SimpleNamespace(positions=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 2.0)))
    base = SimpleNamespace(backend=backend, seam_stitch_pairs={"side": ((0, 1),)})
    geometry = seam_geometry(backend, base.seam_stitch_pairs)
    assert geometry[0]["max_span_mm"] == 2.0
    record = checkpoint_record(
        1,
        "step-001.png",
        backend.positions(),
        ((0, 1, 1),),
        2.0,
        2.0,
        base,
        connected_components,
        "diagnostic-only-cube",
    )
    assert record["contact_state"] == "diagnostic-only-cube"
    assert record["components"] == 1
    assert record["penetration_mm"] == 0.0
    assert record["seam_world_spans_mm"] == geometry
