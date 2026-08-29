"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
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


def _toolbar_names():
    main_window = Gui.getMainWindow()
    if main_window is None:
        return []
    return [bar.windowTitle() for bar in main_window.findChildren(QtWidgets.QToolBar)
            if bar.isVisible()]


def _dock_state():
    main_window = Gui.getMainWindow()
    if main_window is None:
        return []
    return [dock.windowTitle() for dock in main_window.findChildren(QtWidgets.QDockWidget)
            if dock.isVisible()]


def activate_workbench(name, expected_commands):
    """Activate a real workbench and verify its toolbar/actions are visible."""
    Gui.activateWorkbench(name)
    Gui.updateGui()
    main_window = Gui.getMainWindow()
    if main_window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    # FreeCAD may restore a toolbar as hidden from a previous session. Make the
    # workbench toolbar explicit so CI captures the actual workbench UI.
    for toolbar in main_window.findChildren(QtWidgets.QToolBar):
        if toolbar.windowTitle() == name:
            toolbar.show()
            toolbar.raise_()
    Gui.updateGui()
    toolbars = _toolbar_names()
    missing = [command for command in expected_commands if not Gui.listCommands().count(command)]
    progress("workbench=%s active=%s toolbars=%s missing_commands=%s docks=%s" % (
        name, Gui.activeWorkbench().name(), ",".join(toolbars), ",".join(missing), ",".join(_dock_state())))
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate workbench %s" % name)
    if name not in toolbars:
        raise RuntimeError("visible toolbar missing for workbench %s" % name)
    if missing:
        raise RuntimeError("expected GUI commands are not registered: %s" % ", ".join(missing))


def show_task(panel, state_name):
    Gui.Control.showDialog(panel)
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    progress("task-panel=%s visible=%s docks=%s" % (
        state_name, bool(getattr(panel, "form", None) and panel.form.isVisible()), ",".join(_dock_state())))
    if not getattr(panel, "form", None) or not panel.form.isVisible():
        raise RuntimeError("task panel did not become visible for %s" % state_name)


def save_view(filename, view="Current"):
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    path = os.path.join(OUT, filename)
    Gui.activeDocument().activeView().saveImage(path, 1280, 720, view)
    progress("screenshot=%s" % path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("screenshot was not generated: %s" % path)


progress("script-start")
try:
    from PatternCommands import create_pattern_piece_from_parameters
    from PatternModel import Seam
    from PatternObjects import add_seam
    from PatternGui import PatternDraftingTaskPanel
    from SewingCommands import create_sewing_operation
    from SewingGui import SewingTaskPanel
    from SimulationObjects import create_simulation_scene, step_scene
    from SimulationGui import SimulationTaskPanel
    progress("gui-modules-import-ok")
except Exception:
    progress("import-error")
    progress(traceback.format_exc())
    raise


def run_scenario():
    doc = None
    panels = []
    try:
        progress("scenario-start")
        main_window = Gui.getMainWindow()
        progress("main-window=%s" % (main_window is not None))
        if main_window is not None:
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            Gui.updateGui()
            progress("main-window-shown")

        doc = App.newDocument("ClothDocumentation")
        front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()
        progress("pattern-created pieces=2")

        # Pattern Design: the drafting task panel is shown beside the real 3D
        # pattern, making the screenshot useful for both UI and visual QA.
        activate_workbench("Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
        panel = PatternDraftingTaskPanel(front)
        panels.append(panel)
        show_task(panel, "Pattern Design")
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        save_view("cloth-pattern-design.png")
        Gui.Control.closeDialog()
        progress("pattern-task-closed")

        # Sewing: create the persisted semantic seam, then open the actual
        # sewing editor. The operation and stitch correspondence are visible in
        # the viewport while the task panel exposes validation/stitch controls.
        seam = add_seam(doc, Seam(
            piece_a=str(front.PieceId), edge_a=1,
            piece_b=str(back.PieceId), edge_b=3,
            id="FrontBack", alignment="uniform", stitch_group="MainSeam"))
        doc.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(seam)
        sewing = create_sewing_operation()
        doc.recompute()
        progress("sewing-created status=%s stitches=%s" % (sewing.Status, sewing.StitchCount))
        activate_workbench("Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sewing)
        panel = SewingTaskPanel(sewing)
        panels.append(panel)
        show_task(panel, "Sewing")
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()
        save_view("cloth-sewing.png")
        Gui.Control.closeDialog()
        progress("sewing-task-closed")

        # Simulation: use the real scene and controls, then leave the task
        # panel visible while the rendered scene is captured.
        scene = create_simulation_scene(doc)
        step_scene(scene, 1)
        doc.recompute()
        progress("simulation-created particles=%s steps=%s" % (scene.ParticleCount, scene.Steps))
        activate_workbench("Cloth Simulation", ["ClothSimulation_Edit"])
        panel = SimulationTaskPanel(scene)
        panels.append(panel)
        show_task(panel, "Simulation")
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        save_view("cloth-simulation.png")

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


# FreeCAD executes an FCMacro from its existing GUI application. Run the
# scenario directly, then close the existing main window so the CLI process
# terminates after the screenshots have been written.
run_scenario()
progress("script-end")
main_window = Gui.getMainWindow()
if main_window is not None:
    main_window.close()
    progress("main-window-closed")
