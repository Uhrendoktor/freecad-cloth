"""Static contract for FreeCAD GUI startup ordering in acceptance workflows."""
import ast
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


def test_committed_bootstrap_defers_acceptance_until_after_delayed_startup():
    source = (ROOT / "tests" / "freecad_ci_bootstrap.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="tests/freecad_ci_bootstrap.py")
    callback = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_run_acceptance"
    )

    def is_runpy_run_path(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "runpy"
            and node.func.attr == "run_path"
        )

    def is_qt_single_shot(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "singleShot"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "QTimer"
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "QtCore"
        )

    runpy_calls = [node for node in ast.walk(tree) if is_runpy_run_path(node)]
    assert len(runpy_calls) == 1
    assert runpy_calls[0] in ast.walk(callback)

    timer_calls = [node for node in ast.walk(tree) if is_qt_single_shot(node)]
    assert len(timer_calls) == 1
    assert timer_calls[0] not in ast.walk(callback)

    assert "import FreeCADGui as Gui" in source
    assert "window.show()" in source
    assert "sys.path[:] = [p for p in sys.path if p != ROOT]" in source
    assert "QtCore.QTimer.singleShot(0, _run_acceptance)" in source
    assert "Gui.addWorkbench(" not in source
    assert "processEvents()" not in source
    assert "traceback.print_exc()" in source
    assert "app.exit(0)" in source
    assert "app.exit(1)" in source
    assert source.index("sys.path[:] = [p for p in sys.path if p != ROOT]") < source.index("import FreeCADGui as Gui")
    assert source.index("window.show()") < source.index("def _run_acceptance():")
    assert source.index("def _run_acceptance():") < source.index("QtCore.QTimer.singleShot(0, _run_acceptance)")
    assert source.index("QtCore.QTimer.singleShot(0, _run_acceptance)") > source.index('runpy.run_path(script, run_name="__main__")')


def test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in sketcher
    assert "cp /workspace/tests/freecad_ci_bootstrap.py /tmp/freecad_ci_bootstrap.py" in sketcher
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.py" in sketcher
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.py" not in sketcher
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert "FREECAD_USER_HOME=/tmp/freecad-user" in sketcher
    assert "FREECAD_USER_DATA=/tmp/freecad-user-data" in sketcher
    assert "FREECAD_USER_TEMP=/tmp/freecad-user-temp" in sketcher
    assert '-w /tmp "$FREECAD_IMAGE"' in visual
    assert "cp /workspace/tests/freecad_ci_bootstrap.py /tmp/freecad_ci_bootstrap.py" in visual
    assert "/opt/freecad/AppRun /tmp/freecad_ci_bootstrap.py" in visual
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.py" not in visual
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
    test_committed_bootstrap_defers_acceptance_until_after_delayed_startup()
    test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap()
    test_canonical_readme_turntable_launches_from_neutral_cwd()
