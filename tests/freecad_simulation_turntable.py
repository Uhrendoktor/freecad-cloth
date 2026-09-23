"""Render a deterministic simple blanket-over-cube simulation for the README."""
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
        raise RuntimeError("failed screenshot: %s" % state)
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(header[16:20], "big") != 640 or int.from_bytes(header[20:24], "big") != 480:
        raise RuntimeError("invalid PNG capture for %s" % state)


def combined_center(objects):
    boxes = []
    for obj in objects:
        mesh = getattr(obj, "Mesh", None)
        bound = getattr(mesh, "BoundBox", None) if mesh is not None else None
        if bound is None:
            shape = getattr(obj, "Shape", None)
            bound = getattr(shape, "BoundBox", None) if shape is not None else None
        if bound is not None and bound.isValid():
            boxes.append(bound)
    if not boxes:
        raise RuntimeError("no visible geometry bounds")
    return App.Vector(
        0.5 * (min(b.XMin for b in boxes) + max(b.XMax for b in boxes)),
        0.5 * (min(b.YMin for b in boxes) + max(b.YMax for b in boxes)),
        0.5 * (min(b.ZMin for b in boxes) + max(b.ZMax for b in boxes)),
    )


def render_turntable(view, objects, frame_dir, frame_count=72):
    os.makedirs(frame_dir, exist_ok=True)
    frame_total = frame_count + 1
    center = combined_center(objects)
    target = coin.SbVec3f(center.x, center.y, center.z)
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    events()
    camera = view.getCameraNode()
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - target
    if base_offset.length() <= 0:
        raise RuntimeError("zero camera radius")
    up = coin.SbVec3f(0.0, 0.0, 1.0)
    for frame in range(frame_total):
        angle = 2.0 * pi * min(frame, frame_count) / frame_count
        camera.position = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle).multVec(base_offset) + target
        camera.pointAt(target, up)
        if hasattr(view, "redraw"):
            view.redraw()
        events()
        save_png(view, os.path.join(frame_dir, "frame-%03d.png" % frame), "turntable frame %03d" % frame)
    camera.position = base_position
    camera.pointAt(target, up)
    if hasattr(view, "redraw"):
        view.redraw()
    events()
    log("turntable-pass dir=%s frames=%d" % (frame_dir, frame_total))


def _make_rectangle_sketch(doc, name, width, height):
    import Part
    import Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    points = (
        (-0.5 * width, -0.5 * height),
        (0.5 * width, -0.5 * height),
        (0.5 * width, 0.5 * height),
        (-0.5 * width, 0.5 * height),
    )
    sketch.addGeometry([
        Part.LineSegment(
            App.Vector(points[i][0], points[i][1], 0),
            App.Vector(points[(i + 1) % 4][0], points[(i + 1) % 4][1], 0),
        ) for i in range(4)
    ], False)
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)
    ])
    doc.recompute()
    return sketch


def _adopt_sketch(sketch, name):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=5.0, grainline=0.0)
    piece.Label = name
    App.ActiveDocument.recompute()
    if piece.Sketch is not sketch:
        raise RuntimeError("pattern piece did not retain native sketch")
    return piece


def _style_mesh(obj):
    obj.ViewObject.DisplayMode = "Shaded"
    obj.ViewObject.ShapeColor = (0.22, 0.48, 0.86)
    obj.ViewObject.LineWidth = 1.0


def _nearest_pin_indices(panel_indices, positions, targets):
    available = list(panel_indices)
    result = []
    for target in targets:
        index = min(
            available,
            key=lambda i: (
                (positions[i][0] - target.x) ** 2
                + (positions[i][1] - target.y) ** 2
                + (positions[i][2] - target.z) ** 2
            ),
        )
        result.append(index)
        available.remove(index)
    return tuple(result)


def _center_z(points):
    if not points:
        raise RuntimeError("empty simulation particle set")
    return sum(float(p[2]) for p in points) / len(points)


def build_simulation_state(doc):
    from freecad_cloth.simulation.DrapeTarget import create_drape_target, refresh_drape_target
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene

    scene = create_quality_simulation_scene(doc)
    avatar = scene.AvatarProxy.SourceObject
    if avatar is not None:
        avatar.ViewObject.Visibility = False

    cube = doc.addObject("Part::Box", "BlanketCube")
    cube.Label = "Blanket Demo Cube"
    cube.Length = 240.0
    cube.Width = 160.0
    cube.Height = 120.0
    cube.Placement = App.Placement(App.Vector(-120.0, -80.0, 0.0), App.Rotation())
    cube.ViewObject.ShapeColor = (0.72, 0.72, 0.72)

    target = scene.DrapeTarget
    if target is None:
        target = create_drape_target(doc, cube, "FreeCAD Geometry", deflection=1.0, thickness=0.0)
        scene.DrapeTarget = target
    else:
        from freecad_cloth.simulation.DrapeTarget import assign_drape_target
        assign_drape_target(target, cube, "FreeCAD Geometry")
    refresh_drape_target(target)

    sketch = _make_rectangle_sketch(doc, "BlanketSource", 420.0, 320.0)
    blanket = _adopt_sketch(sketch, "Blanket")
    blanket.Placement = App.Placement(App.Vector(0.0, 0.0, 310.0), App.Rotation())
    blanket.Sketch.Placement = blanket.Placement

    scene.QualityPreset = "Balanced"
    scene.ParticleDistance = float(os.environ.get("CLOTH_BLANKET_PARTICLE_DISTANCE_MM", "20.0"))
    scene.SolverIterations = int(os.environ.get("CLOTH_BLANKET_SOLVER_ITERATIONS", "32"))
    scene.SolverSubsteps = int(os.environ.get("CLOTH_BLANKET_SOLVER_SUBSTEPS", "1"))
    scene.TimeStep = float(os.environ.get("CLOTH_BLANKET_TIMESTEP", str(1.0 / 120.0)))
    scene.StitchSamples = 4
    scene.GravityX = scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.8
    scene.ClothPieces = [blanket]

    doc.recompute()
    proxy = scene.Proxy._base_or_restore()
    panel = scene.DrapePanels[0]
    positions = tuple(proxy.backend.positions())
    indices = tuple(proxy.panel_indices[panel.Name])
    left = App.Vector(-210.0, -120.0, 310.0)
    right = App.Vector(210.0, -120.0, 310.0)
    pins = _nearest_pin_indices(indices, positions, (left, right))
    scene.PinSelection = [str(index) for index in pins]
    doc.recompute()
    initial_positions = tuple(scene.Proxy._base_or_restore().backend.positions())
    log("blanket-pins=%s" % (pins,))

    blanket.ViewObject.Visibility = True
    blanket.Sketch.ViewObject.Visibility = False
    panel.ViewObject.Visibility = False
    _style_mesh(panel)
    panel.Label = "Simulated Blanket"
    cube.ViewObject.Visibility = True
    doc.recompute()

    return scene, cube, blanket, panel, initial_positions


def main():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show()
    events()
    init_gui = os.path.join(ROOT, "InitGui.py")
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()

    doc = App.newDocument("ClothBlanketTurntable")
    try:
        scene, cube, blanket, panel, initial_positions = build_simulation_state(doc)
        view = Gui.activeDocument().activeView()
        objects = [cube, panel]
        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"))

        steps = int(os.environ.get("CLOTH_BLANKET_STEPS", "90"))
        scene.Steps = steps
        doc.recompute()
        events()
        if int(scene.Steps) != steps or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("blanket simulation did not reach a finite %d-step state" % steps)
        if panel.Mesh.CountFacets <= 50:
            raise RuntimeError("blanket drape mesh is too small")
        final_positions = tuple(scene.Proxy._base_or_restore().backend.positions())
        initial_z = _center_z(initial_positions)
        final_z = _center_z(final_positions)
        displacement = abs(final_z - initial_z)
        minimum_z = min(float(position[2]) for position in final_positions)
        cube_top = float(cube.Placement.Base.z) + float(cube.Height)
        log("blanket-motion-diagnostic max_centroid_displacement_mm=%.2f final_centroid_z_mm=%.2f min_z_mm=%.2f cube_top_z_mm=%.2f" % (
            displacement, final_z, minimum_z, cube_top,
        ))
        if displacement < 40.0:
            raise RuntimeError("blanket moved only %.2f mm; expected real draping motion" % displacement)
        if minimum_z > cube_top + 35.0:
            raise RuntimeError("blanket did not approach cube surface: min_z=%.2f cube_top=%.2f" % (minimum_z, cube_top))

        panel.ViewObject.Visibility = True
        cube.ViewObject.Visibility = True
        doc.recompute()
        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-draped-turntable-frames"))
        log("blanket-turntable-pass")
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
