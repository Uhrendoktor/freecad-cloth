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
from freecad_cloth.sewing.SewingView import seam_color_map
from freecad_cloth.common.DrapeVisualSanity import mesh_shape_sanity
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
    return App.Vector(
        0.5 * (min(b.XMin for b in boxes) + max(b.XMax for b in boxes)),
        0.5 * (min(b.YMin for b in boxes) + max(b.YMax for b in boxes)),
        0.5 * (min(b.ZMin for b in boxes) + max(b.ZMax for b in boxes)),
    )


def render_turntable(view, objects, frame_dir, frame_count=72):
    os.makedirs(frame_dir, exist_ok=True)
    smoke = frame_count == 2
    effective_count = 2 if smoke else frame_count
    include_endpoint = not smoke
    frame_total = effective_count + 1 if include_endpoint else effective_count
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
    for frame in range(frame_total):
        angle = 2.0 * pi * min(frame, effective_count) / effective_count
        camera.position = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle).multVec(base_offset) + target
        camera.pointAt(target, up); events()
        save_png(view, os.path.join(frame_dir, "frame-%03d.png" % frame), "turntable frame %03d" % frame)
    camera.position = base_position; camera.pointAt(target, up); events()
    log("turntable-pass dir=%s frames=%d" % (frame_dir, frame_total))


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width, mirror_x=False):
    import Part, Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    raw_points = [
        (0.0, 0.0),
        (hem_width, 0.0),
        (panel_width, 0.82 * garment_height),
        (0.86 * panel_width, 0.97 * garment_height),
        (0.64 * panel_width, garment_height),
        (0.36 * panel_width, garment_height),
        (0.14 * panel_width, 0.97 * garment_height),
        (0.0, 0.82 * garment_height),
    ]
    points = [(hem_width - x, y) for x, y in raw_points] if mirror_x else raw_points
    sketch.addGeometry([
        Part.LineSegment(
            App.Vector(points[i][0], points[i][1], 0),
            App.Vector(points[(i + 1) % 8][0], points[(i + 1) % 8][1], 0),
        ) for i in range(8)
    ], False)
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", i, 2, (i + 1) % 8, 1) for i in range(8)
    ])
    doc.recompute()
    return sketch, points


def _adopt_sketch(sketch, name):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
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
    seam_ids = [str(getattr(seam, "SeamId", "")).strip() for seam, _, _ in seam_records]
    if not seam_ids or any(not seam_id for seam_id in seam_ids):
        raise RuntimeError("turntable seam overlay is missing semantic SeamId")
    if len(set(seam_ids)) != len(seam_ids):
        raise RuntimeError("turntable seam overlay contains duplicate SeamId values")
    colors = seam_color_map(seam_ids)
    if len(set(colors.values())) != len(seam_ids):
        raise RuntimeError("turntable seam palette did not produce distinct colors")

    overlays = []
    for index, (seam, piece_a, piece_b) in enumerate(seam_records):
        seam_id = str(getattr(seam, "SeamId", "")).strip()
        segments = []
        records = (
            (piece_a, int(seam.EdgeA), float(seam.StartA), float(seam.EndA), False),
            (piece_b, int(seam.EdgeB), float(seam.StartB), float(seam.EndB), bool(seam.ReversedB)),
        )
        for piece, edge, start, end, reverse in records:
            points = _outline(piece)
            a, b = points[edge], points[(edge + 1) % len(points)]
            if simulated is None:
                def point(t):
                    local = App.Vector(
                        a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t,
                        2.0,
                    )
                    return piece.Placement.multVec(local)
            else:
                payload = simulated[piece.Name]
                chain = payload["boundary_edges"][edge]
                positions = payload["positions"]
                sampled = _sample_boundary_chain(chain, positions, start, end, count=16)
                if reverse:
                    sampled = tuple(reversed(sampled))
                for left_point, right_point in zip(sampled, sampled[1:]):
                    segments.append(Part.makeLine(
                        App.Vector(left_point.x, left_point.y, left_point.z + 2.0),
                        App.Vector(right_point.x, right_point.y, right_point.z + 2.0),
                    ))
                continue
            if reverse:
                start, end = 1.0 - end, 1.0 - start
            segments.append(Part.makeLine(point(start), point(end)))

        obj_name = "%s%02d" % (name, index)
        obj = doc.getObject(obj_name) or doc.addObject("Part::Feature", obj_name)
        obj.Label = "Tunic seam %s — %s" % (seam_id, "simulated" if simulated is not None else "authored")
        obj.Shape = Part.makeCompound(segments) if segments else Part.Shape()
        obj.ViewObject.LineColor = colors[seam_id]
        obj.ViewObject.LineWidth = 5.0
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True
        overlays.append(obj)
    return overlays

def _sample_boundary_chain(indices, positions, start, end, count=16):
    if len(indices) < 2:
        raise RuntimeError("semantic drape boundary edge has fewer than two vertices")
    pts = [App.Vector(*positions[int(index)]) for index in indices]
    cumulative = [0.0]
    for left, right in zip(pts, pts[1:]):
        cumulative.append(cumulative[-1] + (right - left).Length)
    total = cumulative[-1]
    if total <= 1e-9:
        return (pts[0], pts[-1])
    out = []
    for sample in range(max(2, int(count))):
        u = float(start) + (float(end) - float(start)) * sample / float(max(1, count - 1))
        u = max(0.0, min(1.0, u))
        distance = u * total
        segment = min(
            range(len(pts) - 1),
            key=lambda i: abs(cumulative[i + 1] - distance) if cumulative[i] <= distance <= cumulative[i + 1]
            else min(abs(cumulative[i] - distance), abs(cumulative[i + 1] - distance)),
        )
        span = cumulative[segment + 1] - cumulative[segment]
        local = 0.0 if span <= 1e-9 else (distance - cumulative[segment]) / span
        out.append(pts[segment] + (pts[segment + 1] - pts[segment]) * local)
    return tuple(out)


def _semantic_simulated_boundaries(scene, panels, pieces):
    proxy = scene.Proxy._base_or_restore()
    positions = tuple(proxy.backend.positions())
    if not positions:
        raise RuntimeError("simulation produced no particle positions")
    result = {}
    for panel, piece in zip(panels, pieces):
        edge_chains = proxy.panel_boundary_edges.get(panel.Name)
        if not edge_chains:
            raise RuntimeError("simulation proxy lost semantic boundary provenance for %s" % panel.Name)
        result[piece.Name] = {
            "positions": positions,
            "boundary_edges": tuple(tuple(int(i) for i in edge) for edge in edge_chains),
        }
    return result


def _seam_endpoint_gap(simulated, seam_records):
    gaps = []
    for seam, piece_a, piece_b in seam_records:
        left = simulated[piece_a.Name]
        right = simulated[piece_b.Name]
        edge_a = left["boundary_edges"][int(seam.EdgeA)]
        edge_b = right["boundary_edges"][int(seam.EdgeB)]
        a = _sample_boundary_chain(edge_a, left["positions"], float(seam.StartA), float(seam.EndA), count=2)
        b = _sample_boundary_chain(edge_b, right["positions"], float(seam.StartB), float(seam.EndB), count=2)
        if bool(seam.ReversedB):
            b = tuple(reversed(b))
        for point_a, point_b in zip(a, b):
            gaps.append((point_a - point_b).Length)
    return max(gaps) if gaps else 0.0


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
    z_span = float(box.ZMax - box.ZMin)
    panel_width = max(390.0, min(500.0, 0.46 * torso_width + 28.0))
    hem_width = max(410.0, min(530.0, 0.48 * torso_width + 32.0))
    hem_z = box.ZMin + 0.40 * z_span
    garment_height = max(560.0, box.ZMin + 0.76 * z_span - hem_z)
    clearance = float(os.environ.get("CLOTH_TUNIC_CLEARANCE_MM", "10.0"))

    def make_piece(name, y, mirror_x=False):
        sketch, outline = _make_tunic_sketch(
            doc, name + "Source", panel_width, garment_height, hem_width, mirror_x=mirror_x
        )
        piece = _adopt_sketch(sketch, name)
        rotation = App.Rotation(App.Vector(1, 0, 0), 90.0)
        piece.Placement = App.Placement(
            App.Vector((box.XMin + box.XMax) * 0.5 - hem_width / 2.0, y, hem_z),
            rotation,
        )
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    front, front_outline = make_piece("VisualTunicFront", box.YMax + clearance, mirror_x=False)
    back, back_outline = make_piece("VisualTunicBack", box.YMin - clearance, mirror_x=False)

    seam_records = []
    seam_specs = (
        (1, 1, False, "TunicRightSide"),
        (3, 3, False, "TunicRightShoulder"),
        (5, 5, False, "TunicLeftShoulder"),
        (7, 7, False, "TunicLeftSide"),
    )
    for edge_a, edge_b, reversed_b, seam_id in seam_specs:
        seam = Seam(
            str(front.PieceId), edge_a,
            str(back.PieceId), edge_b,
            id=seam_id,
            alignment="uniform",
            stitch_group="TunicAssembly",
            reversed_b=reversed_b,
        )
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        seam_records.append((seam_obj, front, back))

    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = float(os.environ.get("CLOTH_TUNIC_PARTICLE_DISTANCE_MM", "18.0"))
    scene.SolverIterations = int(os.environ.get("CLOTH_TUNIC_SOLVER_ITERATIONS", "8"))
    scene.SolverSubsteps = int(os.environ.get("CLOTH_TUNIC_SOLVER_SUBSTEPS", "2"))
    scene.TimeStep = float(os.environ.get("CLOTH_TUNIC_TIMESTEP", str(1.0 / 120.0)))
    scene.StitchSamples = int(os.environ.get("CLOTH_TUNIC_STITCH_SAMPLES", "8"))
    scene.GravityX = scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.78
    scene.ClothPieces = [front, back]
    refresh_drape_target(scene.DrapeTarget)
    doc.recompute()

    def authored_shoulder_pins(piece, outline):
        points = [(float(x), float(y)) for x, y in outline]
        shoulder_targets = (points[3], points[6])
        segments = [
            LineSegment("%s:edge:%d" % (piece.PieceId, i), points[i], points[(i + 1) % len(points)])
            for i in range(8)
        ]
        mesh = triangulate(ParametricPattern(segments))
        available = list(mesh.boundary_vertex_indices)
        pins = []
        for target_x, target_y in shoulder_targets:
            index = min(
                available,
                key=lambda i: (mesh.vertices[i][0] - target_x) ** 2 + (mesh.vertices[i][1] - target_y) ** 2,
            )
            pins.append(index)
            available.remove(index)
        return tuple(pins)

    front_pins = authored_shoulder_pins(front, front_outline)
    if not front_pins:
        raise RuntimeError("tunic shoulder pin selection is empty")
    scene.PinSelection = [str(i) for i in front_pins]
    log("pin-map front-shoulders=%s" % (front_pins,))
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
        style_mesh(panel, label)
        panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    authored = _seam_overlay(doc, "TunicSeamsAuthored", seam_records)
    for seam_obj in authored:
        seam_obj.ViewObject.Visibility = True
    return scene, avatar, panels, seam_records, authored, (front, back)


def render_simulation_motion(view, scene, frame_dir, frame_count=16, final_steps=120):
    os.makedirs(frame_dir, exist_ok=True)
    final_steps = max(1, int(final_steps))
    steps = [round(i * final_steps / float(frame_count - 1)) for i in range(frame_count)]
    unique_steps = tuple(dict.fromkeys(int(step) for step in steps))
    view.setCameraType("Orthographic")
    view.viewFront(); view.fitAll(); events()
    camera = view.getCameraNode()
    for index, target_step in enumerate(unique_steps):
        scene.Steps = int(target_step)
        scene.Document.recompute()
        if not bool(getattr(scene, "FiniteState", True)):
            raise RuntimeError("non-finite simulation state at motion frame %d/%d" % (index, target_step))
        save_png(view, os.path.join(frame_dir, "frame-%03d.png" % index), "simulation motion step %d" % target_step)
    log("simulation-motion-pass frames=%d final_steps=%d" % (len(unique_steps), final_steps))


def main():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show(); events()
    init_gui = os.path.join(ROOT, "InitGui.py")
    if "ClothPatternWorkbench" not in Gui.listWorkbenches():
        exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()
    doc = App.newDocument("ClothSimulationTurntable")
    try:
        scene, avatar, panels, seam_records, authored, pieces = build_simulation_state(doc)
        view = Gui.activeDocument().activeView(); view.setCameraType("Orthographic")
        objects = [avatar] + panels
        render_turntable(view, objects, os.path.join(OUT, "cloth-simulation-arranged-turntable-frames"))
        for seam_obj in authored:
            seam_obj.ViewObject.Visibility = False
        steps = int(os.environ.get("CLOTH_TUNIC_STEPS", "120"))
        scene.Steps = steps
        doc.recompute(); events()
        if int(scene.Steps) != steps or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("simulation did not reach a finite %d-step state" % steps)
        if any(panel.Mesh.CountFacets <= 10 for panel in panels):
            raise RuntimeError("draped tunic panel mesh is empty")
        for panel in panels:
            mesh_vertices, mesh_triangles = panel.Mesh.Topology
            points = tuple((float(vertex.x), float(vertex.y), float(vertex.z)) for vertex in mesh_vertices)
            triangles = tuple(tuple(int(index) for index in face) for face in mesh_triangles)
            health = mesh_shape_sanity(points, triangles)
            log("mesh-health panel=%s spike_ratio=%.3f spike_fraction=%.5f footprint_aspect=%.3f" % (
                panel.Name, health["edge_spike_ratio"], health["spike_edge_fraction"],
                health["footprint_aspect_ratio"],
            ))
            if not health["finite"] or health["edge_spike_ratio"] > 4.0 or health["spike_edge_fraction"] > 0.02:
                raise RuntimeError("draped tunic panel mesh has spike outliers: %r" % health)
        front, back = pieces
        simulated = _semantic_simulated_boundaries(scene, panels, pieces)
        _seam_overlay(doc, "TunicSeamsSimulated", seam_records, simulated)
        seam_gap = _seam_endpoint_gap(simulated, seam_records)
        log("simulation-seam-diagnostic max_endpoint_gap_mm=%.2f semantic-boundaries=true" % seam_gap)
        backend = getattr(getattr(scene, "Proxy", None), "_base_or_restore", lambda: None)()
        backend_name = getattr(getattr(backend, "backend", None), "name", "unknown") if backend is not None else "unknown"
        log("simulation-state-pass backend=%s steps=%d particles=%d triangles=%d facets=(%d,%d) seam_max_gap_mm=%.2f" % (
            backend_name, steps, int(scene.ParticleCount),
            sum(len(t) for t in getattr(backend, "panel_triangles", {}).values()) if backend is not None else 0,
            panels[0].Mesh.CountFacets, panels[1].Mesh.CountFacets, seam_gap,
        ))
        render_simulation_motion(
            view,
            scene,
            os.path.join(OUT, "cloth-simulation-motion-frames"),
            frame_count=16,
            final_steps=steps,
        )
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
