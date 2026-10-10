"""Fast visual/structural A-B audit for the canonical tunic drape.

Runs the production cloth avatar + native Sketcher tunic fixture with the selected
backend, highlights authored seams and pinned vertices, and writes checkpoint
screenshots plus topology metrics. This intentionally avoids the heavy turntable
and full GUI acceptance suite.
"""

from __future__ import annotations

import contextlib
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
SEAMS = (
    (1, 1, "TunicRightSide"),
    (3, 3, "TunicRightShoulder"),
    (5, 5, "TunicLeftShoulder"),
    (7, 7, "TunicLeftSide"),
)


def log(message: str):
    print(f"DRAPE-DEBUG: {message}", flush=True)


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


def _arc_through_midpoint(Part, start, end, midpoint):
    """Build a minor native circular arc through an explicit on-arc point."""
    import math

    sx, sy = float(start.x), float(start.y)
    ex, ey = float(end.x), float(end.y)
    mx, my = float(midpoint.x), float(midpoint.y)
    start_sq = sx * sx + sy * sy
    end_sq = ex * ex + ey * ey
    middle_sq = mx * mx + my * my
    determinant = 2.0 * (sx * (ey - my) + ex * (my - sy) + mx * (sy - ey))
    if abs(determinant) <= 1e-9:
        raise RuntimeError("tunic armhole points are collinear; cannot construct an arc")

    center_x = (start_sq * (ey - my) + end_sq * (my - sy) + middle_sq * (sy - ey)) / determinant
    center_y = (start_sq * (mx - ex) + end_sq * (sx - mx) + middle_sq * (ex - sx)) / determinant
    radius = math.hypot(sx - center_x, sy - center_y)
    if not math.isfinite(radius) or radius <= 1e-9:
        raise RuntimeError("tunic armhole circle has an invalid radius")

    def curve_value(curve, parameter_value):
        getter = getattr(curve, "valueAt", None)
        if not callable(getter):
            getter = getattr(curve, "value", None)
        if not callable(getter):
            raise RuntimeError("tunic armhole curve has no native parameter evaluator")
        return getter(float(parameter_value))

    tau = 2.0 * math.pi
    selected = None
    for normal_z in (1.0, -1.0):
        circle = Part.Circle(
            App.Vector(center_x, center_y, 0.0),
            App.Vector(0.0, 0.0, normal_z),
            radius,
        )
        # Derive parameters from the native circle basis instead of assuming
        # which global direction its X axis uses for either normal orientation.
        zero_point = curve_value(circle, 0.0)
        quarter_point = curve_value(circle, math.pi / 2.0)
        axis_x = (
            (float(zero_point.x) - center_x) / radius,
            (float(zero_point.y) - center_y) / radius,
        )
        axis_y = (
            (float(quarter_point.x) - center_x) / radius,
            (float(quarter_point.y) - center_y) / radius,
        )

        def parameter(point_x, point_y, axis_x=axis_x, axis_y=axis_y):
            dx = point_x - center_x
            dy = point_y - center_y
            return (
                math.atan2(
                    dx * axis_y[0] + dy * axis_y[1],
                    dx * axis_x[0] + dy * axis_x[1],
                )
                % tau
            )

        start_angle = parameter(sx, sy)
        end_angle = parameter(ex, ey)
        middle_angle = parameter(mx, my)
        sweep = (end_angle - start_angle) % tau
        middle_sweep = (middle_angle - start_angle) % tau
        if sweep > 1e-9 and middle_sweep <= sweep + 1e-9:
            selected = (circle, normal_z, start_angle, sweep, middle_sweep)
            break

    if selected is None:
        raise RuntimeError("tunic armhole points do not define a consistent circular sweep")
    circle, normal_z, start_angle, sweep, middle_sweep = selected
    if sweep >= math.pi:
        raise RuntimeError(
            "tunic armhole through-point selects a major arc: sweep-rad=%.6f" % sweep
        )

    arc = Part.ArcOfCircle(circle, start_angle, start_angle + sweep)
    checks = (
        ("start", start, start_angle),
        ("end", end, start_angle + sweep),
        ("midpoint", midpoint, start_angle + middle_sweep),
    )
    for role, expected, parameter_value in checks:
        actual = curve_value(arc, parameter_value)
        error = math.hypot(float(actual.x) - float(expected.x), float(actual.y) - float(expected.y))
        if error > 1e-5:
            raise RuntimeError(
                "tunic armhole arc lost authored %s: error-mm=%.6f "
                "normal-z=%.0f expected=(%.4f,%.4f) actual=(%.4f,%.4f)"
                % (
                    role,
                    error,
                    normal_z,
                    float(expected.x),
                    float(expected.y),
                    float(actual.x),
                    float(actual.y),
                )
            )
    return arc


def _make_tunic_sketch(
    doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop
):

    h = float(garment_height)
    neck_z = (1.0 - float(neckline_drop)) * h
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = 0.88 * h
    shoulder_z = 0.98 * h
    points = [
        (0.0, 0.0),
        (hem_width, 0.0),
        (x_offset + 0.84 * panel_width, armhole_z),
        (x_offset + 0.90 * panel_width, shoulder_z),
        (x_offset + float(neckline_ratio) * panel_width, neck_z),
        (x_offset + (1.0 - float(neckline_ratio)) * panel_width, neck_z),
        (x_offset + 0.10 * panel_width, shoulder_z),
        (x_offset + 0.16 * panel_width, armhole_z),
    ]
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 7), (3, 6), (4, 5)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            raise RuntimeError("debug tunic profile lost canonical bilateral symmetry")
    sketch = doc.addObject("Sketcher::SketchObject", name)
    armhole_mid_z = armhole_z + 0.5 * (shoulder_z - armhole_z)
    for idx, start in enumerate(points):
        end = points[(idx + 1) % len(points)]
        start_vector = App.Vector(start[0], start[1], 0)
        end_vector = App.Vector(end[0], end[1], 0)
        if idx == 2:
            midpoint = App.Vector(x_offset + 0.82 * panel_width, armhole_mid_z, 0)
            geometry = _arc_through_midpoint(Part, start_vector, end_vector, midpoint)
        elif idx == 6:
            midpoint = App.Vector(x_offset + 0.18 * panel_width, armhole_mid_z, 0)
            geometry = _arc_through_midpoint(Part, start_vector, end_vector, midpoint)
        else:
            geometry = Part.LineSegment(start_vector, end_vector)
        sketch.addGeometry(geometry, False)
    return sketch, points


def _adopt_sketch(sketch, name, seam_allowance):
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece

    return add_pattern_piece(
        sketch.Document, sketch, label=name, seam_allowance=float(seam_allowance)
    )


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
        area = 0.5 * math.hypot(*cross)
        edges = (math.dist(pa, pb), math.dist(pa, pc), math.dist(pb, pc))
        min_area = min(min_area, area)
        min_edge = min(min_edge, *edges)
        if area < 1e-3 or min(edges) < 1e-2:
            bad += 1
    return {
        "degenerate_triangles": bad,
        "minimum_triangle_area": min_area if math.isfinite(min_area) else 0.0,
        "minimum_edge_length": min_edge if math.isfinite(min_edge) else 0.0,
    }


def _metrics(
    backend, stitches, pin_indices, initial_pins, target_vertices, triangles, requested_step
):
    from freecad_cloth.common.MeshValidation import nearest_target_clearance

    positions = backend.positions()
    seam_gaps = []
    for a, b in stitches:
        pa, pb = positions[int(a)], positions[int(b)]
        seam_gaps.append(math.dist(pa, pb))
    pin_drifts = []
    for index, initial in zip(pin_indices, initial_pins, strict=False):
        current = positions[int(index)]
        pin_drifts.append(math.dist(current, initial))
    xs = [float(p[0]) for p in positions]
    ys = [float(p[1]) for p in positions]
    zs = [float(p[2]) for p in positions]
    metrics = {
        "backend": getattr(backend, "name", "unknown"),
        "requested_step": requested_step,
        "finite": bool(backend.finite()),
        "bounds": [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)],
        "centroid": [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)],
        "maximum_seam_gap_mm": max(seam_gaps) if seam_gaps else 0.0,
        "seam_gaps_mm": seam_gaps,
        "maximum_pin_drift_mm": max(pin_drifts) if pin_drifts else 0.0,
        "minimum_vertex_to_target_mm": (
            nearest_target_clearance(positions, target_vertices)
            if positions and target_vertices
            else None
        ),
        "finite_vertices": all(math.isfinite(float(c)) for p in positions for c in p),
        "collision_mode": os.environ.get("CLOTH_PBD_COLLISION_MODE", "mesh")
        if getattr(backend, "name", "") == "position-based-dynamics"
        else "n/a",
    }
    metrics.update(_triangle_degeneracy(positions, triangles))
    return metrics


def run():
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target
    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel

    backend_requested = "pbd"
    log(
        "backend={} collision={}".format(
            backend_requested, os.environ.get("CLOTH_PBD_COLLISION_MODE", "mesh")
        )
    )

    doc = App.newDocument("ClothDrapeDebug")
    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    if avatar is None:
        raise RuntimeError("production avatar missing")
    box = avatar.Mesh.BoundBox
    y_span = box.YMax - box.YMin
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    def arrangement_world(name):
        raw = next(
            (
                value
                for value in getattr(avatar, "ArrangementPoints", ())
                if str(value).split("|", 1)[0] == name
            ),
            None,
        )
        if raw is None:
            raise RuntimeError("canonical tunic is missing avatar arrangement point %s" % name)
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))

    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    x_mid = 0.5 * (float(shoulder_left.x) + float(shoulder_right.x))
    shoulder_z = 0.5 * (float(shoulder_left.z) + float(shoulder_right.z))
    hem_z = float(hip_point.z)
    shoulder_width = abs(float(shoulder_right.x) - float(shoulder_left.x))
    shoulder_span_ratio = 0.86 - 0.14
    panel_width = max(420.0, shoulder_width / shoulder_span_ratio + 20.0)
    hem_width = max(500.0, panel_width + 80.0)
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    front_y = box.YMax + clearance
    back_y = box.YMin - clearance
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def make_piece(name, y, neckline_ratio, neckline_drop):
        sketch, outline = _make_tunic_sketch(
            doc,
            name + "Source",
            panel_width,
            garment_height,
            hem_width,
            neckline_ratio,
            neckline_drop,
        )
        doc.recompute()
        piece = _adopt_sketch(sketch, name, 10.0)
        piece.Placement = App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    front, front_outline = make_piece("DebugTunicFront", front_y, 0.78, 0.18)
    back, back_outline = make_piece("DebugTunicBack", back_y, 0.76, 0.12)
    for edge_a, edge_b, seam_id in SEAMS:
        from freecad_cloth.pattern.PatternModel import Seam
        from freecad_cloth.pattern.PatternObjects import add_seam

        add_seam(
            doc,
            Seam(
                str(front.PieceId),
                edge_a,
                str(back.PieceId),
                edge_b,
                id=seam_id,
                alignment="uniform",
                stitch_group="TunicAssembly",
            ),
        )
    scene.ParticleDistance = 22.0
    scene.SolverIterations = 12
    scene.SolverSubsteps = 2
    scene.FabricFriction = 0.80
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.ClothPieces = [front, back]
    refresh_drape_target(scene.DrapeTarget)
    doc.recompute()

    front_positions, front_triangles, _ = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_positions, back_triangles, _ = quality_piece_mesh(back, 0.0, scene.ParticleDistance)
    triangles = tuple(front_triangles) + tuple(
        (a + len(front_positions), b + len(front_positions), c + len(front_positions))
        for a, b, c in back_triangles
    )

    def pin_indices(piece, outline, positions):
        x_offset = 0.5 * (float(hem_width) - float(panel_width))
        targets = (
            (x_offset + 0.10 * panel_width, 0.98 * garment_height),
            (x_offset + 0.90 * panel_width, 0.98 * garment_height),
        )
        result = []
        available = list(range(len(positions)))
        for local_x, local_y in targets:
            target = piece.Placement.multVec(App.Vector(local_x, local_y, 0.0))
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
    stitches = (
        tuple((int(c.a), int(c.b)) for c in getattr(backend.system, "stitches", ()))
        if hasattr(backend, "system")
        else tuple(getattr(backend, "_stitches", ()))
    )
    if not stitches:
        raise RuntimeError("production seam graph produced no stitches")
    backend.pin(pins)
    backend.set_stitches(stitches, compliance=0.0)
    target_vertices = [tuple(v) for v in avatar.Mesh.Points]
    initial_pins = tuple(backend.positions()[i] for i in pins)

    debug_group = doc.addObject("App::DocumentObjectGroup", "DrapeDebug")
    seam_colors = ((1.0, 0.85, 0.0), (1.0, 0.45, 0.0), (0.2, 1.0, 0.2), (0.2, 0.8, 1.0))
    for (edge_a, _edge_b, seam_id), color in zip(SEAMS, seam_colors, strict=False):
        p0 = front_outline[edge_a]
        p1 = front_outline[(edge_a + 1) % len(front_outline)]
        world = [
            front.Placement.multVec(App.Vector(p0[0], p0[1], 0.0)),
            front.Placement.multVec(App.Vector(p1[0], p1[1], 0.0)),
        ]
        debug_group.addObject(
            _debug_line(doc, f"DebugSeam_{seam_id}", [(p.x, p.y, p.z) for p in world], color)
        )
    for index, initial in enumerate(initial_pins):
        debug_group.addObject(
            _debug_sphere(doc, "DebugPin_%02d" % index, initial, (1.0, 0.2, 1.0), 13.0)
        )
    for panel_obj in scene.DrapePanels:
        _style_mesh(panel_obj)
        panel_obj.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    events()

    panel = SimulationQualityTaskPanel(scene)
    panel.accept()
    close_task()
    doc.recompute()

    metrics = []
    try:
        for target_step in STEPS:
            current = int(scene.Steps)
            if target_step > current:
                panel.step(target_step - current)
            doc.recompute()
            events()
            values = _metrics(
                backend, stitches, pins, initial_pins, target_vertices, triangles, target_step
            )
            values["backend_requested"] = backend_requested
            metrics.append(values)
            view = Gui.activeDocument().activeView()
            view.setCameraType("Orthographic")
            view.viewRear()
            view.fitAll()
            events()
            view.saveImage(
                str(OUT / ("front-step-%03d.png" % target_step)), 1280, 720, "Current", 1
            )
            if target_step == 30:
                view.viewLeft()
                view.fitAll()
                events()
                view.saveImage(str(OUT / "left-step-030.png"), 1280, 720, "Current", 1)
    finally:
        close_task()
        (OUT / "metrics.json").write_text(
            json.dumps(
                {
                    "backend": getattr(backend, "name", backend_requested),
                    "collision_mode": os.environ.get("CLOTH_PBD_COLLISION_MODE", "mesh"),
                    "checkpoints": metrics,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with contextlib.suppress(Exception):
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    run()
