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
    assert run.index("window = Gui.getMainWindow()") < run.index("doc = App.newDocument")
    assert run.index("window.show()") < run.index("doc = App.newDocument")
    assert run.index("events()") < run.index("doc = App.newDocument")
    assert "InitGui.py" in run


def test_committed_macro_bootstrap_is_gui_ready_and_path_safe():
    source = (ROOT / "tests" / "freecad_ci_bootstrap.FCMacro").read_text(encoding="utf-8")
    assert "import FreeCADGui as Gui" in source
    assert "window.show()" in source
    assert "sys.path[:] = [p for p in sys.path if p != ROOT]" in source
    assert "processEvents()" in source
    assert source.index("sys.path[:] = [p for p in sys.path if p != ROOT]") < source.index("import FreeCADGui as Gui")
    assert source.index("window.show()") < source.index("processEvents()")
    assert source.index("processEvents()") < source.index("sys.path.insert(0, ROOT)")
    assert source.index("sys.path.insert(0, ROOT)") < source.index('runpy.run_path(script, run_name="__main__")')


def test_canonical_gui_jobs_launch_macro_bootstrap_from_neutral_cwd():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in sketcher
    assert "cp /workspace/tests/freecad_ci_bootstrap.FCMacro /tmp/freecad_ci_bootstrap.FCMacro" in sketcher
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.FCMacro" in sketcher
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert "FREECAD_USER_HOME=/tmp/freecad-user" in sketcher
    assert "FREECAD_USER_DATA=/tmp/freecad-user-data" in sketcher
    assert "FREECAD_USER_TEMP=/tmp/freecad-user-temp" in sketcher
    assert '-w /tmp "$FREECAD_IMAGE"' in visual
    assert "cp /workspace/tests/freecad_ci_bootstrap.FCMacro /tmp/freecad_ci_bootstrap.FCMacro" in visual
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.FCMacro" in visual
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_visual_examples.py" in visual
    assert "FREECAD_USER_HOME=/tmp/freecad-user" in visual
    assert "FREECAD_USER_DATA=/tmp/freecad-user-data" in visual
    assert "FREECAD_USER_TEMP=/tmp/freecad-user-temp" in visual


def test_canonical_readme_turntable_launches_from_neutral_cwd():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    turntable = workflow.split("  gui-turntables:", 1)[1].split("  gui-tunic-visual:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_avatar_screenshot.py" in turntable
    assert "/opt/freecad/AppRun /workspace/tests/freecad_simulation_turntable.py" in turntable


if __name__ == "__main__":
    test_sketcher_acceptance_prepares_gui_before_manual_initgui()
    test_visual_example_prepares_gui_before_manual_initgui()
    test_committed_macro_bootstrap_is_gui_ready_and_path_safe()
    test_canonical_gui_jobs_launch_macro_bootstrap_from_neutral_cwd()
    test_canonical_readme_turntable_launches_from_neutral_cwd()
