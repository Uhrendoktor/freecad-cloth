"""Diagnostic controls for separating target/contact behavior from gravity and garment complexity.

This script is intentionally diagnostic-only. It exercises the existing FreeCAD/Tissu
runtime without changing physics, solver budgets, canonical fixtures, or release gates.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part


OUT = Path(os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/tissu-contact-diagnostics"))
OUT.mkdir(parents=True, exist_ok=True)
STEPS = (0, 1)
PARTICLE_DISTANCE = 24.0


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def _add_rectangle_sketch(doc, name, width, height):
    import Sketcher

    sketch = doc.addObject("Sketcher::SketchObject", name)
    pts = (
        (0.0, 0.0),
        (float(width), 0.0),
        (float(width), float(height)),
        (0.0, float(height)),
    )
    for index, start in enumerate(pts):
        end = pts[(index + 1) % 4]
        sketch.addGeometry(
            Part.LineSegment(
                App.Vector(start[0], start[1], 0.0),
                App.Vector(end[0], end[1], 0.0),
            ),
            False,
        )
    doc.recompute()
    return sketch


def _adopt_sketch(sketch, name):
    import FreeCADGui as Gui
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=0.0, grainline=0.0)
    Gui.Selection.clearSelection()
    doc = sketch.Document
    doc.recompute()
    return piece


def _mesh_points(obj):
    mesh = getattr(obj, "Mesh", None)
    if mesh is None:
        raise RuntimeError("missing Mesh property on %s" % getattr(obj, "Name", "object"))
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        raise RuntimeError("missing mesh topology on %s" % getattr(obj, "Name", "object"))
    vertices, _triangles = topology
    return tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)


def _bounds(points):
    if not points:
        raise RuntimeError("cannot measure empty point set")
    return (
        min(p[0] for p in points), max(p[0] for p in points),
        min(p[1] for p in points), max(p[1] for p in points),
        min(p[2] for p in points), max(p[2] for p in points),
    )


def _centroid(points):
    n = float(len(points))
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def _minimum_vertex_distance(source_points, target_points):
    best = float("inf")
    best_pair = None
    for source in source_points:
        for target in target_points:
            d2 = sum((source[i] - target[i]) ** 2 for i in range(3))
            if d2 < best:
                best = d2
                best_pair = (source, target)
    return math.sqrt(best) if math.isfinite(best) else None, best_pair


def _target_signature(target):
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("diagnostic target has no source")
    return {
        "target_type": str(getattr(target, "TargetType", "")),
        "source_name": str(getattr(source, "Name", "")),
        "source_label": str(getattr(source, "Label", "")),
        "source_revision": int(getattr(source, "AvatarRevision", 0)),
        "source_vertices": int(getattr(source, "MeshVertexCount", getattr(source.Mesh, "CountPoints", 0))),
        "source_triangles": int(getattr(source, "MeshTriangleCount", getattr(source.Mesh, "CountFacets", 0))),
        "collision_triangles_authored": int(getattr(target, "CollisionTriangleCount", 0)),
        "collision_vertices_authored": int(getattr(target, "CollisionVertexCount", 0)),
    }


def _screenshot(view, path):
    view.setCameraType("Orthographic")
    view.fitAll()
    _events()
    view.saveImage(str(path), 1280, 720, "White", 1)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError("screenshot missing: %s" % path)


def _case_record(case_id, target, cloth_points_before, cloth_points_after, solver_surface_triangles, steps, image_paths):
    before_centroid = _centroid(cloth_points_before)
    after_centroid = _centroid(cloth_points_after)
    before_bounds = _bounds(cloth_points_before)
    after_bounds = _bounds(cloth_points_after)
    target_source = getattr(target, "SourceObject", None)
    target_points = _mesh_points(target_source)
    before_distance, before_pair = _minimum_vertex_distance(cloth_points_before, target_points)
    after_distance, after_pair = _minimum_vertex_distance(cloth_points_after, target_points)
    displacement = math.sqrt(
        sum((after_centroid[i] - before_centroid[i]) ** 2 for i in range(3))
    )
    if displacement > 0.01 and (after_distance is None or before_distance is None or after_distance >= before_distance):
        contact_state = "projection-or-contact-response-observed"
    elif displacement <= 0.01:
        contact_state = "no-observable-response"
    else:
        contact_state = "response-toward-target-or-tangential-motion"
    return {
        "case": case_id,
        "steps": int(steps),
        "finite": all(math.isfinite(float(c)) for point in cloth_points_after for c in point),
        "cloth_before": {
            "bounds": before_bounds,
            "centroid": before_centroid,
            "nearest_target_vertex_distance_mm": before_distance,
            "nearest_pair": before_pair,
        },
        "cloth_after": {
            "bounds": after_bounds,
            "centroid": after_centroid,
            "nearest_target_vertex_distance_mm": after_distance,
            "nearest_pair": after_pair,
        },
        "centroid_displacement_mm": displacement,
        "solver_collision_triangles": int(solver_surface_triangles),
        "contact_state": contact_state,
        "images": image_paths,
        "target": _target_signature(target),
    }


def _build_scene(doc):
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import (
        create_quality_simulation_scene,
        ensure_quality_properties,
    )
    scene = create_quality_simulation_scene(doc)
    ensure_quality_properties(scene)
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = PARTICLE_DISTANCE
    scene.SolverIterations = 1
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = 0.0
    scene.FabricFriction = 0.5
    scene.PinMode = "None"
    scene.PinSelection = []
    scene.FabricTransparency = 0
    doc.recompute()
    return scene


def _build_piece(doc, name, placement, width=360.0, height=360.0):
    sketch = _add_rectangle_sketch(doc, name + "Source", width, height)
    piece = _adopt_sketch(sketch, name)
    piece.Placement = placement
    piece.Sketch.Placement = placement
    sketch.ViewObject.Visibility = False
    piece.ViewObject.Visibility = False
    doc.recompute()
    return piece


def _run_case(case_id, scene, piece, camera):
    scene.ClothPieces = [piece]
    scene.Steps = 0
    scene.touch()
    scene.Document.recompute()
    base = scene.Proxy._base_or_restore()
    backend = getattr(base, "backend", None)
    if backend is None:
        raise RuntimeError("%s did not build a simulation backend" % case_id)
    target = scene.DrapeTarget
    if target is None:
        raise RuntimeError("%s has no DrapeTarget" % case_id)
    status = __import__("freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]).target_status(target)
    if status["state"] != "ready":
        raise RuntimeError("%s DrapeTarget is not ready: %s" % (case_id, status))
    panel = next((obj for obj in scene.DrapePanels if obj.Name), None)
    if panel is None:
        raise RuntimeError("%s did not create a drape panel" % case_id)
    before = _mesh_points(panel)
    view = Gui.activeDocument().activeView()
    _screenshot(view, OUT / (case_id + "-step-000.png"))
    if camera == "front":
        view.viewFront()
    elif camera == "top":
        view.viewTop()
    else:
        view.viewAxonometric()
    _events()
    _screenshot(view, OUT / (case_id + "-step-000-camera.png"))

    scene.Steps = 1
    scene.Document.recompute()
    _events()
    after = _mesh_points(panel)
    _screenshot(view, OUT / (case_id + "-step-001-camera.png"))
    image_paths = [
        case_id + "-step-000.png",
        case_id + "-step-000-camera.png",
        case_id + "-step-001-camera.png",
    ]
    record = _case_record(
        case_id,
        target,
        before,
        after,
        len(getattr(base, "collision_surface", None).triangles)
        if getattr(base, "collision_surface", None) is not None
        else int(getattr(target, "CollisionTriangleCount", 0)),
        int(scene.Steps),
        image_paths,
    )
    record["backend"] = str(getattr(backend, "name", ""))
    return record


def _run_control_cube():
    doc = App.newDocument("TissuContactControlCube")
    try:
        scene = _build_scene(doc)
        cube = doc.addObject("Part::Feature", "DiagnosticCube")
        cube.Label = "Diagnostic Collision Cube"
        cube.Shape = Part.makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
        doc.recompute()
        from freecad_cloth.simulation.SimulationObjects import set_avatar_collision_source
        set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
        piece = _build_piece(
            doc,
            "CubeCloth",
            App.Placement(App.Vector(-180.0, -180.0, 58.5), App.Rotation()),
        )
        cube.ViewObject.Visibility = True
        record = _run_case("control-0-cube", scene, piece, "axonometric")
        return record
    finally:
        App.closeDocument(doc.Name)


def _run_control_avatar():
    doc = App.newDocument("TissuContactControlAvatar")
    try:
        scene = _build_scene(doc)
        avatar = scene.AvatarProxy.SourceObject
        box = avatar.Mesh.BoundBox
        center_y = (float(box.YMin) + float(box.YMax)) / 2.0
        center_z = float(box.ZMin) + 0.67 * float(box.ZMax - box.ZMin)
        center_x = (float(box.XMin) + float(box.XMax)) / 2.0
        placement = App.Placement(
            App.Vector(center_x - 180.0, center_y, center_z - 180.0),
            App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0),
        )
        piece = _build_piece(doc, "AvatarCloth", placement)
        avatar.ViewObject.Visibility = True
        record = _run_case("control-0a-avatar", scene, piece, "front")
        return record
    finally:
        App.closeDocument(doc.Name)


def main():
    records = [
        _run_control_cube(),
        _run_control_avatar(),
    ]
    manifest = {
        "schema": 1,
        "purpose": "diagnostic-only-contact-controls",
        "solver_settings_frozen": {
            "backend_requested": os.environ.get("CLOTH_SIMULATION_BACKEND", "auto"),
            "particle_distance_mm": PARTICLE_DISTANCE,
            "iterations": 1,
            "substeps": 1,
            "timestep_s": 1.0 / 120.0,
            "gravity_mm_s2": [0.0, 0.0, 0.0],
            "fabric_friction": 0.5,
        },
        "cases": records,
        "release_gate_effect": "none",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
