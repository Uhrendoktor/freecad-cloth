# Copyright (C) 2026 FreeCAD Cloth contributors
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
from tests.support.freecad_input import wait_for_gui_ready
from tests.support.freecad_mesh_geometry import opposite_top_edge_vertices


import contextlib
import pathlib

from freecad_cloth.common.MeshValidation import validate_mesh
from freecad_cloth.common.VisualCaptureValidation import png_has_visible_content
from freecad_cloth.simulation.DrapeVisualSanity import (
    inspect_drape,
    maximum_box_penetration,
    mesh_shape_sanity,
)
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

# Keep the README turntable on the same geometry-appropriate collision path as
# the standalone blanket acceptance when the target is generic FreeCAD geometry.
os.environ.setdefault("CLOTH_PBD_COLLISION_MODE", "mesh")

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
BLANKET_SIZE = (
    200.0  # Validated 200 mm release fixture; keep pins/placement derived from this value.
)
BLANKET_PARTICLE_DISTANCE = (
    16.0  # Match the validated blanket-over-cube release fixture; contract requires >= 12 mm.
)
BLANKET_START_Z = 115.0  # Keep the 40 mm drape-motion gate robust with the pinned solver.
# The README fixture uses the same pinned PositionBasedDynamics mesh-collision runtime as the
# canonical turntable job and the validated 200 mm blanket visual example.
pathlib.Path(OUT).mkdir(exist_ok=True, parents=True)
LOG = os.path.join(OUT, "simulation-turntable-progress.log")
TURNTABLE_FRAMES = max(12, int(os.environ.get("CLOTH_TURNTABLE_FRAMES", "72")))


def log(message):
    with pathlib.Path(LOG).open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def _png_has_visible_content(path):
    """Validate turntable frames through the shared PNG decoder."""
    return png_has_visible_content(
        path,
        expected_width=640,
        expected_height=480,
        minimum_pixels=1000,
        pixel_threshold=245,
        require_all_channels_below=True,
    )


def save_png(view, path, state):
    deadline = time.monotonic() + 2.0
    capture_index = 0
    while time.monotonic() < deadline:
        capture_index += 1
        temp_path = path + ".capture-%d.tmp.png" % capture_index
        try:
            if hasattr(view, "redraw"):
                view.redraw()
            events()
            time.sleep(0.05)
            if hasattr(view, "redraw"):
                view.redraw()
            events()
            view.saveImage(temp_path, 640, 480, "White")
            if pathlib.Path(temp_path).is_file() and pathlib.Path(temp_path).stat().st_size >= 1000:
                with pathlib.Path(temp_path).open("rb") as handle:
                    header = handle.read(24)
                valid_dimensions = (
                    header[:8] == b"\x89PNG\r\n\x1a\n"
                    and int.from_bytes(header[16:20], "big") == 640
                    and int.from_bytes(header[20:24], "big") == 480
                )
                if valid_dimensions and _png_has_visible_content(temp_path):
                    pathlib.Path(temp_path).replace(path)
                    log("png-capture=passed state=%s attempts=%d" % (state, capture_index))
                    return
            log("png-capture=retry state=%s attempts=%d" % (state, capture_index))
        finally:
            with contextlib.suppress(FileNotFoundError):
                pathlib.Path(temp_path).unlink()
        time.sleep(0.05)
    msg = f"PNG capture contains no visible rendered content for {state}"
    raise RuntimeError(msg)


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
        msg = "no visible geometry bounds"
        raise RuntimeError(msg)
    return App.Vector(
        0.5 * (min(b.XMin for b in boxes) + max(b.XMax for b in boxes)),
        0.5 * (min(b.YMin for b in boxes) + max(b.YMax for b in boxes)),
        0.5 * (min(b.ZMin for b in boxes) + max(b.ZMax for b in boxes)),
    )


def render_turntable(view, objects, frame_dir, frame_count=72):
    pathlib.Path(frame_dir).mkdir(exist_ok=True, parents=True)
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
    stage_started = time.monotonic()
    frame_total = frame_count + 1
    log("turntable-stage-start dir=%s frames=%d" % (frame_dir, frame_total))
    center = combined_center(objects)
    target = coin.SbVec3f(center.x, center.y, center.z)
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    log("camera-presentation=passed projection=Orthographic orientation=Axonometric")
    events()
    camera = view.getCameraNode()
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - target
    if base_offset.length() <= 0:
        msg = "zero camera radius"
        raise RuntimeError(msg)
    up = coin.SbVec3f(0.0, 0.0, 1.0)
    frame_hashes = []
    start_angle = pi / 2.0
    for frame in range(frame_total):
        # Start from a cloth-visible angle, then cover a full 360 degrees
        # without duplicating frame 000 at the end.
        angle = start_angle + 2.0 * pi * frame / frame_total
        camera.position = (
            coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle).multVec(base_offset) + target
        )
        camera.pointAt(target, up)
        if hasattr(view, "redraw"):
            view.redraw()
        events()
        frame_path = os.path.join(frame_dir, "frame-%03d.png" % frame)
        save_png(view, frame_path, "turntable frame %03d" % frame)
        with pathlib.Path(frame_path).open("rb") as handle:
            frame_hashes.append(hashlib.sha256(handle.read()).hexdigest())
        if frame == 0 or (frame + 1) % 18 == 0 or frame == frame_total - 1:
            log(
                "turntable-progress dir=%s frame=%d/%d elapsed_ms=%.1f"
                % (frame_dir, frame + 1, frame_total, 1000.0 * (time.monotonic() - stage_started))
            )
    if len(frame_hashes) != frame_total or len(set(frame_hashes)) != frame_total:
        msg = f"turntable frames are not all distinct: {frame_dir}"
        raise RuntimeError(msg)
    camera.position = base_position
    camera.pointAt(target, up)
    if hasattr(view, "redraw"):
        view.redraw()
    events()
    log(
        "turntable-stage-pass dir=%s frames=%d elapsed_ms=%.1f"
        % (frame_dir, frame_total, 1000.0 * (time.monotonic() - stage_started))
    )
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
    sketch.addGeometry(
        [
            Part.LineSegment(
                App.Vector(points[i][0], points[i][1], 0),
                App.Vector(points[(i + 1) % 4][0], points[(i + 1) % 4][1], 0),
            )
            for i in range(4)
        ],
        False,
    )
    sketch.addConstraint(
        [Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)]
    )
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
        msg = "pattern piece did not retain native sketch"
        raise RuntimeError(msg)
    return piece


def _style_mesh(obj):
    obj.ViewObject.DisplayMode = "Shaded"
    obj.ViewObject.ShapeColor = (0.22, 0.48, 0.86)
    obj.ViewObject.LineWidth = 1.0


def _opposite_top_edge_pins(piece, panel_indices) -> tuple[tuple[int, int], float]:
    """Map top-edge mesh vertices into solver particle-index space.

    Args:
        piece: Authoritative pattern-piece object to tessellate.
        panel_indices: Mapping from mesh-local to solver particle indices.

    Returns:
        The two global pin indices and their horizontal span in millimetres.
    """
    mesh_positions, _, boundary = quality_piece_mesh(piece, 0.0, BLANKET_PARTICLE_DISTANCE)
    top_indices, span_mm = opposite_top_edge_vertices(mesh_positions, boundary, 0.75 * BLANKET_SIZE)
    return tuple(int(panel_indices[index]) for index in top_indices), span_mm


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
        msg = "empty simulation particle set"
        raise RuntimeError(msg)
    return sum(float(p[2]) for p in points) / len(points)


def validate_blanket_drape(panel, cube):

    vertices, triangles = panel.Mesh.Topology
    points = tuple((float(vertex.x), float(vertex.y), float(vertex.z)) for vertex in vertices)
    faces = tuple(tuple(int(index) for index in triangle) for triangle in triangles)
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
        msg = f"blanket mesh failed structural validation: {mesh_result!r}"
        raise RuntimeError(msg)
    if (
        not shape["finite"]
        or shape["edge_spike_ratio"] > 4.0
        or shape["spike_edge_fraction"] > 0.02
        or shape["footprint_aspect_ratio"] > 4.0
    ):
        msg = f"blanket mesh has spike/outlier geometry: {shape!r}"
        raise RuntimeError(msg)
    if not drape.finite or drape.state != "structurally-plausible":
        msg = f"blanket drape sanity check failed: {drape!r}"
        raise RuntimeError(msg)
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
    stage_started = time.monotonic()
    log(
        f"stage=scene-build-start particle_distance={BLANKET_PARTICLE_DISTANCE:.1f} solver_iterations=4 solver_substeps=1"
    )
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    from freecad_cloth.simulation.DrapeCommands import set_drape_target_source
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    from freecad_cloth.simulation.SimulationQualityRuntime import (
        QualitySimulationProxy,
        ensure_quality_properties,
    )

    sketch = _make_rectangle_sketch(doc, "BlanketSource", BLANKET_SIZE, BLANKET_SIZE)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    blanket = create_pattern_piece_from_selected_sketch(
        name="Blanket", allowance=0.0, grainline=0.0
    )
    if blanket.Sketch is not sketch:
        msg = "pattern piece did not retain native sketch"
        raise RuntimeError(msg)
    placement = App.Placement(App.Vector(0.0, 0.0, BLANKET_START_Z), App.Rotation())
    blanket.Placement = placement
    blanket.Sketch.Placement = placement

    cube = doc.addObject("Part::Feature", "BlanketTargetCube")
    cube.Label = "Collision Target — Cube"
    cube.Shape = __import__("Part").makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
    doc.recompute()

    scene = create_simulation_scene(doc)
    set_drape_target_source(scene, cube, thickness=2.0, deflection=1.0)
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.ClothPieces = [blanket]
    scene.StartHeight = 0.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.TimeStep = 1.0 / 60.0
    scene.ParticleDistance = max(BLANKET_PARTICLE_DISTANCE, float(scene.ParticleDistance))
    scene.SolverIterations = 4
    scene.SolverSubsteps = 1
    scene.FabricColor = (0.14, 0.32, 0.78)
    scene.FabricSpecular = 0.70
    scene.FabricRoughness = 0.20
    scene.FabricTransparency = 12
    doc.recompute()

    panels = list(scene.DrapePanels)
    if len(panels) != 1:
        msg = "blanket turntable must create one drape panel"
        raise RuntimeError(msg)
    panel = panels[0]
    proxy = scene.Proxy._base_or_restore()
    positions = tuple(proxy.backend.positions())
    panel_indices = tuple(proxy.panel_indices[panel.Name])
    pins, span = _opposite_top_edge_pins(blanket, panel_indices)
    scene.PinSelection = [str(index) for index in pins]
    log(f"blanket-pins=passed opposite-corners span={span:.3f} indices={pins}")
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
    positions = tuple(scene.Proxy._base_or_restore().backend.positions())
    log(
        "stage=scene-build-pass particles=%d particle_distance=%.1f solver_iterations=%d solver_substeps=%d elapsed_ms=%.1f"
        % (
            len(positions),
            float(scene.ParticleDistance),
            int(scene.SolverIterations),
            int(scene.SolverSubsteps),
            1000.0 * (time.monotonic() - stage_started),
        )
    )
    return scene, cube, blanket, panel, positions


def main():
    total_started = time.monotonic()
    documentation_capture_only = os.environ.get(
        "CLOTH_DOCUMENTATION_CAPTURE_ONLY", ""
    ).strip().lower() in {"1", "true", "yes"}
    with pathlib.Path(LOG).open("w", encoding="utf-8"):
        pass
    window = wait_for_gui_ready(Gui, events)
    log(
        "stage=fixture-start backend=pbd collision_mode={} pbd_substeps={} steps={}".format(
            os.environ.get("CLOTH_PBD_COLLISION_MODE", "mesh"),
            os.environ.get("CLOTH_PBD_SUBSTEPS", "1"),
            os.environ.get("CLOTH_BLANKET_STEPS", "120"),
        )
    )
    init_gui = os.path.join(ROOT, "InitGui.py")
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        with pathlib.Path(init_gui).open(encoding="utf-8") as handle:
            exec(handle.read(), globals(), globals())
    events()

    doc = App.newDocument("ClothBlanketTurntable")
    try:
        scene, cube, _blanket, panel, initial_positions = build_simulation_state(doc)
        view = Gui.activeDocument().activeView()
        arranged_objects = [cube, panel]
        arranged_started = time.monotonic()
        render_turntable(
            view,
            arranged_objects,
            os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"),
            frame_count=TURNTABLE_FRAMES,
        )
        log(
            "stage=arranged-render-pass frames=%d elapsed_ms=%.1f"
            % (TURNTABLE_FRAMES + 1, 1000.0 * (time.monotonic() - arranged_started))
        )

        steps = int(os.environ.get("CLOTH_BLANKET_STEPS", "120"))
        simulation_started = time.monotonic()
        log(
            "stage=simulation-start steps=%d particle_distance=%.1f solver_iterations=%d solver_substeps=%d pbd_substeps=%s"
            % (
                steps,
                float(scene.ParticleDistance),
                int(scene.SolverIterations),
                int(scene.SolverSubsteps),
                os.environ.get("CLOTH_PBD_SUBSTEPS", "1"),
            )
        )
        scene.Steps = steps
        doc.recompute()
        events()
        if documentation_capture_only:
            log(
                "stage=documentation-capture-only steps=%d simulated_time_s=%.3f"
                % (steps, float(scene.SimulatedTime))
            )
        else:
            if (
                int(scene.Steps) != steps
                or float(scene.SimulatedTime) <= 0.0
                or not bool(scene.FiniteState)
            ):
                raise RuntimeError(
                    "blanket simulation did not reach a finite %d-step state" % steps
                )
            if panel.Mesh.CountFacets <= 50:
                msg = "blanket drape mesh is too small"
                raise RuntimeError(msg)
            final_positions = tuple(scene.Proxy._base_or_restore().backend.positions())
            max_penetration = maximum_box_penetration(
                final_positions,
                (
                    float(cube.Shape.BoundBox.XMin),
                    float(cube.Shape.BoundBox.XMax),
                    float(cube.Shape.BoundBox.YMin),
                    float(cube.Shape.BoundBox.YMax),
                    float(cube.Shape.BoundBox.ZMin),
                    float(cube.Shape.BoundBox.ZMax),
                ),
            )
            log(f"collision-penetration=passed max_penetration_mm={max_penetration:.3f}")
            if max_penetration > 3.0:
                msg = f"blanket penetrated collision cube by {max_penetration:.2f} mm"
                raise RuntimeError(msg)
            log(
                "blanket-turntable-config particle_distance=%.1f iterations=%d particles=%d steps=%d"
                % (
                    float(scene.ParticleDistance),
                    int(scene.SolverIterations),
                    int(scene.ParticleCount),
                    steps,
                )
            )
            initial_z = _center_z(initial_positions)
            final_z = _center_z(final_positions)
            displacement = abs(final_z - initial_z)
            minimum_z = min(float(position[2]) for position in final_positions)
            cube_top = float(cube.Shape.BoundBox.ZMax)
            log(
                f"blanket-motion-diagnostic max_centroid_displacement_mm={displacement:.2f} final_centroid_z_mm={final_z:.2f} min_z_mm={minimum_z:.2f} cube_top_z_mm={cube_top:.2f}"
            )
            log(
                "stage=simulation-pass steps=%d simulated_time_s=%.3f elapsed_ms=%.1f"
                % (
                    steps,
                    float(scene.SimulatedTime),
                    1000.0 * (time.monotonic() - simulation_started),
                )
            )
            if displacement < 40.0:
                msg = f"blanket moved only {displacement:.2f} mm; expected real draping motion"
                raise RuntimeError(msg)
            if minimum_z > cube_top + 35.0:
                msg = f"blanket did not approach cube surface: min_z={minimum_z:.2f} cube_top={cube_top:.2f}"
                raise RuntimeError(msg)

            validation_started = time.monotonic()
            log("stage=validation-start")
            panel.ViewObject.Visibility = True
            cube.ViewObject.Visibility = True
            doc.recompute()
            _shape, drape = validate_blanket_drape(panel, cube)
            log(
                "stage=validation-pass state={} clearance_mm={} elapsed_ms={:.1f}".format(
                    drape.state,
                    "none"
                    if drape.target_vertex_clearance is None
                    else f"{drape.target_vertex_clearance:.2f}",
                    1000.0 * (time.monotonic() - validation_started),
                )
            )
        draped_started = time.monotonic()
        render_turntable(
            view,
            [cube, panel],
            os.path.join(OUT, "cloth-simulation-draped-turntable-frames"),
            frame_count=TURNTABLE_FRAMES,
        )
        log(
            "stage=draped-render-pass frames=%d elapsed_ms=%.1f"
            % (TURNTABLE_FRAMES + 1, 1000.0 * (time.monotonic() - draped_started))
        )
        log("blanket-turntable-pass")
        log("stage=total-pass elapsed_ms=%.1f" % (1000.0 * (time.monotonic() - total_started)))
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
    print(f"SIMULATION TURNTABLE FAILURE: {error!r}", flush=True)
    print(traceback.format_exc(), flush=True)
    log(f"simulation-turntable-fail exception={error!r}")
    os._exit(1)
