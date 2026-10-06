"""Structural checks for the canonical Python package tree."""

from pathlib import Path


def test_project_metadata_exists():
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project]" in text
    assert 'name = "freecad-cloth"' in text
    assert "[build-system]" in text


def test_workbench_package_boundaries_exist():
    root = Path(__file__).resolve().parents[1]
    for name in ("pattern", "sewing", "simulation", "avatar", "common", "shared"):
        package = root / "freecad_cloth" / name
        assert (package / "__init__.py").is_file()
    for name in ("pattern", "sewing", "simulation"):
        assert (root / "freecad_cloth" / name / "workbench.py").is_file()


def test_only_bootstrap_python_files_remain_at_root():
    root = Path(__file__).resolve().parents[1]
    assert {path.name for path in root.glob("*.py")} <= {
        "Init.py",
        "InitGui.py",
        "sitecustomize.py",
    }


def test_root_initgui_does_not_swallow_drapetarget_import_errors():
    root = Path(__file__).resolve().parents[1]
    source = (root / "InitGui.py").read_text(encoding="utf-8")
    assert "import freecad_cloth.simulation.DrapeTarget" not in source
    assert "target execute/recompute guard" not in source
    assert "Gui = None" in source


def test_freecad_entry_points_remain_at_root():
    root = Path(__file__).resolve().parents[1]
    assert (root / "Init.py").is_file()
    assert (root / "InitGui.py").is_file()
    gui = (root / "InitGui.py").read_text(encoding="utf-8")
    assert "Gui.addWorkbench(ClothPatternWorkbench())" in gui
    assert "Gui.addWorkbench(ClothSewingWorkbench())" in gui
    assert "Gui.addWorkbench(ClothSimulationWorkbench())" in gui


def test_shared_contract_is_freecad_independent():
    from freecad_cloth.shared.collision import CollisionSurface
    from freecad_cloth.shared.targets import DrapeTargetRef

    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    target = DrapeTargetRef("freecad", "Body", revision=2)
    assert surface.region == "body"
    assert target.revision == 2
    assert target.is_freecad_object()
    assert not target.is_human()


def test_human_documentation_contract():
    root = Path(__file__).resolve().parents[1]
    user_guide = root / "docs" / "USER_GUIDE.md"
    docs_readme = root / "docs" / "README.md"
    assert user_guide.is_file()
    assert "USER_GUIDE.md" in docs_readme.read_text(encoding="utf-8")


def test_canonical_workflow_pr_validation_contract():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:" in workflow
    assert "pull_request_target:" not in workflow
    assert "types: [opened, synchronize, reopened]" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow


def test_workbench_benchmark_merge_script_is_checked_in():
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "merge_workbench_benchmark.py"
    assert script.is_file()
    source = script.read_text(encoding="utf-8")
    assert 'names = ["Pattern", "Sewing", "Simulation"]' in source
    assert "benchmark.json" in source


def test_blanket_evidence_validates_after_docker_restore():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    block = workflow.split("  gui-visual-examples:", 1)[1].split("  publish-readme-turntables:", 1)[
        0
    ]
    assert "test-script: tests/freecad_visual_examples.py" in block
    assert "validate-command:" in block
    assert "artifact-path:" in block


def test_turntable_frame_counts_validate_after_restore():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    block = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert "test-script: tests/freecad_simulation_turntable.py" in block
    assert "validate-command:" in block
    assert "artifact-path:" in block


def test_canonical_workflow_keeps_simple_local_first_fallback():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "runner_watchdog:" in workflow
    watchdog = (root / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    assert "runner-watchdog=fallback" in watchdog
    assert "-f runner_mode=hosted" in workflow
    assert "-f fallback_source_run=" in workflow
    assert "pull_request_broker:" not in workflow
    assert "runner_router:" not in workflow
    assert "runner_heartbeat:" not in workflow
    assert "sketcher-startup-diagnostic:" not in workflow
    assert "*/5 * * * *" not in workflow


def test_seam_graph_has_one_canonical_implementation():
    root = Path(__file__).resolve().parents[1]
    assert (root / "freecad_cloth" / "sewing" / "SeamGraph.py").is_file()
    assert not (root / "freecad_cloth" / "pattern" / "SeamGraph.py").exists()


def test_no_code_imports_removed_seam_reference_namespace():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.glob("freecad_cloth/**/*.py"):
        source = path.read_text(encoding="utf-8")
        if "from freecad_cloth.sewing.SeamReference import" in source:
            offenders.append(path.as_posix())
    assert not offenders, offenders


def test_pr_simulation_execution_and_publication_are_privilege_separated():
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
    assert "permissions:" not in gui
    assert "freecad-test@" in gui
    assert "contents: write" in publish
    assert "pull-requests: write" in publish
    assert "runs-on: ubuntu-latest" in publish
    assert "actions/download-artifact@" in publish
    assert "actions/checkout@" in publish
    assert "ref: ${{ github.event.pull_request.base.sha }}" in publish
    assert "without executing PR code" in publish


def test_workflow_actions_use_immutable_release_pins():
    import re

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    references = re.findall(
        r"uses: [^@\\n]+@([0-9a-f]{40})(?:\\s+#\\s+v[0-9.]+)?",
        workflow,
    )
    assert references
    assert all(len(sha) == 40 for sha in references)

def test_avatar_commands_do_not_depend_on_simulation_package():
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "AvatarCommands.py").read_text(
        encoding="utf-8"
    )
    assert "freecad_cloth.simulation.SimulationObjects" not in source


def test_freecad_runner_preserves_script_owned_logs():
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")
    assert "stdout=log_handle" in source
    assert "runpy.run_path" in source


def test_modern_loader_does_not_mutate_sys_path():
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad" / "freecad_cloth" / "init_gui.py").read_text(encoding="utf-8")
    assert "sys.path" not in source


def test_sitecustomize_is_host_compatibility_only():
    root = Path(__file__).resolve().parents[1]
    source = (root / "sitecustomize.py").read_text(encoding="utf-8")
    assert "QPixmap" in source
    assert "CLOTH_SIMULATION_BACKEND" not in source
    assert "CLOTH_CI_ENABLE_PBD" not in source
    assert "CLOTH_CI_DISABLE_PBD" not in source
    assert "_install_pbd_backend_hook" not in source


def test_manifest_declares_all_bundled_workbenches():
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "package.xml").read_text(encoding="utf-8")
    for classname in (
        "ClothPatternWorkbench",
        "ClothSewingWorkbench",
        "ClothSimulationWorkbench",
    ):
        assert f"<classname>{classname}</classname>" in manifest
    assert manifest.count("<workbench>") == 3
    assert "<freecadmin>1.1.0</freecadmin>" in manifest


def test_freecad_classic_and_modern_loader_surfaces_are_documented_and_aligned():
    root = Path(__file__).resolve().parents[1]
    classic = (root / "InitGui.py").read_text(encoding="utf-8")
    modern = (root / "freecad" / "freecad_cloth" / "init_gui.py").read_text(encoding="utf-8")
    for workbench in ("ClothPatternWorkbench", "ClothSewingWorkbench", "ClothSimulationWorkbench"):
        assert workbench in classic
        assert workbench in modern
    assert (
        "loader layouts"
        in (root / "docs" / "PROJECT_STRUCTURE.md").read_text(encoding="utf-8").lower()
    )


def test_consolidated_architecture_has_no_parallel_authority_modules():
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
    assert all(not path.exists() for path in forbidden)
    assert (root / "freecad_cloth" / "shared" / "collision.py").is_file()
    assert (root / "freecad_cloth" / "simulation" / "SimulationQualityRuntime.py").is_file()
    assert (root / "freecad_cloth" / "pattern" / "SketchAuthority.py").is_file()


def test_neutral_collision_contract_is_singleton():
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "shared" / "collision.py").read_text(encoding="utf-8")
    assert "class CollisionSurface" in source
    avatar = (root / "freecad_cloth" / "avatar" / "AvatarCollision.py").read_text(
        encoding="utf-8"
    )
    assert "class CollisionSurface" not in avatar
