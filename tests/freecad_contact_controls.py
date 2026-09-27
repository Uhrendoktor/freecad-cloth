"""Diagnostic controls for isolating Tissu mesh contact from gravity/sewing.

This is intentionally diagnostic-only. It never changes canonical release gates.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["CLOTH_SIMULATION_BACKEND"] = "tissu"
os.environ["CLOTH_TISSU_SUBSTEPS"] = "1"
os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"
os.environ["CLOTH_TISSU_COLLISION_TRIANGLES"] = "2048"

from freecad_cloth.avatar.AvatarCollision import coarsen_collision_surface
from freecad_cloth.common.MeshValidation import validate_mesh
from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.DrapeTarget import collision_surface, refresh_drape_target, target_status
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
from freecad_cloth.simulation.TissuBackend import TissuBackend

OUT = Path(os.environ.get("CLOTH_CONTACT_CONTROLS_DIR", "artifacts/contact-controls"))
OUT.mkdir(parents=True, exist_ok=True)
THICKNESS_MM = 0.5
PROBE_HALF_SIZE_MM = 1.5
PENETRATION_MM = 0.75


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


def _normalize(v):
    length = math.sqrt(sum(float(c) ** 2 for c in v))
    if length <= 1e-12:
        raise RuntimeError("degenerate probe normal")
    return tuple(float(c) / length for c in v)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(a, s):
    return tuple(float(c) * float(s) for c in a)


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _face_normal(a, b, c):
    return _normalize(_cross(_sub(b, a), _sub(c, a)))


def _oriented_probe(surface, triangle):
    ia, ib, ic = triangle
    a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
    face_center = tuple((float(a[i]) + float(b[i]) + float(c[i])) / 3.0 for i in range(3))
    normal = _face_normal(a, b, c)
    center = surface.center
    if _dot(_sub(face_center, center), normal) < 0.0:
        normal = _scale(normal, -1.0)
    return face_center, normal


def _basis(normal):
    trial = (0.0, 0.0, 1.0)
    if abs(_dot(normal, trial)) > 0.9:
        trial = (0.0, 1.0, 0.0)
    u = _normalize(_cross(normal, trial))
    v = _normalize(_cross(normal, u))
    return u, v


def _make_probe_system(center, normal, offset):
    u, v = _basis(normal)
    points = []
    for su, sv in (
        (-PROBE_HALF_SIZE_MM, -PROBE_HALF_SIZE_MM),
        (PROBE_HALF_SIZE_MM, -PROBE_HALF_SIZE_MM),
        (PROBE_HALF_SIZE_MM, PROBE_HALF_SIZE_MM),
        (-PROBE_HALF_SIZE_MM, PROBE_HALF_SIZE_MM),
    ):
        points.append(_add(_add(center, _scale(normal, offset)), _add(_scale(u, su), _scale(v, sv))))

    system = ClothSystem.grid(
        2.0 * PROBE_HALF_SIZE_MM,
        2.0 * PROBE_HALF_SIZE_MM,
        nx=2,
        ny=2,
        origin=points[0],
    )
    # Replace the axis-aligned grid with the tangent-space square above while
    # keeping the existing four-particle topology and constraints intact.
    for particle, position in zip(system.particles, points):
        particle.x, particle.y, particle.z = position
        particle.px, particle.py, particle.pz = position
    triangles = ((0, 1, 3), (0, 3, 2))
    return system, triangles


def _signed_plane(point, face_center, normal):
    return _dot(_sub(point, face_center), normal)


def _run_backend(surface, face_center, normal, offset, label):
    system, triangles = _make_probe_system(face_center, normal, offset)
    backend = TissuBackend(
        system,
        triangles=triangles,
        pins=(),
        stitches=(),
        collision_surface=surface.with_thickness(THICKNESS_MM),
        collision_mode="mesh",
    )
    initial = tuple(backend.positions())
    backend.step(
        dt=1.0 / 120.0,
        iterations=8,
        gravity=(0.0, 0.0, 0.0),
        surface=backend.solver_collision_surface,
    )
    final = tuple(backend.positions())
    initial_signed = min(_signed_plane(p, face_center, normal) for p in initial)
    final_signed = min(_signed_plane(p, face_center, normal) for p in final)
    delta = final_signed - initial_signed
    if offset < 0.0:
        if delta > 0.25:
            state = "resolved_outward"
        elif delta < -0.25:
            state = "moved_inward"
        else:
            state = "persistent_inside"
    else:
        state = "outside_preserved" if final_signed >= 0.0 else "moved_inside"
    return {
        "label": label,
        "initial_signed_plane_mm": initial_signed,
        "final_signed_plane_mm": final_signed,
        "signed_plane_delta_mm": delta,
        "initial_positions": initial,
        "final_positions": final,
        "state": state,
        "finite": bool(backend.finite()),
        "solver_triangles": len(getattr(backend.solver_collision_surface, "triangles", ())),
    }


def _set_probe_shape(obj, positions):
    p = [App.Vector(*position) for position in positions]
    obj.Shape = Part.Face(Part.makePolygon(p + [p[0]]))


def _save_probe_view(name, avatar=None, target_box=None, probe=None):
    if avatar is not None:
        avatar.ViewObject.Transparency = 72
        avatar.ViewObject.Visibility = True
    if target_box is not None:
        target_box.ViewObject.Visibility = True
    if probe is not None:
        probe.ViewObject.ShapeColor = (0.95, 0.25, 0.15)
        probe.ViewObject.LineColor = (0.15, 0.02, 0.01)
        probe.ViewObject.LineWidth = 3.0
        probe.ViewObject.Visibility = True
    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    _events()
    view.saveImage(str(OUT / name), 1200, 900, "Current", 1)



def _write_manifest(results, error=None):
    payload = {
        "schema": 1,
        "suite": "tissu-contact-controls",
        "backend": "tissu",
        "solver": {"dt_s": 1.0 / 120.0, "iterations": 8, "substeps": 1, "gravity_mm_s2": [0.0, 0.0, 0.0]},
        "surface": {"thickness_mm": THICKNESS_MM, "triangle_limit": 2048},
        "results": results,
    }
    if error is not None:
        payload["error"] = repr(error)
    (OUT / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

def _cube_control():
    doc = App.newDocument("TissuContactControlCube")
    cube = doc.addObject("Part::Feature", "TargetCube")
    cube.Shape = Part.makeBox(100.0, 100.0, 100.0, App.Vector(-50.0, -50.0, -50.0))
    cube.ViewObject.Transparency = 65

    from freecad_cloth.avatar.AvatarCollision import CollisionSurface
    surface = CollisionSurface(
        (
            (-50.0, -50.0, -50.0), (50.0, -50.0, -50.0), (50.0, 50.0, -50.0), (-50.0, 50.0, -50.0),
            (-50.0, -50.0, 50.0), (50.0, -50.0, 50.0), (50.0, 50.0, 50.0), (-50.0, 50.0, 50.0),
        ),
        (
            (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
            (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
        ),
        "cube",
        0.0,
    )
    surface.validate()
    face_center = (0.0, 0.0, 50.0)
    normal = (0.0, 0.0, 1.0)
    inside = _run_backend(surface, face_center, normal, -PENETRATION_MM, "cube_inside")
    outside = _run_backend(surface, face_center, normal, PENETRATION_MM, "cube_outside")

    probe = doc.addObject("Part::Feature", "ProbeCloth")
    _set_probe_shape(probe, inside["initial_positions"])
    _save_probe_view("cube-inside-step-0.png", target_box=cube, probe=probe)
    _set_probe_shape(probe, inside["final_positions"])
    _save_probe_view("cube-inside-step-1.png", target_box=cube, probe=probe)

    doc.close()
    return {
        "rung": "0",
        "target": "cube",
        "source_triangles": len(surface.triangles),
        "solver_triangles": len(surface.triangles),
        "inside": {k: v for k, v in inside.items() if k not in {"initial_positions", "final_positions"}},
        "outside": {k: v for k, v in outside.items() if k not in {"initial_positions", "final_positions"}},
        "screenshots": ["cube-inside-step-0.png", "cube-inside-step-1.png"],
        "topology": validate_mesh(surface.vertices, surface.triangles, prefer_trimesh=False).__dict__,
    }


def _avatar_control():
    doc = App.newDocument("TissuContactControlAvatar")
    scene = create_quality_simulation_scene(doc)
    target = scene.DrapeTarget
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("production DrapeTarget has no source object")
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        refresh_drape_target(target)
        status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError("production DrapeTarget is not ready: %s" % status)
    full = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    solver_surface = coarsen_collision_surface(full, 2048)
    if len(solver_surface.triangles) != 2048:
        raise RuntimeError("expected exactly 2048 solver collision triangles, got %d" % len(solver_surface.triangles))
    # Prefer a sizeable, torso-height triangle so the local tangent probe is
    # genuinely on the production torso rather than an extremity.
    candidates = []
    for triangle in solver_surface.triangles:
        a, b, c = (solver_surface.vertices[i] for i in triangle)
        center = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
        area = 0.5 * math.sqrt(sum(value * value for value in _cross(_sub(b, a), _sub(c, a))))
        if 700.0 <= center[2] <= 1200.0 and abs(center[0]) <= 250.0 and area >= 10.0:
            candidates.append((area, triangle))
    if not candidates:
        raise RuntimeError("no suitable torso triangle survived the 2048-triangle collision coarsening")
    _, triangle = max(candidates, key=lambda item: item[0])
    face_center, normal = _oriented_probe(full, triangle)
    inside = _run_backend(solver_surface, face_center, normal, -PENETRATION_MM, "avatar_inside")
    outside = _run_backend(solver_surface, face_center, normal, PENETRATION_MM, "avatar_outside")

    probe = doc.addObject("Part::Feature", "ProbeCloth")
    _set_probe_shape(probe, inside["initial_positions"])
    _save_probe_view("avatar-inside-step-0.png", avatar=source, probe=probe)
    _set_probe_shape(probe, inside["final_positions"])
    _save_probe_view("avatar-inside-step-1.png", avatar=source, probe=probe)

    solver_metrics = validate_mesh(solver_surface.vertices, solver_surface.triangles, prefer_trimesh=False)
    doc.close()
    return {
        "rung": "0a",
        "target": "production_avatar",
        "source_vertices": len(full.vertices),
        "source_triangles": len(full.triangles),
        "solver_triangles": len(solver_surface.triangles),
        "target_topology": {"kind": "authored_full_surface", "vertices": len(full.vertices), "faces": len(full.triangles)},
        "solver_topology": solver_metrics.__dict__,
        "probe_triangle": list(triangle),
        "probe_face_center": face_center,
        "probe_outward_normal": normal,
        "inside": {k: v for k, v in inside.items() if k not in {"initial_positions", "final_positions"}},
        "outside": {k: v for k, v in outside.items() if k not in {"initial_positions", "final_positions"}},
        "screenshots": ["avatar-inside-step-0.png", "avatar-inside-step-1.png"],
    }


def main():
    results = []
    try:
        results.append(_cube_control())
        _write_manifest(results)
        results.append(_avatar_control())
        _write_manifest(results)
        failures = []
        for result in results:
            for key in ("inside", "outside"):
                payload = result[key]
                if not payload["finite"]:
                    failures.append("%s/%s/nonfinite" % (result["rung"], key))
            if result["rung"] == "0":
                if result["inside"]["state"] != "resolved_outward":
                    failures.append("0/inside/%s" % result["inside"]["state"])
                if result["outside"]["state"] != "outside_preserved":
                    failures.append("0/outside/%s" % result["outside"]["state"])
            if result["rung"] == "0a":
                if result["inside"]["state"] != "resolved_outward":
                    failures.append("0a/inside/%s" % result["inside"]["state"])
                if result["outside"]["state"] != "outside_preserved":
                    failures.append("0a/outside/%s" % result["outside"]["state"])
        if failures:
            raise RuntimeError("diagnostic contact controls failed: " + ",".join(failures))
        print("contact-controls=passed")
        for result in results:
            print(
                "contact-control rung=%s target=%s inside=%s outside=%s solver_triangles=%s"
                % (
                    result["rung"],
                    result["target"],
                    result["inside"]["state"],
                    result["outside"]["state"],
                    result["solver_triangles"],
                )
            )
        return 0
    except Exception as exc:
        try:
            _write_manifest(results, error=exc)
        except Exception:
            pass
        raise
    finally:
        try:
            app = getattr(App, "ActiveDocument", None)
            if app is not None:
                App.closeDocument(app.Name)
        except Exception:
            pass
        try:
            Gui.updateGui()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
