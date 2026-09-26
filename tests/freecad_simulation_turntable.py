"""Render a deterministic simple blanket-over-cube simulation for the README."""
import hashlib
import os
import sys
import time
import traceback
from math import pi

ROOT = "/workspace"

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from pivy import coin

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from freecad_cloth.common.DrapeVisualSanity import inspect_drape, mesh_shape_sanity
from freecad_cloth.common.MeshValidation import validate_mesh
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh


# Keep the README turntable on the same geometry-appropriate collision path as
# the standalone blanket acceptance when the target is generic FreeCAD geometry.
os.environ.setdefault("CLOTH_TISSU_COLLISION_MODE", "mesh")

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
BLANKET_SIZE = 200.0  # Validated 200 mm release fixture; keep pins/placement derived from this value.
# The README fixture uses the same pinned Tissu mesh-collision runtime as the
# canonical turntable job and the validated 200 mm blanket visual example.
os.environ["CLOTH_SIMULATION_BACKEND"] = "tissu"
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


def _png_has_visible_content(path):
    import struct
    import zlib

    raw = open(path, "rb").read()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    offset = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    while offset + 8 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
            if bit_depth != 8 or color_type not in (2, 6):
                return False
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    if width != 640 or height != 480 or bit_depth != 8 or color_type not in (2, 6) or not compressed:
        return False
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    data = zlib.decompress(bytes(compressed))
    if len(data) != (stride + 1) * height:
        return False
    previous = bytearray(stride)
    visible = 0
    index = 0
    for _ in range(height):
        filter_type = data[index]
        index += 1
        row = bytearray(data[index:index + stride])
        index += stride
        for col in range(stride):
            left = row[col - channels] if col >= channels else 0
            up = previous[col]
            up_left = previous[col - channels] if col >= channels else 0
            if filter_type == 1:
                row[col] = (row[col] + left) & 0xFF
            elif filter_type == 2:
                row[col] = (row[col] + up) & 0xFF
            elif filter_type == 3:
                row[col] = (row[col] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                row[col] = (row[col] + predictor) & 0xFF
            elif filter_type != 0:
                return False
        for pixel in range(width):
            base = pixel * channels
            if max(row[base:base + 3]) < 245:
                visible += 1
                if visible >= 1000:
                    return True
        previous = row
    return False


def wait_for_gui_ready(timeout_seconds=15.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        window = Gui.getMainWindow()
        if window is not None and window.isVisible():
            window.show()
            events()
            return window
        events()
        time.sleep(0.05)
    raise RuntimeError("FreeCAD GUI did not become visible within %.1fs" % timeout_seconds)


def save_png(view, path, state):
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if hasattr(view, "redraw"):
            view.redraw()
        events()
        view.saveImage(path, 640, 480, "White")
        if os.path.isfile(path) and os.path.getsize(path) >= 1000:
            with open(path, "rb") as handle:
                header = handle.read(24)
            valid_dimensions = (
                header[:8] == b"\x89PNG\r\n\x1a\n"
                and int.from_bytes(header[16:20], "big") == 640
                and int.from_bytes(header[20:24], "big") == 480
            )
            if valid_dimensions and _png_has_visible_content(path):
                return
        time.sleep(0.05)
    raise RuntimeError("PNG capture contains no visible rendered content for %s" % state)


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
    visible_names = {obj.Name for obj in objects}
    visibility = []
    doc = App.ActiveDocument
    if doc is not None:
        for obj in doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            if view_object is None:
                continue
            previous = bool(getattr(view_object, "Visibility", False))
            visibility.append((view_object, previous))
            view_object.Visibility = getattr(obj, "Name", None) in visible_names
    try:
        _render_turntable_isolated(view, objects, frame_dir, frame_count)
    finally:
        for view_object, previous in visibility:
            view_object.Visibility = previous


def _render_turntable_isolated(view, objects, frame_dir, frame_count=72):
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
    frame_hashes = []
    start_angle = pi / 2.0
    for frame in range(frame_total):
        # Start from a cloth-visible angle, then cover a full 360 degrees
        # without duplicating frame 000 at the end.
        angle = start_angle + 2.0 * pi * frame / frame_total
        camera.position = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle).multVec(base_offset) + target
        camera.pointAt(target, up)
        if hasattr(view, "redraw"):
            view.redraw()
        events()
        frame_path = os.path.join(frame_dir, "frame-%03d.png" % frame)
        save_png(view, frame_path, "turntable frame %03d" % frame)
        with open(frame_path, "rb") as handle:
            frame_hashes.append(hashlib.sha256(handle.read()).hexdigest())
    if len(frame_hashes) != frame_total or len(set(frame_hashes)) != frame_total:
        raise RuntimeError("turntable frames are not all distinct: %s" % frame_dir)
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


def _opposite_top_edge_pins(piece, positions, panel_indices):
    mesh_positions, _, boundary = quality_piece_mesh(piece, 0.0, 20.0)
    boundary_vertices = tuple(sorted(set(index for chain in boundary for index in chain), key=lambda index: index))
    if not boundary_vertices:
        raise RuntimeError("blanket quality mesh has no boundary vertices")
    top_y = max(float(mesh_positions[index][1]) for index in boundary_vertices)
    top_edge = tuple(index for index in boundary_vertices if abs(float(mesh_positions[index][1]) - top_y) <= 1e-9)
    if len(top_edge) < 2:
        raise RuntimeError("blanket top edge has fewer than two boundary vertices")
    top = (
        min(top_edge, key=lambda index: float(mesh_positions[index][0])),
        max(top_edge, key=lambda index: float(mesh_positions[index][0])),
    )
    span = abs(float(mesh_positions[top[1]][0]) - float(mesh_positions[top[0]][0]))
    if span < 0.75 * BLANKET_SIZE:
        raise RuntimeError("blanket pins are not opposite top-edge corners: span=%.3f" % span)
    return tuple(int(panel_indices[top_index]) for top_index in top), span


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


def validate_blanket_drape(panel, cube):
    from freecad_cloth.common.DrapeVisualSanity import inspect_drape, mesh_shape_sanity
    from freecad_cloth.common.MeshValidation import validate_mesh

    vertices, triangles = panel.Mesh.Topology
    points = tuple(
        (float(vertex.x), float(vertex.y), float(vertex.z))
        for vertex in vertices
    )
    faces = tuple(
        tuple(int(index) for index in triangle)
        for triangle in triangles
    )
    mesh_result = validate_mesh(points, faces, prefer_trimesh=False)
    shape = mesh_shape_sanity(points, faces)
    target_points = tuple(
        (float(vertex.Point.x), float(vertex.Point.y), float(vertex.Point.z))
        for vertex in cube.Shape.Vertexes
    )
    target_box = cube.Shape.BoundBox
    drape = inspect_drape(
        points,
        target_points,
        target_height=float(target_box.ZLength),
        target_width=max(float(target_box.XLength), float(target_box.YLength)),
    )
    if not mesh_result.finite or mesh_result.components != 1 or mesh_result.degenerate_faces:
        raise RuntimeError("blanket mesh failed structural validation: %r" % mesh_result)
    if (
        not shape["finite"]
        or shape["edge_spike_ratio"] > 4.0
        or shape["spike_edge_fraction"] > 0.02
        or shape["footprint_aspect_ratio"] > 4.0
    ):
        raise RuntimeError("blanket mesh has spike/outlier geometry: %r" % shape)
    if not drape.finite or drape.state != "structurally-plausible":
        raise RuntimeError("blanket drape sanity check failed: %r" % drape)
    log(
        "mesh-quality=passed vertices=%d faces=%d components=%d "
        "spikes=%.3f spike_fraction=%.6f aspect=%.3f drape=%s"
        % (
            mesh_result.vertices,
            mesh_result.faces,
            mesh_result.components,
            shape["edge_spike_ratio"],
            shape["spike_edge_fraction"],
            shape["footprint_aspect_ratio"],
            drape.state,
        )
    )
    return shape, drape


def build_simulation_state(doc):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy, ensure_quality_properties

    sketch = _make_rectangle_sketch(doc, "BlanketSource", BLANKET_SIZE, BLANKET_SIZE)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    blanket = create_pattern_piece_from_selected_sketch(name="Blanket", allowance=0.0, grainline=0.0)
    if blanket.Sketch is not sketch:
        raise RuntimeError("pattern piece did not retain native sketch")
    placement = App.Placement(App.Vector(-BLANKET_SIZE / 2.0, -BLANKET_SIZE / 2.0, 150.0), App.Rotation())
    blanket.Placement = placement
    blanket.Sketch.Placement = placement

    cube = doc.addObject("Part::Feature", "BlanketTargetCube")
    cube.Label = "Collision Target — Cube"
    cube.Shape = __import__("Part").makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
    doc.recompute()

    scene = create_simulation_scene(doc)
    set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.ClothPieces = [blanket]
    scene.StartHeight = 0.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.TimeStep = 1.0 / 60.0
    scene.ParticleDistance = max(12.0, float(scene.ParticleDistance))
    scene.SolverIterations = 4
    scene.FabricColor = (0.14, 0.32, 0.78)
    scene.FabricSpecular = 0.70
    scene.FabricRoughness = 0.20
    scene.FabricTransparency = 12
    doc.recompute()

    panels = list(scene.DrapePanels)
    if len(panels) != 1:
        raise RuntimeError("blanket turntable must create one drape panel")
    panel = panels[0]
    proxy = scene.Proxy._base_or_restore()
    positions = tuple(proxy.backend.positions())
    panel_indices = tuple(proxy.panel_indices[panel.Name])
    pins, span = _opposite_top_edge_pins(blanket, positions, panel_indices)
    scene.PinSelection = [str(index) for index in pins]
    log("blanket-pins=passed opposite-corners span=%.3f indices=%s" % (span, pins))
    doc.recompute()

    sketch.ViewObject.Visibility = False
    blanket.ViewObject.Visibility = False
    blanket.ViewObject.ShapeColor = (0.14, 0.32, 0.78)
    cube.ViewObject.ShapeColor = (0.62, 0.62, 0.62)
    panel.ViewObject.ShapeColor = (0.14, 0.32, 0.78)
    panel.ViewObject.DisplayMode = "Shaded"
    panel.ViewObject.Visibility = True
    cube.ViewObject.Visibility = True
    doc.recompute()
    return scene, cube, blanket, panel, tuple(scene.Proxy._base_or_restore().backend.positions())


def main():
    window = wait_for_gui_ready()
    init_gui = os.path.join(ROOT, "InitGui.py")
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()

    doc = App.newDocument("ClothBlanketTurntable")
    try:
        scene, cube, blanket, panel, initial_positions = build_simulation_state(doc)
        view = Gui.activeDocument().activeView()
        arranged_objects = [cube, panel]
        render_turntable(view, arranged_objects, os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"))

        steps = int(os.environ.get("CLOTH_BLANKET_STEPS", "120"))
        scene.Steps = steps
        doc.recompute()
        events()
        if int(scene.Steps) != steps or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("blanket simulation did not reach a finite %d-step state" % steps)
        if panel.Mesh.CountFacets <= 50:
            raise RuntimeError("blanket drape mesh is too small")
        final_positions = tuple(scene.Proxy._base_or_restore().backend.positions())
        log("blanket-turntable-config particle_distance=%.1f iterations=%d particles=%d steps=%d" % (float(scene.ParticleDistance), int(scene.SolverIterations), int(scene.ParticleCount), steps))
        initial_z = _center_z(initial_positions)
        final_z = _center_z(final_positions)
        displacement = abs(final_z - initial_z)
        minimum_z = min(float(position[2]) for position in final_positions)
        cube_top = float(cube.Shape.BoundBox.ZMax)
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
        validate_blanket_drape(panel, cube)

        render_turntable(view, [cube, panel], os.path.join(OUT, "cloth-simulation-draped-turntable-frames"))
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
