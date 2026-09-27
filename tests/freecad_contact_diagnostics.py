"""Diagnostic controls 0/0a for the cloth complexity ladder.

This module is dormant in normal CI. A temporary marker file is used only by the
supervisor diagnostic PR to invoke it from the existing GUI audit job.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated"))
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "gui-progress.log"
PREFIX = "cloth-simulation-draped-diagnostic-control"


def log(message):
    line = "DIAGNOSTIC-LADDER: " + str(message)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def events():
    try:
        Gui.updateGui()
    except Exception:
        pass
    try:
        app = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets").QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _save(path, view):
    events()
    view.fitAll()
    events()
    view.saveImage(str(path), 1280, 720, "Current", 1)
    if not path.is_file() or path.stat().st_size < 1000:
        raise RuntimeError("diagnostic screenshot missing or too small: %s" % path)


def _make_rectangle_sketch(doc, name, width, height):
    import Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    points = (
        (-0.5 * width, -0.5 * height),
        (0.5 * width, -0.5 * height),
        (0.5 * width, 0.5 * height),
        (-0.5 * width, 0.5 * height),
    )
    for i in range(4):
        sketch.addGeometry(
            Part.LineSegment(
                App.Vector(points[i][0], points[i][1], 0),
                App.Vector(points[(i + 1) % 4][0], points[(i + 1) % 4][1], 0),
            ),
            False,
        )
    doc.recompute()
    return sketch


def _adopt_sketch(sketch, name):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=0.0, grainline=0.0)
    if piece.Sketch is not sketch:
        raise RuntimeError("diagnostic PatternPiece did not retain source sketch")
    doc = sketch.Document
    doc.recompute()
    return piece


def _scene_baseline(scene):
    return {
        "particle_distance_mm": float(getattr(scene, "ParticleDistance")),
        "solver_iterations": int(getattr(scene, "SolverIterations")),
        "solver_substeps": int(getattr(scene, "SolverSubsteps")),
        "time_step": float(getattr(scene, "TimeStep")),
        "gravity": (
            float(getattr(scene, "GravityX")),
            float(getattr(scene, "GravityY")),
            float(getattr(scene, "GravityZ")),
        ),
        "fabric_friction": float(getattr(scene, "FabricFriction")),
    }


def _inside_counts(shape, positions):
    return sum(
        1
        for point in positions
        if shape.isInside(App.Vector(float(point[0]), float(point[1]), float(point[2])), 0.01, True)
    )


def _bounds(positions):
    xs = [float(p[0]) for p in positions]
    ys = [float(p[1]) for p in positions]
    zs = [float(p[2]) for p in positions]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "centroid": [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)],
    }


def _write_panel(backend, scene, panel):
    positions = backend.positions()
    indices = tuple(backend.panel_indices.get(panel.Name, ()))
    triangles = backend.panel_triangles.get(panel.Name, ())
    if not indices:
        return
    vertices = [App.Vector(*positions[i]) for i in indices]
    faces = [Part.Face(Part.makePolygon([
        vertices[tri[0]], vertices[tri[1]], vertices[tri[2]], vertices[tri[0]]
    ])) for tri in triangles if max(tri) < len(vertices)]
    panel.Mesh = Part.makePolygon([]) if not faces else Part.makeCompound([face.Shape for face in faces])


def _prepare_scene(doc, target, piece):
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy, ensure_quality_properties
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source

    scene = create_simulation_scene(doc)
    set_avatar_collision_source(scene, target, thickness=2.0, deflection=1.0)
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.ClothPieces = [piece]
    scene.PinSelection = []
    scene.PinMode = "None"
    scene.ParticleDistance = 32.0
    scene.SolverIterations = 1
    scene.SolverSubsteps = 1
    scene.FabricFriction = 0.85
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    doc.recompute()
    return scene


def _run_case(doc, scene, target, case_id):
    scene.Steps = 0
    doc.recompute()
    backend = scene.Proxy._base_or_restore().backend
    if getattr(backend, "name", "") != "tissu":
        raise RuntimeError("diagnostic case %s did not select Tissu backend" % case_id)
    source_shape = target.Shape
    before = tuple(backend.positions())
    before_inside = _inside_counts(source_shape, before)
    started = time.monotonic()
    view = Gui.activeDocument().activeView()
    _save(OUT / ("%s-%s-step-000.png" % (PREFIX, case_id)), view)

    scene.Steps = 1
    doc.recompute()
    after = tuple(backend.positions())
    after_inside = _inside_counts(source_shape, after)
    _save(OUT / ("%s-%s-step-001.png" % (PREFIX, case_id)), view)

    metrics = {
        "case_id": case_id,
        "target_kind": "FreeCAD Geometry" if case_id == "0" else "MakeHuman DrapeTarget",
        "piece_count": 1,
        "seam_mode": "none",
        "pin_mode": "none",
        "cloth_bounds_world_mm_before_step": _bounds(before),
        "cloth_bounds_world_mm_after_step": _bounds(after),
        "finite_before": bool(backend.finite()),
        "finite_after": bool(backend.finite()),
        "inside_vertices_before": int(before_inside),
        "inside_vertices_after": int(after_inside),
        "inside_vertices_resolved": int(after_inside <= before_inside),
        "runtime_ms": 1000.0 * (time.monotonic() - started),
        "solver_triangle_count": len(getattr(backend, "solver_triangles", ())) if hasattr(backend, "solver_triangles") else None,
        "collision_mode": os.environ.get("CLOTH_TISSU_COLLISION_MODE", "mesh"),
        "collision_triangle_budget": int(os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", "2048")),
        "baseline": _scene_baseline(scene),
    }
    return metrics


def control_0():
    doc = App.newDocument("ClothDiagnosticControl0")
    try:
        cube = doc.addObject("Part::Feature", "DiagnosticCube")
        cube.Shape = Part.makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
        sketch = _make_rectangle_sketch(doc, "DiagnosticCubeCloth", 120.0, 120.0)
        piece = _adopt_sketch(sketch, "DiagnosticCubeClothPiece")
        placement = App.Placement(App.Vector(0.0, 0.0, 59.0), App.Rotation())
        piece.Placement = placement
        piece.Sketch.Placement = placement
        scene = _prepare_scene(doc, cube, piece)
        return _run_case(doc, scene, cube, "0")
    finally:
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass


def _avatar_probe_point(avatar):
    box = avatar.Mesh.BoundBox
    points = []
    z_mid = float(box.ZMin + 0.60 * box.ZLength)
    x_mid = float((box.XMin + box.XMax) * 0.5)
    for point in avatar.Mesh.Points:
        if abs(float(point.x) - x_mid) <= 0.25 * float(box.XLength) and abs(float(point.z) - z_mid) <= 0.18 * float(box.ZLength):
            points.append(point)
    if not points:
        points = list(avatar.Mesh.Points)
    return max(points, key=lambda p: float(p.y))


def control_0a():
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene

    doc = App.newDocument("ClothDiagnosticControl0a")
    try:
        scene0 = create_quality_simulation_scene(doc)
        avatar = getattr(scene0.AvatarProxy, "SourceObject", None)
        if avatar is None:
            raise RuntimeError("production avatar missing")
        probe = _avatar_probe_point(avatar)
        sketch = _make_rectangle_sketch(doc, "DiagnosticAvatarCloth", 160.0, 180.0)
        piece = _adopt_sketch(sketch, "DiagnosticAvatarClothPiece")
        placement = App.Placement(
            App.Vector(float(probe.x) - 80.0, float(probe.y) - 1.0, float(probe.z) - 90.0),
            App.Rotation(App.Vector(1, 0, 0), 90.0),
        )
        piece.Placement = placement
        piece.Sketch.Placement = placement
        scene = _prepare_scene(doc, doc.getObject("DrapeTarget").SourceObject, piece)
        return _run_case(doc, scene, avatar, "0a")
    finally:
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass


def run():
    os.environ["CLOTH_SIMULATION_BACKEND"] = "tissu"
    os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_TISSU_COLLISION_TRIANGLES"] = "2048"
    results = []
    results.append(control_0())
    results.append(control_0a())
    payload = {
        "schema": 1,
        "controls": results,
        "first_failure": next(
            (item["case_id"] for item in results if item["inside_vertices_after"] > item["inside_vertices_before"]),
            None,
        ),
    }
    (OUT / "diagnostic-control-results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    log("diagnostic-controls=" + json.dumps(payload, sort_keys=True))
    log("diagnostic-controls=passed" if payload["first_failure"] is None else "diagnostic-controls=failed first_failure=%s" % payload["first_failure"])
    return payload


if __name__ == "__main__":
    run()
