"""Fast deterministic visual/topology inspection of the production drape backend."""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

OUT = Path(os.environ.get("CLOTH_DEBUG_DIR", "artifacts/freecad-drape-debug"))
OUT.mkdir(parents=True, exist_ok=True)
STEPS = (0, 2, 6)


def events():
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    Gui.updateGui()


def close_task():
    try:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        pass


def triangle_metrics(positions, triangles):
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


def sampled_min_distance(source, target, source_limit=256, target_limit=1024):
    if not source or not target:
        return None
    src = source if len(source) <= source_limit else source[:: max(1, len(source) // source_limit)]
    tgt = target if len(target) <= target_limit else target[:: max(1, len(target) // target_limit)]
    best = float("inf")
    for a in src:
        for b in tgt:
            d2 = sum((float(a[i]) - float(b[i])) ** 2 for i in range(3))
            if d2 < best:
                best = d2
    return math.sqrt(best) if math.isfinite(best) else None


def update_debug_geometry(doc, seam_obj, pin_obj, backend, pins):
    positions = backend.positions()
    lines = []
    for a, b in getattr(backend, "_stitches", ()):
        pa, pb = positions[int(a)], positions[int(b)]
        lines.append(Part.makePolygon([App.Vector(*pa), App.Vector(*pb)]))
    seam_obj.Shape = Part.makeCompound(lines) if lines else Part.Shape()
    spheres = [Part.makeSphere(13.0, App.Vector(*positions[int(i)])) for i in pins]
    pin_obj.Shape = Part.makeCompound(spheres) if spheres else Part.Shape()
    doc.recompute()


def checkpoint_metrics(backend, pins, initial_pins, target_vertices, triangles, step):
    positions = backend.positions()
    seam_gaps = [math.dist(positions[int(a)], positions[int(b)]) for a, b in getattr(backend, "_stitches", ())]
    pin_drifts = [math.dist(positions[int(i)], p0) for i, p0 in zip(pins, initial_pins)]
    xs = [float(p[0]) for p in positions]
    ys = [float(p[1]) for p in positions]
    zs = [float(p[2]) for p in positions]
    result = {
        "backend": getattr(backend, "name", "unknown"),
        "collision_mode": os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh"),
        "requested_step": step,
        "finite": bool(backend.finite()),
        "bounds": [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)],
        "centroid": [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)],
        "maximum_seam_gap_mm": max(seam_gaps) if seam_gaps else 0.0,
        "maximum_pin_drift_mm": max(pin_drifts) if pin_drifts else 0.0,
        "sampled_minimum_vertex_to_target_mm": sampled_min_distance(positions, target_vertices),
        "finite_vertices": all(math.isfinite(float(c)) for p in positions for c in p),
        "cloth_vertices": len(positions),
        "stitch_constraints": len(getattr(backend, "_stitches", ())),
        "pin_constraints": len(pins),
    }
    result.update(triangle_metrics(positions, triangles))
    return result


def run():
    backend_requested = os.environ.get("CLOTH_SIMULATION_BACKEND", "auto")
    collision_mode = os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh")
    print("DRAPE-DEBUG: backend=%s collision=%s" % (backend_requested, collision_mode), flush=True)
    doc = App.newDocument("ClothDrapeDebugFast")
    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    if avatar is None:
        raise RuntimeError("production avatar missing")
    base = scene.Proxy._base_or_restore()
    backend = getattr(base, "backend", None)
    if backend is None:
        raise RuntimeError("production simulation backend missing")
    pins = tuple(dict.fromkeys(int(i) for i in (
        getattr(backend, "_pins", ())
        or getattr(backend, "_pin_indices", ())
        or tuple(getattr(getattr(backend, "system", None), "pins", {}).keys())
    )))
    stitches = tuple((int(a), int(b)) for a, b in getattr(backend, "_stitches", ()))
    if not stitches and hasattr(backend, "system"):
        stitches = tuple((int(c.a), int(c.b)) for c in getattr(backend.system, "stitches", ()))
        backend._stitches = stitches
    if not stitches:
        raise RuntimeError("production backend has no stitch constraints")
    target_vertices = [tuple(v) for v in avatar.Mesh.Points]
    initial_positions = backend.positions()
    initial_pins = tuple(initial_positions[i] for i in pins)
    triangles = []
    for panel in scene.DrapePanels:
        source = getattr(panel, "SourceObject", panel)
        try:
            _, tris, _ = quality_piece_mesh(source, 0.0, scene.ParticleDistance)
            triangles.extend(tris)
        except Exception:
            pass
    if not triangles and hasattr(backend, "system"):
        triangles = tuple(getattr(backend.system, "triangles", ()))
    for panel in scene.DrapePanels:
        panel.ViewObject.DisplayMode = "Flat Lines"
        panel.ViewObject.ShapeColor = (0.78, 0.16, 0.08)
        panel.ViewObject.LineColor = (0.18, 0.01, 0.01)
        panel.ViewObject.LineWidth = 1.6
        panel.ViewObject.Visibility = True
    try:
        avatar.ViewObject.DisplayMode = "Flat Lines"
        avatar.ViewObject.Transparency = 72
        avatar.ViewObject.LineColor = (0.25, 0.25, 0.25)
    except Exception:
        pass
    seam_obj = doc.addObject("Part::Feature", "DebugCurrentStitches")
    seam_obj.ViewObject.LineColor = (1.0, 0.90, 0.0)
    seam_obj.ViewObject.LineWidth = 4.0
    pin_obj = doc.addObject("Part::Feature", "DebugActivePins")
    pin_obj.ViewObject.ShapeColor = (1.0, 0.10, 1.0)
    pin_obj.ViewObject.Transparency = 5
    update_debug_geometry(doc, seam_obj, pin_obj, backend, pins)
    doc.recompute(); events()
    panel = SimulationQualityTaskPanel(scene)
    panel.accept(); close_task(); doc.recompute()
    checkpoints = []
    try:
        for target_step in STEPS:
            while int(scene.Steps) < target_step:
                panel.step(1)
            doc.recompute(); update_debug_geometry(doc, seam_obj, pin_obj, backend, pins); events()
            checkpoints.append(checkpoint_metrics(backend, pins, initial_pins, target_vertices, triangles, target_step))
            view = Gui.activeDocument().activeView()
            view.setCameraType("Orthographic"); view.viewRear(); view.fitAll(); events()
            view.saveImage(str(OUT / ("front-step-%03d.png" % target_step)), 1280, 720, "Current", 1)
            if target_step == 6:
                view.viewLeft(); view.fitAll(); events()
                view.saveImage(str(OUT / "left-step-006.png"), 1280, 720, "Current", 1)
    finally:
        close_task()
        (OUT / "metrics.json").write_text(json.dumps({
            "backend": getattr(backend, "name", backend_requested),
            "collision_mode": collision_mode,
            "checkpoints": checkpoints,
        }, indent=2), encoding="utf-8")
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass


if __name__ == "__main__":
    run()
