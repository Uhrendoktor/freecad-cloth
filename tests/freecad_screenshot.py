"""Deterministic FreeCAD GUI screenshots; run under Xvfb with software rendering."""
import os
import sys
import tempfile
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")


def log(message):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(message + "\n")
        f.flush()


def events():
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def ensure_task_view_visible():
    """Make FreeCAD 1.1's standalone Tasks dock visible before checking a panel."""
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable while opening task panel")
    docks = window.findChildren(QtWidgets.QDockWidget)
    summary = ["%s:%s:%s" % (dock.objectName(), dock.windowTitle(), dock.isVisible()) for dock in docks]
    log("dock-widgets=" + " | ".join(summary))
    task_dock = window.findChild(QtWidgets.QDockWidget, "Tasks")
    if task_dock is not None:
        action = task_dock.toggleViewAction()
        if not action.isChecked():
            action.trigger()
        task_dock.show(); task_dock.raise_(); events()
        if not task_dock.isVisible():
            window.removeDockWidget(task_dock)
            window.addDockWidget(QtCore.Qt.RightDockWidgetArea, task_dock)
            task_dock.show(); task_dock.raise_(); events()
        log("task-dock=Tasks checked=%s visible=%s" % (action.isChecked(), task_dock.isVisible()))
        if task_dock.isVisible():
            return task_dock
    combo = window.findChild(QtWidgets.QDockWidget, "Model")
    if combo is not None:
        combo.show()
        tabs = combo.findChild(QtWidgets.QTabWidget)
        if tabs is not None:
            for index in range(tabs.count()):
                if tabs.tabText(index).strip().lower() == "tasks":
                    tabs.setCurrentIndex(index); combo.raise_(); events()
                    log("task-tab=Tasks visible=%s" % combo.isVisible())
                    return combo
    raise RuntimeError("FreeCAD Tasks dock/tab is unavailable or could not be made visible")


def validate_task(panel, name, required):
    events(); ensure_task_view_visible(); events()
    if not panel.form.isVisible():
        log("task-panel-hidden name=%s active=%s parent=%s; retrying form.show()" % (
            name, bool(Gui.Control.activeDialog()), type(panel.form.parentWidget()).__name__ if panel.form.parentWidget() else "None"))
        panel.form.show(); panel.form.setVisible(True); panel.form.raise_(); panel.form.activateWindow(); events()
    visible = panel.form.isVisible() or panel.form.isVisibleTo(Gui.getMainWindow())
    log("task-panel-state name=%s isVisible=%s isVisibleToMain=%s active=%s" % (
        name, panel.form.isVisible(), panel.form.isVisibleTo(Gui.getMainWindow()), bool(Gui.Control.activeDialog())))
    if not visible:
        raise RuntimeError("task panel did not become visible: %s" % name)
    text = " | ".join(str(w.text() if callable(getattr(w, "text", None)) else getattr(w, "text", ""))
                      for w in [panel.form] + panel.form.findChildren(QtWidgets.QWidget)
                      if getattr(w, "text", "") or callable(getattr(w, "text", None)))
    missing = [item for item in required if item not in text]
    log("task-panel=%s visible=true missing=%s" % (name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (name, ",".join(missing)))


def show_task(panel, name, required=(), reuse_active=False):
    if not reuse_active:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog(); events()
        Gui.Control.showDialog(panel)
    validate_task(panel, name, required)


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise RuntimeError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name); events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is not visible after workbench activation")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    events()
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))
    log("workbench=%s toolbar=%s" % (name, toolbar))


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); events()
    image = window.grab(); path = os.path.join(OUT, name)
    if image.isNull() or image.width() != 1280 or image.height() != 720:
        raise RuntimeError("invalid GUI capture for %s: %sx%s" % (state, image.width(), image.height()))
    if not image.save(path) or os.path.getsize(path) < 20000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    log("screenshot=%s state=%s size=1280x720 bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write("%s\t%s\t%s\n" % (name, state, proof))


def close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog(); events()


def pattern_and_sewing():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel
    import Part
    doc = App.newDocument("ClothVisualRegression")
    front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
    back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
    front.Placement.Base.x = -160; back.Placement.Base.x = 20
    marker = doc.addObject("Part::Feature", "GrainlineMarker")
    marker.Shape = Part.makeLine(App.Vector(-90, 10, 1), App.Vector(-90, 80, 1)); doc.recompute()
    if front.Shape.isNull() or back.Shape.isNull(): raise RuntimeError("pattern fixture produced empty geometry")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
    panel = PatternPieceTaskPanel(front)
    show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-pattern-design.png", "Pattern Workbench", "two 140x90 mm pieces with native 10 mm seam allowance and task-panel dimensions"); close_task()
    seam = add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="FrontBack", alignment="uniform", stitch_group="MainSeam"))
    sewing = create_sewing_operation(); doc.recompute()
    if str(seam.Status) != "Valid" or seam.Shape.isNull() or str(sewing.Status) != "Valid" or sewing.Shape.isNull(): raise RuntimeError("sewing fixture is invalid")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
    panel = SewingTaskPanel(sewing)
    show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-sewing.png", "Sewing Workbench", "real semantic seam and sewing operation with native diagnostics"); close_task(); App.closeDocument(doc.Name)


def drapetarget_public_lifecycle():
    """Exercise the public DrapeTarget and Simulation command/task-panel lifecycle."""
    import Part
    from freecad_cloth.simulation.DrapeTarget import target_status
    from freecad_cloth.simulation.SimulationCommands import simulation_status
    doc = App.newDocument("DrapeTargetPublicAcceptance")
    body = doc.addObject("Part::Feature", "TargetBody")
    body.Label = "Acceptance CAD Target"
    body.Shape = Part.makeBox(80, 80, 120, App.Vector(-40, -40, -60))
    doc.recompute()

    activate("ClothSimulationWorkbench", "Cloth Simulation", [
        "ClothSimulation_Create", "ClothSimulation_Edit", "ClothSimulation_Step", "ClothSimulation_Run", "ClothSimulation_Reset",
        "ClothDrape_CreateTarget", "ClothDrape_CreateMannequinTarget", "ClothDrape_EditTarget", "ClothDrape_RefreshTarget",
    ])
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(body); events()
    Gui.runCommand("ClothSimulation_Create", 0); events()
    scene = next(o for o in doc.Objects if getattr(o, "Type", "") == "ClothSimulation")
    Gui.runCommand("ClothDrape_CreateTarget", 0); events()
    target = doc.getObject("DrapeTarget")
    if target is None or target.SourceObject != body or str(target.TargetType) != "FreeCAD Geometry":
        raise RuntimeError("public FreeCAD geometry target command did not attach the selected source")
    if target_status(target)["state"] != "ready":
        raise RuntimeError("created FreeCAD target is not ready: %s" % target_status(target))

    from freecad_cloth.simulation.DrapeGui import DrapeTargetTaskPanel
    panel = DrapeTargetTaskPanel(target)
    show_task(panel, "Drape Target", ("Drape Target", "Provider", "Source", "Tessellation", "Collision thickness", "Apply & Refresh"))
    if not panel.source.currentText() or not panel.target_type.currentText():
        raise RuntimeError("Drape Target task panel did not expose provider/source controls")
    close_task()

    with tempfile.TemporaryDirectory() as directory:
        path = str(os.path.join(directory, "drape-target.FCStd"))
        doc.recompute(); doc.saveAs(path); App.closeDocument(doc.Name)
        doc = App.openDocument(path); scene = doc.getObject(scene.Name) if doc.getObject(scene.Name) else next(o for o in doc.Objects if getattr(o, "Type", "") == "ClothSimulation")
        target = doc.getObject("DrapeTarget"); body = doc.getObject("TargetBody")
        if target is None or body is None or target.SourceObject != body:
            raise RuntimeError("DrapeTarget source did not survive save/reload")
        body.Placement.Base.x += 25.0
        doc.recompute(); events()
        stale = target_status(target)
        if stale["state"] != "stale" or not stale["stale"]:
            raise RuntimeError("moving the saved target did not produce stale status: %s" % stale)
        status = simulation_status()
        if not status["target_stale"] or status["target_state"] != "stale":
            raise RuntimeError("simulation status did not expose stale target: %s" % status)
        panel = __import__("freecad_cloth.simulation.SimulationQualityGui", fromlist=["SimulationQualityTaskPanel"]).SimulationQualityTaskPanel(scene)
        show_task(panel, "Simulation stale target", ("Simulation quality", "Step", "Run 30", "Reset", "Simulation blocked"))
        if panel.step_button.isEnabled() or panel.run_button.isEnabled() or not panel.reset_button.isEnabled():
            raise RuntimeError("stale target did not disable Step/Run while retaining Reset")
        close_task()

        Gui.runCommand("ClothDrape_RefreshTarget", 0); events()
        target = doc.getObject("DrapeTarget")
        refreshed = target_status(target)
        if refreshed["state"] != "ready":
            raise RuntimeError("public DrapeTarget refresh did not restore ready state: %s" % refreshed)
        panel = __import__("freecad_cloth.simulation.SimulationQualityGui", fromlist=["SimulationQualityTaskPanel"]).SimulationQualityTaskPanel(scene)
        show_task(panel, "Simulation refreshed target", ("Simulation quality", "Step", "Run 30", "Reset"))
        if not panel.step_button.isEnabled() or not panel.run_button.isEnabled():
            raise RuntimeError("refreshed target did not re-enable Step/Run")
        panel.step(1); doc.recompute(); events()
        if int(scene.Steps) < 1:
            raise RuntimeError("simulation did not advance after target refresh")
        close_task()

    Gui.runCommand("ClothDrape_CreateMannequinTarget", 0); events()
    target = doc.getObject("DrapeTarget")
    if target is None or str(target.TargetType) != "Mannequin" or getattr(target, "SourceObject", None) is None:
        raise RuntimeError("public mannequin DrapeTarget command did not attach a mannequin")
    if target_status(target)["state"] != "ready":
        raise RuntimeError("mannequin target is not ready: %s" % target_status(target))
    status = simulation_status()
    if status["target_state"] != "ready" or status["target_stale"]:
        raise RuntimeError("simulation did not accept refreshed mannequin target: %s" % status)
    Gui.runCommand("ClothSimulation_Reset", 0); events()
    App.closeDocument(doc.Name)
    log("drapetarget-public-lifecycle=passed")


def simulation():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target
    doc = App.newDocument("ClothSimulationVisualRegression")
    front = create_pattern_piece_from_parameters("SimFront", 140.0, 90.0, 10.0, 0.0)
    back = create_pattern_piece_from_parameters("SimBack", 140.0, 90.0, 10.0, 0.0)
    front.Placement.Base.x = -150; back.Placement.Base.x = 10
    add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="SimFrontBack", alignment="uniform", stitch_group="MainSeam"))
    scene = create_quality_simulation_scene(doc); scene.ClothPieces = [front, back]; refresh_drape_target(scene.DrapeTarget)
    scene.QualityPreset = "Fast"; scene.ParticleDistance = 10.0; doc.recompute()
    if scene.DrapeTarget is None or scene.AvatarProxy is None or not scene.DrapePanels: raise RuntimeError("simulation fixture did not create avatar and garment panels")
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    panel = SimulationQualityTaskPanel(scene)
    show_task(panel, "Simulation Workbench arranged", ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset", "State:"))
    Gui.activeDocument().activeView().viewAxonometric(); Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-simulation-arranged.png", "Simulation Workbench arranged", "deterministic avatar and arranged garment panels with ready task state")
    for batch in (6, 6, 6, 6):
        panel.step(batch); doc.recompute(); events()
    if int(scene.Steps) != 24 or float(scene.SimulatedTime) <= 0 or not bool(scene.FiniteState): raise RuntimeError("simulation did not reach a finite 24-step state")
    show_task(panel, "Simulation Workbench draped", ("State:", "24", "particles", "Fast"), reuse_active=True)
    Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-simulation-draped.png", "Simulation Workbench draped", "same scene after 24 real task-panel simulation steps"); close_task(); App.closeDocument(doc.Name)
    drapetarget_public_lifecycle()


exit_code = 0
log("script-start")
try:
    if Gui.getMainWindow() is None: raise RuntimeError("FreeCAD GUI main window did not launch")
    Gui.getMainWindow().show(); events()
    if not Gui.getMainWindow().isVisible(): raise RuntimeError("FreeCAD GUI main window failed to become visible")
    log("gui-launch-ok window=%sx%s" % (Gui.getMainWindow().width(), Gui.getMainWindow().height()))
    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events()
    pattern_and_sewing(); simulation(); log("scenario-pass")
except Exception:
    exit_code = 1; log("scenario-fail"); log(traceback.format_exc())
finally:
    try:
        close_task()
        for document in list(App.listDocuments().values()):
            try: App.closeDocument(document.Name)
            except Exception: pass
        events(); log("script-end exit-code=%d" % exit_code)
        window = Gui.getMainWindow()
        if window is not None: window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None: app.quit()
    except Exception:
        log("shutdown-error"); log(traceback.format_exc()); exit_code = 1
sys.stdout.flush(); sys.stderr.flush(); sys.exit(exit_code)
