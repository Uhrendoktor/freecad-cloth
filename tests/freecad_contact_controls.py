"""Diagnostic collision controls 0/0a for the cloth complexity ladder.

These controls are opt-in diagnostics only. They must not alter production
solver settings or release gates.
"""
import json
import math
import os
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Mesh

from freecad_cloth.avatar.AvatarCollision import surface_from_freecad
from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle, _closest_point_triangle
from freecad_cloth.simulation.DrapeTarget import target_status
from freecad_cloth.simulation.TissuBackend import TissuBackend, _normalize as _normalise


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CLOTH_CONTACT_CONTROLS_OUT", ROOT / "artifacts" / "contact-controls"))
OUT.mkdir(parents=True, exist_ok=True)
SCHEMA = 1


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()


def _unit(a, b):
    return tuple(float(b[i] - a[i]) for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _face_normal(a, b, c, center):
    normal = _normalise(_cross(_unit(a, b), _unit(a, c)))
    if normal is None:
        raise RuntimeError("selected avatar triangle is degenerate")
    midpoint = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
    if _dot(normal, tuple(center[i] - midpoint[i] for i in range(3))) > 0.0:
        normal = tuple(-value for value in normal)
    return normal


def _select_face(surface):
    center = surface.center
    target_z = center[2] * 0.58
    best = None
    for index, (ia, ib, ic) in enumerate(surface.triangles):
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        centroid = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
        score = abs(centroid[2] - target_z) + 0.01 * math.hypot(centroid[0] - center[0], centroid[1] - center[1])
        key = (score, index)
        if best is None or key < best[0]:
            best = (key, index, (a, b, c))
    if best is None:
        raise RuntimeError("avatar collision surface has no triangles")
    return best[1], best[2]


def _write_cloth_mesh(doc, name, points, color):
    obj = doc.addObject("Mesh::Feature", name)
    mesh = Mesh.Mesh()
    mesh.addFacet(App.Vector(*points[0]), App.Vector(*points[1]), App.Vector(*points[2]))
    obj.Mesh = mesh
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.LineColor = color
    return obj


def _render(path, cloth_obj=None):
    view = Gui.activeDocument().activeView()
    view.viewAxonometric()
    view.fitAll()
    _events()
    view.saveImage(str(path), 1280, 720, "White")
    if not path.is_file() or path.stat().st_size < 5000:
        raise RuntimeError("contact-control screenshot failed: %s" % path)


def _manifest_entry(rung, case_id, target, piece_count, pin_mode, seam_mode, solver, collision, pre_step, checkpoints):
    return {
        "schema": SCHEMA,
        "case": {
            "rung": rung,
            "id": case_id,
            "target": target,
            "piece_count": piece_count,
            "pin_mode": pin_mode,
            "seam_mode": seam_mode,
        },
        "solver": solver,
        "collision": collision,
        "pre_step": pre_step,
        "checkpoints": checkpoints,
    }


def run():
    os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_TISSU_COLLISION_TRIANGLES"] = "0"
    os.environ["CLOTH_TISSU_SUBSTEPS"] = "1"

    doc = App.newDocument("ClothContactControls")
    avatar = None
    cloth = None
    try:
        from freecad_cloth.avatar.AvatarCommands import create_avatar

        avatar = create_avatar(doc=doc)
        doc.recompute()
        target = doc.getObject("DrapeTarget")
        if target is None:
            raise RuntimeError("control target was not created")
        status = target_status(target)
        if status["state"] != "ready":
            raise RuntimeError("control target is not ready: %s" % status)
        surface = surface_from_freecad(target.SourceObject, float(target.CollisionDeflection), float(target.CollisionThickness))

        triangle_index, face = _select_face(surface)
        a, b, c = face
        normal = _face_normal(a, b, c, surface.center)
        midpoint = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))

        closest = _closest_point_triangle(tuple(midpoint[i] + 8.0 * normal[i] for i in range(3)), a, b, c)
        static_point = tuple(midpoint[i] + 8.0 * normal[i] for i in range(3))
        static_distance = math.sqrt(sum((static_point[i] - closest[i]) ** 2 for i in range(3)))

        collision_meta = {
            "source_signature": list(surface.region for _ in [0]) + [len(surface.vertices), len(surface.triangles)],
            "source_triangles": len(surface.triangles),
            "solver_triangles": len(surface.triangles),
            "target_bounds": [
                min(v[0] for v in surface.vertices), max(v[0] for v in surface.vertices),
                min(v[1] for v in surface.vertices), max(v[1] for v in surface.vertices),
                min(v[2] for v in surface.vertices), max(v[2] for v in surface.vertices),
            ],
        }
        solver_meta = {
            "backend": "tissu",
            "particle_distance_mm": None,
            "iterations": 1,
            "substeps": 1,
            "timestep_s": 1.0 / 60.0,
            "gravity_z_mm_s2": 0.0,
        }

        static_basis_a = (static_point[0] + 4.0, static_point[1], static_point[2])
        static_basis_b = (static_point[0], static_point[1] + 4.0, static_point[2])
        _write_cloth_mesh(doc, "StaticProbe", (static_point, static_basis_a, static_basis_b), (0.2, 0.7, 0.2))
        _render(OUT / "control-0-static.png")
        control0 = _manifest_entry(
            0, "static-surface-probe", "exact-makehuman-drapetarget", 1, "None", "none",
            solver_meta, collision_meta,
            {
                "piece_bounds": [[min(static_point[0], static_point[0]), max(static_point[0], static_point[0]),
                                  min(static_point[1], static_point[1]), max(static_point[1], static_point[1]),
                                  min(static_point[2], static_point[2]), max(static_point[2], static_point[2])]],
                "unsigned_clearance_mm": static_distance,
                "seam_pairs": [],
                "triangle_index": triangle_index,
                "nearest_point": list(closest),
            },
            [{"step": 0, "image": "control-0-static.png", "finite": True, "components": 1,
              "max_seam_gap_mm": 0.0, "target_clearance_mm": static_distance, "contact_state": "outside-near-surface"}],
        )

        penetration = 1.0
        cloth_points = tuple(
            tuple(face[i] - penetration * normal[i] for i in range(3)) for face in (a, b, c)
        )
        cloth = _write_cloth_mesh(doc, "AvatarInteriorProbe", cloth_points, (0.85, 0.35, 0.35))
        _render(OUT / "control-0a-step-000.png")

        system = ClothSystem([Particle(*p) for p in cloth_points], [])
        backend = TissuBackend(system, ((0, 1, 2),), collision_surface=surface, collision_mode="mesh")
        pre_centroid = tuple(sum(p[i] for p in cloth_points) / 3.0 for i in range(3))
        pre_signed = _dot(tuple(pre_centroid[i] - midpoint[i] for i in range(3)), normal)

        backend.step(dt=1.0 / 60.0, iterations=1, gravity=(0.0, 0.0, 0.0), surface=surface)
        post = backend.positions()
        post_centroid = tuple(sum(p[i] for p in post) / 3.0 for i in range(3))
        post_signed = _dot(tuple(post_centroid[i] - midpoint[i] for i in range(3)), normal)
        displacement = math.sqrt(sum((post_centroid[i] - pre_centroid[i]) ** 2 for i in range(3)))
        if post_signed >= 0.0:
            contact_state = "resolved"
        elif post_signed > pre_signed + 1e-6:
            contact_state = "moved-toward-outside"
        elif post_signed < pre_signed - 1e-6:
            contact_state = "moved-further-inside"
        else:
            contact_state = "persisted-inside"

        cloth.Mesh = Mesh.Mesh()
        cloth.Mesh.addFacet(App.Vector(*post[0]), App.Vector(*post[1]), App.Vector(*post[2]))
        _render(OUT / "control-0a-step-001.png")

        control0a = _manifest_entry(
            "0a", "avatar-shallow-penetration", "exact-makehuman-drapetarget", 1, "None", "none",
            solver_meta, collision_meta,
            {
                "piece_bounds": [[min(p[0] for p in cloth_points), max(p[0] for p in cloth_points),
                                  min(p[1] for p in cloth_points), max(p[1] for p in cloth_points),
                                  min(p[2] for p in cloth_points), max(p[2] for p in cloth_points)]],
                "unsigned_clearance_mm": abs(pre_signed),
                "seam_pairs": [],
                "triangle_index": triangle_index,
                "surface_normal": list(normal),
            },
            [
                {"step": 0, "image": "control-0a-step-000.png", "finite": True, "components": 1,
                 "max_seam_gap_mm": 0.0, "target_clearance_mm": abs(pre_signed), "contact_state": "deliberately-interior"},
                {"step": 1, "image": "control-0a-step-001.png", "finite": backend.finite(), "components": 1,
                 "max_seam_gap_mm": 0.0, "target_clearance_mm": abs(post_signed), "contact_state": contact_state},
            ],
        )

        manifest = {
            "schema": SCHEMA,
            "controls": [control0, control0a],
            "selection": {"triangle_index": triangle_index, "triangle_midpoint": list(midpoint), "outward_normal": list(normal)},
            "tissu": {"collision_mode": "mesh", "collision_triangles": len(surface.triangles), "substeps": 1, "iterations": 1},
        }
        (OUT / "contact-controls.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("contact-control-0=passed nearest-distance=%.6f" % static_distance)
        print("contact-control-0a=passed state=%s pre-signed=%.6f post-signed=%.6f displacement=%.6f" % (
            contact_state, pre_signed, post_signed, displacement
        ))
        print("contact-controls=passed artifact=%s" % (OUT / "contact-controls.json"))
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    run()
