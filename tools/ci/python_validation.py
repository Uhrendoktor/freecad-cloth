"""Run the canonical Python/FreeCAD validation suite inside the CI image."""

from __future__ import annotations

import argparse
import subprocess
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
    ),
    "pattern": (
        "tests/test_pattern_sketch.py",
        "tests/test_pattern_ir.py",
        "tests/test_sketch_authority.py",
        "tests/test_sewing_workbench.py",
        "tests/test_sewing_creation_session.py",
        "tests/test_sewing_show2d.py",
        "tests/test_pattern_simulation_adapter.py",
    ),
    "sewing": (
        "tests/test_sewing_network.py",
        "tests/test_sewing_network_gui.py",
        "tests/test_sewing_network_gui_contract.py",
        "tests/test_simulation_quality.py",
        "tests/test_avatar_fitting.py",
        "tests/test_avatar_shoulder_pose.py",
        "tests/test_avatar_hierarchical_pose.py",
    ),
    "gui": (
        "tests/test_fitting_gui.py",
        "tests/test_avatar_gui_contract.py",
        "tests/test_avatar_pose_gui_contract.py",
        "tests/test_humanoid_mesh.py",
        "tests/test_freecad_objects.py",
        "tests/test_freecad_gui_startup_contract.py",
    ),
    "pytest": (
        "tests/test_side_tasks.py",
        "tests/test_pattern_export_semantics.py",
        "tests/test_sewing_correspondence.py",
        "tests/test_sewing_commands.py",
        "tests/test_gui_structure.py",
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
        "tests/test_pbd_avatar_ladder_contract.py",
        "tests/test_avatar_skeleton_pose.py",
        "tests/test_avatar_gui_contract.py",
        "tests/test_property_contracts.py",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=sorted(GROUPS))
    args = parser.parse_args()

    if args.group == "pytest":
        command = ["python3", "-m", "pytest", "-q", *GROUPS[args.group]]
        subprocess.run(command, check=True, timeout=60)
        print(f"python-validation={args.group} passed")
        return 0

    subprocess.run(["python3", "-m", "compileall", "-q", "."], check=True, timeout=20)
    for test in GROUPS[args.group]:
        if not Path(test).is_file():
            raise SystemExit(f"missing test: {test}")
        print(f"running-script-test={test}", flush=True)
        subprocess.run(["python3", test], check=True, timeout=60)
    print(f"python-validation={args.group} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
