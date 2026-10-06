"""Static contract for FreeCAD GUI startup ordering in acceptance workflows."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sketcher_acceptance_prepares_gui_before_workbench_assertion():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    run = source.split("def run_acceptance():", 1)[1]
    assert run.index("window = Gui.getMainWindow()") < run.index("_bootstrap_workbenches()")
    assert run.index("window.show()") < run.index("_bootstrap_workbenches()")
    assert run.index("_events()") < run.index("_bootstrap_workbenches()")
    assert '_stage("gui-ready")' in run


def test_visual_capture_contract_uses_structural_validation_without_size_heuristic():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    validator = (ROOT / "freecad_cloth" / "common" / "VisualCaptureValidation.py").read_text(
        encoding="utf-8"
    )
    assert "validate_png_capture" in source
    assert "st_size < 5000" not in source
    assert "expected_width=640" in source
    assert "expected_height=480" in source
    assert "nonwhite_pixels" in validator
    assert "distinct_rgb" in validator


def test_visual_example_prepares_gui_and_explicit_workbench_registration():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    run = source.split("def main():", 1)[1]
    window_index = run.index("window = Gui.getMainWindow()")
    show_index = run.index("window.show()", window_index)
    first_events_index = run.index("events()", show_index)
    modules_index = run.index("_load_cloth_modules()", first_events_index)
    init_gui_index = run.index('init_gui = ROOT / "InitGui.py"', modules_index)
    guard_index = run.index(
        'if "ClothPatternWorkbench" not in Gui.listWorkbenches():', init_gui_index
    )
    exec_index = run.index("exec(", guard_index)
    compile_index = run.index("compile(", exec_index)
    assert exec_index < compile_index
    post_events_index = run.index("events()", exec_index)
    registered_index = run.index("raise RuntimeError", post_events_index)
    document_index = run.index('doc = App.newDocument("ClothBlanketExample")', registered_index)
    module_helper = source.split("def _load_cloth_modules():", 1)[1].split("def main():", 1)[0]
    assert window_index < show_index < first_events_index < modules_index
    assert (
        modules_index
        < init_gui_index
        < guard_index
        < exec_index
        < post_events_index
        < registered_index
        < document_index
    )
    assert "site.addsitedir(str(ROOT))" in module_helper
    assert "from freecad_cloth." in module_helper
    assert "sys.path[:] = [entry for entry in sys.path if entry not in" in source
    assert "str(ROOT)" in source
    assert source.index("sys.path[:] =") < source.index("import FreeCAD as App")
    assert "InitGui.py" in run


def test_freecad_extension_package_uses_namespace_gui_entry_point():
    extension = ROOT / "freecad" / "freecad_cloth"
    assert extension.is_dir()
    assert not (ROOT / "freecad" / "__init__.py").exists()
    assert (extension / "__init__.py").is_file()
    source = (extension / "init_gui.py").read_text(encoding="utf-8")
    assert "Gui.addWorkbench(ClothPatternWorkbench())" in source
    assert "Gui.addWorkbench(ClothSimulationWorkbench())" in source
    assert "Gui.addWorkbench(ClothSewingWorkbench())" in source
    assert "from freecad_cloth." in source


def test_freecad_package_metadata_declares_all_bundled_gui_workbenches():
    metadata = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert '<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">' in metadata
    for classname in (
        "ClothPatternWorkbench",
        "ClothSewingWorkbench",
        "ClothSimulationWorkbench",
    ):
        assert f"<classname>{classname}</classname>" in metadata
    assert metadata.count("<workbench>") == 3
    assert metadata.count("<subdirectory>./</subdirectory>") == 3
    assert "<freecadmin>1.1.0</freecadmin>" in metadata
    assert "exec(compile(init_gui" not in metadata


def test_sketcher_acceptance_uses_freecad_startup_registration():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    assert 'if "ClothPatternWorkbench" not in Gui.listWorkbenches():' in source
    assert "ClothPatternWorkbench was not loaded by FreeCAD startup" in source
    assert "init_gui.read_text(encoding=" not in source
    run = source.split("def run_acceptance():", 1)[1]
    bootstrap_index = run.index("_bootstrap_workbenches()")
    stage_index = run.index('_stage("gui-ready")')
    assert stage_index < bootstrap_index
    assert "app.quit()" in source


def test_canonical_gui_jobs_use_shared_freecad_test_boundaries():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-simple:", 1)[1].split("  gui-tunic-visual:", 1)[0]
    tunic = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    assert "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" in gui
    assert "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" in tunic
    assert "case: sketcher, script: tests/freecad_sketcher_acceptance.py" in gui
    assert "case: pattern-export, script: tests/freecad_pattern_export_smoke.py" in gui
    assert "test-script: ${{ matrix.script }}" in gui
    assert "test-script: tests/freecad_tunic_audit_production.py" in tunic
    assert "freecad_ci_bootstrap.FCMacro" not in workflow
    assert "/opt/freecad/AppRun" not in workflow
    assert "docker run" not in workflow


def test_canonical_concurrency_preserves_main_runs_and_checks_artifact_budget():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "canonical-pr-{0}" in workflow
    assert "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}" in workflow
    assert "cancel-stale-pr-runs:" not in workflow
    assert "artifact-budget:" in workflow
    budget = workflow.split("  artifact-budget:", 1)[1].split("  benchmark:", 1)[0]
    for producer in (
        "diagnostic-pbd-contact",
        "simulation-ladder",
        "python",
        "gui-simple",
        "gui-tunic-visual",
        "gui-turntables",
        "gui-visual-examples",
        "benchmark",
    ):
        assert producer in budget
    assert "tools/ci/check_artifact_budget.py" in budget
    quality = workflow.split("  agent-quality:", 1)[1].split("  local_runner_readiness:", 1)[0]
    assert "python -m ruff format tools/ci" in quality
    for job in (
        "local_runner_readiness:",
        "runner_watchdog:",
        "pbd_validation_image:",
        "diagnostic-pbd-contact:",
        "simulation-ladder:",
        "python:",
        "gui-simple:",
        "gui-tunic-visual:",
        "gui-turntables:",
        "gui-visual-examples:",
        "publish-pr-simulation-evidence:",
        "publish-readme-turntables:",
        "maintenance-cleanup:",
        "artifact-budget:",
        "benchmark:",
    ):
        start = workflow.index(f"\n  {job}")
        match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 1 :])
        end = start + 1 + match.start() if match else len(workflow)
        block = workflow[start:end]
        assert "needs:" in block
        assert "agent-quality" in block


def test_canonical_readme_turntable_uses_shared_freecad_test_action():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    turntable = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" in turntable
    assert "test-script: tests/freecad_avatar_screenshot.py" in turntable
    assert "test-script: tests/freecad_simulation_turntable.py" in turntable
    assert "/opt/freecad/AppRun" not in turntable


def test_readme_turntable_scripts_import_freecad_gui_before_repository_path_injection():
    for name in ("freecad_avatar_screenshot.py", "freecad_simulation_turntable.py"):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        gui_index = source.index("import FreeCADGui as Gui")
        path_guard = source.index("if ROOT not in sys.path:")
        assert gui_index < path_guard
        assert source.index("import FreeCAD as App") < path_guard


if __name__ == "__main__":
    test_sketcher_acceptance_prepares_gui_before_workbench_assertion()
    test_visual_example_prepares_gui_and_explicit_workbench_registration()
    test_sketcher_acceptance_uses_explicit_initgui_startup()
    test_canonical_gui_jobs_use_shared_freecad_test_boundaries()
    test_canonical_concurrency_preserves_main_runs_and_checks_artifact_budget()
    test_canonical_readme_turntable_uses_shared_freecad_test_action()
    test_readme_turntable_scripts_import_freecad_gui_before_repository_path_injection()


def test_large_gui_acceptance_scripts_fail_fast_from_freecad_process():
    root = Path(__file__).resolve().parents[1]
    for name in (
        "freecad_avatar_screenshot.py",
        "freecad_simulation_turntable.py",
        "freecad_visual_examples.py",
        "freecad_screenshot_source.py",
    ):
        source = (root / "tests" / name).read_text(encoding="utf-8")
        assert "os._exit(1)" in source, name
