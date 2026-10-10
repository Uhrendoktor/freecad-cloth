"""Run the canonical Python/FreeCAD validation suite inside the CI image."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

GROUPS = {
    "core": (
        "tests/test_core.py",
        "tests/test_mesh.py",
        "tests/test_meshpart_adapter.py",
        "tests/test_mesh_validation.py",
        "tests/test_avatar_visual_sanity.py",
        "tests/test_drape_visual_sanity.py",
        "tests/test_cloth_solver.py",
        "tests/test_avatar_hip_pose.py",
        "tests/test_avatar_model.py",
        "tests/test_avatar_orientation.py",
        "tests/test_avatar_pose_fidelity.py",
        "tests/test_avatar_pose_geometry.py",
        "tests/test_avatar_provider.py",
        "tests/test_avatar_standing_pose.py",
        "tests/test_backend_authority.py",
        "tests/test_collision_surface.py",
        "tests/test_command_adapter.py",
        "tests/test_derived_geometry.py",
        "tests/test_drape_failure_classifier.py",
        "tests/test_drape_target.py",
        "tests/test_drape_target_status.py",
        "tests/test_drapetarget_simulation_authority.py",
        "tests/test_pattern_geometry.py",
        "tests/test_pattern_topology_repair.py",
        "tests/test_surface_pen.py",
    ),
    "pattern": (
        "tests/test_pattern_sketch.py",
        "tests/test_pattern_ir.py",
        "tests/test_sketch_authority.py",
        "tests/test_sewing_workbench.py",
        "tests/test_sewing_creation_session.py",
        "tests/test_sewing_show2d.py",
        "tests/test_pattern_simulation_adapter.py",
        "tests/test_pattern_gui_contract.py",
        "tests/test_pattern_mark_enablement.py",
        "tests/test_pattern_marks.py",
    ),
    "sewing": (
        "tests/test_sewing_network.py",
        "tests/test_sewing_network_gui.py",
        "tests/test_sewing_network_gui_contract.py",
        "tests/test_simulation_quality.py",
        "tests/test_avatar_fitting.py",
        "tests/test_avatar_shoulder_pose.py",
        "tests/test_avatar_hierarchical_pose.py",
        "tests/test_sewing_command_surface.py",
        "tests/test_sewing_gui_contract.py",
        "tests/test_sewing_icons.py",
        "tests/test_sewing_repair.py",
        "tests/test_seam_contract.py",
        "tests/test_seam_document_adapter.py",
        "tests/test_seam_reference.py",
    ),
    "gui": (
        "tests/test_fitting_gui.py",
        "tests/test_avatar_gui_contract.py",
        "tests/test_avatar_pose_gui_contract.py",
        "tests/test_humanoid_mesh.py",
        "tests/test_freecad_objects.py",
        "tests/test_freecad_gui_startup_contract.py",
        "tests/test_drape_gui.py",
        "tests/test_simulation_gui.py",
        "tests/test_freecad_input.py",
    ),
    "pytest": (
        "tests/test_side_tasks.py",
        "tests/test_pattern_export_semantics.py",
        "tests/test_sewing_correspondence.py",
        "tests/test_sewing_commands.py",
        "tests/test_gui_structure.py",
        "tests/test_viewport_gizmo_style.py",
        "tests/test_simulation_scene.py",
        "tests/test_simulation_quality_runtime.py",
        "tests/test_simulation_quality_gui_contract.py",
        "tests/test_project_structure.py",
        "tests/test_agent_context_contract.py",
        "tests/test_cloth_diagnostics.py",
        "tests/test_seam_graph.py",
        "tests/test_workbench_icons.py",
        "tests/test_tunic_audit_contract.py",
        "tests/test_readme_visual_contract.py",
        "tests/test_sketcher_bootstrap_contract.py",
        "tests/test_canonical_python_validation_contract.py",
        "tests/test_pbd_contact_diagnostics_contract.py",
        "tests/test_pbd_cube_ladder_contract.py",
        "tests/test_pbd_avatar_ladder_contract.py",
        "tests/test_avatar_skeleton_pose.py",
        "tests/test_property_contracts.py",
        "tests/test_validation_models.py",
        "tests/test_boundary_validation_expansion.py",
        "tests/test_artifact_budget.py",
        "tests/test_agent_observation_bundle.py",
        "tests/test_ci_configuration.py",
        "tests/test_explicit_any_annotations.py",
        "tests/test_garment_warning_contract.py",
        "tests/test_markdown_contract.py",
        "tests/test_runner_routing_contract.py",
        "tests/test_simulation_commands.py",
        "tests/test_simulation_dataflow.py",
        "tests/test_simulation_quality_signature.py",
        "tests/test_simulation_review_contract.py",
        "tests/test_visual_capture_validation.py",
        "tests/test_workbench_command_contract.py",
        "tests/test_workbench_contract.py",
        "tests/test_shared_adapters.py",
        "tests/test_workbench_registration.py",
    ),
}


def validate_test_routing() -> None:
    """Fail closed when a pytest module is missing from or duplicated across groups."""
    routed = Counter(Path(test).as_posix() for tests in GROUPS.values() for test in tests)
    existing = {path.as_posix() for path in Path("tests").glob("test_*.py")}
    stale = sorted(path for path in routed if not Path(path).is_file())
    missing = sorted(existing - set(routed))
    duplicated = sorted(path for path, count in routed.items() if count > 1)
    errors = []
    if stale:
        errors.append("stale routing entries: " + ", ".join(stale))
    if missing:
        errors.append("unrouted pytest modules: " + ", ".join(sorted(missing)))
    if duplicated:
        errors.append("duplicated pytest modules: " + ", ".join(duplicated))
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"test-routing=passed modules={len(existing)} groups={len(GROUPS)}",
        flush=True,
    )


def main() -> int:
    """Run the canonical Python validation suite."""
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=sorted(GROUPS))
    cli_args = list(sys.argv[1:])
    if cli_args and Path(cli_args[0]).name == Path(__file__).name:
        cli_args = cli_args[1:]
    args = parser.parse_args(cli_args)

    validate_test_routing()
    tests = GROUPS[args.group]
    missing = [test for test in tests if not Path(test).is_file()]
    if missing:
        raise SystemExit("missing tests: " + ", ".join(missing))
    env = os.environ.copy()
    env["CLOTH_EXPECTED_TEST_MODULES"] = os.pathsep.join(tests)
    command = [
        "python3",
        "-m",
        "pytest",
        "-p",
        "tools.ci.pytest_collection_contract",
        "-q",
        *tests,
    ]
    print(f"running-pytest-group={args.group} tests={len(tests)}", flush=True)
    subprocess.run(command, check=True, timeout=110, env=env)
    print(f"python-validation={args.group} passed", flush=True)
    return 0


try:
    status = main()
except BaseException:
    print(traceback.format_exc(), flush=True)
    status = 1
sys.stdout.flush()
os._exit(status)
