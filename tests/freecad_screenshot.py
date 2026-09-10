"""Deterministic FreeCAD GUI screenshots; run under Xvfb with software rendering."""
import importlib.util
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

ROOT = "/workspace"
if ROOT not in sys.path: sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")


def log(message):
    with open(LOG, "a", encoding="utf-8") as f: f.write(message + "\n")


def events():
    Gui.updateGui(); QtWidgets.QApplication.processEvents()


def ensure_task_view_visible():
    window = Gui.getMainWindow()
    if window is None: raise RuntimeError("FreeCAD main window is unavailable while opening task panel")
    task_dock = window.findChild(QtWidgets.QDockWidget, "Tasks")
    if task_dock is not None:
        action = task_dock.toggleViewAction()
        if not action.isChecked(): action.trigger()
        task_dock.show(); task_dock.raise_(); events()
        if task_dock.isVisible(): return task_dock
    combo = window.findChild(QtWidgets.QDockWidget, "Model")
    if combo is not None:
        combo.show(); tabs = combo.findChild(QtWidgets.QTabWidget)
        if tabs is not None:
            for index in range(tabs.count()):
                if tabs.tabText(index).strip().lower() == "tasks":
                    tabs.setCurrentIndex(index); combo.raise_(); events(); return combo
    raise RuntimeError("FreeCAD Tasks dock/tab is unavailable or could not be made visible")


def validate_task(panel, name, required):
    events(); ensure_task_view_visible(); events()
    if not panel.form.isVisible():
        panel.form.show(); panel.form.setVisible(True); panel.form.raise_(); panel.form.activateWindow(); events()
    if not (panel.form.isVisible() or panel.form.isVisibleTo(Gui.getMainWindow())): raise RuntimeError("task panel did not become visible: %s" % name)
    text = " | ".join(str(w.text() if callable(getattr(w, "text", None)) else getattr(w, "text", "")) for w in [panel.form] + panel.form.findChildren(QtWidgets.QWidget) if getattr(w, "text", "") or callable(getattr(w, "text", None)))
    missing = [item for item in required if item not in text]
    log("task-panel=%s visible=true missing=%s" % (name, ",".join(missing)))
    if missing: raise RuntimeError("task panel %s is missing visible text: %s" % (name, ",".join(missing)))


def show_task(panel, name, required=(), reuse_active=False):
    if not reuse_active:
        if Gui.Control.activeDialog(): Gui.Control.closeDialog(); events()
        Gui.Control.showDialog(panel)
    validate_task(panel, name, required)
    return ensure_task_view_visible()


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches(): raise RuntimeError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name); events(); window = Gui.getMainWindow()
    if window is None or not window.isVisible(): raise RuntimeError("FreeCAD main window is not visible after workbench activation")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar: bar.show()
    events()
    if Gui.activeWorkbench().name() != name: raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing: raise RuntimeError("commands are not registered: " + ",".join(missing))
    log("workbench=%s toolbar=%s" % (name, toolbar))


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible(): raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); events()
    image = window.grab(); path = os.path.join(OUT, name)
    if image.isNull() or image.width() != 1280 or image.height() != 720: raise RuntimeError("invalid GUI capture for %s: %sx%s" % (state, image.width(), image.height()))
    if not image.save(path) or os.path.getsize(path) < 20000: raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    log("screenshot=%s state=%s size=1280x720 bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as f: f.write("%s\t%s\t%s\n" % (name, state, proof))


def close_task():
    if Gui.Control.activeDialog(): Gui.Control.closeDialog(); events()


def pattern_and_sewing():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel
    import Part
    doc = App.newDocument("ClothVisualRegression")
    front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0); back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
    front.Placement.Base.x = -160; back.Placement.Base.x = 20
    marker = doc.addObject("Part::Feature", "GrainlineMarker"); marker.Shape = Part.makeLine(App.Vector(-90, 10, 1), App.Vector(-90, 80, 1)); doc.recompute()
    if front.Shape.isNull() or back.Shape.isNull(): raise RuntimeError("pattern fixture produced empty geometry")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
    panel = PatternPieceTaskPanel(front); show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-pattern-design.png", "Pattern Workbench", "two 140x90 mm pieces with native 10 mm seam allowance and task-panel dimensions")
    close_task(); seam = add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="FrontBack", alignment="uniform", stitch_group="MainSeam")); sewing = create_sewing_operation(); doc.recompute()
    if str(seam.Status) != "Valid" or seam.Shape.isNull() or str(sewing.Status) != "Valid" or sewing.Shape.isNull(): raise RuntimeError("sewing fixture is invalid")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "real semantic seam and sewing operation with native diagnostics")
    close_task(); App.closeDocument(doc.Name)


def _style_garment(panel, label):
    panel.Label = label
    try:
        view = panel.ViewObject; view.DisplayMode = "Flat Lines"; view.ShapeColor = (0.78, 0.34, 0.22); view.LineColor = (0.95, 0.12, 0.05); view.LineWidth = 2.0
    except (AttributeError, TypeError, ValueError): pass


def _hide_tasks_for_visual_capture(dock):
    if dock is not None: dock.hide(); events()


def _restore_tasks_after_visual_capture(dock):
    if dock is not None: dock.show(); dock.raise_(); events()


def _fit_visual_selection(view, *objects):
    """Frame only the mannequin and actual drape, excluding helper/collision geometry."""
    Gui.Selection.clearSelection()
    for obj in objects:
        if obj is not None: Gui.Selection.addSelection(obj)
    events()
    try:
        view.fitSelection()
    finally:
        Gui.Selection.clearSelection()
    events()


def simulation():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target

    doc = App.newDocument("ClothSimulationVisualRegression")
    garment = create_pattern_piece_from_parameters("VisualTunic", 440.0, 560.0, 10.0, 0.0)
    garment.Label = "Simple Tunic Panel"; garment.Placement.Base.x = -220.0; garment.Placement.Base.y = -120.0
    scene = create_quality_simulation_scene(doc); scene.DrapePanels = []
    unused_panel = doc.getObject("DrapePanelB")
    if unused_panel is not None: unused_panel.ViewObject.Visibility = False
    source_sketch = doc.getObject("VisualTunic")
    if source_sketch is not None: source_sketch.ViewObject.Visibility = False
    scene.ClothPieces = [garment]; scene.QualityPreset = "Fast"; scene.ParticleDistance = 20.0; scene.SolverIterations = 5; scene.StartHeight = 1500.0; scene.PinSelection = ["0", "1"]
    refresh_drape_target(scene.DrapeTarget); doc.recompute()
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar": raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if scene.DrapeTarget is None or not scene.DrapePanels: raise RuntimeError("visual garment fixture did not create drape target/panel")
    drape = scene.DrapePanels[0]; _style_garment(drape, "Drape: Simple Tunic Panel"); avatar.ViewObject.Visibility = True; doc.recompute()
    if int(getattr(avatar, "MeshVertexCount", 0)) <= 100 or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100: raise RuntimeError("visual fixture does not contain a real humanoid mesh")

    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    panel = SimulationQualityTaskPanel(scene)
    task_dock = show_task(panel, "Simulation Workbench arranged", ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset"))
    view = Gui.activeDocument().activeView(); view.setCameraType("Perspective"); view.viewAxonometric(); _fit_visual_selection(view, avatar, drape)
    _hide_tasks_for_visual_capture(task_dock); save("cloth-simulation-arranged.png", "Simulation Workbench arranged", "single 440x560 mm tunic panel placed against the production MakeHuman mannequin; three-quarter perspective framed to the mannequin and cloth only"); _restore_tasks_after_visual_capture(task_dock)

    for batch in (6, 6, 6, 6): panel.step(batch); doc.recompute(); events()
    if int(scene.Steps) != 24 or float(scene.SimulatedTime) <= 0 or not bool(scene.FiniteState): raise RuntimeError("simulation did not reach a finite 24-step drape state")
    if drape.Mesh.CountFacets <= 10: raise RuntimeError("draped garment panel has no visible mesh facets")
    show_task(panel, "Simulation Workbench draped", ("State:", "24", "particles", "Fast"), reuse_active=True)
    view.setCameraType("Perspective"); view.viewAxonometric(); _fit_visual_selection(view, avatar, drape)
    _hide_tasks_for_visual_capture(task_dock); save("cloth-simulation-draped.png", "Simulation Workbench draped", "same single tunic panel after 24 real simulation steps; three-quarter perspective framed to the mannequin and drape only"); _restore_tasks_after_visual_capture(task_dock)
    close_task(); App.closeDocument(doc.Name)


def load_and_run(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None: raise RuntimeError("cannot load acceptance module: %s" % path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.run_acceptance()


def canonical_garment_e2e():
    load_and_run(os.path.join(ROOT, "tests", "freecad_garment_e2e_smoke.py"), "freecad_garment_e2e_smoke"); log("canonical-garment-e2e=passed")


def simulation_quality_acceptance():
    load_and_run(os.path.join(ROOT, "tests", "freecad_simulation_quality_acceptance.py"), "freecad_simulation_quality_acceptance"); log("simulation-quality-acceptance=passed")


def avatar_provider_acceptance():
    load_and_run(os.path.join(ROOT, "tests", "freecad_avatar_acceptance.py"), "freecad_avatar_acceptance"); log("avatar-provider-acceptance=passed")


exit_code = 0; log("script-start")
try:
    if Gui.getMainWindow() is None: raise RuntimeError("FreeCAD GUI main window did not launch")
    Gui.getMainWindow().show(); events()
    if not Gui.getMainWindow().isVisible(): raise RuntimeError("FreeCAD GUI main window failed to become visible")
    log("gui-launch-ok window=%sx%s" % (Gui.getMainWindow().width(), Gui.getMainWindow().height()))
    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events()
    avatar_provider_acceptance(); canonical_garment_e2e(); simulation_quality_acceptance(); pattern_and_sewing(); simulation(); log("scenario-pass")
except BaseException as error:
    exit_code = 1; print("SCENARIO FAILURE: %r" % (error,), flush=True); print(traceback.format_exc(), flush=True); log("scenario-fail exception=%r" % (error,)); log(traceback.format_exc())
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
