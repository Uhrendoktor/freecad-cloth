"""Static regression contract for the native Sketcher FreeCAD startup boundary."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sketcher_acceptance_initializes_gui_before_manual_initgui_bootstrap():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    run = source.split("def run_acceptance():", 1)[1]
    assert run.index("window = Gui.getMainWindow()") < run.index("_bootstrap_workbenches()")
    assert run.index("window.show()") < run.index("_bootstrap_workbenches()")
    assert run.index("_events()") < run.index("_bootstrap_workbenches()")
    assert 'raise RuntimeError("FreeCAD GUI main window is not available")' in run
    assert '_stage("gui-ready")' in run
