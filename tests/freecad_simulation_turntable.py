"""Render deterministic 360-degree turntables for arranged and draped simulation states."""
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


def save_png(view, path, width=640, height=480, state="capture"):
    view.saveImage(path, width, height, "White")
    if not os.path.isfile(path) or os.path.getsize(path) < 5000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("invalid PNG capture for %s" % state)
    rendered_width = int.from_bytes(header[16:20], "big")
    rendered_height = int.from_bytes(header[20:24], "big")
    if (rendered_width, rendered_height) != (width, height):
        raise RuntimeError(
            "invalid rendered dimensions for %s: %sx%s"
            % (state, rendered_width, rendered_height)
        )


def combined_center(objects):
    boxes = []
    for obj in objects:
        mesh = getattr(obj, "Mesh", None)
        if mesh is None:
            continue
        box = mesh.BoundBox
        if box.isValid():
            boxes.append(box)
    if not boxes:
        raise RuntimeError("simulation turntable has no visible mesh bounds")
    return App.Vector(
        0.5 * (min(box.XMin for box in boxes) + max(box.XMax for box in boxes)),
        0.5 * (min(box.YMin for box in boxes) + max(box.YMax for box in boxes)),
        0.5 * (min(box.ZMin for box in boxes) + max(box.ZMax for box in boxes)),
    )


def render_turntable(view, objects, frame_dir, frame_count=72):
    os.makedirs(frame_dir, exist_ok=True)
    center = combined_center(objects)
    center_coin = coin.SbVec3f(center.x, center.y, center.z)

    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    view.zoomIn()
    events()

    camera = view.getCameraNode()
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - center_coin
    if base_offset.length() <= 0:
        raise RuntimeError("simulation turntable camera radius is zero")

    up = coin.SbVec3f(0.0, 0.0, 1.0)
    camera.pointAt(center_coin, up)
    log("turntable-start dir=%s frames=%d radius=%.4f" % (frame_dir, frame_count, base_offset.length()))

    for frame in range(frame_count):
        angle = 2.0 * pi * frame / frame_count
        rotation = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle)
        camera.position = rotation.multVec(base_offset) + center_coin
        camera.pointAt(center_coin, up)
        events()
        save_png(
            view,
            os.path.join(frame_dir, "frame-%03d.png" % frame),
            640,
            480,
            "simulation turntable frame %03d" % frame,
        )

    camera.position = base_position
    camera.pointAt(center_coin, up)
    events()
    save_png(
        view,
        os.path.join(frame_dir, "frame-%03d.png" % frame_count),
        640,
        480,
        "simulation turntable closing frame",
    )
    log("turntable-pass dir=%s frames=%d" % (frame_dir, frame_count + 1))


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width, neckline_ratio):
    import Part, Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (panel_width, 0.82 * garment_height),
        (0.86 * panel_width, 0.97 * garment_height),
        (neckline_ratio * panel_width, garment_height),
        ((1.0 - neckline_ratio) * panel_width, garment_height),
        (0.14 * panel_width, 0.97 * garment_height),
        (0.00, 0.82 * garment_height),
    ]
    geometry = [
        Part.LineSegment(
            App.Vector(points[i][0], points[i][1], 0),
            App.Vector(points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1], 0),
        )
        for i in range(len(points))
    ]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 4, 1),
        Sketcher.Constraint("Coincident", 4, 2, 5, 1),
        Sketcher.Constraint("Coincident", 5, 2, 6, 1),
        Sketcher.Constraint("Coincident", 6, 2, 7, 1),
        Sketcher.Constraint("Coincident", 7, 2, 0, 1),
    ])
    doc.recompute()
    return sketch, points


def _adopt_sketch(sketch, name, allowance, grainline):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=allowance, grainline=grainline)
    piece.Label = name
    App.ActiveDocument.recompute()
    if piece.Sketch is not sketch:
        raise RuntimeError("Cloth PatternPiece did not retain the selected native Sketcher source")
    return piece


def style_mesh(obj, label):
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.ShapeColor = (0.86, 0.20, 0.10)
        obj.ViewObject.LineColor = (0.20, 0.02, 0.01)
        obj.ViewObject.LineWidth = 1.5
    except (AttributeError, TypeError, ValueError):
        pass


def build_simulation_state(doc):
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target

    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if target is None:
        raise RuntimeError("visual fixture did not create DrapeTarget")

    box = avatar.Mesh.BoundBox
    x_mid = (box.XMin + box.XMax) / 2.0
    y_span = box.YMax - box.YMin
    z_span = box.ZMax - box.ZMin
    chest = 980.0
    hip = 1020.0
    ease = 55.0
    panel_width = max(420.0, 0.50 * chest + ease)
    hem_width = max(450.0, 0.50 * hip + ease)
    shoulder_z = box.ZMin + 0.76 * z_span
    hem_z = box.ZMin + 0.40 * z_span
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(6.0, 0.02 * body_depth)
    front_y = box.YMin - clearance
    back_y = box.YMax + clearance
    rotation = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def make_piece(name, y, neckline_ratio):
        sketch, outline = _make_tunic_sketch(doc, name + "Source", panel_width, garment_height, hem_width, neckline_ratio)
        piece = _adopt_sketch(sketch, name, 10.0, 0.0)
        piece.Label = name
        piece.Placement = App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rotation)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    front, front_outline = make_piece("VisualTunicFront", front_y, 0.64)
    back, back_outline = make_piece("VisualTunicBack", back_y, 0.68)
    # Keep only the authored shoulder seams in the coarse visual fixture. The side
    # stitches cross the avatar volume and can inject a non-physical upward impulse
    # into the back panel during the low-resolution XPBD turntable solve.
    for edge_a, edge_b, seam_id in (
        (2, 6, "TunicRightShoulder"),
        (6, 2, "TunicLeftShoulder"),
    ):
        add_seam(doc, Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly"))

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
    refresh_drape_target(target)
    doc.recompute()

    def local_boundary(piece, outline):
        points = [(float(x), float(y)) for x, y in outline]
        segments = [
            LineSegment("%s:edge:%d" % (piece.PieceId, i), points[i], points[(i + 1) % len(points)])
            for i in range(len(points))
        ]
        mesh = triangulate(ParametricPattern(segments))
        h = max(y for _, y in points)
        pins = tuple(
            i
            for i in mesh.boundary_vertex_indices
            if float(mesh.vertices[i][1]) >= 0.86 * h - 1e-6
            and (float(mesh.vertices[i][0]) <= 0.32 * panel_width + 1e-6 or float(mesh.vertices[i][0]) >= 0.68 * panel_width - 1e-6)
        )
        return mesh, pins

    fmesh, front_pins = local_boundary(front, front_outline)
    _, back_pins_local = local_boundary(back, back_outline)
    front_positions, _front_triangles, _front_boundary = __import__("freecad_cloth.simulation.SimulationMeshQuality", fromlist=["quality_piece_mesh"]).quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_pins = tuple(len(front_positions) + i for i in back_pins_local)
    scene.PinSelection = [str(i) for i in front_pins + back_pins]
    doc.recompute()

    for source in (doc.getObject("VisualTunicFront"), doc.getObject("VisualTunicBack")):
        if source is not None:
            source.ViewObject.Visibility = False
        sketch = getattr(source, "Sketch", None) if source is not None else None
        if sketch is not None:
            sketch.ViewObject.Visibility = False

    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels, got %d" % len(panels))
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back")):
        style_mesh(panel, label)
        panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    return scene, avatar, panels


def main():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show()
    events()
    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()

    doc = App.newDocument("ClothSimulationTurntable")
    try:
        scene, avatar, panels = build_simulation_state(doc)
        view = Gui.activeDocument().activeView()
        view.setCameraType("Orthographic")
        objects = [avatar] + panels

        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"))

        from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
        simulation_panel = SimulationQualityTaskPanel(scene)
        for batch in (10, 10, 10):
            simulation_panel.step(batch)
            doc.recompute()
            events()
        if int(scene.Steps) != 30 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("simulation did not reach a finite 30-step state")
        if any(panel.Mesh.CountFacets <= 10 for panel in panels):
            raise RuntimeError("draped tunic panel mesh is empty")

        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-draped-turntable-frames"))
        log("simulation-turntable-pass")
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        events()
        window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


try:
    main()
except BaseException as error:
    print("SIMULATION TURNTABLE FAILURE: %r" % (error,), flush=True)
    print(traceback.format_exc(), flush=True)
    log("simulation-turntable-fail exception=%r" % (error,))
    raise