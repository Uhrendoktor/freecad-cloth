"""Static contract for FreeCAD GUI startup ordering in acceptance workflows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_sketcher_acceptance_prepares_gui_before_workbench_assertion():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    run = source.split("def run_acceptance():", 1)[1]
    assert run.index("window = Gui.getMainWindow()") < run.index("_bootstrap_workbenches()")
    assert run.index("window.show()") < run.index("_bootstrap_workbenches()")
    assert run.index("_events()") < run.index("_bootstrap_workbenches()")
    assert '_stage("gui-ready")' in run

def test_visual_example_prepares_gui_and_explicit_workbench_registration():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    run = source.split("def main():", 1)[1]
    window_index = run.index("window = Gui.getMainWindow()")
    show_index = run.index("window.show()", window_index)
    first_events_index = run.index("events()", show_index)
    modules_index = run.index("_load_cloth_modules()", first_events_index)
    init_gui_index = run.index('init_gui = ROOT / "InitGui.py"', modules_index)
    guard_index = run.index('if "ClothPatternWorkbench" not in Gui.listWorkbenches():', init_gui_index)
    exec_index = run.index("exec(compile(init_gui.read_text", guard_index)
    post_events_index = run.index("events()", exec_index)
    registered_index = run.index("raise RuntimeError", post_events_index)
    document_index = run.index('doc = App.newDocument("ClothBlanketExample")', registered_index)
    module_helper = source.split("def _load_cloth_modules():", 1)[1].split("def main():", 1)[0]
    assert window_index < show_index < first_events_index < modules_index
    assert modules_index < init_gui_index < guard_index < exec_index < post_events_index < registered_index < document_index
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


def test_freecad_package_metadata_declares_root_gui_workbench():
    metadata = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert '<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">' in metadata
    assert "<classname>ClothPatternWorkbench</classname>" in metadata
    assert "<subdirectory>./</subdirectory>" in metadata
    assert "exec(compile(init_gui" not in metadata


def test_sketcher_acceptance_uses_explicit_initgui_startup():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    assert "sys.path[:] = [entry for entry in sys.path if entry not in (\"\", str(ROOT))]" in source
    assert "if \"ClothPatternWorkbench\" not in Gui.listWorkbenches():" in source
    assert "registered by explicit InitGui startup" in source
    assert "init_gui.read_text(encoding=\"utf-8\")" in source
    run = source.split("def run_acceptance():", 1)[1]
    bootstrap_index = run.index("_bootstrap_workbenches()")
    stage_index = run.index('_stage("gui-ready")')
    assert stage_index < bootstrap_index
    assert "app.quit()" in source

def test_canonical_gui_jobs_use_deterministic_startup_boundaries():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert "/opt/freecad/AppRun /workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert "cp -a /workspace/Init.py /workspace/InitGui.py" not in sketcher
    assert "cp -a /workspace/Init.py /workspace/InitGui.py /workspace/package.xml /workspace/resources /workspace/freecad_cloth /tmp/freecad-mod/freecad-cloth/" in visual
    assert "/opt/freecad/AppRun -M /tmp/freecad-mod -P /tmp/freecad-mod/freecad-cloth /workspace/tests/freecad_visual_examples.py" in visual
    assert "freecad_ci_bootstrap.FCMacro" not in sketcher
    assert "freecad_ci_bootstrap.FCMacro" not in visual

def test_canonical_concurrency_cancels_stale_pr_runs():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "canonical-${{ github.workflow }}-pr-" in workflow
    assert "github.event.pull_request.number" in workflow
    assert "cancel-in-progress: true" in workflow

def test_canonical_readme_turntable_launches_from_neutral_cwd():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    turntable = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_avatar_screenshot.py" in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_simulation_turntable.py" in turntable

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
    test_canonical_gui_jobs_use_deterministic_startup_boundaries()
    test_canonical_concurrency_cancels_stale_pr_runs()
    test_canonical_readme_turntable_launches_from_neutral_cwd()
    test_readme_turntable_scripts_import_freecad_gui_before_repository_path_injection()