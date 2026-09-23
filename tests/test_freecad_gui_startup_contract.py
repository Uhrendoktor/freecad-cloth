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


def test_committed_bootstrap_defers_gui_import_to_acceptance_script():
    source = (ROOT / "tests" / "freecad_ci_bootstrap.py").read_text(encoding="utf-8")
    assert "import FreeCADGui as Gui" not in source
    assert "window.show()" not in source
    assert "processEvents()" not in source
    assert 'sys.path.insert(0, ROOT)' in source
    assert source.index("sys.path.insert(0, ROOT)") < source.index('runpy.run_path(script, run_name="__main__")')


def test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    sketcher = workflow.split("gui-sketcher-acceptance:", 1)[1].split("gui-pattern-export:", 1)[0]
    visual = workflow.split("gui-visual-examples:", 1)[1].split("publish-readme-turntables:", 1)[0]
    assert '-w /tmp "$FREECAD_IMAGE"' in sketcher
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.py" in sketcher
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_sketcher_acceptance.py" in sketcher
    assert '-w /tmp "$FREECAD_IMAGE"' in visual
    assert "/opt/freecad/AppRun /workspace/tests/freecad_ci_bootstrap.py" in visual
    assert "CLOTH_CI_SCRIPT=/workspace/tests/freecad_visual_examples.py" in visual


if __name__ == "__main__":
    test_sketcher_acceptance_prepares_gui_before_manual_initgui()
    test_visual_example_prepares_gui_before_manual_initgui()
    test_committed_bootstrap_prepares_gui_before_acceptance_script()
    test_canonical_gui_jobs_launch_from_neutral_cwd_with_bootstrap()
