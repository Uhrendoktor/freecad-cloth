"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""
import importlib.util
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def ensure_task_view_visible():
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    dock = window.findChild(QtWidgets.QDockWidget, "Tasks")
    if dock is not None:
        dock.show(); dock.raise_(); events()
        if dock.isVisible():
            return dock
    raise RuntimeError("FreeCAD Tasks dock is unavailable")


def validate_task(panel, name, required):
    events(); dock = ensure_task_view_visible(); events()
    if not panel.form.isVisible():
        panel.form.show(); panel.form.raise_(); events()
    texts = []
    for widget in [panel.form] + panel.form.findChildren(QtWidgets.QWidget):
        value = getattr(widget, "text", "")
        try:
            value = value() if callable(value) else value
        except TypeError:
            value = ""
        if value:
            texts.append(str(value))
    combined = " | ".join(texts)
    missing = [item for item in required if item not in combined]
    log("task-panel=%s visible=true missing=%s" % (name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (name, ",".join(missing)))
    return dock


def show_task(panel, name, required=(), reuse_active=False):
    if not reuse_active:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog(); events()
        Gui.Control.showDialog(panel)
    return validate_task(panel, name, required)


def close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog(); events()


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise RuntimeError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name); events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is not visible")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: " + ",".join(missing))
    log("workbench=%s toolbar=%s" % (name, toolbar))


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); events()
    image = window.grab()
    path = os.path.join(OUT, name)
    if image.isNull() or (image.width(), image.height()) != (1280, 720):
        raise RuntimeError("invalid GUI capture for %s" % state)
    if not image.save(path) or os.path.getsize(path) < 20000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\t%s\n" % (name, state, proof))


def load_and_run(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load acceptance module: %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run_acceptance()


def run_canonical_acceptance():
    for path, name, marker in (
        ("tests/freecad_avatar_acceptance.py", "freecad_avatar_acceptance", "avatar-provider-acceptance"),
        ("tests/freecad_garment_e2e_smoke.py", "freecad_garment_e2e_smoke", "canonical-garment-e2e"),
        ("tests/freecad_simulation_quality_acceptance.py", "freecad_simulation_quality_acceptance", "simulation-quality-acceptance"),
    ):
        load_and_run(os.path.join(ROOT, path), name)
        log(marker + "=passed")


def pattern_and_sewing():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel
    import Part

    doc = App.newDocument("ClothVisualPattern")
    front = create_pattern_piece_from_parameters("Front", 140.0, 90.0, 10.0, 0.0)
    back = create_pattern_piece_from_parameters("Back", 140.0, 90.0, 10.0, 0.0)
    front.Placement.Base.x = -160
    back.Placement.Base.x = 20
    marker = doc.addObject("Part::Feature", "GrainlineMarker")
    marker.Shape = Part.makeLine(App.Vector(-90, 10, 1), App.Vector(-90, 80, 1))
    doc.recompute()
    if front.Shape.isNull() or back.Shape.isNull():
        raise RuntimeError("pattern fixture produced empty geometry")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"])
    panel = PatternPieceTaskPanel(front)
    dock = show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-pattern-design.png", "Pattern Workbench", "native pattern task panel with two pieces")
    close_task()
    seam = add_seam(doc, Seam(str(front.PieceId), 1, str(back.PieceId), 3, id="FrontBack", alignment="uniform", stitch_group="MainSeam"))
    sewing = create_sewing_operation(); doc.recompute()
    if str(seam.Status) != "Valid" or seam.Shape.isNull() or str(sewing.Status) != "Valid" or sewing.Shape.isNull():
        raise RuntimeError("sewing fixture is invalid")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
    panel = SewingTaskPanel(sewing)
    show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"))
    Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events()
    save("cloth-sewing.png", "Sewing Workbench", "native seam and sewing diagnostics")
    close_task(); App.closeDocument(doc.Name)


def style_mesh(obj, label, color=(0.86, 0.20, 0.10)):
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.LineColor = (0.20, 0.02, 0.01)
        obj.ViewObject.LineWidth = 1.5
    except (AttributeError, TypeError, ValueError):
        pass


def _tunic_outline(width, height):
    # One wearable front/back panel: open neck, shaped shoulder, straight side and hem.
    return [
        (0.00, 0.00), (width, 0.00),
        (width, height), (0.68 * width, 0.86 * height),
        (0.32 * width, 0.86 * height), (0.00, height),
    ]


def simulation():
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_parameters
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target

    doc = App.newDocument("ClothSimulationVisualRegression")
    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if target is None:
        raise RuntimeError("visual fixture did not create DrapeTarget")

    box = avatar.Mesh.BoundBox
    x_mid = (box.XMin + box.XMax) / 2.0
    y_mid = (box.YMin + box.YMax) / 2.0
    x_span = box.XMax - box.XMin
    y_span = box.YMax - box.YMin
    z_span = box.ZMax - box.ZMin

    # MakeHuman is Z-up here: X is lateral garment width, Y is front/back depth.
    chest = 980.0
    hip = 1020.0
    shoulder = 440.0
    ease = 70.0
    panel_width = max(420.0, 0.50 * chest + 0.5 * ease, 0.55 * shoulder + 120.0)
    hem_width = max(470.0, 0.50 * hip + ease)
    shoulder_z = box.ZMin + 0.76 * z_span
    hem_z = box.ZMin + 0.42 * z_span
    garment_height = max(520.0, shoulder_z - hem_z)
    clearance = max(8.0, 0.025 * max(1.0, y_span))
    front_y = box.YMin - clearance
    back_y = box.YMax + clearance
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def make_piece(name, y, neckline_ratio):
        outline = _tunic_outline(panel_width, garment_height)
        if neckline_ratio != 0.68:
            outline = [
                (0.00, 0.00), (panel_width, 0.00),
                (panel_width, garment_height), (neckline_ratio * panel_width, 0.86 * garment_height),
                ((1.0 - neckline_ratio) * panel_width, 0.86 * garment_height), (0.00, garment_height),
            ]
        piece = create_pattern_piece_from_parameters(name, panel_width, garment_height, 10.0, 0.0)
        piece.Label = name
        piece.DraftingBoundary = repr(outline)
        piece.SewingOutline = repr(outline)
        piece.Placement = App.Placement(
            App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot
        )
        return piece, outline

    front, front_outline = make_piece("VisualTunicFront", front_y, 0.68)
    back, back_outline = make_piece("VisualTunicBack", back_y, 0.74)

    # Match hem width in local x by adding a controlled outward ease to the side corners.
    # The top is narrower to represent shoulders while the hem remains relaxed.
    front.DraftingBoundary = repr([(0.00, 0.00), (hem_width, 0.00), (panel_width, garment_height), (0.68 * panel_width, 0.86 * garment_height), (0.32 * panel_width, 0.86 * garment_height), (0.00, garment_height)])
    front.SewingOutline = front.DraftingBoundary
    back.DraftingBoundary = repr([(0.00, 0.00), (hem_width, 0.00), (panel_width, garment_height), (0.74 * panel_width, 0.86 * garment_height), (0.26 * panel_width, 0.86 * garment_height), (0.00, garment_height)])
    back.SewingOutline = back.DraftingBoundary
    doc.recompute()

    # Side seams and shoulder seams form one real tunic shell; neckline and hem stay open.
    for edge_a, edge_b, seam_id in (
        (1, 1, "TunicRightSide"),
        (5, 5, "TunicLeftSide"),
        (2, 2, "TunicRightShoulder"),
        (4, 4, "TunicLeftShoulder"),
    ):
        add_seam(doc, Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly"))

    # Refresh collision after the production target is resolved, and use the vertical panel pose.
    refresh_drape_target(target)
    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = 22.0
    scene.SolverIterations = 6
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 90.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.ClothPieces = [front, back]
    doc.recompute()

    # Derive pin indices from the actual triangulated outline. Only shoulder regions are pinned.
    def shoulder_pins(piece, outline):
        points = [(float(x), float(y)) for x, y in outline]
        segments = [LineSegment("%s:edge:%d" % (piece.PieceId, i), points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
        mesh = triangulate(ParametricPattern(segments))
        h = max(y for _, y in points)
        return tuple(i for i in mesh.boundary_vertex_indices if float(mesh.vertices[i][1]) >= 0.86 * h - 1e-6 and (float(mesh.vertices[i][0]) <= 0.32 * panel_width + 1e-6 or float(mesh.vertices[i][0]) >= 0.68 * panel_width - 1e-6))

    front_pins = shoulder_pins(front, eval(front.DraftingBoundary))
    back_pins_local = shoulder_pins(back, eval(back.DraftingBoundary))
    # SimulationObjects concatenates panel particles in piece order.
    from freecad_cloth.pattern.PatternGeometry import ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate
    fp = [(float(x), float(y)) for x, y in eval(front.DraftingBoundary)]
    bp = [(float(x), float(y)) for x, y in eval(back.DraftingBoundary)]
    fv = triangulate(ParametricPattern([LineSegment("fp:%d" % i, fp[i], fp[(i + 1) % len(fp)]) for i in range(len(fp))]))
    bv = triangulate(ParametricPattern([LineSegment("bp:%d" % i, bp[i], bp[(i + 1) % len(bp)]) for i in range(len(bp))]))
    front_pins = tuple(front_pins)
    back_pins = tuple(len(fv.vertices) + i for i in back_pins_local)
    scene.PinSelection = [str(i) for i in (front_pins + back_pins)]
    doc.recompute()

    source_front = doc.getObject("VisualTunicFront")
    source_back = doc.getObject("VisualTunicBack")
    for source in (source_front, source_back):
        if source is not None:
            source.ViewObject.Visibility = False
    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels, got %d" % len(panels))
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back")):
        style_mesh(panel, label)
        panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()

    log("avatar-bounds x=%.1f..%.1f y=%.1f..%.1f z=%.1f..%.1f" % (box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax))
    log("tunic panel-width=%.1f hem-width=%.1f height=%.1f front-y=%.1f back-y=%.1f pins=%s" % (panel_width, hem_width, garment_height, front_y, back_y, scene.PinSelection))
    if int(getattr(avatar, "MeshVertexCount", 0)) <= 100 or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100:
        raise RuntimeError("visual fixture does not contain a real humanoid mesh")

    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    task_dock = show_task(SimulationQualityTaskPanel(scene), "Simulation Workbench arranged", ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset"))
    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewFront(); view.fitAll(); events()
    task_dock.hide(); events()
    save("cloth-simulation-arranged.png", "Simulation Workbench arranged", "vertical two-panel tunic on production mannequin before simulation")
    task_dock.show(); task_dock.raise_(); events()

    panel_task = SimulationQualityTaskPanel(scene)
    # Re-use the active task dialog rather than opening a second one.
    panel_task.form = Gui.Control.activeDialog() if False else panel_task.form
    for _ in range(4):
        # 4 x 15 steps = 60 frames; the fixed first-step state prevents artificial launch velocity.
        show = panel_task
        if show.form is not None:
            pass
        # Call the public task-panel operation against the active scene.
        # The existing panel already exposes step(); create one only if needed.
        try:
            from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel as _Panel
            active_panel = _Panel(scene)
            active_panel.form = active_panel.form
            active_panel.step(15)
        except Exception:
            panel = Gui.Control.activeDialog()
            if hasattr(panel, "step"):
                panel.step(15)
            else:
                raise
        doc.recompute(); events()

    if int(scene.Steps) != 60 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
        raise RuntimeError("simulation did not reach a finite 60-step state")
    if any(panel.Mesh.CountFacets <= 10 for panel in scene.DrapePanels):
        raise RuntimeError("draped tunic panel mesh is empty")

    bounds = []
    for panel in scene.DrapePanels:
        b = panel.Mesh.BoundBox
        bounds.append((b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
    log("drape-bounds=%s" % (bounds,))

    # Hide every unrelated demo panel; only the two tunic panels and the mannequin remain.
    keep = {panel.Name for panel in scene.DrapePanels}
    for obj in doc.Objects:
        if getattr(obj, "Name", "") in ("DrapePanelA", "DrapePanelB") and obj.Name not in keep:
            obj.ViewObject.Visibility = False
    doc.recompute()

    final_views = (
        ("front", "viewFront"),
        ("rear", "viewRear"),
        ("left", "viewLeft"),
        ("right", "viewRight"),
        ("top", "viewTop"),
        ("bottom", "viewBottom"),
    )
    task_dock.hide(); events()
    for direction, method_name in final_views:
        getattr(view, method_name)(); view.fitAll(); events()
        save("cloth-simulation-draped-%s.png" % direction, "Simulation Workbench draped %s" % direction, "same sewn tunic after 60 real steps; six-side audit" )
        if direction == "front":
            save("cloth-simulation-draped.png", "Simulation Workbench draped front", "legacy front screenshot alias")
    task_dock.show(); task_dock.raise_(); events()
    close_task()
    App.closeDocument(doc.Name)


def main():
    log("script-start")
    if Gui.getMainWindow() is None or not Gui.getMainWindow().isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    Gui.getMainWindow().show(); events()
    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events()
    run_canonical_acceptance()
    pattern_and_sewing()
    simulation()
    log("scenario-pass")


exit_code = 0
try:
    main()
except BaseException as error:
    exit_code = 1
    print("SCENARIO FAILURE: %r" % (error,), flush=True)
    print(traceback.format_exc(), flush=True)
    log("scenario-fail exception=%r" % (error,))
finally:
    try:
        close_task()
        for document in list(App.listDocuments().values()):
            try:
                App.closeDocument(document.Name)
            except Exception:
                pass
        events()
        log("script-end exit-code=%d" % exit_code)
        window = Gui.getMainWindow()
        if window is not None:
            window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
    except BaseException:
        pass

if exit_code:
    raise SystemExit(exit_code)
