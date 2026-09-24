"""Static contract for FreeCAD GUI startup ordering in acceptance workflows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sketcher_acceptance_prepares_gui_before_manual_initgui():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    run = source.split("def run_acceptance():", 1)[1]
    assert run.index("window = Gui.getMainWindow()") < run.index("_bootstrap_workbenches()")
    assert run.index("window.show()") < run.index("_bootstrap_workbenches()")
    assert run.index("_events()") < run.index("_bootstrap_workbenches()")
    assert '_stage("gui-ready")' in run


def test_visual_example_prepares_gui_before_manual_initgui():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")
    run = source.split("def main():", 1)[1]
    window_index = run.index("window = Gui.getMainWindow()")
    show_index = run.index("window.show()", window_index)
    first_events_index = run.index("events()", show_index)
    modules_index = run.index("_load_cloth_modules()", first_events_index)
    init_gui_index = run.index("init_gui = os.path.join", modules_index)
    guard_index = run.index('if "ClothPatternWorkbench" not in Gui.listWorkbenches():', init_gui_index)
    exec_index = run.index("exec(compile(open(init_gui", guard_index)
    document_index = run.index('doc = App.newDocument("ClothBlanketExample")', exec_index)

    module_helper = source.split("def _load_cloth_modules():", 1)[1].split("def main():", 1)[0]
    module_prefix = source.split("import FreeCAD as App", 1)[0]
    assert window_index < show_index < first_events_index < modules_index
    assert modules_index < init_gui_index < guard_index < exec_index < document_index
    assert "site.addsitedir(str(ROOT))" in module_helper
    assert "from freecad_cloth." in module_helper
    path_isolation = "sys.path[:] = [entry for entry in sys.path if entry not in"
    assert path_isolation in module_prefix
    assert "str(ROOT)" in module_prefix
    assert module_prefix.index("sys.path[:] =") < module_prefix.index("import FreeCAD as App")
    assert "site.addsitedir(str(Path(__file__).resolve().parents[1]))" not in source
    assert "InitGui.py" in run


def test_committed_fcmacro_defers_acceptance_until_after_delayed_startup():
    source = (ROOT / "tests" / "freecad_ci_bootstrap.FCMacro").read_text(encoding="utf-8")
    assert "import FreeCADGui as Gui" in source
    assert "window.show()" in source
    assert "sys.path[:] = [p for p in sys.path if p != ROOT]" in source
    assert "QtCore.QTimer.singleShot(0, _run_acceptance)" in source
    assert "processEvents()" not in source
    assert source.index("sys.path[:] = [p for p in sys.path if p != ROOT]") < source.index("import FreeCADGui as Gui")
    assert source.index("window.show()") < source.index("QtCore.QTimer.singleShot(0, _run_acceptance)")
    callback = source.split("def _run_acceptance():", 1)[1].split("QtCore.QTimer.singleShot(0, _run_acceptance)", 1)[0]
    assert "runpy.run_path(script, run_name=\"__main__\")" in callback
    assert "sys.path.insert(0, ROOT)" in callback
    assert source.index("QtCore.QTimer.singleShot(0, _run_acceptance)") > source.index("def _run_acceptance():")


def test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in sketcher
    assert "cp /workspace/tests/freecad_ci_bootstrap.FCMacro /tmp/freecad_ci_bootstrap.FCMacro" in sketcher
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.FCMacro" in sketcher
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.FCMacro" not in sketcher
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert "FREECAD_USER_HOME=/tmp/freecad-user" in sketcher
    assert "FREECAD_USER_DATA=/tmp/freecad-user-data" in sketcher
    assert "FREECAD_USER_TEMP=/tmp/freecad-user-temp" in sketcher
    assert '-w /tmp "$FREECAD_IMAGE"' in visual
    assert "cp /workspace/tests/freecad_ci_bootstrap.FCMacro /tmp/freecad_ci_bootstrap.FCMacro" in visual
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.FCMacro" in visual
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.FCMacro" not in visual
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_visual_examples.py" in visual
    assert "FREECAD_USER_HOME=/tmp/freecad-user" in visual
    assert "FREECAD_USER_DATA=/tmp/freecad-user-data" in visual
    assert "FREECAD_USER_TEMP=/tmp/freecad-user-temp" in visual


def test_canonical_readme_turntable_launches_from_neutral_cwd():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    turntable = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_avatar_screenshot.py" in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_simulation_turntable.py" in turntable


if __name__ == "__main__":
    test_sketcher_acceptance_prepares_gui_before_manual_initgui()
    test_visual_example_prepares_gui_before_manual_initgui()
    test_committed_fcmacro_defers_acceptance_until_after_delayed_startup()
    test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap()
    test_canonical_readme_turntable_launches_from_neutral_cwd()
