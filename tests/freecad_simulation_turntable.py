"""Render deterministic tunic turntables with seam overlays."""
import ast
import os
import sys
import traceback
from math import pi

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from pivy import coin

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "simulation-turntable-progress.log")


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def save_png(view, path, state):
    view.saveImage(path, 640, 480, "White")
    if not os.path.isfile(path) or os.path.getsize(path) < 5000:
        raise RuntimeError("failed screenshot: %s" % path)
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(header[16:20], "big") != 640 or int.from_bytes(header[20:24], "big") != 480:
        raise RuntimeError("invalid PNG capture for %s" % state)


def combined_center(objects):
    boxes = [o.Mesh.BoundBox for o in objects if getattr(o, "Mesh", None) is not None and o.Mesh.BoundBox.isValid()]
    if not boxes:
        raise RuntimeError("no visible mesh bounds")
    return App.Vector(0.5 * (min(b.XMin for b in boxes) + max(b.XMax for b in boxes)), 0.5 * (min(b.YMin for b in boxes) + max(b.YMax for b in boxes)), 0.5 * (min(b.ZMin for b in boxes) + max(b.ZMax for b in boxes)))


def render_turntable(view, objects, frame_dir, frame_count=72):
    os.makedirs(frame_dir, exist_ok=True)
    center = combined_center(objects)
    target = coin.SbVec3f(center.x, center.y, center.z)
    view.setCameraType("Orthographic")
    view.viewFront(); view.fitAll(); view.zoomIn(); events()
    camera = view.getCameraNode()
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - target
    if base_offset.length() <= 0:
        raise RuntimeError("zero camera radius")
    up = coin.SbVec3f(0.0, 0.0, 1.0)
    for frame in range(frame_count + 1):
        angle = 2.0 * pi * min(frame, frame_count) / frame_count
        camera.position = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle).multVec(base_offset) + target
        camera.pointAt(target, up); events()
        save_png(view, os.path.join(frame_dir, "frame-%03d.png" % frame), "turntable frame %03d" % frame)
    camera.position = base_position; camera.pointAt(target, up); events()
    log("turntable-pass dir=%s frames=%d" % (frame_dir, frame_count + 1))


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width):
    import Part, Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    points = [(0.0, 0.0), (hem_width, 0.0), (panel_width, 0.82 * garment_height), (0.86 * panel_width, 0.97 * garment_height), (0.64 * panel_width, garment_height), (0.36 * panel_width, garment_height), (0.14 * panel_width, 0.97 * garment_height), (0.0, 0.82 * garment_height)]
    sketch.addGeometry([Part.LineSegment(App.Vector(points[i][0], points[i][1], 0), App.Vector(points[(i + 1) % 8][0], points[(i + 1) % 8][1], 0)) for i in range(8)], False)
    sketch.addConstraint([Sketcher.Constraint("Coincident", i, 2, (i + 1) % 8, 1) for i in range(8)])
    doc.recompute()
    return sketch, points


def _adopt_sketch(sketch, name):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=10.0, grainline=0.0)
    piece.Label = name
    App.ActiveDocument.recompute()
    if piece.Sketch is not sketch:
        raise RuntimeError("pattern piece did not retain native sketch")
    return piece


def style_mesh(obj, label):
    obj.Label = label
    obj.ViewObject.DisplayMode = "Flat Lines"
    obj.ViewObject.ShapeColor = (0.86, 0.20, 0.10)
    obj.ViewObject.LineColor = (0.20, 0.02, 0.01)
    obj.ViewObject.LineWidth = 1.5


def _outline(piece):
    return [(float(x), float(y)) for x, y in ast.literal_eval(str(piece.SewingOutline))]


def _seam_overlay(doc, name, seam_records, simulated=None):
    import Part
    segments = []
    for seam, piece_a, piece_b in seam_records:
        for piece, edge, start, end, reverse in ((piece_a, int(seam.EdgeA), float(seam.StartA), float(seam.EndA), False), (piece_b, int(seam.EdgeB), float(seam.StartB), float(seam.EndB), bool(seam.ReversedB))):
            points = _outline(piece)
            a, b = points[edge], points[(edge + 1) % len(points)]
            if simulated is None:
                def point(t):
                    local = App.Vector(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 2.0)
                    return piece.Placement.multVec(local)
            else:
                vertices = simulated[piece.Name]
                edge_a, edge_b = vertices[edge], vertices[(edge + 1) % len(vertices)]
                def point(t):
                    return App.Vector(edge_a.x + (edge_b.x - edge_a.x) * t, edge_a.y + (edge_b.y - edge_a.y) * t, edge_a.z + (edge_b.z - edge_a.z) * t + 2.0)
            if reverse:
                start, end = 1.0 - end, 1.0 - start
            segments.append(Part.makeLine(point(start), point(end)))
    obj = doc.getObject(name) or doc.addObject("Part::Feature", name)
    obj.Label = "Tunic seams — %s" % ("simulated" if simulated is not None else "authored")
    obj.Shape = Part.makeCompound(segments) if segments else Part.Shape()
    obj.ViewObject.LineColor = (1.0, 0.72, 0.05)
    obj.ViewObject.LineWidth = 5.0
    obj.ViewObject.DisplayMode = "Flat Lines"
    obj.ViewObject.Visibility = True
    return obj


def _boundary_points(panel, count):
    points = panel.Mesh.Points
    if len(points) < count:
        raise RuntimeError("drape panel exposes fewer mesh points than pattern boundary vertices")
    return tuple(points[i] for i in range(count))


def build_simulation_state(doc):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternMesh import triangulate
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    scene = create_quality_simulation_scene(doc)
    avatar = scene.AvatarProxy.SourceObject
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("missing production ClothAvatar")
    box = avatar.Mesh.BoundBox
    torso_width = float(box.XMax - box.XMin)
    y_span = float(box.YMax - box.YMin)
    z_span = float(box.ZMax - box.ZMin)
    panel_width = max(420.0, min(560.0, 0.50 * torso_width + 35.0))
    hem_width = max(440.0, min(590.0, 0.52 * torso_width + 35.0))
    hem_z = box.ZMin + 0.40 * z_span
    garment_height = max(560.0, box.ZMin + 0.76 * z_span - hem_z)
    clearance = max(6.0, 0.02 * max(120.0, min(260.0, y_span)))
    rotation = App.Rotation(App.Vector(1, 0, 0), 90.0)
    def make_piece(name, y):
        sketch, outline = _make_tunic_sketch(doc, name + "Source", panel_width, garment_height, hem_width)
        piece = _adopt_sketch(sketch, name)
        piece.Placement = App.Placement(App.Vector((box.XMin + box.XMax) * 0.5 - hem_width / 2.0, y, hem_z), rotation)
        piece.Sketch.Placement = piece.Placement
        return piece, outline
    front, front_outline = make_piece("VisualTunicFront", box.YMax + clearance)
    back, back_outline = make_piece("VisualTunicBack", box.YMin - clearance)
    seam_records = []
    for ea, eb, seam_id in ((1, 1, "TunicRightSide"), (2, 2, "TunicRightShoulder"), (6, 6, "TunicLeftShoulder"), (7, 7, "TunicLeftSide")):
        seam = Seam(str(front.PieceId), ea, str(back.PieceId), eb, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        seam_records.append((seam_obj, front, back))
    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = 22.0
    scene.SolverIterations = 12
    scene.SolverSubsteps = 2
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.80
    scene.ClothPieces = [front, back]
    refresh_drape_target(scene.DrapeTarget)
    doc.recompute()
    def pins(piece, outline):
        points = [(float(x), float(y)) for x, y in outline]
        segments = [LineSegment("%s:edge:%d" % (piece.PieceId, i), points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
        mesh = triangulate(ParametricPattern(segments))
        h = max(y for _, y in points)
        return tuple(i for i in mesh.boundary_vertex_indices if mesh.vertices[i][1] >= 0.96 * h)
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
    front_positions, _, _ = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    scene.PinSelection = [str(i) for i in pins(front, front_outline)] + [str(len(front_positions) + i) for i in pins(back, back_outline)]
    doc.recompute()
    for source in (front, back):
        source.ViewObject.Visibility = False
        source.Sketch.ViewObject.Visibility = False
    for seam_obj, _, _ in seam_records:
        seam_obj.ViewObject.Visibility = False
    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels")
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back")):
        style_mesh(panel, label); panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    authored = _seam_overlay(doc, "TunicSeamsAuthored", seam_records)
    authored.ViewObject.Visibility = True
    return scene, avatar, panels, seam_records, authored, (front, back)


def main():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show(); events()
    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()
    doc = App.newDocument("ClothSimulationTurntable")
    try:
        scene, avatar, panels, seam_records, authored, pieces = build_simulation_state(doc)
        view = Gui.activeDocument().activeView(); view.setCameraType("Orthographic")
        objects = [avatar] + panels
        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"))
        authored.ViewObject.Visibility = False
        from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
        simulation_panel = SimulationQualityTaskPanel(scene)
        for batch in (10, 10, 10):
            simulation_panel.step(batch); doc.recompute(); events()
        if int(scene.Steps) != 30 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("simulation did not reach a finite 30-step state")
        if any(panel.Mesh.CountFacets <= 10 for panel in panels):
            raise RuntimeError("draped tunic panel mesh is empty")
        front, back = pieces
        simulated = {
            front.Name: _boundary_points(panels[0], len(_outline(front))),
            back.Name: _boundary_points(panels[1], len(_outline(back))),
        }
        _seam_overlay(doc, "TunicSeamsSimulated", seam_records, simulated)
        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-draped-turntable-frames"))
        log("simulation-turntable-pass")
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        events(); window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None: app.quit()


try:
    main()
except BaseException as error:
    print("SIMULATION TURNTABLE FAILURE: %r" % (error,), flush=True)
    print(traceback.format_exc(), flush=True)
    log("simulation-turntable-fail exception=%r" % (error,))
    raise
# trigger