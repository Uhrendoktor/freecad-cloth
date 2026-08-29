"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
import os
import sys

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

# The GUI launcher executes this file through a temporary .FCMacro.  In that
# mode Python's import path is based on the macro location (/tmp), not the
# checked-out workbench directory.  The workflow deliberately runs from the
# repository root, so make that location explicit before importing workbench
# modules.  This also keeps the scenario runnable from a normal FreeCAD macro
# invocation without relying on the caller to set PYTHONPATH.
REPO_ROOT = os.getcwd()
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PatternCommands import create_pattern_piece_from_parameters
from SimulationObjects import create_drape_scene

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)


def run_scenario():
    doc = None
    try:
        Gui.showMainWindow()
        doc = App.newDocument("ClothDocumentation")
        Gui.activateWorkbench("Cloth Pattern")
        create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "cloth-pattern.png"), 1280, 720, "Current", 1)

        Gui.activateWorkbench("Cloth Simulation")
        create_drape_scene(doc)
        doc.recompute()
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        Gui.activeDocument().activeView().saveImage(os.path.join(OUT, "cloth-simulation.png"), 1280, 720, "Current", 1)

        assert os.path.exists(os.path.join(OUT, "cloth-pattern.png"))
        assert os.path.exists(os.path.join(OUT, "cloth-simulation.png"))
        print("generated", os.path.join(OUT, "cloth-pattern.png"), flush=True)
        print("generated", os.path.join(OUT, "cloth-simulation.png"), flush=True)
    finally:
        if doc is not None:
            doc.close()
        try:
            Gui.getMainWindow().close()
        except Exception:
            pass
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


Gui.showMainWindow()
QtCore.QTimer.singleShot(0, run_scenario)
app = QtWidgets.QApplication.instance()
if app is not None:
    app.exec()
else:
    raise RuntimeError("FreeCAD did not create a Qt application")
