# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for the diagnostic contact controls.

These assertions protect the diagnostic scope and the shared manifest contract without
making the diagnostic artifact a release gate.
"""

from pathlib import Path
from types import SimpleNamespace

from tests.support.assertions import require
from tests.support.pbd_contact_helpers import (
    checkpoint_record,
    connected_components,
    seam_geometry,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests" / "freecad_pbd_contact_diagnostics.py").read_text(encoding="utf-8")
HELPERS = (ROOT / "tests" / "support" / "pbd_contact_helpers.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")


def test_diagnostic_controls_are_static_and_one_step() -> None:
    """Verify contact diagnostic controls remain static, one-step, and outside release gates."""
    require(condition=('"control-0-cube"' in SOURCE), message="Expected condition to hold: '\"control-0-cube\"' in SOURCE")
    require(condition=('"control-0a-avatar"' in SOURCE), message="Expected condition to hold: '\"control-0a-avatar\"' in SOURCE")
    require(condition=("scene.Steps = 1" in SOURCE), message="Expected condition to hold: \"scene.Steps = 1\" in SOURCE")
    require(condition=('"diagnostic-only-contact-controls"' in SOURCE), message="Expected condition to hold: '\"diagnostic-only-contact-controls\"' in SOURCE")
    require(condition=('"release_gate_effect": "none"' in SOURCE), message="Expected condition to hold: '\"release_gate_effect\": \"none\"' in SOURCE")
    require(condition=("scene.GravityZ = 0.0" in SOURCE), message="Expected condition to hold: \"scene.GravityZ = 0.0\" in SOURCE")


def test_diagnostic_manifest_contains_shared_schema_fields() -> None:
    """Verify the diagnostic manifest preserves all required shared schema fields."""
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
        require(condition=(needle in SOURCE), message="Expected condition to hold: needle in SOURCE")


def test_canonical_workflow_uses_single_opt_in_dispatch_job() -> None:
    """Verify contact diagnostics run only through the single explicit opt-in dispatch job."""
    require(condition=("diagnostic_controls:" in WORKFLOW), message="Expected condition to hold: \"diagnostic_controls:\" in WORKFLOW")
    require(condition=("diagnostic-pbd-contact:" in WORKFLOW), message="Expected condition to hold: \"diagnostic-pbd-contact:\" in WORKFLOW")
    require(condition=("github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls" in WORKFLOW), message="Expected condition to hold: \"github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls\" in WORKFLOW")
    require(condition=("needs: [agent-quality, local_runner_readiness, pbd_validation_image]" in WORKFLOW), message="Expected condition to hold: \"needs: [agent-quality, local_runner_readiness, pbd_validation_image]\" in WORKFLOW")
    require(condition=("needs: [diagnostic-pbd-contact]" not in WORKFLOW), message="Expected condition to hold: \"needs: [diagnostic-pbd-contact]\" not in WORKFLOW")


def test_diagnostic_entrypoint_and_failure_evidence_are_explicit() -> None:
    """Verify the diagnostic entrypoint and failure evidence remain explicit."""
    require(condition=("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1" in WORKFLOW), message="Expected condition to hold: \"CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1\" in WORKFLOW")
    require(condition=('os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1"' in SOURCE), message="Expected condition to hold: 'os.environ.get(\"CLOTH_CONTACT_DIAGNOSTICS_EXECUTE\") == \"1\"' in SOURCE")
    require(condition=("CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED" in SOURCE), message="Expected condition to hold: \"CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED\" in SOURCE")
    require(condition=("schedule_freecad_main(_scheduled_main)" in SOURCE), message="Expected condition to hold: \"schedule_freecad_main(_scheduled_main)\" in SOURCE")
    require(condition=("QtCore.QTimer.singleShot(0, callback)" in HELPERS), message="Expected condition to hold: \"QtCore.QTimer.singleShot(0, callback)\" in HELPERS")
    require(condition=("os._exit(status)" in SOURCE), message="Expected condition to hold: \"os._exit(status)\" in SOURCE")
    require(condition=("Gui.activeDocument().activeView()" in SOURCE), message="Expected condition to hold: \"Gui.activeDocument().activeView()\" in SOURCE")
    require(condition=("solver_collision_surface" in SOURCE), message="Expected condition to hold: \"solver_collision_surface\" in SOURCE")
    require(condition=("point_inside_closed_mesh" in HELPERS), message="Expected condition to hold: \"point_inside_closed_mesh\" in HELPERS")
    require(
        condition="from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh" in HELPERS,
        message="The import-safe helper must use the production mesh-containment function.",
    )
    require(condition=("make_shutdown_gui(_progress)" in SOURCE), message="Expected condition to hold: \"make_shutdown_gui(_progress)\" in SOURCE")
    require(condition=("app.quit()" in HELPERS), message="Expected condition to hold: \"app.quit()\" in HELPERS")
    require(condition=("App.exit()" not in SOURCE), message="Expected condition to hold: \"App.exit()\" not in SOURCE")
    require(condition=("gui-shutdown-requested" in HELPERS), message="Expected condition to hold: \"gui-shutdown-requested\" in HELPERS")
    require(condition=("faulthandler.dump_traceback_later(30.0, repeat=True" in SOURCE), message="Expected condition to hold: \"faulthandler.dump_traceback_later(30.0, repeat=True\" in SOURCE")
    require(condition=("diagnostic contact controls start" in SOURCE), message="Expected condition to hold: \"diagnostic contact controls start\" in SOURCE")
    require(condition=("test-script: tests/freecad_pbd_contact_diagnostics.py" in WORKFLOW), message="Expected condition to hold: \"test-script: tests/freecad_pbd_contact_diagnostics.py\" in WORKFLOW")
    require(condition=("ArrangementPoint.from_string" in SOURCE), message="Expected condition to hold: \"ArrangementPoint.from_string\" in SOURCE")
    require(condition=("state = _inside_outside(" in SOURCE), message="Expected condition to hold: \"state = _inside_outside(\" in SOURCE")
    require(condition=("float(candidate.x)" in SOURCE), message="Expected condition to hold: \"float(candidate.x)\" in SOURCE")
    require(condition=("float(candidate.y)" in SOURCE), message="Expected condition to hold: \"float(candidate.y)\" in SOURCE")
    require(condition=("float(candidate.z)" in SOURCE), message="Expected condition to hold: \"float(candidate.z)\" in SOURCE")
    require(condition=("interior_seed_source" in SOURCE), message="Expected condition to hold: \"interior_seed_source\" in SOURCE")
    require(condition=("float(center.y) + 120.0" in SOURCE), message="Expected condition to hold: \"float(center.y) + 120.0\" in SOURCE")
    require(condition=("width=72.0" in SOURCE), message="Expected condition to hold: \"width=72.0\" in SOURCE")
    require(condition=('mesh_is_inside = getattr(mesh, "isInside", None)' in HELPERS), message="Expected condition to hold: 'mesh_is_inside = getattr(mesh, \"isInside\", None)' in HELPERS")
    require(condition=("did not create a true interior pre-step state" in SOURCE), message="Expected condition to hold: \"did not create a true interior pre-step state\" in SOURCE")
    require(condition=("pbd-env: collision_mode=" in SOURCE), message="Expected condition to hold: \"pbd-env: collision_mode=\" in SOURCE")
    require(condition=("diagnostic-pbd-contact:" in WORKFLOW), message="Expected condition to hold: \"diagnostic-pbd-contact:\" in WORKFLOW")
    require(condition=("artifacts/pbd-contact-diagnostics/app-run.log" in WORKFLOW), message="Expected condition to hold: \"artifacts/pbd-contact-diagnostics/app-run.log\" in WORKFLOW")
    diagnostic = WORKFLOW.split("  diagnostic-pbd-contact:", 1)[1].split("  simulation-ladder:", 1)[
        0
    ]
    require(condition=("artifact-name: pbd-contact-diagnostics" in diagnostic), message="Expected condition to hold: \"artifact-name: pbd-contact-diagnostics\" in diagnostic")
    require(condition=("artifact-path: artifacts/pbd-contact-diagnostics/**" in diagnostic), message="Expected condition to hold: \"artifact-path: artifacts/pbd-contact-diagnostics/**\" in diagnostic")


def test_workflow_validator_matches_shared_manifest() -> None:
    """Verify the canonical workflow still invokes the manifest contract validator."""
    require(condition=("tools/ci/validate_manifests.py" in WORKFLOW), message="Expected condition to hold: \"tools/ci/validate_manifests.py\" in WORKFLOW")
    require(condition=("simulation-ladder" in WORKFLOW), message="Expected condition to hold: \"simulation-ladder\" in WORKFLOW")
    require(condition=("artifact" in WORKFLOW.lower()), message="Expected condition to hold: \"artifact\" in WORKFLOW.lower()")
    require(condition=("test-script: tests/freecad_pbd_contact_diagnostics.py" in WORKFLOW), message="Expected condition to hold: \"test-script: tests/freecad_pbd_contact_diagnostics.py\" in WORKFLOW")
    require(condition=("simulation-ladder" in WORKFLOW), message="Expected condition to hold: \"simulation-ladder\" in WORKFLOW")
    require(condition=("validate_manifests.py" in WORKFLOW), message="Expected condition to hold: \"validate_manifests.py\" in WORKFLOW")


def test_cube_ladder_diagnostic_job_has_scoped_branch_trigger() -> None:
    """Verify the cube collision ladder keeps its scoped branch trigger."""
    require(condition=("contains(github.event.pull_request.head.ref, 'cube-ladder-2481')" in WORKFLOW), message="Expected condition to hold: \"contains(github.event.pull_request.head.ref, 'cube-ladder-2481')\" in WORKFLOW")


def test_cube_ladder_caches_collision_proximity_mesh() -> None:
    """Verify the cube ladder reuses its collision proximity mesh during checkpoints."""
    source = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    require(condition=("proximity_mesh = trimesh.Trimesh(" in source), message="Expected condition to hold: \"proximity_mesh = trimesh.Trimesh(\" in source")
    require(condition=("proximity_mesh.nearest.on_surface" in source), message="Expected condition to hold: \"proximity_mesh.nearest.on_surface\" in source")
    require(condition=("_surface_signed_clearance(" in source), message="Expected condition to hold: \"_surface_signed_clearance(\" in source")
    require(condition=("source_shape," in source), message="Expected condition to hold: \"source_shape,\" in source")
    require(condition=("collision_surface," in source), message="Expected condition to hold: \"collision_surface,\" in source")
    require(condition=("proximity_mesh," in source), message="Expected condition to hold: \"proximity_mesh,\" in source")
    require(condition=("for step in CHECKPOINTS:" in source), message="Expected condition to hold: \"for step in CHECKPOINTS:\" in source")
    require(condition=("scene.Steps = int(step)" in source), message="Expected condition to hold: \"scene.Steps = int(step)\" in source")


def test_cube_ladder_bootstrap_faulthandler_is_freecad_safe() -> None:
    """Verify FreeCAD-safe startup and traceback handling in the cube ladder."""
    source = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    require(condition=("runpy.run_path(" not in source), message="Expected condition to hold: \"runpy.run_path(\" not in source")
    require(condition=("from pbd_contact_helpers import" in source), message="Expected condition to hold: \"from pbd_contact_helpers import\" in source")
    require(condition=('_HELPER_DIR = Path(__file__).resolve().parent / "support"' in source), message="Expected condition to hold: '_HELPER_DIR = Path(__file__).resolve().parent / \"support\"' in source")
    require(condition=("sys.path.insert(0, str(_HELPER_DIR))" in source), message="Expected condition to hold: \"sys.path.insert(0, str(_HELPER_DIR))\" in source")
    require(condition=("before-support-helper-import" in source), message="Expected condition to hold: \"before-support-helper-import\" in source")
    require(condition=("_TRACE_HANDLE = _BOOT_LOG.open(" in source), message="Expected condition to hold: \"_TRACE_HANDLE = _BOOT_LOG.open(\" in source")
    require(condition=("faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)" in source), message="Expected condition to hold: \"faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)\" in source")
    require(condition=("faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)" in source), message="Expected condition to hold: \"faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)\" in source")
    require(condition=("file=sys.stderr" not in source), message="Expected condition to hold: \"file=sys.stderr\" not in source")
    require(condition=('_boot("script-start")' in source), message="Expected condition to hold: '_boot(\"script-start\")' in source")
    require(condition=("_freecad_entrypoint_name = Path(__file__).stem" in source), message="Expected condition to hold: \"_freecad_entrypoint_name = Path(__file__).stem\" in source")
    require(condition=('_freecad_gui_hosted = bool(getattr(App, "GuiUp", False))' in source), message="Expected condition to hold: '_freecad_gui_hosted = bool(getattr(App, \"GuiUp\", False))' in source")
    require(condition=("def _schedule_freecad_main():" in source), message="Expected condition to hold: \"def _schedule_freecad_main():\" in source")
    require(condition=("schedule_freecad_main(_run_and_shutdown)" in source), message="Expected condition to hold: \"schedule_freecad_main(_run_and_shutdown)\" in source")
    require(condition=("QtCore.QTimer.singleShot(0, callback)" in HELPERS), message="Expected condition to hold: \"QtCore.QTimer.singleShot(0, callback)\" in HELPERS")
    require(condition=('_boot("freecad-hosted-entrypoint")' in source), message="Expected condition to hold: '_boot(\"freecad-hosted-entrypoint\")' in source")
    require(condition=("__name__ == _freecad_entrypoint_name" in source), message="Expected condition to hold: \"__name__ == _freecad_entrypoint_name\" in source")
    require(condition=('_boot("direct-entrypoint")' in source), message="Expected condition to hold: '_boot(\"direct-entrypoint\")' in source")


def test_progressive_collision_ladder_is_a_normal_gate() -> None:
    """Verify the progressive collision ladder remains a normal full-validation gate."""
    require(condition=("simulation-ladder:" in WORKFLOW), message="Expected condition to hold: \"simulation-ladder:\" in WORKFLOW")
    block = WORKFLOW.split("  simulation-ladder:", 1)[1]
    require(condition=("if: ${{ inputs.execution_mode == 'full' && github.event_name != 'schedule' }}" in block), message="Expected condition to hold: \"if: ${{ inputs.execution_mode == 'full' && github.event_name != 'schedule' }}\" in block")
    require(condition=("CLOTH_PBD_SUBSTEPS: 8" in WORKFLOW), message="Expected condition to hold: \"CLOTH_PBD_SUBSTEPS: 8\" in WORKFLOW")
    require(condition=("CLOTH_PBD_COLLISION_TOLERANCE_MM: 2" in WORKFLOW), message="Expected condition to hold: \"CLOTH_PBD_COLLISION_TOLERANCE_MM: 2\" in WORKFLOW")
    require(condition=("test-script: tests/freecad_pbd_cube_ladder.py" in block), message="Expected condition to hold: \"test-script: tests/freecad_pbd_cube_ladder.py\" in block")
    require(condition=("validate_manifests.py simulation" in block), message="Expected condition to hold: \"validate_manifests.py simulation\" in block")
    require(condition=("artifact-name: simulation-collision-ladder" in block), message="Expected condition to hold: \"artifact-name: simulation-collision-ladder\" in block")
    require(condition=("artifact-name: simulation-collision-ladder" in block), message="Expected condition to hold: \"artifact-name: simulation-collision-ladder\" in block")
    require(condition=("artifact-path: artifacts/simulation-ladder/**" in block), message="Expected condition to hold: \"artifact-path: artifacts/simulation-ladder/**\" in block")


def test_shared_pbd_helpers_are_import_safe_and_keep_ladder_contracts_explicit() -> None:
    """Verify PBD support helpers remain import-safe and ladder contracts are explicit."""
    cube = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    avatar = (ROOT / "tests" / "freecad_pbd_avatar_ladder.py").read_text(encoding="utf-8")
    require(condition=("runpy.run_path(" not in cube + avatar), message="Expected condition to hold: \"runpy.run_path(\" not in cube + avatar")
    require(condition=("from pbd_contact_helpers import" in cube), message="Expected condition to hold: \"from pbd_contact_helpers import\" in cube")
    require(condition=('_HELPER_DIR = Path(__file__).resolve().parent / "support"' in cube), message="Expected condition to hold: '_HELPER_DIR = Path(__file__).resolve().parent / \"support\"' in cube")
    require(condition=("_REPO_ROOT = Path(__file__).resolve().parents[1]" in cube), message="Expected condition to hold: \"_REPO_ROOT = Path(__file__).resolve().parents[1]\" in cube")
    require(condition=("sys.path.insert(0, str(_REPO_ROOT))" in cube), message="Expected condition to hold: \"sys.path.insert(0, str(_REPO_ROOT))\" in cube")
    require(condition=("sys.path.insert(0, str(_HELPER_DIR))" in cube), message="Expected condition to hold: \"sys.path.insert(0, str(_HELPER_DIR))\" in cube")
    require(condition=("from pbd_contact_helpers import" in avatar), message="Expected condition to hold: \"from pbd_contact_helpers import\" in avatar")
    require(condition=('_HELPER_DIR = Path(__file__).resolve().parent / "support"' in avatar), message="Expected condition to hold: '_HELPER_DIR = Path(__file__).resolve().parent / \"support\"' in avatar")
    require(condition=("_REPO_ROOT = Path(__file__).resolve().parents[1]" in avatar), message="Expected condition to hold: \"_REPO_ROOT = Path(__file__).resolve().parents[1]\" in avatar")
    require(condition=("sys.path.insert(0, str(_REPO_ROOT))" in avatar), message="Expected condition to hold: \"sys.path.insert(0, str(_REPO_ROOT))\" in avatar")
    require(condition=("sys.path.insert(0, str(_HELPER_DIR))" in avatar), message="Expected condition to hold: \"sys.path.insert(0, str(_HELPER_DIR))\" in avatar")
    require(condition=('if __name__ == "__main__"' not in HELPERS), message="Expected condition to hold: 'if __name__ == \"__main__\"' not in HELPERS")
    require(condition=("def build_scene(" in HELPERS), message="Expected condition to hold: \"def build_scene(\" in HELPERS")
    require(condition=("def checkpoint_record(" in HELPERS), message="Expected condition to hold: \"def checkpoint_record(\" in HELPERS")


def test_shared_checkpoint_builder_preserves_case_specific_contact_labels() -> None:
    """Verify checkpoint records retain case-specific contact labels."""
    backend = SimpleNamespace(positions=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 2.0)))
    base = SimpleNamespace(backend=backend, seam_stitch_pairs={"side": ((0, 1),)})
    geometry = seam_geometry(backend, base.seam_stitch_pairs)
    require(condition=(geometry[0]["max_span_mm"] == 2.0), message="Expected condition to hold: geometry[0][\"max_span_mm\"] == 2.0")
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
    require(condition=(record["contact_state"] == "diagnostic-only-cube"), message="Expected condition to hold: record[\"contact_state\"] == \"diagnostic-only-cube\"")
    require(condition=(record["components"] == 1), message="Expected condition to hold: record[\"components\"] == 1")
    require(condition=(record["penetration_mm"] == 0.0), message="Expected condition to hold: record[\"penetration_mm\"] == 0.0")
    require(condition=(record["seam_world_spans_mm"] == geometry), message="Expected condition to hold: record[\"seam_world_spans_mm\"] == geometry")
