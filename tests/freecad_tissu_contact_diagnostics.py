"""Diagnostic controls for separating target/contact behavior from gravity and garment complexity.

This script is intentionally diagnostic-only. It exercises the existing FreeCAD/Tissu
runtime without changing physics, solver budgets, canonical fixtures, or release gates.
"""

from __future__ import annotations

import faulthandler
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/tissu-contact-diagnostics"))
OUT.mkdir(parents=True, exist_ok=True)
PROGRESS = OUT / "progress.log"
_PROGRESS_HANDLE = PROGRESS.open("a", encoding="utf-8", buffering=1)
faulthandler.enable(file=_PROGRESS_HANDLE)
_PROGRESS_HANDLE.write("\n=== diagnostic contact controls start ===\n")
_PROGRESS_HANDLE.write(f"entrypoint __name__={__name__!r}\n")
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
import contextlib

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
        raise RuntimeError(
            "missing mesh or shape geometry on {}".format(getattr(obj, "Name", "object"))
        )
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
            d2 = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target, strict=False))
            if d2 < best:
                best = d2
                point = tuple(float(c) for c in target)
    return (math.sqrt(best) if math.isfinite(best) else None), point


def _ray_intersection_x(point, a, b, c):
    px, py, pz = point
    ay, az = float(a[1]) - py, float(a[2]) - pz
    _by, _bz = float(b[1]) - py, float(b[2]) - pz
    _cy, _cz = float(c[1]) - py, float(c[2]) - pz
    det = (float(b[1]) - float(a[1])) * (float(c[2]) - float(a[2])) - (
        float(b[2]) - float(a[2])
    ) * (float(c[1]) - float(a[1]))
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
        states = [
            bool(value) for value in target_mesh.contains(np.asarray(points[:64], dtype=float))
        ]
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
        min(p[0] for p in points),
        max(p[0] for p in points),
        min(p[1] for p in points),
        max(p[1] for p in points),
        min(p[2] for p in points),
        max(p[2] for p in points),
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
    sample = vertices[:: max(1, len(vertices) // 4096)]
    best = float("inf")
    for source in garment_points:
        for target in sample:
            d2 = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target, strict=False))
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
        "source_vertices": int(
            getattr(
                source,
                "MeshVertexCount",
                getattr(mesh, "CountPoints", 0) if mesh is not None else 0,
            )
        ),
        "source_triangles": int(
            getattr(
                source,
                "MeshTriangleCount",
                getattr(mesh, "CountFacets", 0) if mesh is not None else 0,
            )
        ),
        "collision_triangles_authored": int(getattr(target, "CollisionTriangleCount", 0)),
        "collision_vertices_authored": int(getattr(target, "CollisionVertexCount", 0)),
    }


def _screenshot(view, path):
    view.setCameraType("Orthographic")
    view.fitAll()
    _events()
    view.saveImage(str(path), 1280, 720, "White")
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"screenshot missing: {path}")


def _case_record(
    case_id,
    rung,
    target,
    source,
    cloth_points_before,
    cloth_points_after,
    panel_triangles,
    collision_surface,
    steps,
    image_paths,
    runtime_ms,
):
    before_centroid = _centroid(cloth_points_before)
    after_centroid = _centroid(cloth_points_after)
    before_bounds = _bounds(cloth_points_before)
    _bounds(cloth_points_after)
    before_distance = _nearest_surface_distance(cloth_points_before, collision_surface)
    after_distance = _nearest_surface_distance(cloth_points_after, collision_surface)
    _, before_nearest_point = _nearest_surface_observation(cloth_points_before, collision_surface)
    _, after_nearest_point = _nearest_surface_observation(cloth_points_after, collision_surface)
    displacement = math.sqrt(sum((after_centroid[i] - before_centroid[i]) ** 2 for i in range(3)))
    max_vertex_displacement = max(
        math.sqrt(sum((after[i] - before[i]) ** 2 for i in range(3)))
        for before, after in zip(cloth_points_before, cloth_points_after, strict=False)
    )
    before_inside = _inside_outside(cloth_points_before, source)
    after_inside = _inside_outside(cloth_points_after, source)
    if (
        max_vertex_displacement > 0.01
        and before_distance is not None
        and after_distance is not None
        and after_distance >= before_distance
    ):
        contact_state = "projection-or-contact-response-observed"
    elif max_vertex_displacement <= 0.01:
        contact_state = "no-observable-response"
    else:
        contact_state = "response-toward-target-or-tangential-motion"

    target_points, target_triangles = _mesh_geometry(source)
    target_bounds = _bounds(target_points)
    target_sig = _target_signature(target)
    target_surface_triangles = int(len(getattr(collision_surface, "triangles", ()) or ()))
    signed_before = (
        None
        if before_distance is None
        else (-before_distance if before_inside in {"inside", "mixed"} else before_distance)
    )
    signed_after = (
        None
        if after_distance is None
        else (-after_distance if after_inside in {"inside", "mixed"} else after_distance)
    )
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
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.SimulationObjects import (
        create_simulation_scene,
        set_avatar_collision_source,
    )
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
        raise RuntimeError(f"{case_id} did not build a simulation backend")
    _progress(f"{case_id}: backend={getattr(backend, 'name', '')}")
    _progress(
        "tissu-env: collision_mode={} collision_triangles={} backend_module={}".format(
            os.environ.get("CLOTH_TISSU_COLLISION_MODE", "<unset>"),
            os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", "<unset>"),
            getattr(
                __import__("freecad_cloth.simulation.TissuBackend", fromlist=["__file__"]),
                "__file__",
                "<unknown>",
            ),
        )
    )
    target = scene.DrapeTarget
    if target is None:
        raise RuntimeError(f"{case_id} has no DrapeTarget")
    status = __import__(
        "freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]
    ).target_status(target)
    if status["state"] != "ready":
        raise RuntimeError(f"{case_id} DrapeTarget is not ready: {status}")
    panel = next((obj for obj in scene.DrapePanels if obj.Name), None)
    if panel is None:
        raise RuntimeError(f"{case_id} did not create a drape panel")
    before, panel_triangles = _mesh_geometry(panel)
    solver_collision_surface = getattr(
        getattr(base, "backend", None),
        "solver_collision_surface",
        getattr(base, "collision_surface", None),
    )
    solver_triangle_count = len(getattr(solver_collision_surface, "triangles", ()) or ())
    _progress(
        f"{case_id}: panel-vertices={len(before)} collision-triangles={solver_triangle_count}"
    )
    view = Gui.activeDocument().activeView()
    if view is None:
        raise RuntimeError(f"{case_id} has no active FreeCAD view")
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
        raise RuntimeError(f"{case_id} target source missing")
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
        if scene.AvatarProxy.SourceObject is not None and hasattr(
            scene.AvatarProxy.SourceObject, "ViewObject"
        ):
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
                (
                    value
                    for value in getattr(avatar, "ArrangementPoints", ())
                    if str(value).split("|", 1)[0] == name
                ),
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
                    state = _inside_outside(
                        ((float(candidate.x), float(candidate.y), float(candidate.z)),), avatar
                    )
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
            f"control-0a-avatar: interior-seed={float(center.x):.2f},{float(center.y):.2f},{float(center.z):.2f}"
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
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            avatar.ViewObject.Transparency = 70
        record = _run_case("control-0a-avatar", 0, scene, piece, "front")
        if record["control"]["inside_outside_before"] not in {"inside", "mixed"}:
            raise RuntimeError(
                "control-0a-avatar did not create a true interior pre-step state: {}".format(
                    record["control"]["inside_outside_before"]
                )
            )
        record["control"]["interior_probe"] = True
        record["control"]["interior_seed_source"] = (
            "avatar-arrangement-points-with-mesh-inside-search"
        )
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
    ]
    manifest = {
        "schema": 1,
        "purpose": "diagnostic-only-contact-controls",
        "cases": records,
        "release_gate_effect": "none",
        "solver_settings_frozen": {
            "backend_requested": "tissu",
            "particle_distance_mm": PARTICLE_DISTANCE,
            "iterations": 1,
            "substeps": 1,
            "timestep_s": 1.0 / 120.0,
            "gravity_z_mm_s2": 0.0,
            "gravity_mm_s2": [0.0, 0.0, 0.0],
            "fabric_friction": 0.5,
        },
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
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
        _progress(f"qt-quit-failed={exc!r}")
    _progress("gui-shutdown-requested")


def _scheduled_main():
    status = 1
    try:
        status = int(main() or 0)
    except BaseException as exc:
        _progress(f"main-failed={exc!r}")
    finally:
        with contextlib.suppress(Exception):
            faulthandler.cancel_dump_traceback_later()
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
