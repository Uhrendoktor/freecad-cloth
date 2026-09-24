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

def test_visual_example_prepares_gui_before_module_imports():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    run = source.split("def main():", 1)[1]
    window_index = run.index("window = Gui.getMainWindow()")
    show_index = run.index("window.show()", window_index)
    first_events_index = run.index("events()", show_index)
    modules_index = run.index("_load_cloth_modules()", first_events_index)
    guard_index = run.index('if "ClothPatternWorkbench" not in Gui.listWorkbenches():', modules_index)
    document_index = run.index('doc = App.newDocument("ClothBlanketExample")', guard_index)
    module_helper = source.split("def _load_cloth_modules():", 1)[1].split("def main():", 1)[0]
    assert window_index < show_index < first_events_index < modules_index < guard_index < document_index
    assert "site.addsitedir(str(ROOT))" in module_helper
    assert "from freecad_cloth." in module_helper
    assert "sys.path[:] = [entry for entry in sys.path if entry not in" in source
    assert "str(ROOT)" in source
    assert source.index("sys.path[:] =") < source.index("import FreeCAD as App")
    assert "exec(compile(open(init_gui" not in source

def test_sketcher_acceptance_uses_freecad_module_path_startup():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    assert "sys.path[:] = [entry for entry in sys.path if entry not in (\"\", str(ROOT))]" in source
    assert "if \"ClothPatternWorkbench\" not in Gui.listWorkbenches():" in source
    assert "registered by FreeCAD module-path startup" in source
    assert "exec(compile(init_gui" not in source
    assert "app.quit()" in source

def test_canonical_gui_jobs_use_freecad_module_path():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert "cp -a /workspace/Init.py /workspace/InitGui.py /workspace/package.xml /workspace/resources /workspace/freecad_cloth /tmp/freecad-mod/freecad-cloth/" in sketcher
    assert "/opt/freecad/AppRun -M /tmp/freecad-mod -P /tmp/freecad-mod/freecad-cloth /workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert "cp -a /workspace/Init.py /workspace/InitGui.py /workspace/package.xml /workspace/resources /workspace/freecad_cloth /tmp/freecad-mod/freecad-cloth/" in visual
    assert "/opt/freecad/AppRun -M /tmp/freecad-mod -P /tmp/freecad-mod/freecad-cloth /workspace/tests/freecad_visual_examples.py" in visual
    assert "freecad_ci_bootstrap.FCMacro" not in sketcher
    assert "freecad_ci_bootstrap.FCMacro" not in visual

def test_canonical_validation_is_commit_scoped_and_not_cancellable():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "canonical-${{ github.workflow }}-" in workflow
    assert "github.sha" in workflow
    assert "cancel-in-progress: false" in workflow

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
    test_visual_example_prepares_gui_before_module_imports()
    test_sketcher_acceptance_uses_freecad_module_path_startup()
    test_canonical_gui_jobs_use_freecad_module_path()
    test_canonical_validation_is_commit_scoped_and_not_cancellable()
    test_canonical_readme_turntable_launches_from_neutral_cwd()
    test_readme_turntable_scripts_import_freecad_gui_before_repository_path_injection()