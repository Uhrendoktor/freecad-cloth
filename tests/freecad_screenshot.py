"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtCore
except ImportError:
    from PySide2 import QtCore

REPO_ROOT = "/workspace"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEBUG = os.path.join(os.environ.get("CLOTH_SCREENSHOT_DIR", "/workspace/docs/images/generated"), "gui-progress.log")
os.makedirs(os.path.dirname(DEBUG), exist_ok=True)


def progress(message):
    with open(DEBUG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()


progress("script-start")
try:
    from PatternCommands import create_pattern_piece_from_parameters
    progress("pattern-import-ok")
    from SimulationObjects import create_simulation_scene, step_scene
    progress("simulation-import-ok")
except Exception:
    progress("import-error")
    progress(traceback.format_exc())
    raise

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)


def run_scenario():
    doc = None
    try:
        progress("scenario-start")
        main_window = Gui.getMainWindow()
        progress("main-window=" + str(main_window is not None))
        if main_window is not None:
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            Gui.updateGui()
            progress("main-window-shown")

        doc = App.newDocument("ClothDocumentation")
        progress("document-created")
        create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()
        progress("pattern-created")
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        progress("pattern-view-ready")
        Gui.activeDocument().activeView().saveImage(
            os.path.join(OUT, "cloth-pattern.png"), 1280, 720, "Current"
        )
        progress("pattern-saved")

        # create_drape_scene intentionally advances the full 30-step reference
        # scenario.  The GUI smoke test only needs a rendered simulation scene,
        # so construct it and advance one solver step to keep the CI smoke test
        # bounded while still exercising the real simulation/rendering path.
        scene = create_simulation_scene(doc)
        progress("simulation-created")
        step_scene(scene, 1)
        progress("simulation-stepped")
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        Gui.updateGui()
        progress("simulation-view-ready")
        Gui.activeDocument().activeView().saveImage(
            os.path.join(OUT, "cloth-simulation.png"), 1280, 720, "Current"
        )
        progress("simulation-saved")

        if not os.path.exists(os.path.join(OUT, "cloth-pattern.png")):
            raise RuntimeError("cloth-pattern.png was not generated")
        if not os.path.exists(os.path.join(OUT, "cloth-simulation.png")):
            raise RuntimeError("cloth-simulation.png was not generated")
        progress("scenario-complete")
    except Exception:
        progress("scenario-error")
        progress(traceback.format_exc())
        raise
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
            progress("document-closed")


# FreeCAD executes an FCMacro from its existing GUI application.  Run the
# scenario directly, then close the existing main window so the CLI process
# terminates after the screenshots have been written.
run_scenario()
progress("script-end")
main_window = Gui.getMainWindow()
if main_window is not None:
    main_window.close()
    progress("main-window-closed")
