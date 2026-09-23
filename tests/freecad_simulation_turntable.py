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


# Keep the README fixture on the same conservative torso-envelope profile used by
# the canonical tunic visual audit. This is test/visual-fixture policy only; the
# production backend remains unchanged.


def _tight_tissu_collision_envelope(surface):
    if surface is None or not surface.vertices:
        return ()
    xs = [float(v[0]) for v in surface.vertices]
    ys = [float(v[1]) for v in surface.vertices]
    zs = [float(v[2]) for v in surface.vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    height = max(1.0, max_z - min_z)
    width = max(1.0, max_x - min_x)
    depth = max(1.0, max_y - min_y)
    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)
    radius = max(90.0, min(170.0, 0.16 * width, 0.48 * depth))
    bottom = min_z + 0.38 * height
    top = min_z + 0.76 * height
    samples = (0.0, 0.25, 0.50, 0.75, 1.0)
    return tuple(
        ((center_x, center_y, bottom + (top - bottom) * t), radius)
        for t in samples
    )

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from freecad_cloth.simulation import TissuBackend as _tissu_backend
from freecad_cloth.sewing.SewingView import seam_color_map

_tissu_backend._collision_envelope = _tight_tissu_collision_envelope
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


def _polyline_point(points, fraction):
    if not points:
        raise RuntimeError("semantic seam edge has no solver points")
    if len(points) == 1:
        return points[0]
    target = max(0.0, min(1.0, float(fraction)))
    lengths = []
    total = 0.0
    for left, right in zip(points, points[1:]):
        length = (right - left).Length
        lengths.append(length)
        total += length
    if total <= 1e-12:
        return points[0]
    distance = target * total
    travelled = 0.0
    for index, length in enumerate(lengths):
        if travelled + length >= distance:
            local = 0.0 if length <= 1e-12 else (distance - travelled) / length
            left, right = points[index], points[index + 1]
            return left + (right - left) * local
        travelled += length
    return points[-1]


def _sample_polyline(points, start, end, count=12, reverse=False):
    start = float(start); end = float(end)
    if reverse:
        start, end = 1.0 - end, 1.0 - start
    return [
        _polyline_point(points, start + (end - start) * (index / float(max(1, count - 1))))
        for index in range(max(2, int(count)))
    ]


def _solver_boundary_map(scene, pieces, panels):
    from freecad_cloth.common.PatternSimulationAdapter import resolve_simulation_pattern
    resolved = resolve_simulation_pattern(scene.Document, tuple(pieces))
    proxy = scene.Proxy._base_or_restore()
    positions = tuple(proxy.backend.positions())
    mapping = {}
    for piece, panel in zip(pieces, panels):
        piece_ir = resolved.piece(str(piece.PieceId))
        edge_ids = tuple(str(boundary.id) for boundary in piece_ir.boundaries)
        chains = proxy.panel_boundary_edges.get(panel.Name)
        if chains is None or len(chains) != len(edge_ids):
            raise RuntimeError("solver boundary provenance is incomplete for %s" % piece.Name)
        semantic = {}
        for edge_id, chain in zip(edge_ids, chains):
            points = tuple(App.Vector(*positions[int(index)]) for index in chain)
            if len(points) < 2:
                raise RuntimeError("semantic seam edge %s has too few solver points" % edge_id)
            semantic[edge_id] = points
        mapping[piece.Name] = {"ids": edge_ids, "chains": semantic}
    return mapping


def _semantic_edge_id(seam, side, piece_data, edge_index):
    edge_id = str(getattr(seam, "Edge%sId" % side, "")).strip()
    if edge_id and edge_id in piece_data["chains"]:
        return edge_id
    if 0 <= int(edge_index) < len(piece_data["ids"]):
        return piece_data["ids"][int(edge_index)]
    raise RuntimeError("seam %s has no resolvable semantic %s edge" % (getattr(seam, "SeamId", seam), side))


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
        sides = []
        for side, piece in (("A", piece_a), ("B", piece_b)):
            edge_index = int(getattr(seam, "Edge%s" % side, 0))
            start = float(getattr(seam, "Start%s" % side, 0.0))
            end = float(getattr(seam, "End%s" % side, 1.0))
            reverse = bool(getattr(seam, "ReversedB", False)) if side == "B" else False
            if simulated is None:
                outline = _outline(piece)
                a, b = outline[edge_index], outline[(edge_index + 1) % len(outline)]
                base = (
                    App.Vector(a[0], a[1], 2.0),
                    App.Vector(b[0], b[1], 2.0),
                )
                local_points = _sample_polyline(base, start, end, count=8, reverse=reverse)
                points = [piece.Placement.multVec(point) for point in local_points]
            else:
                piece_data = simulated.get(piece.Name)
                if piece_data is None:
                    raise RuntimeError("solver seam overlay has no piece provenance for %s" % piece.Name)
                edge_id = _semantic_edge_id(seam, side, piece_data, edge_index)
                points = _sample_polyline(piece_data["chains"][edge_id], start, end, count=16, reverse=reverse)
                if side == "A":
                    pass
            sides.append(points)

        shapes = [Part.makePolygon(points) for points in sides if len(points) >= 2]
        for left, right in zip(sides[0], sides[1]):
            if (right - left).Length > 1e-9:
                shapes.append(Part.makeLine(left, right))
        if not shapes:
            raise RuntimeError("turntable seam overlay generated no geometry for %s" % seam_id)
        obj_name = "%s%02d" % (name, index)
        obj = doc.getObject(obj_name) or doc.addObject("Part::Feature", obj_name)
        obj.Label = "Tunic seam %s — %s" % (seam_id, "simulated" if simulated is not None else "authored")
        obj.Shape = Part.makeCompound(shapes)
        obj.ViewObject.LineColor = colors[seam_id]
        obj.ViewObject.LineWidth = 5.0
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.Visibility = True
        overlays.append(obj)
    return overlays


def _seam_endpoint_gap(simulated, seam_records):
    gaps = []
    for seam, piece_a, piece_b in seam_records:
        data_a = simulated[piece_a.Name]
        data_b = simulated[piece_b.Name]
        edge_a = _semantic_edge_id(seam, "A", data_a, int(seam.EdgeA))
        edge_b = _semantic_edge_id(seam, "B", data_b, int(seam.EdgeB))
        a = _sample_polyline(data_a["chains"][edge_a], float(seam.StartA), float(seam.EndA), count=2)
        b = _sample_polyline(data_b["chains"][edge_b], float(seam.StartB), float(seam.EndB), count=2, reverse=bool(seam.ReversedB))
        gaps.extend(((left - right).Length for left, right in zip(a, b)))
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
    z_span = float(box.ZMax - box.ZMin)
    chest = 860.0; hip = 880.0; ease = 10.0
    panel_width = max(420.0, 0.50 * chest + ease)
    hem_width = max(450.0, 0.50 * hip + ease)
    shoulder_z = box.ZMin + 0.76 * z_span
    hem_z = box.ZMin + 0.40 * z_span
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, float(box.YMax - box.YMin)))
    clearance = max(8.0, 0.025 * body_depth)

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
    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())
    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())
    required_indices = (1, 2, 6, 7)
    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8 or any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices):
        raise RuntimeError("README turntable fixture is missing authored semantic edge IDs")
    seam_specs = (
        (front_edge_ids[1], back_edge_ids[1], "TunicRightSide"),
        (front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"),
        (front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"),
        (front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"),
    )
    for edge_a_id, edge_b_id, seam_id in seam_specs:
        seam = Seam(
            str(front.PieceId), edge_a_id,
            str(back.PieceId), edge_b_id,
            id=seam_id,
            alignment="uniform",
            stitch_group="TunicAssembly",
        )
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        if str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id:
            raise RuntimeError("README turntable seam %s did not retain authored semantic edge IDs" % seam_id)
        seam_records.append((seam_obj, front, back))

    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = float(os.environ.get("CLOTH_TUNIC_PARTICLE_DISTANCE_MM", "24.0"))
    scene.SolverIterations = int(os.environ.get("CLOTH_TUNIC_SOLVER_ITERATIONS", "64"))
    scene.SolverSubsteps = int(os.environ.get("CLOTH_TUNIC_SOLVER_SUBSTEPS", "1"))
    scene.TimeStep = float(os.environ.get("CLOTH_TUNIC_TIMESTEP", str(1.0 / 120.0)))
    scene.StitchSamples = int(os.environ.get("CLOTH_TUNIC_STITCH_SAMPLES", "8"))
    scene.GravityX = scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.85
    scene.ClothPieces = [front, back]
    refresh_drape_target(scene.DrapeTarget)
    doc.recompute()

    def authored_shoulder_pins(piece, particle_indices, positions):
        targets = (
            (0.14 * panel_width, 0.97 * garment_height),
            (0.86 * panel_width, 0.97 * garment_height),
        )
        available = list(particle_indices)
        result = []
        for local_x, local_y in targets:
            target_point = piece.Placement.multVec(App.Vector(float(local_x), float(local_y), 0.0))
            index = min(
                available,
                key=lambda i: (positions[i][0] - target_point.x) ** 2
                + (positions[i][1] - target_point.y) ** 2
                + (positions[i][2] - target_point.z) ** 2,
            )
            result.append(index)
            available.remove(index)
        return tuple(result)

    proxy = scene.Proxy
    positions = tuple(proxy.backend.positions())
    panel_indices = proxy.panel_indices
    front_panel = scene.DrapePanels[0]
    back_panel = scene.DrapePanels[1]
    front_pins = authored_shoulder_pins(front, tuple(panel_indices[front_panel.Name]), positions)
    back_pins = authored_shoulder_pins(back, tuple(panel_indices[back_panel.Name]), positions)
    if not front_pins:
        raise RuntimeError("README tunic shoulder pin selection is empty")
    scene.PinSelection = [str(i) for i in front_pins]
    if any(int(a) in front_pins and int(b) in front_pins for pairs in getattr(proxy, "seam_stitch_pairs", {}).values() for a, b in pairs):
        raise RuntimeError("README tunic pin contract pins both endpoints of a sewn pair")
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
        steps = int(os.environ.get("CLOTH_TUNIC_STEPS", "90"))
        scene.Steps = steps
        doc.recompute(); events()
        if int(scene.Steps) != steps or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
            raise RuntimeError("simulation did not reach a finite %d-step state" % steps)
        if any(panel.Mesh.CountFacets <= 10 for panel in panels):
            raise RuntimeError("draped tunic panel mesh is empty")
        front, back = pieces
        simulated = _solver_boundary_map(scene, pieces, panels)
        _seam_overlay(doc, "TunicSeamsSimulated", seam_records, simulated)
        seam_gap = _seam_endpoint_gap(simulated, seam_records)
        if seam_gap > 35.0:
            raise RuntimeError("README turntable seam provenance did not converge: max endpoint gap %.2f mm" % seam_gap)
        log("simulation-seam-diagnostic max_endpoint_gap_mm=%.2f semantic-provenance=true" % seam_gap)
        backend = getattr(getattr(scene, "Proxy", None), "_base_or_restore", lambda: None)()
        backend_name = getattr(getattr(backend, "backend", None), "name", "unknown") if backend is not None else "unknown"
        log("simulation-state-pass backend=%s steps=%d particles=%d triangles=%d facets=(%d,%d) seam_max_gap_mm=%.2f" % (
            backend_name, steps, int(scene.ParticleCount),
            sum(len(t) for t in getattr(backend, "panel_triangles", {}).values()) if backend is not None else 0,
            panels[0].Mesh.CountFacets, panels[1].Mesh.CountFacets, seam_gap,
        ))
        for panel in panels:
            panel.ViewObject.DisplayMode = "Shaded"
            panel.ViewObject.LineWidth = 1.0
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
