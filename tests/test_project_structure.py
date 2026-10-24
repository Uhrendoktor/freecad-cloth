# Copyright (C) 2026 FreeCAD Cloth contributors
"""Structural checks for the canonical Python package tree."""

import ast
import re
import tomllib
from pathlib import Path

from freecad_cloth.shared.collision import CollisionSurface
from freecad_cloth.shared.targets import DrapeTargetRef
from support.assertions import require

EXPECTED_SINGLE_REGISTRATION_COUNT = 1
EXPECTED_TARGET_REVISION = 2
EXPECTED_SHA_LENGTH = 40
EXPECTED_BUNDLED_WORKBENCH_COUNT = 3


def test_project_metadata_exists() -> None:
    """Check that package and build metadata are declared."""
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    require(
        condition=("[project]" in text),
        message="test_project_metadata_exists: required condition failed",
    )
    require(
        condition=('name = "freecad-cloth"' in text),
        message="test_project_metadata_exists: required condition failed",
    )
    require(
        condition=("[build-system]" in text),
        message="test_project_metadata_exists: required condition failed",
    )


def test_anny_avatar_runtime_is_a_required_project_dependency() -> None:
    """Require the supported avatar runtime dependency ranges in project metadata."""
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    required = set(project["dependencies"])
    require(
        condition=("anny>=0.6,<0.7" in required),
        message="test_anny_avatar_runtime_is_a_req...: required condition failed",
    )
    require(
        condition=("clad-body[anny]>=0.6.1,<0.7" in required),
        message="test_anny_avatar_runtime_is_a_req...: required condition failed",
    )
    require(
        condition=("avatar" not in project.get("optional-dependencies", {})),
        message="test_anny_avatar_runtime_is_a_req...: required condition failed",
    )


def test_workbench_package_boundaries_exist() -> None:
    """Verify first-party packages and workbench modules are present."""
    root = Path(__file__).resolve().parents[1]
    for name in ("pattern", "sewing", "simulation", "avatar", "common", "shared"):
        package = root / "freecad_cloth" / name
        require(
            condition=((package / "__init__.py").is_file()),
            message="test_workbench_package_boundaries...: required condition failed",
        )
    for name in ("pattern", "sewing", "simulation"):
        require(
            condition=((root / "freecad_cloth" / name / "workbench.py").is_file()),
            message="test_workbench_package_boundaries...: required condition failed",
        )


def test_only_bootstrap_python_files_remain_at_root() -> None:
    """Keep implementation modules out of the repository root."""
    root = Path(__file__).resolve().parents[1]
    require(
        condition=(
            {path.name for path in root.glob("*.py")}
            <= {
                "Init.py",
                "InitGui.py",
                "sitecustomize.py",
            }
        ),
        message="test_only_bootstrap_python_files_...: required condition failed",
    )


def test_root_initgui_delegates_without_swallowing_bootstrap_errors() -> None:
    """Require InitGui.py to delegate bootstrap errors instead of swallowing them."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "InitGui.py").read_text(encoding="utf-8")
    require(
        condition=("from freecad_cloth.bootstrap import initialize_workbenches" in source),
        message="test_root_initgui_delegates_witho...: required condition failed",
    )
    require(
        condition=("initialize_workbenches(" in source),
        message="test_root_initgui_delegates_witho...: required condition failed",
    )
    require(
        condition=("except Exception" not in source),
        message="test_root_initgui_delegates_witho...: required condition failed",
    )
    require(
        condition=("freecad_cloth.simulation.DrapeTarget" not in source),
        message="test_root_initgui_delegates_witho...: required condition failed",
    )


def test_freecad_entry_points_remain_at_root() -> None:
    """Verify the classic FreeCAD entrypoint files remain available."""
    root = Path(__file__).resolve().parents[1]
    require(
        condition=((root / "Init.py").is_file()),
        message="test_freecad_entry_points_remain_...: required condition failed",
    )
    require(
        condition=((root / "InitGui.py").is_file()),
        message="test_freecad_entry_points_remain_...: required condition failed",
    )
    gui = (root / "InitGui.py").read_text(encoding="utf-8")
    require(
        condition=("from freecad_cloth.bootstrap import initialize_workbenches" in gui),
        message="test_freecad_entry_points_remain_...: required condition failed",
    )
    require(
        condition=(gui.count("initialize_workbenches(") == EXPECTED_SINGLE_REGISTRATION_COUNT),
        message="test_freecad_entry_points_remain_...: required condition failed",
    )


def test_classic_and_modern_loaders_share_registration_implementation() -> None:
    """Keep both FreeCAD loaders delegated to the single bootstrap registrar."""
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "freecad_cloth" / "bootstrap.py").read_text(encoding="utf-8")
    for path in (
        root / "InitGui.py",
        root / "freecad" / "freecad_cloth" / "init_gui.py",
    ):
        source = path.read_text(encoding="utf-8")
        require(
            condition=("from freecad_cloth.bootstrap import initialize_workbenches" in source),
            message="test_classic_and_modern_loaders_s...: required condition failed",
        )
        require(
            condition=(source.count("initialize_workbenches(") == 1),
            message="test_classic_and_modern_loaders_s...: required condition failed",
        )
        require(
            condition=("Gui.addWorkbench(" not in source),
            message="test_classic_and_modern_loaders_s...: required condition failed",
        )
    for workbench in (
        "ClothPatternWorkbench",
        "ClothSimulationWorkbench",
        "ClothSewingWorkbench",
    ):
        require(
            condition=(f'("{workbench}",' in bootstrap),
            message="test_classic_and_modern_loaders_s...: required condition failed",
        )
    require(
        condition=(
            bootstrap.count("addWorkbench(workbench_type())") == EXPECTED_SINGLE_REGISTRATION_COUNT
        ),
        message="test_classic_and_modern_loaders_s...: required condition failed",
    )


def test_shared_contract_is_freecad_independent() -> None:
    """Verify shared collision and target values import without a FreeCAD host."""
    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    target = DrapeTargetRef("freecad", "Body", revision=2)
    require(
        condition=(surface.region == "body"),
        message="test_shared_contract_is_freecad_i...: required condition failed",
    )
    require(
        condition=(target.revision == EXPECTED_TARGET_REVISION),
        message="test_shared_contract_is_freecad_i...: required condition failed",
    )
    require(
        condition=(target.is_freecad_object()),
        message="test_shared_contract_is_freecad_i...: required condition failed",
    )
    require(
        condition=(not target.is_human()),
        message="test_shared_contract_is_freecad_i...: required condition failed",
    )


def test_human_documentation_contract() -> None:
    """Ensure the user guide exists and is linked from the documentation index."""
    root = Path(__file__).resolve().parents[1]
    user_guide = root / "docs" / "users" / "USER_GUIDE.md"
    docs_readme = root / "docs" / "README.md"
    require(
        condition=(user_guide.is_file()),
        message="test_human_documentation_contract: required condition failed",
    )
    require(
        condition=("users/USER_GUIDE.md" in docs_readme.read_text(encoding="utf-8")),
        message="test_human_documentation_contract: required condition failed",
    )


def test_canonical_workflow_pr_validation_contract() -> None:
    """Preserve the canonical workflow's trusted event and validation boundaries."""
    root = Path(__file__).resolve().parents[1]
    workflows = root / ".github" / "workflows"
    shared = (workflows / "canonical-execution.yml").read_text(encoding="utf-8")
    commit = (workflows / "commit-validation.yml").read_text(encoding="utf-8")
    merge = (workflows / "merge-validation.yml").read_text(encoding="utf-8")
    publication = (workflows / "main-publication.yml").read_text(encoding="utf-8")

    require(
        condition=("workflow_call:" in shared),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("pull_request:" not in shared),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("pull_request_target:" not in shared + commit + merge + publication),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("types: [opened, synchronize, reopened, ready_for_review, edited]" in commit),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("workflow_dispatch:" in commit),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("branches: [main]" in publication),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("merge_group:" in merge),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("types: [checks_requested]" in merge),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("Required pre-merge validation" in merge),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )
    require(
        condition=("required-pre-merge-validation:" not in commit),
        message="test_canonical_workflow_pr_valida...: required condition failed",
    )


def test_workbench_benchmark_merge_script_is_checked_in() -> None:
    """Ensure the canonical workbench benchmark merger is checked in."""
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "merge_workbench_benchmark.py"
    require(
        condition=(script.is_file()),
        message="test_workbench_benchmark_merge_sc...: required condition failed",
    )
    source = script.read_text(encoding="utf-8")
    require(
        condition=('names = ["Pattern", "Sewing", "Simulation"]' in source),
        message="test_workbench_benchmark_merge_sc...: required condition failed",
    )
    require(
        condition=("benchmark.json" in source),
        message="test_workbench_benchmark_merge_sc...: required condition failed",
    )


def test_blanket_evidence_validates_after_docker_restore() -> None:
    """Keep blanket visual evidence validation and artifact contracts aligned."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    block = workflow.split("  gui-visual-examples:", 1)[1].split("  publish-readme-turntables:", 1)[
        0
    ]
    require(
        condition=("test-script: tests/freecad_visual_examples.py" in block),
        message="test_blanket_evidence_validates_a...: required condition failed",
    )
    require(
        condition=("validate-command:" in block),
        message="test_blanket_evidence_validates_a...: required condition failed",
    )
    require(
        condition=("artifact-path:" in block),
        message="test_blanket_evidence_validates_a...: required condition failed",
    )


def test_turntable_frame_counts_validate_after_restore() -> None:
    """Keep turntable validation aligned with its script and artifact contract."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    block = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    require(
        condition=("test-script: tests/freecad_simulation_turntable.py" in block),
        message="test_turntable_frame_counts_valid...: required condition failed",
    )
    require(
        condition=("validate-command:" in block),
        message="test_turntable_frame_counts_valid...: required condition failed",
    )
    require(
        condition=("artifact-path:" in block),
        message="test_turntable_frame_counts_valid...: required condition failed",
    )


def test_canonical_workflow_keeps_simple_local_first_fallback() -> None:
    """Preserve the simple local-first runner fallback policy."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition=("runner_watchdog:" in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    watchdog = (root / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    require(
        condition=("runner-watchdog=fallback" in watchdog),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("runner_mode:" in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("fallback_source_run:" in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("default: local" in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("pull_request_broker:" not in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("runner_router:" not in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("runner_heartbeat:" not in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("sketcher-startup-diagnostic:" not in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )
    require(
        condition=("*/5 * * * *" not in workflow),
        message="test_canonical_workflow_keeps_sim...: required condition failed",
    )


def test_seam_graph_has_one_canonical_implementation() -> None:
    """Require the canonical seam graph to live in the sewing package."""
    root = Path(__file__).resolve().parents[1]
    require(
        condition=((root / "freecad_cloth" / "sewing" / "SeamGraph.py").is_file()),
        message="test_seam_graph_has_one_canonical...: required condition failed",
    )
    require(
        condition=(not (root / "freecad_cloth" / "pattern" / "SeamGraph.py").exists()),
        message="test_seam_graph_has_one_canonical...: required condition failed",
    )


def test_no_code_imports_removed_seam_reference_namespace() -> None:
    """Reject imports from the removed seam-reference namespace."""
    root = Path(__file__).resolve().parents[1]
    instructions = (root / "AGENTS.md").read_text(encoding="utf-8")
    require(
        condition=("freecad_cloth.pattern.SeamReference" in instructions),
        message="test_no_code_imports_removed_seam...: required condition failed",
    )
    require(
        condition=("freecad_cloth.sewing.SeamReference" not in instructions),
        message="test_no_code_imports_removed_seam...: required condition failed",
    )
    offenders = []
    for path in root.glob("freecad_cloth/**/*.py"):
        source = path.read_text(encoding="utf-8")
        if "from freecad_cloth.sewing.SeamReference import" in source:
            offenders.append(path.as_posix())
    require(
        condition=(not offenders),
        message="test_no_code_imports_removed_seam...: required condition failed",
    )


def test_pr_simulation_execution_and_publication_are_privilege_separated() -> None:
    """Keep unprivileged execution separate from privileged publication."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  publish-pr-simulation-evidence:", 1)[
        0
    ]
    publish = workflow.split("  publish-pr-simulation-evidence:", 1)[1].split(
        "  gui-turntables:", 1
    )[0]
    require(
        condition=("permissions:" not in gui),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("freecad-test@" in gui),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("contents: write" in publish),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("pull-requests: write" in publish),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("runs-on: ubuntu-latest" in publish),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("publish-visual-evidence@" in publish),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=("mode: pr" in publish),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=(
            "evidence-head: ${{ github.event.pull_request.head.sha || github.sha }}" in publish
        ),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )
    require(
        condition=(
            "source-sha: ${{ github.event.pull_request.head.sha || github.sha }}" in publish
        ),
        message="test_pr_simulation_execution_and_...: required condition failed",
    )


def test_workflow_actions_use_immutable_release_pins() -> None:
    """Require immutable commit pins for external workflow actions."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    references = re.findall(
        r"uses: [^@\n]+@([0-9a-f]{40})(?:\s+#\s+v[0-9.]+)?",
        workflow,
    )
    require(
        condition=bool(references),
        message="test_workflow_actions_use_immutab...: required condition failed",
    )
    require(
        condition=(all(len(sha) == EXPECTED_SHA_LENGTH for sha in references)),
        message="test_workflow_actions_use_immutab...: required condition failed",
    )


def test_avatar_commands_do_not_depend_on_simulation_package() -> None:
    """Keep avatar command code independent of simulation modules."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "avatar_commands.py").read_text(encoding="utf-8")
    require(
        condition=("freecad_cloth.simulation.SimulationObjects" not in source),
        message="test_avatar_commands_do_not_depen...: required condition failed",
    )


def test_freecad_runner_uses_native_app_run_and_optional_mod_staging() -> None:
    """Require the runner to use AppRun and support optional module staging."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")
    require(
        condition=('command = ["/opt/freecad/AppRun"]' in source),
        message="test_freecad_runner_uses_native_a...: required condition failed",
    )
    require(
        condition=(
            'command.extend(["-M", "/tmp/freecad-mod", "-P", "/tmp/freecad-mod/freecad-cloth"])'
            in source
        ),
        message="test_freecad_runner_uses_native_a...: required condition failed",
    )
    require(
        condition=("command.append(str(args.test_script))" in source),
        message="test_freecad_runner_uses_native_a...: required condition failed",
    )
    require(
        condition=("runpy.run_path" not in source),
        message="test_freecad_runner_uses_native_a...: required condition failed",
    )
    require(
        condition=("init_gui.read_text" not in source),
        message="test_freecad_runner_uses_native_a...: required condition failed",
    )


def test_freecad_runner_preserves_script_owned_logs() -> None:
    """Preserve logs produced by test scripts when the runner exits."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")
    require(
        condition=("stdout=subprocess.PIPE" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("process.communicate(timeout=timeout_seconds)" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("args.log_file.is_file()" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("args.log_file.read_text(" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("if not existing_log.strip():" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=('args.log_file.write_text(output, encoding="utf-8")' in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("sys.stdout.write(output)" in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )
    require(
        condition=("runpy.run_path" not in source),
        message="test_freecad_runner_preserves_scr...: required condition failed",
    )


def test_modern_loader_does_not_mutate_sys_path() -> None:
    """Keep the modern loader independent of sys.path mutations."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad" / "freecad_cloth" / "init_gui.py").read_text(encoding="utf-8")
    require(
        condition=("sys.path" not in source),
        message="test_modern_loader_does_not_mutat...: required condition failed",
    )


def test_sitecustomize_is_host_compatibility_only() -> None:
    """Limit sitecustomize to host compatibility behavior."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "sitecustomize.py").read_text(encoding="utf-8")
    require(
        condition=("QPixmap" in source),
        message="test_sitecustomize_is_host_compat...: required condition failed",
    )
    require(
        condition=("CLOTH_SIMULATION_BACKEND" not in source),
        message="test_sitecustomize_is_host_compat...: required condition failed",
    )
    require(
        condition=("CLOTH_CI_ENABLE_PBD" not in source),
        message="test_sitecustomize_is_host_compat...: required condition failed",
    )
    require(
        condition=("CLOTH_CI_DISABLE_PBD" not in source),
        message="test_sitecustomize_is_host_compat...: required condition failed",
    )
    require(
        condition=("_install_pbd_backend_hook" not in source),
        message="test_sitecustomize_is_host_compat...: required condition failed",
    )


def test_manifest_declares_all_bundled_workbenches() -> None:
    """Keep all bundled workbenches represented in the package manifest."""
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "package.xml").read_text(encoding="utf-8")
    for classname in (
        "ClothPatternWorkbench",
        "ClothSewingWorkbench",
        "ClothSimulationWorkbench",
    ):
        require(
            condition=(f"<classname>{classname}</classname>" in manifest),
            message="test_manifest_declares_all_bundle...: required condition failed",
        )
    require(
        condition=(manifest.count("<workbench>") == EXPECTED_BUNDLED_WORKBENCH_COUNT),
        message="test_manifest_declares_all_bundle...: required condition failed",
    )
    require(
        condition=("<freecadmin>1.1.0</freecadmin>" in manifest),
        message="test_manifest_declares_all_bundle...: required condition failed",
    )


def test_freecad_classic_and_modern_loader_surfaces_are_documented_and_aligned() -> None:
    """Keep both loader surfaces aligned with their documented bootstrap contract."""
    root = Path(__file__).resolve().parents[1]
    loaders = (
        root / "InitGui.py",
        root / "freecad" / "freecad_cloth" / "init_gui.py",
    )
    bootstrap = (root / "freecad_cloth" / "bootstrap.py").read_text(encoding="utf-8")
    for loader in loaders:
        source = loader.read_text(encoding="utf-8")
        require(
            condition=("from freecad_cloth.bootstrap import initialize_workbenches" in source),
            message="test_freecad_classic_and_modern_l...: required condition failed",
        )
        require(
            condition=("initialize_workbenches(" in source),
            message="test_freecad_classic_and_modern_l...: required condition failed",
        )
        require(
            condition=("Gui.addWorkbench(" not in source),
            message="test_freecad_classic_and_modern_l...: required condition failed",
        )
    for workbench in ("ClothPatternWorkbench", "ClothSewingWorkbench", "ClothSimulationWorkbench"):
        require(
            condition=(f'("{workbench}",' in bootstrap),
            message="test_freecad_classic_and_modern_l...: required condition failed",
        )
    require(
        condition=(
            "loader layouts"
            in (root / "docs" / "developers" / "PROJECT_STRUCTURE.md")
            .read_text(encoding="utf-8")
            .lower()
        ),
        message="test_freecad_classic_and_modern_l...: required condition failed",
    )


def test_consolidated_architecture_has_no_parallel_authority_modules() -> None:
    """Reject duplicate modules for responsibilities that have been consolidated."""
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        root / "freecad_cloth" / "pattern" / "PatternSchema.py",
        root / "freecad_cloth" / "pattern" / "PatternSync.py",
        root / "freecad_cloth" / "sewing" / "SewingAssembly.py",
        root / "freecad_cloth" / "sewing" / "SewingPlan.py",
        root / "freecad_cloth" / "sewing" / "SewingSemantics.py",
        root / "freecad_cloth" / "sewing" / "SeamReference.py",
        root / "freecad_cloth" / "simulation" / "SimulationStaleGuard.py",
        root / "freecad_cloth" / "simulation" / "SimulationQualityRuntimeV2.py",
        root / "freecad_cloth" / "common" / "PatternSimulationAdapter.py",
        root / "freecad_cloth" / "common" / "SketchAuthority.py",
        root / "freecad_cloth" / "common" / "DrapeFailureClassifier.py",
        root / "freecad_cloth" / "common" / "DrapeVisualSanity.py",
        root / "freecad_cloth" / "common" / "ClothDiagnostics.py",
        root / "freecad_cloth" / "common" / "ClothDiagnosticsGui.py",
    )
    require(
        condition=(all(not path.exists() for path in forbidden)),
        message="test_consolidated_architecture_ha...: required condition failed",
    )
    require(
        condition=((root / "freecad_cloth" / "shared" / "collision.py").is_file()),
        message="test_consolidated_architecture_ha...: required condition failed",
    )
    require(
        condition=(
            (root / "freecad_cloth" / "simulation" / "SimulationQualityRuntime.py").is_file()
        ),
        message="test_consolidated_architecture_ha...: required condition failed",
    )
    require(
        condition=((root / "freecad_cloth" / "pattern" / "SketchAuthority.py").is_file()),
        message="test_consolidated_architecture_ha...: required condition failed",
    )


def test_neutral_collision_contract_is_singleton() -> None:
    """Keep the canonical collision surface value type in the shared package."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "shared" / "collision.py").read_text(encoding="utf-8")
    require(
        condition=("class CollisionSurface" in source),
        message="test_neutral_collision_contract_i...: required condition failed",
    )
    avatar = (root / "freecad_cloth" / "avatar" / "AvatarCollision.py").read_text(encoding="utf-8")
    require(
        condition=("class CollisionSurface" not in avatar),
        message="test_neutral_collision_contract_i...: required condition failed",
    )


def test_python_sources_do_not_import_removed_architecture_modules() -> None:
    """Reject source imports from the removed parallel architecture modules.

    Raises:
        AssertionError: If a Python source references a removed architecture module.
    """
    root = Path(__file__).resolve().parents[1]
    forbidden_modules = {
        "freecad_cloth.pattern.PatternSchema",
        "freecad_cloth.pattern.PatternSync",
        "freecad_cloth.sewing.SewingAssembly",
        "freecad_cloth.sewing.SewingPlan",
        "freecad_cloth.sewing.SewingSemantics",
        "freecad_cloth.sewing.SeamReference",
        "freecad_cloth.simulation.SimulationStaleGuard",
        "freecad_cloth.simulation.SimulationQualityRuntimeV2",
        "freecad_cloth.common.PatternSimulationAdapter",
        "freecad_cloth.common.SketchAuthority",
        "freecad_cloth.common.DrapeFailureClassifier",
        "freecad_cloth.common.DrapeVisualSanity",
        "freecad_cloth.common.ClothDiagnostics",
        "freecad_cloth.common.ClothDiagnosticsGui",
    }
    offenders = []
    for directory in (root / "freecad_cloth", root / "tests", root / "tools"):
        for path in directory.rglob("*.py"):
            try:
                module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                msg = f"invalid Python source {path}: {exc}"
                raise AssertionError(msg) from exc
            for node in ast.walk(module):
                imported = set()
                source_line: int | None = None
                if isinstance(node, ast.ImportFrom):
                    source_line = node.lineno
                    if node.module:
                        imported.add(node.module)
                    imported.update(
                        f"{node.module}.{alias.name}" if node.module else alias.name
                        for alias in node.names
                    )
                elif isinstance(node, ast.Import):
                    source_line = node.lineno
                    imported.update(alias.name for alias in node.names)
                if source_line is not None:
                    offenders.extend(
                        f"{path.relative_to(root)}:{source_line}: {name}"
                        for name in imported & forbidden_modules
                    )
    require(
        condition=(not offenders),
        message="test_python_sources_do_not_import...: required condition failed",
    )
