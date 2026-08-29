"""Deterministic FreeCAD GUI workbench-chrome regression scenario.

Run under Xvfb with the real FreeCAD GUI.  Screenshots intentionally capture
both the application chrome and document viewport so toolbar/task-panel
regressions are visible in CI artifacts.
"""
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

REPO_ROOT = "/workspace"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
DEBUG = os.path.join(OUT, "gui-progress.log")


def progress(message):
    with open(DEBUG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()


def toolbar_snapshot(workbench):
    """Show toolbars belonging to the active workbench and report actions."""
    window = Gui.getMainWindow()
    matches = []
    for toolbar in window.findChildren(QtWidgets.QToolBar):
        title = toolbar.windowTitle() or toolbar.objectName()
        actions = [a.text().strip() for a in toolbar.actions() if a.text().strip()]
        if workbench.lower() in title.lower() or any(
            workbench.lower().split()[1] in action.lower() for action in actions
        ):
            toolbar.setVisible(True)
            matches.append("%s=[%s]" % (title, ", ".join(actions)))
    if not matches:
        raise RuntimeError("no visible custom toolbar found for %s" % workbench)
    progress("toolbar:%s:%s" % (workbench, " | ".join(matches)))


def dock_snapshot():
    """Keep FreeCAD's standard Combo View/task-panel chrome visible."""
    window = Gui.getMainWindow()
    docks = []
    for dock in window.findChildren(QtWidgets.QDockWidget):
        title = dock.windowTitle() or dock.objectName()
        if title:
            docks.append("%s=%s" % (title, "visible" if dock.isVisible() else "hidden"))
        if "combo" in title.lower() or "task" in title.lower():
            dock.setVisible(True)
    progress("docks:" + " | ".join(docks))


def capture(name, workbench):
    """Capture the complete application window, not just the 3D viewport."""
    Gui.updateGui()
    toolbar_snapshot(workbench)
    dock_snapshot()
    Gui.updateGui()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    image = window.grab()
    path = os.path.join(OUT, name)
    if not image.save(path):
        raise RuntimeError("failed to save %s" % path)
    progress("screenshot:%s:size=%sx%s" % (name, image.width(), image.height()))


def activate(name):
    Gui.activateWorkbench(name)
    Gui.updateGui()
    actual = str(Gui.activeWorkbench())
    progress("workbench:%s->%s" % (name, actual))
    if actual != name:
        raise RuntimeError("expected workbench %r, got %r" % (name, actual))


def run_scenario():
    doc = None
    try:
        progress("scenario-start")
        main_window = Gui.getMainWindow()
        if main_window is None:
            raise RuntimeError("FreeCAD main window is unavailable")
        main_window.showMaximized()
        main_window.raise_()
        main_window.activateWindow()
        Gui.updateGui()

        from PatternCommands import create_pattern_piece_from_parameters
        from PatternGui import PatternPieceTaskPanel
        from SewingCommands import create_seam_from_selection, create_sewing_operation
        from SewingGui import SewingTaskPanel
        from SimulationObjects import create_simulation_scene, step_scene

        doc = App.newDocument("ClothGuiRegression")
        front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()

        activate("Cloth Pattern")
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(front)
        pattern_panel = PatternPieceTaskPanel(front)
        Gui.Control.showDialog(pattern_panel)
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        capture("cloth-pattern.png", "Cloth Pattern")
        Gui.Control.closeDialog()

        # Build a real persistent seam/operation so the Sewing screenshot shows
        # the same document-facing workflow users get in the workbench.
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(front, "Edge1")
        Gui.Selection.addSelection(back, "Edge1")
        seam = create_seam_from_selection()
        operation = create_sewing_operation()
        doc.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(operation)

        activate("Cloth Sewing")
        sewing_panel = SewingTaskPanel(operation)
        Gui.Control.showDialog(sewing_panel)
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        capture("cloth-sewing.png", "Cloth Sewing")
        Gui.Control.closeDialog()
        progress("seam:%s operation:%s" % (seam.Name, operation.Name))

        activate("Cloth Simulation")
        scene = create_simulation_scene(doc)
        step_scene(scene, 1)
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        capture("cloth-simulation.png", "Cloth Simulation")

        for filename in ("cloth-pattern.png", "cloth-sewing.png", "cloth-simulation.png"):
            path = os.path.join(OUT, filename)
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                raise RuntimeError("missing screenshot artifact: %s" % filename)
        progress("scenario-complete")
    except Exception:
        progress("scenario-error")
        progress(traceback.format_exc())
        raise
    finally:
        try:
            Gui.Control.closeDialog()
        except Exception:
            pass
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
            progress("document-closed")


run_scenario()
progress("script-end")
main_window = Gui.getMainWindow()
if main_window is not None:
    main_window.close()
    progress("main-window-closed")
