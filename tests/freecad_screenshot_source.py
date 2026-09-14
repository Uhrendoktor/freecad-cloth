"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""
import importlib.util
import json
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
METRICS = os.path.join(OUT, "drape-visual-metrics.json")


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


def show_task(panel, name, required=()):
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
    image = window.grab(); path = os.path.join(OUT, name)
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
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.run_acceptance()


def run_canonical_acceptance():
    for path, name, marker in ((
        "tests/freecad_avatar_acceptance.py", "freecad_avatar_acceptance", "avatar-provider-acceptance"),
        ("tests/freecad_garment_e2e_smoke.py", "freecad_garment_e2e_smoke", "canonical-garment-e2e"),
        ("tests/freecad_simulation_quality_acceptance.py", "freecad_simulation_quality_acceptance", "simulation-quality-acceptance")):
        load_and_run(os.path.join(ROOT, path), name); log(marker + "=passed")


def _mesh_points(mesh):
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        return ()
    vertices, _triangles = topology
    return tuple((float(p.x), float(p.y), float(p.z)) for p in vertices)


def write_drape_metrics(panels, avatar, center_x=None, shoulder_z=None, hem_z=None):
    from freecad_cloth.common.DrapeVisualSanity import inspect_drape, summarize
    avatar_vertices = _mesh_points(getattr(avatar, "Mesh", None)); box = avatar.Mesh.BoundBox
    target_height = float(box.ZMax - box.ZMin)
    target_width = float(max(box.XMax - box.XMin, box.YMax - box.YMin))
    if shoulder_z is None:
        shoulder_z = float(box.ZMin) + 0.76 * target_height
    if hem_z is None:
        hem_z = float(box.ZMin) + 0.40 * target_height
    upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))
    lower_margin = 0.20 * max(1.0, float(shoulder_z) - float(hem_z))
    records = []
    for panel in panels:
        vertices = _mesh_points(getattr(panel, "Mesh", None))
        metrics = inspect_drape(vertices, avatar_vertices, target_height=target_height, target_width=target_width)
        record = {"panel": str(getattr(panel, "Label", getattr(panel, "Name", ""))), **summarize(metrics)}
        if center_x is not None:
            record["centroid_lateral_offset"] = abs(float(metrics.centroid[0]) - float(center_x))
            if record["centroid_lateral_offset"] > target_width * 0.18:
                raise RuntimeError("draped panel %s is laterally detached from the avatar center: %.1f mm" % (record["panel"], record["centroid_lateral_offset"]))
        if metrics.target_vertex_clearance is None or metrics.target_vertex_clearance > target_width * 0.15:
            raise RuntimeError("draped panel %s is too far from the collision target" % record["panel"])
        if metrics.vertical_span_ratio < 0.25 or metrics.lateral_span_ratio < 0.25:
            raise RuntimeError("draped panel %s collapsed into a visually weak state" % record["panel"])
        if float(metrics.bounds[5]) > float(shoulder_z) + upper_margin:
            raise RuntimeError("draped panel %s rises too far above the shoulder zone: %.1f mm" % (record["panel"], metrics.bounds[5]))
        if float(metrics.bounds[4]) < float(hem_z) - lower_margin:
            raise RuntimeError("draped panel %s falls too far below the intended hem zone: %.1f mm" % (record["panel"], metrics.bounds[4]))
        if float(metrics.centroid[2]) > float(shoulder_z) + upper_margin:
            raise RuntimeError("draped panel %s centroid is above the shoulder zone: %.1f mm" % (record["panel"], metrics.centroid[2]))
        records.append(record)
        log("drape-metrics=%s" % json.dumps(record, sort_keys=True))
    with open(METRICS, "w", encoding="utf-8") as handle:
        json.dump({"target_height": target_height, "target_width": target_width, "shoulder_z": shoulder_z, "hem_z": hem_z, "panels": records}, handle, indent=2, sort_keys=True)


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop=0.08):
    import Part, Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    neck_z = (1.0 - float(neckline_drop)) * garment_height
    points = [
        (0.00, 0.00), (hem_width, 0.00),
        (panel_width, 0.82 * garment_height), (0.86 * panel_width, 0.97 * garment_height),
        (neckline_ratio * panel_width, neck_z), ((1.0 - neckline_ratio) * panel_width, neck_z),
        (0.14 * panel_width, 0.97 * garment_height), (0.00, 0.82 * garment_height),
    ]
    geometry = [Part.LineSegment(App.Vector(points[i][0], points[i][1], 0), App.Vector(points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1], 0)) for i in range(len(points))]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint([
        Sketcher.Constraint("Coincident",0,2,1,1), Sketcher.Constraint("Coincident",1,2,2,1),
        Sketcher.Constraint("Coincident",2,2,3,1), Sketcher.Constraint("Coincident",3,2,4,1),
        Sketcher.Constraint("Coincident",4,2,5,1), Sketcher.Constraint("Coincident",5,2,6,1),
        Sketcher.Constraint("Coincident",6,2,7,1), Sketcher.Constraint("Coincident",7,2,0,1)])
    doc.recompute(); return sketch, points


def _adopt_sketch(sketch, name, allowance, grainline):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=allowance, grainline=grainline)
    piece.Label = name; doc = App.ActiveDocument; doc.recompute()
    if piece.Sketch is not sketch:
        raise RuntimeError("Cloth PatternPiece did not retain the selected native Sketcher source")
    return piece


def pattern_and_sewing():
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel
    import Part
    doc = App.newDocument("ClothVisualPattern")
    front_sketch, _front_outline = _make_tunic_sketch(doc, "VisualFront", 520.0, 720.0, 600.0, 0.64, 0.10)
    back_sketch, _back_outline = _make_tunic_sketch(doc, "VisualBack", 520.0, 720.0, 600.0, 0.64, 0.07)
    doc.recompute(); front = _adopt_sketch(front_sketch, "Front Tunic", 10.0, 0.0); back = _adopt_sketch(back_sketch, "Back Tunic", 10.0, 0.0)
    front.Placement.Base.x = -660; back.Placement.Base.x = 40; front.Sketch.Placement = front.Placement; back.Sketch.Placement = back.Placement
    marker = doc.addObject("Part::Feature", "GrainlineMarker"); marker.Shape = Part.makeLine(App.Vector(-400,90,1), App.Vector(-400,640,1))
    front.ViewObject.Visibility = False; back.ViewObject.Visibility = False; front.Sketch.ViewObject.Visibility = True; back.Sketch.ViewObject.Visibility = True; doc.recompute()
    if front.Shape.isNull() or back.Shape.isNull():
        raise RuntimeError("pattern fixture produced empty geometry from native sketches")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D", "ClothPattern_CreateFromSketch"])
    panel = PatternPieceTaskPanel(front); show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-pattern-design.png", "Pattern Workbench", "native Sketcher tunic pattern adopted into Cloth PatternPiece"); close_task()
    seam = add_seam(doc, Seam(str(front.PieceId), 7, str(back.PieceId), 7, id="FrontBack", alignment="endpoints", stitch_group="MainSeam")); doc.recompute()
    sewing = create_sewing_operation(); doc.recompute()
    if str(seam.Status) != "Valid" or seam.Shape.isNull() or str(sewing.Status) != "Valid" or sewing.Shape.isNull():
        raise RuntimeError("sewing fixture is invalid")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name)


def style_mesh(obj, label):
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"; obj.ViewObject.ShapeColor = (0.86, 0.20, 0.10); obj.ViewObject.LineColor = (0.20, 0.02, 0.01); obj.ViewObject.LineWidth = 1.5
    except (AttributeError, TypeError, ValueError):
        pass


def simulation():
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    doc = App.newDocument("ClothSimulationVisualRegression"); scene = create_quality_simulation_scene(doc); avatar = getattr(scene.AvatarProxy, "SourceObject", None); target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if target is None:
        raise RuntimeError("visual fixture did not create DrapeTarget")
    box = avatar.Mesh.BoundBox; x_mid = (box.XMin + box.XMax) / 2.0; y_span = box.YMax - box.YMin; z_span = box.ZMax - box.ZMin
    chest = 980.0; hip = 1020.0; ease = 55.0; panel_width = max(420.0, 0.50 * chest + ease); hem_width = max(450.0, 0.50 * hip + ease)
    shoulder_z = box.ZMin + 0.76 * z_span; hem_z = box.ZMin + 0.40 * z_span; garment_height = max(560.0, shoulder_z - hem_z); body_depth = max(120.0, min(260.0, y_span)); clearance = max(20.0, 0.08 * body_depth); front_y = box.YMin - clearance; back_y = box.YMax + clearance; rot = App.Rotation(App.Vector(1,0,0), 90.0)
    def make_piece(name, y, neckline_ratio, neckline_drop):
        sketch, outline = _make_tunic_sketch(doc, name + "Source", panel_width, garment_height, hem_width, neckline_ratio, neckline_drop); doc.recompute(); piece = _adopt_sketch(sketch, name, 10.0, 0.0); piece.Label = name; piece.Placement = App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot); piece.Sketch.Placement = piece.Placement; return piece, outline
    front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.07)
    # Same-side side seams and authored shoulder seams; the neckline remains open.
    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):
        add_seam(doc, Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly"))
    scene.StartHeight = 0.0; scene.QualityPreset = "Fast"; scene.ParticleDistance = 24.0; scene.SolverIterations = 8; scene.SolverSubsteps = 1; scene.TimeStep = 1.0 / 120.0; scene.GravityX = 0.0; scene.GravityY = 0.0; scene.GravityZ = -9810.0; scene.FabricFriction = 0.75; scene.ClothPieces = [front, back]; refresh_drape_target(target); doc.recompute()
    def authored_shoulder_pins(piece, positions):
        targets = (
            (0.14 * panel_width, 0.97 * garment_height),
            (0.86 * panel_width, 0.97 * garment_height),
        )
        available = list(range(len(positions)))
        result = []
        for local_x, local_y in targets:
            target_point = piece.Placement.multVec(App.Vector(float(local_x), float(local_y), 0.0))
            index = min(available, key=lambda i: (positions[i][0] - target_point.x) ** 2 + (positions[i][1] - target_point.y) ** 2 + (positions[i][2] - target_point.z) ** 2)
            result.append(index)
            available.remove(index)
        return tuple(result)
    front_positions, _front_triangles, _front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_positions, _back_triangles, _back_boundary = quality_piece_mesh(back, 0.0, scene.ParticleDistance)
    front_pins = authored_shoulder_pins(front, front_positions)
    back_pins_local = authored_shoulder_pins(back, back_positions)
    back_pins = tuple(len(front_positions) + i for i in back_pins_local)
    scene.PinSelection = [str(i) for i in front_pins + back_pins]
    log("pin-map authored front=%s back-local=%s back-global=%s" % (front_pins, back_pins_local, back_pins)); doc.recompute()
    for source in (doc.getObject("VisualTunicFront"), doc.getObject("VisualTunicBack")):
        if source is not None: source.ViewObject.Visibility = False
        sketch = getattr(source, "Sketch", None) if source is not None else None
        if sketch is not None: sketch.ViewObject.Visibility = False
    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels, got %d" % len(panels))
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back")):
        style_mesh(panel, label); panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True; doc.recompute(); log("avatar-bounds x=%.1f..%.1f y=%.1f..%.1f z=%.1f..%.1f" % (box.XMin,box.XMax,box.YMin,box.YMax,box.ZMin,box.ZMax)); log("tunic-source=freecad-native-sketcher edges=%d front=%s back=%s" % (len(front.Sketch.Geometry),front.Sketch.Name,back.Sketch.Name))
    if int(getattr(avatar, "MeshVertexCount", 0)) <= 100 or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100:
        raise RuntimeError("visual fixture does not contain a real humanoid mesh")
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    simulation_panel = SimulationQualityTaskPanel(scene); task_dock = show_task(simulation_panel, "Simulation Workbench arranged", ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset")); view = Gui.activeDocument().activeView(); view.setCameraType("Orthographic"); view.viewFront(); view.fitAll(); events(); task_dock.hide(); events(); save("cloth-simulation-arranged.png", "Simulation Workbench arranged", "vertical sewn tunic generated from native Sketcher pattern sources on production mannequin"); task_dock.show(); task_dock.raise_(); events()
    for batch in (15,15,15,15,15,15):
        simulation_panel.step(batch); doc.recompute(); events()
    if int(scene.Steps) != 90 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
        raise RuntimeError("simulation did not reach a finite 90-step state")
    if any(panel.Mesh.CountFacets <= 10 for panel in scene.DrapePanels):
        raise RuntimeError("draped tunic panel mesh is empty")
    write_drape_metrics(panels, avatar, x_mid, shoulder_z=shoulder_z, hem_z=hem_z); bounds = []
    for panel in scene.DrapePanels:
        b = panel.Mesh.BoundBox; bounds.append((b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax))
    log("drape-bounds=%s" % (bounds,)); task_dock.hide(); events()
    for direction, method_name in (("front","viewFront"),("rear","viewRear"),("left","viewLeft"),("right","viewRight"),("top","viewTop"),("bottom","viewBottom")):
        getattr(view, method_name)(); view.fitAll(); events(); save("cloth-simulation-draped-%s.png" % direction, "Simulation Workbench draped %s" % direction, "same sewn tunic after 90 real steps; six-side audit from native Sketcher pattern sources")
        if direction == "front":
            save("cloth-simulation-draped.png", "Simulation Workbench draped front", "legacy front screenshot alias; native Sketcher tunic source")
    task_dock.show(); task_dock.raise_(); events(); close_task(); App.closeDocument(doc.Name)


def main():
    log("script-start")
    if Gui.getMainWindow() is None or not Gui.getMainWindow().isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    Gui.getMainWindow().show(); events(); init_gui = os.path.join(ROOT, "InitGui.py"); exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events(); run_canonical_acceptance(); pattern_and_sewing(); simulation(); log("scenario-pass")


exit_code = 0
try:
    main()
except BaseException as error:
    exit_code = 1; print("SCENARIO FAILURE: %r" % (error,), flush=True); print(traceback.format_exc(), flush=True); log("scenario-fail exception=%r" % (error,))
finally:
    try:
        close_task()
        for document in list(App.listDocuments().values()):
            try: App.closeDocument(document.Name)
            except Exception: pass
        events(); log("script-end exit-code=%d" % exit_code); window = Gui.getMainWindow()
        if window is not None: window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None: app.quit()
    except BaseException:
        pass
if exit_code:
    raise SystemExit(exit_code)
