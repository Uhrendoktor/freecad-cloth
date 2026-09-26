"""Fast visual/structural A-B audit for the canonical tunic drape.

Runs the production cloth avatar + native Sketcher tunic fixture with the selected
backend, highlights authored seams and pinned vertices, and writes checkpoint
screenshots plus topology metrics. This intentionally avoids the heavy turntable
and full GUI acceptance suite.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CLOTH_DEBUG_DIR", "artifacts/freecad-drape-debug"))
OUT.mkdir(parents=True, exist_ok=True)
STEPS = [0, 5, 10, 20, 30]
SEAMS = ((1, 1, "TunicRightSide"), (2, 2, "TunicRightShoulder"), (6, 6, "TunicLeftShoulder"), (7, 7, "TunicLeftSide"))


def log(message: str):
    print("DRAPE-DEBUG: %s" % message, flush=True)


def events():
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    Gui.updateGui()


def show_task(panel):
    Gui.Control.showDialog(panel)
    events()
    return panel


def close_task():
    try:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        pass


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop):
    import Sketcher

    h = float(garment_height)
    neck_z = h * float(neckline_drop)
    points = [
        (0, 0), (hem_width, 0), (panel_width, 0.82 * h),
        (0.86 * panel_width, 0.97 * h),
        (float(neckline_ratio) * panel_width, neck_z),
        ((1.0 - float(neckline_ratio)) * panel_width, neck_z),
        (0.14 * panel_width, 0.97 * h), (0, 0.82 * h),
    ]
    sketch = doc.addObject("Sketcher::SketchObject", name)
    for idx, start in enumerate(points):
        end = points[(idx + 1) % len(points)]
        sketch.addGeometry(Part.LineSegment(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0)), False)
    return sketch, points


def _adopt_sketch(sketch, name, seam_allowance):
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece
    return add_pattern_piece(sketch.Document, sketch, label=name, seam_allowance=float(seam_allowance))


def _style_mesh(obj):
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"
        obj.ViewObject.ShapeColor = (0.80, 0.15, 0.08)
        obj.ViewObject.LineColor = (0.18, 0.01, 0.01)
        obj.ViewObject.LineWidth = 1.6
    except Exception:
        pass


def _debug_line(doc, name, points, color, width=4.0):
    feature = doc.addObject("Part::Feature", name)
    feature.Shape = Part.makePolygon([App.Vector(*p) for p in points])
    try:
        feature.ViewObject.LineColor = color
        feature.ViewObject.LineWidth = width
    except Exception:
        pass
    return feature


def _debug_sphere(doc, name, point, color, radius=12.0):
    feature = doc.addObject("Part::Feature", name)
    feature.Shape = Part.makeSphere(radius, App.Vector(*point))
    try:
        feature.ViewObject.ShapeColor = color
        feature.ViewObject.Transparency = 10
    except Exception:
        pass
    return feature


def _triangle_degeneracy(positions, triangles):
    bad = 0
    min_area = float("inf")
    min_edge = float("inf")
    for a, b, c in triangles:
        pa, pb, pc = positions[int(a)], positions[int(b)], positions[int(c)]
        ab = tuple(float(pb[i]) - float(pa[i]) for i in range(3))
        ac = tuple(float(pc[i]) - float(pa[i]) for i in range(3))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        area = 0.5 * math.sqrt(sum(v * v for v in cross))
        edges = (
            math.sqrt(sum((float(pa[i]) - float(pb[i])) ** 2 for i in range(3))),
            math.sqrt(sum((float(pa[i]) - float(pc[i])) ** 2 for i in range(3))),
            math.sqrt(sum((float(pb[i]) - float(pc[i])) ** 2 for i in range(3))),
        )
        min_area = min(min_area, area)
        min_edge = min(min_edge, *edges)
        if area < 1e-3 or min(edges) < 1e-2:
            bad += 1
    return {"degenerate_triangles": bad, "minimum_triangle_area": min_area if math.isfinite(min_area) else 0.0, "minimum_edge_length": min_edge if math.isfinite(min_edge) else 0.0}


def _minimum_vertex_distance(source, target):
    if not source or not target:
        return None
    best = float("inf")
    for a in source:
        for b in target:
            d2 = sum((float(a[i]) - float(b[i])) ** 2 for i in range(3))
            best = min(best, d2)
    return math.sqrt(best) if math.isfinite(best) else None


def _metrics(backend, stitches, pin_indices, initial_pins, target_vertices, triangles, requested_step):
    positions = backend.positions()
    seam_gaps = []
    for a, b in stitches:
        pa, pb = positions[int(a)], positions[int(b)]
        seam_gaps.append(math.sqrt(sum((float(pa[i]) - float(pb[i])) ** 2 for i in range(3))))
    pin_drifts = []
    for index, initial in zip(pin_indices, initial_pins):
        current = positions[int(index)]
        pin_drifts.append(math.sqrt(sum((float(current[i]) - float(initial[i])) ** 2 for i in range(3))))
    xs = [float(p[0]) for p in positions]; ys = [float(p[1]) for p in positions]; zs = [float(p[2]) for p in positions]
    metrics = {
        "backend": getattr(backend, "name", "unknown"),
        "requested_step": requested_step,
        "finite": bool(backend.finite()),
        "bounds": [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)],
        "centroid": [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)],
        "maximum_seam_gap_mm": max(seam_gaps) if seam_gaps else 0.0,
        "seam_gaps_mm": seam_gaps,
        "maximum_pin_drift_mm": max(pin_drifts) if pin_drifts else 0.0,
        "minimum_vertex_to_target_mm": _minimum_vertex_distance(positions, target_vertices),
        "finite_vertices": all(math.isfinite(float(c)) for p in positions for c in p),
        "collision_mode": os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh") if getattr(backend, "name", "") == "tissu" else "n/a",
    }
    metrics.update(_triangle_degeneracy(positions, triangles))
    return metrics


def run():
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene

    backend_requested = os.environ.get("CLOTH_SIMULATION_BACKEND", "auto")
    log("backend=%s collision=%s" % (backend_requested, os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh")))

    doc = App.newDocument("ClothDrapeDebug")
    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    if avatar is None:
        raise RuntimeError("production avatar missing")
    box = avatar.Mesh.BoundBox
    x_mid = (box.XMin + box.XMax) / 2.0
    y_span = box.YMax - box.YMin
    z_span = box.ZMax - box.ZMin
    panel_width = max(420.0, min(560.0, 0.50 * float(box.XMax - box.XMin) + 35.0))
    hem_width = max(440.0, min(590.0, 0.52 * float(box.XMax - box.XMin) + 35.0))
    shoulder_z = box.ZMin + 0.76 * z_span
    hem_z = box.ZMin + 0.40 * z_span
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(6.0, 0.02 * body_depth)
    front_y = box.YMax + clearance
    back_y = box.YMin - clearance
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def make_piece(name, y):
        sketch, outline = _make_tunic_sketch(doc, name + "Source", panel_width, garment_height, hem_width, 0.64, 0.08)
        doc.recompute()
        piece = _adopt_sketch(sketch, name, 10.0)
        piece.Placement = App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    front, front_outline = make_piece("DebugTunicFront", front_y)
    back, back_outline = make_piece("DebugTunicBack", back_y)
    seam_objects = {}
    for edge_a, edge_b, seam_id in SEAMS:
        from freecad_cloth.pattern.PatternModel import Seam
        from freecad_cloth.pattern.PatternObjects import add_seam
        seam_obj = add_seam(doc, Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly"))
        seam_objects[seam_id] = seam_obj
    scene.ParticleDistance = 22.0
    scene.SolverIterations = 12
    scene.SolverSubsteps = 2
    scene.FabricFriction = 0.80
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = 0.0; scene.GravityY = 0.0; scene.GravityZ = -9810.0
    scene.ClothPieces = [front, back]
    refresh_drape_target(scene.DrapeTarget)
    doc.recompute()

    front_positions, front_triangles, _ = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_positions, back_triangles, _ = quality_piece_mesh(back, 0.0, scene.ParticleDistance)
    triangles = tuple(front_triangles) + tuple((a + len(front_positions), b + len(front_positions), c + len(front_positions)) for a, b, c in back_triangles)

    def pin_indices(piece, outline, positions):
        targets = ((0.14 * panel_width, 0.97 * garment_height), (0.86 * panel_width, 0.97 * garment_height))
        result = []
        available = list(range(len(positions)))
        for local_x, local_y in targets:
            target = piece.Placement.multVec(App.Vector(local_x, local_y, 0.0))
            index = min(available, key=lambda i: (positions[i][0] - target.x) ** 2 + (positions[i][1] - target.y) ** 2 + (positions[i][2] - target.z) ** 2)
            result.append(index); available.remove(index)
        return tuple(result)

    front_pins = pin_indices(front, front_outline, front_positions)
    back_pins_local = pin_indices(back, back_outline, back_positions)
    pins = tuple(front_pins + tuple(len(front_positions) + i for i in back_pins_local))
    scene.PinSelection = [str(i) for i in pins]
    doc.recompute()

    for source in (doc.getObject("DebugTunicFront"), doc.getObject("DebugTunicBack")):
        if source is not None:
            source.ViewObject.Visibility = False
            sketch = getattr(source, "Sketch", None)
            if sketch is not None:
                sketch.ViewObject.Visibility = False

    base = scene.Proxy._base_or_restore()
    backend = getattr(base, "backend", None)
    if backend is None:
        raise RuntimeError("production simulation backend missing")
    stitches = tuple((int(c.a), int(c.b)) for c in getattr(backend.system, "stitches", ())) if hasattr(backend, "system") else tuple(getattr(backend, "_stitches", ()))
    if not stitches:
        raise RuntimeError("production seam graph produced no stitches")
    backend.pin(pins)
    backend.set_stitches(stitches, compliance=0.0)
    target_vertices = [tuple(v) for v in avatar.Mesh.Points]
    initial_pins = tuple(backend.positions()[i] for i in pins)

    debug_group = doc.addObject("App::DocumentObjectGroup", "DrapeDebug")
    for edge_a, _edge_b, seam_id in SEAMS:
        p0 = front_outline[edge_a]
        p1 = front_outline[(edge_a + 1) % len(front_outline)]
        world = [front.Placement.multVec(App.Vector(p0[0], p0[1], 0.0)), front.Placement.multVec(App.Vector(p1[0], p1[1], 0.0))]
        seam_obj = seam_objects[seam_id]
        color = tuple(seam_obj.ViewObject.LineColor[:3])
        feature = _debug_line(doc, "DebugSeam_%s" % seam_id, [(p.x, p.y, p.z) for p in world], color)
        feature.addProperty("App::PropertyString", "SeamId", "Seam").SeamId = seam_id
        debug_group.addObject(feature)
    for index, initial in enumerate(initial_pins):
        debug_group.addObject(_debug_sphere(doc, "DebugPin_%02d" % index, initial, (1.0, 0.2, 1.0), 13.0))
    for panel_obj in scene.DrapePanels:
        _style_mesh(panel_obj)
        panel_obj.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute(); events()

    panel = SimulationQualityTaskPanel(scene)
    panel.accept(); close_task()
    doc.recompute()

    metrics = []
    try:
        for target_step in STEPS:
            current = int(scene.Steps)
            if target_step > current:
                panel.step(target_step - current)
            doc.recompute(); events()
            values = _metrics(backend, stitches, pins, initial_pins, target_vertices, triangles, target_step)
            values["backend_requested"] = backend_requested
            metrics.append(values)
            view = Gui.activeDocument().activeView()
            view.setCameraType("Orthographic")
            view.viewRear(); view.fitAll(); events()
            view.saveImage(str(OUT / ("front-step-%03d.png" % target_step)), 1280, 720, "Current", 1)
            if target_step == 30:
                view.viewLeft(); view.fitAll(); events()
                view.saveImage(str(OUT / "left-step-030.png"), 1280, 720, "Current", 1)
    finally:
        close_task()
        (OUT / "metrics.json").write_text(json.dumps({"backend": getattr(backend, "name", backend_requested), "collision_mode": os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh"), "checkpoints": metrics}, indent=2), encoding="utf-8")
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass


if __name__ == "__main__":
    run()
