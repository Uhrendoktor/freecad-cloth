"""Deterministic GUI visual-regression scenarios; run under Xvfb with FreeCAD."""
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
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")


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


def panel_text(panel):
    if panel is None or getattr(panel, "form", None) is None:
        return ""
    widgets = panel.form.findChildren(QtWidgets.QWidget)
    texts = []
    for widget in [panel.form] + widgets:
        for attr in ("text", "title"):
            value = getattr(widget, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            if value:
                texts.append(str(value))
        value = getattr(widget, "currentText", None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value:
            texts.append(str(value))
    return " | ".join(texts)


def require_panel(panel, state_name, required):
    if not panel.form.isVisible():
        raise RuntimeError("task panel is not visible: %s" % state_name)
    text = panel_text(panel)
    missing = [item for item in required if item not in text]
    progress("panel-content=%s missing=%s" % (state_name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (state_name, ",".join(missing)))


def set_top_camera():
    view = Gui.activeDocument().activeView()
    view.viewTop()
    view.fitAll()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    progress("camera=top fitAll=true")


def set_axon_camera():
    view = Gui.activeDocument().activeView()
    view.viewAxonometric()
    view.fitAll()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    progress("camera=axonometric fitAll=true")


def add_line_feature(doc, name, segments, width=4.0):
    import Part
    feature = doc.addObject("Part::Feature", name)
    feature.Label = name
    feature.Shape = Part.makeCompound([Part.makeLine(a, b) for a, b in segments])
    feature.ViewObject.LineWidth = width
    feature.ViewObject.LineColor = (0.85, 0.15, 0.15)
    return feature


def add_pattern_markers(doc, front, back):
    """Create deterministic visual marker fixtures around real pattern geometry."""
    import FreeCAD as FC
    front_x = float(front.Placement.Base.x)
    back_x = float(back.Placement.Base.x)
    y = 45.0
    markers = []
    for name, x in (("Front notch marker", front_x + 70.0), ("Back notch marker", back_x + 70.0)):
        markers.append(add_line_feature(doc, name, [
            (FC.Vector(x - 5, 90, 0.8), FC.Vector(x, 84, 0.8)),
            (FC.Vector(x, 84, 0.8), FC.Vector(x + 5, 90, 0.8)),
        ]))
    markers.append(add_line_feature(doc, "Front grainline marker", [
        (FC.Vector(front_x + 70, 12, 0.8), FC.Vector(front_x + 70, 78, 0.8)),
        (FC.Vector(front_x + 70, 78, 0.8), FC.Vector(front_x + 66, 70, 0.8)),
        (FC.Vector(front_x + 70, 78, 0.8), FC.Vector(front_x + 74, 70, 0.8)),
    ]))
    for marker in markers:
        marker.ViewObject.LineColor = (0.85, 0.15, 0.15)
    progress("pattern-markers=notches+grainline count=%s" % len(markers))
    return markers


def add_sewing_arrows(doc, front, back):
    """Create deterministic in-plane direction arrows over the real seam visualization."""
    import FreeCAD as FC
    y = 45.0
    arrows = []
    for name, x0, x1 in (("Sew direction A", front.Placement.Base.x + 140.0, front.Placement.Base.x + 128.0),
                         ("Sew direction B", back.Placement.Base.x, back.Placement.Base.x + 12.0)):
        head = FC.Vector(x0, y, 0.9)
        tail = FC.Vector(x1, y, 0.9)
        left = FC.Vector(x0 - (3 if x0 < x1 else -3), y + 4, 0.9)
        right = FC.Vector(x0 - (3 if x0 < x1 else -3), y - 4, 0.9)
        arrows.append(add_line_feature(doc, name, [(tail, head), (head, left), (head, right)]))
    progress("sewing-direction-arrows=count=%s" % len(arrows))
    return arrows


def image_is_useful(path, state_name):
    """Reject empty, tiny, or visually uniform captures rather than accepting -s alone."""
    if not os.path.isfile(path):
        raise RuntimeError("screenshot does not exist: %s" % path)
    file_size = os.path.getsize(path)
    if file_size < 20000:
        raise RuntimeError("screenshot is suspiciously small: %s (%d bytes)" % (path, file_size))
    image = Gui.getMainWindow().grab()
    if image.isNull() or image.width() < 1000 or image.height() < 600:
        raise RuntimeError("captured window is blank/partial for %s: %sx%s" % (state_name, image.width(), image.height()))
    samples = set()
    for y in range(0, image.height(), max(1, image.height() // 24)):
        for x in range(0, image.width(), max(1, image.width() // 32)):
            samples.add(int(image.pixel(x, y)))
    if len(samples) < 80:
        raise RuntimeError("screenshot is visually uniform for %s (%d sampled colors)" % (state_name, len(samples)))
    progress("image-validation=%s path=%s bytes=%d size=%sx%s sampled_colors=%d" % (state_name, path, file_size, image.width(), image.height(), len(samples)))


def save_window(filename, state_name, proof):
    """Capture the complete FreeCAD main window after all required state is visible."""
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    window.show()
    window.raise_()
    window.activateWindow()
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
    image_is_useful(path, state_name)
    with open(MANIFEST, "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\t%s\n" % (filename, state_name, proof))


progress("script-start")
try:
    # FreeCAD's GUI startup already imports InitGui.py and registers the Cloth
    # workbenches.  Re-executing that module here registers the same workbench
    # classes a second time, producing "already exists" and missing-icon noise.
    # Importing it is idempotent and also works when this script is launched in
    # a context where FreeCAD has not imported the module yet.
    import InitGui
    from PatternCommands import create_pattern_piece_from_parameters
    from PatternModel import Seam
    from PatternObjects import add_seam
    from PatternGui import PatternPieceTaskPanel
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
    sim_doc = None
    try:
        progress("scenario-start")
        open(DEBUG, "w", encoding="utf-8").close()
        open(MANIFEST, "w", encoding="utf-8").close()
        window = Gui.getMainWindow()
        if window is not None:
            window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); Gui.updateGui()
            progress("main-window=%sx%s" % (window.width(), window.height()))

        # Pattern workbench: real pieces with native seam allowance, dimensions in the task panel,
        # and deterministic notch/grainline fixtures over the actual geometry.
        doc = App.newDocument("ClothVisualRegression")
        front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
        back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
        front.Placement.Base.x = -160.0
        back.Placement.Base.x = 20.0
        markers = add_pattern_markers(doc, front, back)
        doc.recompute()
        if front.Shape.isNull() or back.Shape.isNull():
            raise RuntimeError("pattern fixture produced empty geometry")
        activate_workbench("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
        pattern_panel = PatternPieceTaskPanel(front)
        show_task(pattern_panel, "Pattern Workbench")
        require_panel(pattern_panel, "Pattern Workbench", ["Piece name", "Width", "Height", "Seam allowance", "Grainline angle"])
        if pattern_panel.width.value() != 140.0 or pattern_panel.height.value() != 90.0 or pattern_panel.allowance.value() != 10.0:
            raise RuntimeError("pattern task panel does not expose deterministic dimensions/allowance")
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(front)
        set_top_camera()
        save_window("cloth-pattern-design.png", "Pattern Workbench", "two 140x90 mm pieces; native 10 mm seam allowance; task-panel dimensions/allowance; notch and grainline markers")
        Gui.Control.closeDialog()

        # Sewing workbench: use the real semantic seam and sewing operation; add only deterministic
        # arrow fixtures so direction is visible at this regression boundary.
        seam = add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="FrontBack", alignment="uniform", stitch_group="MainSeam"))
        doc.recompute()
        if str(seam.Status) != "Valid" or seam.Shape.isNull():
            raise RuntimeError("seam visualization is not valid/non-empty")
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(seam)
        sewing = create_sewing_operation()
        doc.recompute()
        arrows = add_sewing_arrows(doc, front, back)
        if str(sewing.Status) != "Valid" or sewing.Shape.isNull() or int(sewing.StitchCount) < 2:
            raise RuntimeError("sewing operation did not produce valid seam diagnostics")
        progress("sewing-created status=%s stitches=%s length_a=%.2f length_b=%.2f difference=%.2f" % (sewing.Status, sewing.StitchCount, sewing.LengthA, sewing.LengthB, sewing.LengthDifference))
        activate_workbench("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(sewing)
        sewing_panel = SewingTaskPanel(sewing)
        show_task(sewing_panel, "Sewing Workbench")
        require_panel(sewing_panel, "Sewing Workbench", ["Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status", "Seam lengths", "Correspondence", "Repair correspondence"])
        if str(sewing.Status) != "Valid" or abs(float(sewing.LengthDifference)) > 0.5:
            raise RuntimeError("sewing diagnostics are not valid")
        set_top_camera()
        save_window("cloth-sewing.png", "Sewing Workbench", "real seam/sewing geometry; uniform correspondence diagnostics; stitch count and length comparison; deterministic direction arrows")
        Gui.Control.closeDialog()

        # Simulation workbench: separate deterministic document so all links remain in one FreeCAD document.
        progress("simulation-scenario-start")
        sim_doc = App.newDocument("ClothSimulationVisualRegression")
        sim_front = create_pattern_piece_from_parameters("SimFront", 140.0, 90.0, 10.0, 0.0)
        sim_back = create_pattern_piece_from_parameters("SimBack", 140.0, 90.0, 10.0, 0.0)
        sim_front.Placement.Base.x = -150.0
        sim_back.Placement.Base.x = 10.0
        sim_seam = add_seam(sim_doc, Seam(str(sim_front.PieceId), 1, str(sim_back.PieceId), 3, id="SimFrontBack", alignment="uniform", stitch_group="MainSeam"))
        scene = create_quality_simulation_scene(sim_doc)
        scene.ClothPieces = [sim_front, sim_back]
        scene.QualityPreset = "Fast"
        scene.ParticleDistance = 10.0
        scene.SolverIterations = 6
        scene.SolverSubsteps = 1
        scene.FabricDensity = 150.0
        scene.FabricThickness = 0.5
        scene.FabricStretch = 0.02
        scene.FabricShear = 0.02
        scene.FabricBend = 0.01
        scene.FabricFriction = 0.5
        scene.StartHeight = 135.0
        sim_front.Visibility = False
        sim_back.Visibility = False
        sim_seam.Visibility = False
        sim_doc.recompute()
        if scene.DrapeTarget is None or scene.AvatarProxy is None:
            raise RuntimeError("simulation fixture has no avatar/DrapeTarget")
        if not scene.DrapePanels or any(getattr(panel.Mesh, "CountFacets", 0) < 20 for panel in scene.DrapePanels):
            raise RuntimeError("simulation fixture has no useful arranged garment meshes")
        progress("simulation-arranged-ready target=%s avatar=%s particles=%s panels=%s" % (scene.DrapeTarget.Label, scene.AvatarProxy.Label, scene.ParticleCount, len(scene.DrapePanels)))
        activate_workbench("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
        sim_panel = SimulationQualityTaskPanel(scene)
        show_task(sim_panel, "Simulation Workbench arranged")
        require_panel(sim_panel, "Simulation Workbench arranged", ["Simulation quality", "Preset", "Fabric", "Collision", "Simulation steps", "Step", "Run 30", "Reset", "State:"])
        set_axon_camera()
        save_window("cloth-simulation-arranged.png", "Simulation Workbench arranged", "humanoid avatar plus two deterministic arranged garment panels at StartHeight; simulation controls and ready state")

        # Advance through the real task-panel control path, logging each deterministic batch.
        for batch in (6, 6, 6, 6):
            sim_panel.step(batch)
            sim_doc.recompute()
            progress("simulation-step batch=%d total=%d time=%.4f particles=%d finite=%s" % (batch, scene.Steps, scene.SimulatedTime, scene.ParticleCount, scene.FiniteState))
        if int(scene.Steps) != 24 or float(scene.SimulatedTime) <= 0.0 or int(scene.ParticleCount) < 20 or not bool(scene.FiniteState):
            raise RuntimeError("simulation did not reach a finite, non-empty draped state")
        if any(getattr(panel.Mesh, "CountFacets", 0) < 20 for panel in scene.DrapePanels):
            raise RuntimeError("draped panels became empty")
        require_panel(sim_panel, "Simulation Workbench draped", ["State:", "24", "particles", "Fast"])
        set_axon_camera()
        save_window("cloth-simulation-draped.png", "Simulation Workbench draped", "same avatar/garment scene after 24 real simulation steps; non-empty draped meshes; finite state and elapsed simulation time")
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
        if sim_doc is not None and sim_doc.Name in App.listDocuments():
            App.closeDocument(sim_doc.Name); progress("simulation-document-closed")
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
