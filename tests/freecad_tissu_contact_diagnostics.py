"""Diagnostic controls for separating target/contact behavior from gravity and garment complexity.

This script is intentionally diagnostic-only. It exercises the existing FreeCAD/Tissu
runtime without changing physics, solver budgets, canonical fixtures, or release gates.
"""
from __future__ import annotations

import faulthandler
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/tissu-contact-diagnostics"))
OUT.mkdir(parents=True, exist_ok=True)
PROGRESS = OUT / "progress.log"
_PROGRESS_HANDLE = PROGRESS.open("a", encoding="utf-8", buffering=1)
faulthandler.enable(file=_PROGRESS_HANDLE)
_PROGRESS_HANDLE.write("\n=== diagnostic contact controls start ===\n")
_PROGRESS_HANDLE.write("entrypoint __name__=%r\n" % __name__)
_PROGRESS_HANDLE.flush()
faulthandler.dump_traceback_later(30.0, repeat=True, file=_PROGRESS_HANDLE)

def _import_progress(label):
    line = "import: " + str(label)
    with PROGRESS.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)

_import_progress("FreeCAD begin")
import FreeCAD as App
_import_progress("FreeCAD complete")
_import_progress("FreeCADGui begin")
import FreeCADGui as Gui
_import_progress("FreeCADGui complete")
_import_progress("Part begin")
import Part
_import_progress("Part complete")

STEPS = (0, 1)
PARTICLE_DISTANCE = 24.0


def _progress(message):
    line = str(message)
    with PROGRESS.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    Gui.updateGui()


def _ensure_gui_ready():
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show()
    _events()


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


def _mesh_geometry(obj):
    mesh = getattr(obj, "Mesh", None)
    if mesh is not None:
        topology = getattr(mesh, "Topology", None)
        if topology is not None:
            vertices, triangles = topology
            points = tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)
            tris = tuple(tuple(int(i) for i in tri) for tri in triangles)
            return points, tris
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise RuntimeError("missing mesh or shape geometry on %s" % getattr(obj, "Name", "object"))
    vertices, triangles = shape.tessellate(1.0)
    points = tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)
    tris = tuple(tuple(int(i) for i in tri) for tri in triangles)
    return points, tris


def _mesh_points(obj):
    return _mesh_geometry(obj)[0]


def _connected_components(vertices, triangles):
    if not vertices:
        return 0
    parent = list(range(len(vertices)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        a = find(left)
        b = find(right)
        if a != b:
            parent[b] = a

    for triangle in triangles:
        if len(triangle) != 3:
            continue
        a, b, c = (int(i) for i in triangle)
        if all(0 <= i < len(vertices) for i in (a, b, c)):
            union(a, b)
            union(b, c)
    return len({find(i) for i in range(len(vertices))})


def _nearest_surface_observation(garment_points, surface):
    if not garment_points or surface is None:
        return None, None
    vertices = tuple(getattr(surface, "vertices", ()) or ())
    if not vertices:
        return None, None
    best = float("inf")
    point = None
    for source in garment_points:
        for target in vertices:
            d2 = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target))
            if d2 < best:
                best = d2
                point = tuple(float(c) for c in target)
    return (math.sqrt(best) if math.isfinite(best) else None), point


def _ray_intersection_x(point, a, b, c):
    px, py, pz = point
    ay, az = float(a[1]) - py, float(a[2]) - pz
    by, bz = float(b[1]) - py, float(b[2]) - pz
    cy, cz = float(c[1]) - py, float(c[2]) - pz
    det = ((float(b[1]) - float(a[1])) * (float(c[2]) - float(a[2])) -
           (float(b[2]) - float(a[2])) * (float(c[1]) - float(a[1])))
    if abs(det) <= 1e-12:
        return False
    u = (ay * (float(c[2]) - float(a[2])) - az * (float(c[1]) - float(a[1]))) / det
    v = ((float(b[1]) - float(a[1])) * az - (float(b[2]) - float(a[2])) * ay) / det
    if u < -1e-9 or v < -1e-9 or u + v > 1.0 + 1e-9:
        return False
    x_hit = float(a[0]) + u * (float(b[0]) - float(a[0])) + v * (float(c[0]) - float(a[0]))
    return x_hit > px + 1e-7


def _point_inside_mesh(point, vertices, triangles):
    ray = (1.0, 0.3713906763541037, 0.1932424973120743)
    origin = (float(point[0]), float(point[1]), float(point[2]))
    hits = 0
    epsilon = 1e-9

    def cross(left, right):
        return (
            left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0],
        )

    def dot(left, right):
        return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]

    for triangle in triangles:
        if len(triangle) != 3:
            continue
        ia, ib, ic = (int(index) for index in triangle)
        if any(index < 0 or index >= len(vertices) for index in (ia, ib, ic)):
            continue
        a = vertices[ia]
        b = vertices[ib]
        c = vertices[ic]
        e1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        e2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        pvec = cross(ray, e2)
        determinant = dot(e1, pvec)
        if abs(determinant) <= epsilon:
            continue
        inv_det = 1.0 / determinant
        tvec = (origin[0] - a[0], origin[1] - a[1], origin[2] - a[2])
        u = dot(tvec, pvec) * inv_det
        if u < -epsilon or u > 1.0 + epsilon:
            continue
        qvec = cross(tvec, e1)
        v = dot(ray, qvec) * inv_det
        if v < -epsilon or u + v > 1.0 + epsilon:
            continue
        distance = dot(e2, qvec) * inv_det
        if distance > epsilon:
            hits += 1
    return bool(hits % 2)

def _inside_outside(points, source):
    shape = getattr(source, "Shape", None)
    if shape is not None and not getattr(shape, "isNull", lambda: True)():
        states = []
        for point in points[:64]:
            try:
                states.append(bool(shape.isInside(App.Vector(*point), 1e-6, True)))
            except (AttributeError, TypeError, ValueError):
                states = []
                break
        if states:
            if all(states):
                return "inside"
            if not any(states):
                return "outside"
            return "mixed"

    mesh = getattr(source, "Mesh", None)
    mesh_is_inside = getattr(mesh, "isInside", None) if mesh is not None else None
    if callable(mesh_is_inside):
        states = []
        for point in points[:64]:
            try:
                states.append(bool(mesh_is_inside(App.Vector(*point), 1e-6, True)))
            except (AttributeError, TypeError, ValueError):
                states = []
                break
        if states:
            if all(states):
                return "inside"
            if not any(states):
                return "outside"
            return "mixed"

    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return "unknown"
    raw_vertices, raw_faces = topology
    vertices = tuple((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
    triangles = tuple(tuple(int(i) for i in face) for face in raw_faces)
    if not vertices or not triangles:
        return "unknown"
    try:
        import numpy as np
        import trimesh
        target_mesh = trimesh.Trimesh(
            vertices=np.asarray(vertices, dtype=float),
            faces=np.asarray(triangles, dtype=int),
            process=False,
        )
        if not target_mesh.is_watertight:
            raise RuntimeError("target mesh is not watertight")
        states = [bool(value) for value in target_mesh.contains(np.asarray(points[:64], dtype=float))]
    except (ImportError, RuntimeError, TypeError, ValueError):
        states = [_point_inside_mesh(point, vertices, triangles) for point in points[:64]]
    if not states:
        return "unknown"
    if all(states):
        return "inside"
    if not any(states):
        return "outside"
    return "mixed"


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


def _nearest_surface_distance(garment_points, surface):
    if not garment_points or surface is None:
        return None
    vertices = tuple(getattr(surface, "vertices", ()) or ())
    triangles = tuple(getattr(surface, "triangles", ()) or ())
    if not vertices:
        return None
    if triangles:
        try:
            from freecad_cloth.common.MeshValidation import nearest_surface_clearance
            return float(nearest_surface_clearance(garment_points, vertices, triangles))
        except (ImportError, RuntimeError, ValueError):
            pass
    sample = vertices[::max(1, len(vertices) // 4096)]
    best = float("inf")
    for source in garment_points:
        for target in sample:
            d2 = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target))
            if d2 < best:
                best = d2
    return math.sqrt(best) if math.isfinite(best) else None


def _target_signature(target):
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("diagnostic target has no source")
    mesh = getattr(source, "Mesh", None)
    return {
        "target_type": str(getattr(target, "TargetType", "")),
        "source_name": str(getattr(source, "Name", "")),
        "source_label": str(getattr(source, "Label", "")),
        "source_revision": int(getattr(source, "AvatarRevision", 0)),
        "source_vertices": int(getattr(source, "MeshVertexCount", getattr(mesh, "CountPoints", 0) if mesh is not None else 0)),
        "source_triangles": int(getattr(source, "MeshTriangleCount", getattr(mesh, "CountFacets", 0) if mesh is not None else 0)),
        "collision_triangles_authored": int(getattr(target, "CollisionTriangleCount", 0)),
        "collision_vertices_authored": int(getattr(target, "CollisionVertexCount", 0)),
    }


def _screenshot(view, path):
    view.setCameraType("Orthographic")
    view.fitAll()
    _events()
    view.saveImage(str(path), 1280, 720, "White")
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError("screenshot missing: %s" % path)


def _case_record(case_id, rung, target, source, cloth_points_before, cloth_points_after, panel_triangles, collision_surface, steps, image_paths, runtime_ms):
    before_centroid = _centroid(cloth_points_before)
    after_centroid = _centroid(cloth_points_after)
    before_bounds = _bounds(cloth_points_before)
    after_bounds = _bounds(cloth_points_after)
    before_distance = _nearest_surface_distance(cloth_points_before, collision_surface)
    after_distance = _nearest_surface_distance(cloth_points_after, collision_surface)
    _, before_nearest_point = _nearest_surface_observation(cloth_points_before, collision_surface)
    _, after_nearest_point = _nearest_surface_observation(cloth_points_after, collision_surface)
    displacement = math.sqrt(sum((after_centroid[i] - before_centroid[i]) ** 2 for i in range(3)))
    max_vertex_displacement = max(
        math.sqrt(sum((after[i] - before[i]) ** 2 for i in range(3)))
        for before, after in zip(cloth_points_before, cloth_points_after)
    )
    before_inside = _inside_outside(cloth_points_before, source)
    after_inside = _inside_outside(cloth_points_after, source)
    if max_vertex_displacement > 0.01 and before_distance is not None and after_distance is not None and after_distance >= before_distance:
        contact_state = "projection-or-contact-response-observed"
    elif max_vertex_displacement <= 0.01:
        contact_state = "no-observable-response"
    else:
        contact_state = "response-toward-target-or-tangential-motion"

    target_points, target_triangles = _mesh_geometry(source)
    target_bounds = _bounds(target_points)
    target_sig = _target_signature(target)
    target_surface_triangles = int(len(getattr(collision_surface, "triangles", ()) or ()))
    signed_before = None if before_distance is None else (-before_distance if before_inside in {"inside", "mixed"} else before_distance)
    signed_after = None if after_distance is None else (-after_distance if after_inside in {"inside", "mixed"} else after_distance)
    after_components = _connected_components(cloth_points_after, panel_triangles)
    finite = all(math.isfinite(float(c)) for point in cloth_points_after for c in point)

    checkpoint = {
        "step": 0,
        "image": image_paths[0],
        "finite": all(math.isfinite(float(c)) for point in cloth_points_before for c in point),
        "components": _connected_components(cloth_points_before, panel_triangles),
        "max_seam_gap_mm": 0.0,
        "target_clearance_mm": signed_before,
        "contact_state": "static-intersection-probe",
        "inside_outside": before_inside,
        "nearest_target_point": before_nearest_point,
    }
    checkpoint_after = {
        "step": int(steps),
        "image": image_paths[-1],
        "finite": finite,
        "components": after_components,
        "max_seam_gap_mm": 0.0,
        "target_clearance_mm": signed_after,
        "contact_state": contact_state,
        "inside_outside": after_inside,
        "nearest_target_point": after_nearest_point,
    }
    collision = {
        "source_signature": target_sig,
        "source_triangles": len(target_triangles),
        "solver_triangles": target_surface_triangles,
        "target_bounds": target_bounds,
        "target_topology_summary": {
            "vertices": len(target_points),
            "triangles": len(target_triangles),
            "solver_triangles": target_surface_triangles,
        },
    }
    solver = {
        "backend": "tissu",
        "particle_distance_mm": PARTICLE_DISTANCE,
        "iterations": 1,
        "substeps": 1,
        "timestep_s": 1.0 / 120.0,
        "gravity_z_mm_s2": 0.0,
    }
    return {
        "case_id": case_id,
        "predecessor_case_id": None,
        "case": {
            "rung": int(rung),
            "id": case_id,
            "target": str(target_sig["target_type"]).lower().replace(" ", "-"),
            "piece_count": 1,
            "pin_mode": "None",
            "seam_mode": "none",
        },
        "solver": solver,
        "collision": collision,
        "pre_step": {
            "piece_bounds": [list(before_bounds)],
            "unsigned_clearance_mm": before_distance,
            "signed_clearance_mm": signed_before,
            "seam_pairs": [],
            "seam_world_spans_mm": [],
        },
        "checkpoints": [checkpoint, checkpoint_after],
        "finite": finite,
        "connected_components": after_components,
        "max_seam_gap_mm": 0.0,
        "final_clearance_mm": signed_after,
        "runtime_ms": round(float(runtime_ms), 3),
        "first_contact_step": int(steps) if max_vertex_displacement > 0.01 else None,
        "contact_mode": contact_state,
        "control": {
            "nearest_target_point_before": before_nearest_point,
            "nearest_target_point_after": after_nearest_point,
            "nearest_target_distance_before_mm": before_distance,
            "nearest_target_distance_after_mm": after_distance,
            "inside_outside_before": before_inside,
            "inside_outside_after": after_inside,
            "one_step_projection_delta_mm": max_vertex_displacement,
            "centroid_displacement_mm": displacement,
        },
        "images": image_paths,
        "notes": "diagnostic-only; one unchanged Tissu step; release gate unaffected",
    }


def _build_scene(doc):
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import (
        QualitySimulationProxy,
        ensure_quality_properties,
    )
    scene = create_simulation_scene(doc, build=False)
    legacy = doc.getObject("HumanoidAvatar")
    if legacy is not None and hasattr(legacy, "ViewObject"):
        legacy.ViewObject.Visibility = False
    avatar = create_avatar(attach_collision=False, doc=doc)
    avatar.Label = "Cloth Human Avatar (MakeHuman)"
    avatar.ViewObject.Visibility = True
    set_avatar_collision_source(scene, avatar, float(getattr(avatar, "SkinOffset", 3.0)), 1.0)
    scene.AvatarProxy.SourceObject = avatar
    scene.DrapeTarget = doc.getObject("DrapeTarget")
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
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
    return scene


def _build_piece(doc, name, placement, width=120.0, height=120.0):
    sketch = _add_rectangle_sketch(doc, name + "Source", width, height)
    piece = _adopt_sketch(sketch, name)
    piece.Placement = placement
    piece.Sketch.Placement = placement
    sketch.ViewObject.Visibility = False
    piece.ViewObject.Visibility = False
    doc.recompute()
    return piece


def _run_case(case_id, rung, scene, piece, camera):
    started = time.perf_counter()
    _progress(f"{case_id}: assign-piece")
    scene.ClothPieces = [piece]
    scene.Steps = 0
    scene.touch()
    scene.Document.recompute()
    _progress(f"{case_id}: scene-ready")
    base = scene.Proxy._base_or_restore()
    backend = getattr(base, "backend", None)
    if backend is None:
        raise RuntimeError("%s did not build a simulation backend" % case_id)
    _progress(f"{case_id}: backend={getattr(backend, 'name', '')}")
    _progress(
        "tissu-env: collision_mode=%s collision_triangles=%s backend_module=%s"
        % (
            os.environ.get("CLOTH_TISSU_COLLISION_MODE", "<unset>"),
            os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", "<unset>"),
            getattr(__import__("freecad_cloth.simulation.TissuBackend", fromlist=["__file__"]), "__file__", "<unknown>"),
        )
    )
    target = scene.DrapeTarget
    if target is None:
        raise RuntimeError("%s has no DrapeTarget" % case_id)
    status = __import__("freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]).target_status(target)
    if status["state"] != "ready":
        raise RuntimeError("%s DrapeTarget is not ready: %s" % (case_id, status))
    panel = next((obj for obj in scene.DrapePanels if obj.Name), None)
    if panel is None:
        raise RuntimeError("%s did not create a drape panel" % case_id)
    before, panel_triangles = _mesh_geometry(panel)
    solver_collision_surface = getattr(
        getattr(base, "backend", None),
        "solver_collision_surface",
        getattr(base, "collision_surface", None),
    )
    solver_triangle_count = len(getattr(solver_collision_surface, "triangles", ()) or ())
    _progress(f"{case_id}: panel-vertices={len(before)} collision-triangles={solver_triangle_count}")
    view = Gui.activeDocument().activeView()
    if view is None:
        raise RuntimeError("%s has no active FreeCAD view" % case_id)
    _screenshot(view, OUT / (case_id + "-step-000.png"))
    _progress(f"{case_id}: screenshot-000")
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
    after, _after_triangles = _mesh_geometry(panel)
    _screenshot(view, OUT / (case_id + "-step-001-camera.png"))
    _progress(f"{case_id}: screenshot-001")
    image_paths = [
        case_id + "-step-000.png",
        case_id + "-step-000-camera.png",
        case_id + "-step-001-camera.png",
    ]
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("%s target source missing" % case_id)
    record = _case_record(
        case_id,
        rung,
        target,
        source,
        before,
        after,
        panel_triangles,
        solver_collision_surface,
        int(scene.Steps),
        image_paths,
        (time.perf_counter() - started) * 1000.0,
    )
    _progress(f"{case_id}: record-ready")
    return record



def _ladder_snapshot(case_id, step, scene, pieces, collision_surface, cube, initial_positions):
    base = scene.Proxy._base_or_restore()
    backend = base.backend
    positions = tuple(
        (float(point[0]), float(point[1]), float(point[2]))
        for point in backend.positions()
    )
    triangles = []
    for panel in getattr(scene, "DrapePanels", ()):
        triangles.extend(tuple(base.panel_triangles.get(panel.Name, ())))
    bounds = _bounds(positions)
    unsigned_clearance = _nearest_surface_distance(positions, collision_surface)
    inside = _inside_outside(positions, cube)
    signed_clearance = (
        None
        if unsigned_clearance is None
        else (-unsigned_clearance if inside in {"inside", "mixed"} else unsigned_clearance)
    )
    max_displacement = max(
        math.sqrt(sum((positions[index][axis] - initial_positions[index][axis]) ** 2 for axis in range(3)))
        for index in range(min(len(initial_positions), len(positions)))
    ) if positions and initial_positions else 0.0
    seam_pairs = getattr(base, "seam_stitch_pairs", {}) or {}
    seam_records = []
    max_seam_gap = 0.0
    for seam_id, pairs in seam_pairs.items():
        spans = []
        for left, right in pairs:
            a = positions[int(left)]
            b = positions[int(right)]
            distance = math.sqrt(sum((a[axis] - b[axis]) ** 2 for axis in range(3)))
            spans.append(distance)
            max_seam_gap = max(max_seam_gap, distance)
        if spans:
            seam_records.append({
                "seam_id": str(seam_id),
                "pair_count": len(spans),
                "min_mm": min(spans),
                "max_mm": max(spans),
                "mean_mm": sum(spans) / len(spans),
            })
    checkpoint = {
        "step": int(step),
        "image": f"{case_id}-step-{int(step):03d}.png",
        "finite": bool(scene.FiniteState) and all(
            math.isfinite(float(value)) for point in positions for value in point
        ),
        "components": _connected_components(positions, tuple(triangles)),
        "max_seam_gap_mm": max_seam_gap,
        "target_clearance_mm": signed_clearance,
        "contact_state": (
            "motion-observed" if max_displacement > 0.01 else "no-observable-response"
        ),
        "inside_outside": inside,
        "nearest_target_point": None,
        "max_displacement_from_step0_mm": max_displacement,
    }
    return {
        "positions": positions,
        "bounds": bounds,
        "unsigned_clearance": unsigned_clearance,
        "signed_clearance": signed_clearance,
        "seam_records": seam_records,
        "max_seam_gap": max_seam_gap,
        "max_displacement": max_displacement,
        "checkpoint": checkpoint,
    }


def _run_ladder_case(case_id, rung, pin_mode, seam_mode="none", separation_mm=None):
    started = time.perf_counter()
    _progress(f"{case_id}: start")
    doc = App.newDocument("TissuCubeLadder_%s" % case_id)
    try:
        scene = _build_scene(doc)
        scene.StartHeight = 0.0
        scene.TimeStep = 1.0 / 120.0
        scene.SolverIterations = 1
        scene.SolverSubsteps = 1
        scene.GravityX = 0.0
        scene.GravityY = 0.0
        scene.GravityZ = -9810.0
        scene.ParticleDistance = PARTICLE_DISTANCE
        scene.PinMode = str(pin_mode)
        scene.PinSelection = []

        cube = doc.addObject("Part::Feature", "LadderTargetCube")
        cube.Label = "Diagnostic Ladder Collision Cube"
        cube.Shape = Part.makeBox(
            180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0)
        )
        doc.recompute()
        from freecad_cloth.simulation.SimulationObjects import set_avatar_collision_source
        set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
        if scene.AvatarProxy.SourceObject is not None and hasattr(
            scene.AvatarProxy.SourceObject, "ViewObject"
        ):
            scene.AvatarProxy.SourceObject.ViewObject.Visibility = False

        if rung in {1, 2}:
            pieces = [
                _build_piece(
                    doc,
                    "LadderPieceA",
                    App.Placement(
                        App.Vector(-60.0, -60.0, 90.0),
                        App.Rotation(),
                    ),
                    width=120.0,
                    height=120.0,
                )
            ]
        else:
            pieces = [
                _build_piece(
                    doc,
                    "LadderPieceA",
                    App.Placement(
                        App.Vector(-60.0, -60.0, 90.0),
                        App.Rotation(),
                    ),
                    width=120.0,
                    height=120.0,
                ),
                _build_piece(
                    doc,
                    "LadderPieceB",
                    App.Placement(
                        App.Vector(
                            -60.0 + float(separation_mm or 0.0),
                            -60.0,
                            90.0,
                        ),
                        App.Rotation(),
                    ),
                    width=120.0,
                    height=120.0,
                ),
            ]

        seam_object = None
        if seam_mode == "semantic":
            from freecad_cloth.pattern.PatternModel import Seam
            from freecad_cloth.pattern.PatternObjects import add_seam
            seam_object = add_seam(
                doc,
                Seam(
                    str(pieces[0].PieceId),
                    1,
                    str(pieces[1].PieceId),
                    3,
                    id="ladder-side-seam",
                    alignment="uniform",
                    stitch_group="CubeLadder",
                ),
            )
            if str(getattr(seam_object, "Status", "")) != "Valid":
                raise RuntimeError(
                    "ladder semantic seam is not valid: %s"
                    % getattr(seam_object, "Status", "")
                )

        scene.ClothPieces = list(pieces)
        doc.recompute()
        base = scene.Proxy._base_or_restore()
        backend = base.backend
        if backend is None or getattr(backend, "name", "") != "tissu":
            raise RuntimeError(
                "%s did not activate the Tissu backend: %s"
                % (case_id, getattr(backend, "name", "missing"))
            )
        collision_surface = getattr(
            getattr(backend, "solver_collision_surface", None),
            "triangles",
            None,
        )
        if collision_surface is None:
            collision_surface = getattr(
                getattr(backend, "collision_surface", None),
                "triangles",
                None,
            )
        solver_triangle_count = len(collision_surface or ())
        collision_surface = getattr(backend, "solver_collision_surface", None)
        if collision_surface is None:
            collision_surface = getattr(backend, "collision_surface", None)
        if not (collision_surface is not None and 0 < solver_triangle_count <= 2048):
            raise RuntimeError(
                "%s solver collision triangle count is invalid: %s"
                % (case_id, solver_triangle_count)
            )
        if rung in {1, 2}:
            scene.SeamSelection = []
        if rung >= 3 and seam_mode == "none":
            scene.SeamSelection = []

        panels = list(scene.DrapePanels)
        if len(panels) != len(pieces):
            raise RuntimeError(
                "%s expected %d drape panels, got %d"
                % (case_id, len(pieces), len(panels))
            )
        for panel in panels:
            panel.ViewObject.Visibility = True
        cube.ViewObject.Visibility = True
        view = Gui.activeDocument().activeView()
        if view is None:
            raise RuntimeError("%s has no active FreeCAD view" % case_id)
        if rung in {4, 5}:
            view.viewFront()
        else:
            view.viewAxonometric()
        view.fitAll()
        _events()

        before = tuple(
            tuple(float(value) for value in point)
            for point in backend.positions()
        )
        target_points, target_triangles = _mesh_geometry(cube)
        seam_pairs = getattr(base, "seam_stitch_pairs", {}) or {}
        seam_world_spans = []
        for seam_id, pairs in seam_pairs.items():
            spans = []
            for left, right in pairs:
                a = before[int(left)]
                b = before[int(right)]
                spans.append(
                    math.sqrt(sum((a[axis] - b[axis]) ** 2 for axis in range(3)))
                )
            if spans:
                seam_world_spans.append({
                    "seam_id": str(seam_id),
                    "pair_count": len(spans),
                    "min_mm": min(spans),
                    "max_mm": max(spans),
                    "mean_mm": sum(spans) / len(spans),
                })
        initial = _ladder_snapshot(
            case_id, 0, scene, pieces, collision_surface, cube, before
        )
        checkpoints = [initial["checkpoint"]]
        image_paths = [initial["checkpoint"]["image"]]
        _screenshot(view, OUT / initial["checkpoint"]["image"])
        _progress(f"{case_id}: checkpoint=0")
        checkpoint_steps = (1, 5, 15, 45, 90)
        for step in checkpoint_steps:
            scene.Steps = int(step)
            doc.recompute()
            _events()
            snap = _ladder_snapshot(
                case_id, step, scene, pieces, collision_surface, cube, before
            )
            checkpoints.append(snap["checkpoint"])
            image_paths.append(snap["checkpoint"]["image"])
            _screenshot(view, OUT / snap["checkpoint"]["image"])
            _progress(
                "%s: checkpoint=%d finite=%s clearance=%s seam_gap=%s"
                % (
                    case_id,
                    step,
                    snap["checkpoint"]["finite"],
                    snap["checkpoint"]["target_clearance_mm"],
                    snap["checkpoint"]["max_seam_gap_mm"],
                )
            )

        pre_step_clearance = initial["signed_clearance"]
        pre_step = {
            "piece_bounds_world_mm_before_step": [list(initial["bounds"])],
            "target_bounds_world_mm": [list(_bounds(target_points))],
            "signed_clearance_mm": pre_step_clearance,
            "unsigned_min_distance_mm": initial["unsigned_clearance"],
            "seam_pairs": seam_world_spans,
            "seam_world_spans_mm": seam_world_spans,
        }
        if len(pieces) > 1:
            panel_bounds = []
            for panel in panels:
                indices = tuple(base.panel_indices.get(panel.Name, ()))
                if indices:
                    panel_bounds.append(list(_bounds(tuple(before[index] for index in indices))))
            pre_step["piece_bounds_world_mm_before_step"] = panel_bounds

        final = _ladder_snapshot(
            case_id, 90, scene, pieces, collision_surface, cube, before
        )
        record = {
            "case_id": case_id,
            "predecessor_case_id": (
                "control-0-cube" if rung == 1 else f"rung-{rung - 1}"
            ),
            "case": {
                "rung": int(rung),
                "id": case_id,
                "target": "cube",
                "piece_count": len(pieces),
                "pin_mode": str(pin_mode),
                "seam_mode": str(seam_mode),
            },
            "solver": {
                "backend": "tissu",
                "particle_distance_mm": PARTICLE_DISTANCE,
                "iterations": 1,
                "substeps": 1,
                "timestep_s": 1.0 / 120.0,
                "gravity_z_mm_s2": -9810.0,
            },
            "collision": {
                "source_triangles": len(target_triangles),
                "solver_triangles": solver_triangle_count,
                "target_bounds": _bounds(target_points),
                "target_topology_summary": {
                    "vertices": len(target_points),
                    "triangles": len(target_triangles),
                    "solver_triangles": solver_triangle_count,
                },
            },
            "pre_step": pre_step,
            "checkpoints": checkpoints,
            "finite": all(bool(item["finite"]) for item in checkpoints),
            "connected_components": final["checkpoint"]["components"],
            "max_seam_gap_mm": final["max_seam_gap"],
            "final_clearance_mm": final["signed_clearance"],
            "runtime_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "first_contact_step": next(
                (
                    int(item["step"])
                    for item in checkpoints
                    if item["target_clearance_mm"] is not None
                    and float(item["target_clearance_mm"]) <= 2.0
                ),
                None,
            ),
            "contact_mode": final["checkpoint"]["contact_state"],
            "images": image_paths,
            "notes": (
                "diagnostic-only cube ladder rung; shared frozen Tissu settings; "
                "no release-gate effect"
            ),
        }
        return record
    finally:
        App.closeDocument(doc.Name)

def _run_control_cube():
    _progress("control-0-cube: start")
    doc = App.newDocument("TissuContactControlCube")
    try:
        scene = _build_scene(doc)
        cube = doc.addObject("Part::Feature", "DiagnosticCube")
        cube.Label = "Diagnostic Collision Cube"
        cube.Shape = Part.makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
        doc.recompute()
        from freecad_cloth.simulation.SimulationObjects import set_avatar_collision_source
        set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
        if scene.AvatarProxy.SourceObject is not None and hasattr(scene.AvatarProxy.SourceObject, "ViewObject"):
            scene.AvatarProxy.SourceObject.ViewObject.Visibility = False
        piece = _build_piece(
            doc,
            "CubeCloth",
            App.Placement(App.Vector(-180.0, -180.0, 58.5), App.Rotation()),
        )
        cube.ViewObject.Visibility = True
        record = _run_case("control-0-cube", 0, scene, piece, "axonometric")
        return record
    finally:
        App.closeDocument(doc.Name)


def _run_control_avatar():
    _progress("control-0a-avatar: start")
    doc = App.newDocument("TissuContactControlAvatar")
    try:
        scene = _build_scene(doc)
        avatar = scene.AvatarProxy.SourceObject
        if avatar is None:
            raise RuntimeError("control-0a-avatar requires the production avatar source")

        from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

        def arrangement_world(name):
            raw = next(
                (value for value in getattr(avatar, "ArrangementPoints", ()) if str(value).split("|", 1)[0] == name),
                None,
            )
            if raw is None:
                return None
            point = ArrangementPoint.from_string(raw)
            return avatar.Placement.multVec(App.Vector(*point.position()))

        box = getattr(getattr(avatar, "Mesh", None), "BoundBox", None)
        if box is None:
            raise RuntimeError("control-0a-avatar requires mesh collision geometry")
        shoulder_left = arrangement_world("shoulder_left")
        shoulder_right = arrangement_world("shoulder_right")
        hip_point = arrangement_world("hip")
        if shoulder_left is not None and shoulder_right is not None and hip_point is not None:
            x_mid = 0.5 * (float(shoulder_left.x) + float(shoulder_right.x))
            y_mid = 0.5 * (float(shoulder_left.y) + float(shoulder_right.y))
            shoulder_z = 0.5 * (float(shoulder_left.z) + float(shoulder_right.z))
            hip_z = float(hip_point.z)
            x_span = abs(float(shoulder_right.x) - float(shoulder_left.x))
            y_span = max(1.0, float(box.YMax - box.YMin))
        else:
            x_mid = 0.5 * (float(box.XMin) + float(box.XMax))
            y_mid = 0.5 * (float(box.YMin) + float(box.YMax))
            shoulder_z = float(box.ZMin) + 0.76 * float(box.ZMax - box.ZMin)
            hip_z = float(box.ZMin) + 0.40 * float(box.ZMax - box.ZMin)
            x_span = float(box.XMax - box.XMin)
            y_span = float(box.YMax - box.YMin)

        z_span = shoulder_z - hip_z
        if z_span <= 1.0:
            raise RuntimeError("control-0a-avatar has invalid shoulder/hip arrangement span")

        candidate_offsets = (-0.24, -0.12, 0.0, 0.12, 0.24)
        candidate_z = (0.28, 0.40, 0.52, 0.64, 0.76)
        center = None
        for x_factor in candidate_offsets:
            for y_factor in candidate_offsets:
                for z_factor in candidate_z:
                    candidate = App.Vector(
                        x_mid + x_factor * max(40.0, x_span),
                        y_mid + y_factor * max(80.0, min(220.0, y_span)),
                        hip_z + z_factor * z_span,
                    )
                    state = _inside_outside(((float(candidate.x), float(candidate.y), float(candidate.z)),), avatar)
                    if state == "inside":
                        center = candidate
                        break
                if center is not None:
                    break
            if center is not None:
                break
        if center is None:
            raise RuntimeError(
                "control-0a-avatar could not find a deterministic interior arrangement-point probe"
            )
        _progress(
            "control-0a-avatar: interior-seed=%.2f,%.2f,%.2f"
            % (float(center.x), float(center.y), float(center.z))
        )

        # _build_piece seeds the panel at local z=120 mm; +90° X rotation
        # maps that seed to world y=-120 mm, so offset the placement by +120 mm
        # to keep the chosen interior seed at the panel center.
        placement = App.Placement(
            App.Vector(float(center.x) - 36.0, float(center.y) + 120.0, float(center.z) - 36.0),
            App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0),
        )
        piece = _build_piece(doc, "AvatarCloth", placement, width=72.0, height=72.0)
        avatar.ViewObject.Visibility = True
        try:
            avatar.ViewObject.Transparency = 70
        except (AttributeError, TypeError, ValueError):
            pass
        record = _run_case("control-0a-avatar", 0, scene, piece, "front")
        if record["control"]["inside_outside_before"] not in {"inside", "mixed"}:
            raise RuntimeError(
                "control-0a-avatar did not create a true interior pre-step state: %s"
                % record["control"]["inside_outside_before"]
            )
        record["control"]["interior_probe"] = True
        record["control"]["interior_seed_source"] = "avatar-arrangement-points-with-mesh-inside-search"
        return record
    finally:
        App.closeDocument(doc.Name)


def close_gui():
    try:
        import FreeCADGui as Gui
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
    except ImportError:
        return
    window = Gui.getMainWindow()
    if window is not None:
        window.close()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.quit()


def main():
    _progress("main: start")
    _ensure_gui_ready()
    _progress("main: GUI ready")
    records = [
        _run_control_cube(),
        _run_control_avatar(),
        _run_ladder_case("rung-1-pinned", 1, "Automatic"),
        _run_ladder_case("rung-2-unpinned", 2, "None"),
        _run_ladder_case("rung-3-two-piece", 3, "None"),
        _run_ladder_case("rung-4-small-seam-span", 4, "None", "semantic", 66.0),
        _run_ladder_case("rung-5-large-seam-span", 5, "None", "semantic", 150.0),
    ]
    manifest = {
        "schema": 1,
        "purpose": "diagnostic-only-contact-controls",
        "cases": records,
        "release_gate_effect": "none",
        "solver_settings_frozen": {
            "backend_requested": os.environ.get("CLOTH_SIMULATION_BACKEND", "auto"),
            "particle_distance_mm": PARTICLE_DISTANCE,
            "iterations": 1,
            "substeps": 1,
            "timestep_s": 1.0 / 120.0,
            "gravity_z_mm_s2": 0.0,
            "gravity_mm_s2": [0.0, 0.0, 0.0],
            "fabric_friction": 0.5,
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _progress("main: manifest-written")
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    return 0


def _shutdown_gui():
    try:
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
    except Exception as exc:
        _progress("qt-quit-failed=%r" % (exc,))
    _progress("gui-shutdown-requested")


def _scheduled_main():
    status = 1
    try:
        status = int(main() or 0)
    except BaseException as exc:
        _progress("main-failed=%r" % (exc,))
    finally:
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        _shutdown_gui()
        _PROGRESS_HANDLE.flush()
    os._exit(status)


def _schedule_main_once():
    if os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED") == "1":
        _progress("entrypoint:duplicate-schedule-suppressed")
        return
    os.environ["CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED"] = "1"
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    _progress("entrypoint:schedule-main")
    QtCore.QTimer.singleShot(0, _scheduled_main)


if __name__ == "__main__" or os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1":
    _schedule_main_once()

