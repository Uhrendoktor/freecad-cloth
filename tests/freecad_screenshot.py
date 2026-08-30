"""Deterministic GUI documentation scenario; run under Xvfb with FreeCAD."""
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

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

def toolbars():
    window = Gui.getMainWindow()
    if window is None:
        return []
    return [bar.windowTitle() for bar in window.findChildren(QtWidgets.QToolBar) if bar.isVisible()]

def docks():
    window = Gui.getMainWindow()
    if window is None:
        return []
    return [dock.windowTitle() for dock in window.findChildren(QtWidgets.QDockWidget) if dock.isVisible()]

def activate_workbench(internal_name, toolbar_name, expected_commands):
    available = Gui.listWorkbenches()
    progress("workbenches=" + ",".join(sorted(available.keys())))
    if internal_name not in available:
        raise RuntimeError("workbench is not registered: %s" % internal_name)
    Gui.activateWorkbench(internal_name)
    Gui.updateGui()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar_name:
            bar.show()
    Gui.updateGui()
    active = Gui.activeWorkbench().name()
    visible = toolbars()
    missing = [name for name in expected_commands if name not in Gui.listCommands()]
    progress("workbench=%s active=%s toolbar=%s visible_toolbars=%s missing_commands=%s docks=%s" % (internal_name, active, toolbar_name, ",".join(visible), ",".join(missing), ",".join(docks())))
    if active != internal_name:
        raise RuntimeError("failed to activate %s (active=%s)" % (internal_name, active))
    if toolbar_name not in visible:
        raise RuntimeError("toolbar is not visible: %s" % toolbar_name)
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))

def show_task(panel, state_name):
    Gui.Control.showDialog(panel)
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    visible = bool(getattr(panel, "form", None) and panel.form.isVisible())
    progress("task-panel=%s visible=%s docks=%s" % (state_name, visible, ",".join(docks())))
    if not visible:
        raise RuntimeError("task panel did not become visible: %s" % state_name)

def save_window(filename, state_name):
    """Capture the complete FreeCAD main-window client area, not the 3D viewport."""
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    window.show()
    window.raise_()
    window.activateWindow()
    QtWidgets.QApplication.processEvents()
    # Keep the Xvfb capture geometry deterministic while retaining FreeCAD's
    # native menu bar, workbench toolbars, Combo View/task panels and viewport.
    window.resize(1280, 720)
    QtWidgets.QApplication.processEvents()
    image = window.grab()
    path = os.path.join(OUT, filename)
    if image.isNull():
        raise RuntimeError("FreeCAD main-window grab returned an empty image")
    if not image.save(path):
        raise RuntimeError("failed to save full-window screenshot: %s" % path)
    progress("screenshot=%s state=%s scope=main-window size=%sx%s toolbars=%s docks=%s" % (
        path, state_name, image.width(), image.height(), ",".join(toolbars()), ",".join(docks())))
    if image.width() < 1000 or image.height() < 600:
        raise RuntimeError("full-window screenshot is unexpectedly small: %sx%s" % (image.width(), image.height()))

progress("script-start")
try:
    init_gui = os.path.join(REPO_ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    from PatternCommands import create_pattern_piece_from_parameters
    from PatternModel import Seam
    from PatternObjects import add_seam
    from PatternGui import PatternDraftingTaskPanel
    from SewingCommands import create_sewing_operation
    from SewingGui import SewingTaskPanel
    from SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from SimulationQualityGui import SimulationQualityTaskPanel
    progress("gui-modules-import-ok")
except Exception:
    progress("import-error")
    progress(traceback.format_exc())
    raise

def run_scenario():
    doc = None
    quality_doc = None
    try:
        progress("scenario-start")
        window = Gui.getMainWindow()
        if window is not None:
            window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); Gui.updateGui()
            progress("main-window=%sx%s" % (window.width(), window.height()))
        doc = App.newDocument("ClothDocumentation")
        front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        back.Placement.Base.x = 170.0
        doc.recompute()
        activate_workbench("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
        show_task(PatternDraftingTaskPanel(front), "Pattern Design")
        Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll()
        save_window("cloth-pattern-design.png", "Pattern Design")
        Gui.Control.closeDialog()
        seam = add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="FrontBack", alignment="uniform", stitch_group="MainSeam"))
        doc.recompute()
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(seam)
        sewing = create_sewing_operation(); doc.recompute()
        progress("sewing-created status=%s stitches=%s" % (sewing.Status, sewing.StitchCount))
        activate_workbench("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(sewing)
        show_task(SewingTaskPanel(sewing), "Sewing")
        Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll()
        save_window("cloth-sewing.png", "Sewing")
        Gui.Control.closeDialog()
        progress("simulation-quality-start")
        quality_doc = App.newDocument("ClothSimulationDocumentation")
        scene = create_quality_simulation_scene(quality_doc)
        scene.ClothPieces = []
        scene.ParticleDistance = 8.0
        scene.Steps = 1
        quality_doc.recompute()
        progress("simulation-quality-created preset=%s particles=%s steps=%s" % (scene.QualityPreset, scene.ParticleCount, scene.Steps))
        Gui.activeDocument().activeView().viewAxonometric(); Gui.activeDocument().activeView().fitAll()
        activate_workbench("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
        show_task(SimulationQualityTaskPanel(scene), "Simulation Quality")
        save_window("cloth-simulation.png", "Simulation Quality")
        progress("scenario-complete")
    except Exception:
        progress("scenario-error"); progress(traceback.format_exc()); raise
    finally:
        try:
            Gui.Control.closeDialog()
        except Exception:
            pass
        if quality_doc is not None and quality_doc.Name in App.listDocuments():
            App.closeDocument(quality_doc.Name); progress("quality-document-closed")
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name); progress("document-closed")

run_scenario()
progress("script-end")
window = Gui.getMainWindow()
if window is not None:
    window.close()
    progress("main-window-closed")
QtWidgets.QApplication.quit()
progress("application-quit-requested")
