"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
import os
import sys

import FreeCAD as App
import FreeCADGui as Gui

# The macro is executed by the GUI-capable FreeCAD process from /tmp. Expose
# the checked-out workbench explicitly rather than depending on the macro's
# location for Python imports.
REPO_ROOT = "/workspace"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PatternCommands import create_pattern_piece_from_parameters
from SimulationObjects import create_drape_scene

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)


def run_scenario():
    doc = None
    try:
        # `freecad /tmp/macro.FCMacro` already creates the GUI application.
        # FreeCAD 1.0.0 has no FreeCADGui.showMainWindow() API, and a macro
        # must not start a second Qt event loop.
        doc = App.newDocument("ClothDocumentation")
        Gui.activateWorkbench("Cloth Pattern")
        create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        Gui.activeDocument().activeView().saveImage(
            os.path.join(OUT, "cloth-pattern.png"), 1280, 720, "Current", 1
        )

        Gui.activateWorkbench("Cloth Simulation")
        create_drape_scene(doc)
        doc.recompute()
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        Gui.activeDocument().activeView().saveImage(
            os.path.join(OUT, "cloth-simulation.png"), 1280, 720, "Current", 1
        )

        assert os.path.exists(os.path.join(OUT, "cloth-pattern.png"))
        assert os.path.exists(os.path.join(OUT, "cloth-simulation.png"))
        print("generated", os.path.join(OUT, "cloth-pattern.png"), flush=True)
        print("generated", os.path.join(OUT, "cloth-simulation.png"), flush=True)
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        # The GUI application normally remains alive after a macro returns.
        # Close its existing main window so the CI launcher can wait for a
        # normal process exit instead of polling for files indefinitely.
        main_window = Gui.getMainWindow()
        if main_window is not None:
            main_window.close()


run_scenario()
