"""Screenshot-backed avatar complexity ladder for the diagnostic harness.
# Exact-head validation note: this source is exercised only from its PR head.
# Validation note: this diagnostic consumes the shared schema-1 avatar ladder manifest.

This module is diagnostic-only. It reuses the existing Tissu/FreeCAD runtime and
frozen solver settings; it does not participate in release acceptance.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

OUT = Path(os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/tissu-contact-diagnostics"))
OUT.mkdir(parents=True, exist_ok=True)
_BOOT_LOG = OUT / "avatar-ladder-bootstrap.log"
_TRACE_HANDLE = _BOOT_LOG.open("a", encoding="utf-8", buffering=1)

def _boot(message):
    _TRACE_HANDLE.write(str(message) + "\n")
    _TRACE_HANDLE.flush()

import faulthandler
import json
import math
import runpy
import time

_boot("script-start")
_boot("before-import-FreeCAD")
import FreeCAD as App
_boot("import-FreeCAD-complete")
import FreeCADGui as Gui
_boot("import-FreeCADGui-complete")
import Part
_boot("import-Part-complete")
try:
    faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)
    faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)
    _boot("diagnostic-faulthandler-ready")
except (AttributeError, OSError, RuntimeError, ValueError) as exc:
    _boot("diagnostic-faulthandler-unavailable=%r" % (exc,))

_boot("before-shared-helper-runpath")
_shared = runpy.run_path(
    str(Path(__file__).with_name("freecad_tissu_contact_diagnostics.py")),
    run_name="freecad_tissu_contact_diagnostics",
)
_boot("after-shared-helper-runpath")
_build_piece = _shared["_build_piece"]
_build_scene = _shared["_build_scene"]
_connected_components = _shared["_connected_components"]
_events = _shared["_events"]
_mesh_geometry = _shared["_mesh_geometry"]
_nearest_surface_distance = _shared["_nearest_surface_distance"]
_progress = _shared["_progress"]
_screenshot = _shared["_screenshot"]
_shutdown_gui = _shared["_shutdown_gui"]
_target_signature = _shared["_target_signature"]

CHECKPOINTS = (0, 1, 5, 15, 45, 90)


def _vector_tuple(value):
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def _positions_tuple(backend):
    return tuple(tuple(float(c) for c in point) for point in backend.positions())


def _seam_geometry(backend, seam_stitch_pairs):
    positions = _positions_tuple(backend)
    result = []
    for seam_id, pairs in sorted(seam_stitch_pairs.items()):
        measurements = []
        for left, right in pairs:
            a = positions[int(left)]
            b = positions[int(right)]
            distance = math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))
            measurements.append({
                "particle_a": int(left),
                "particle_b": int(right),
                "a_world_mm": [round(value, 6) for value in a],
                "b_world_mm": [round(value, 6) for value in b],
                "distance_mm": round(distance, 6),
            })
        distances = [item["distance_mm"] for item in measurements]
        result.append({
            "seam_id": str(seam_id),
            "pair_count": len(measurements),
            "min_span_mm": round(min(distances), 6) if distances else 0.0,
            "max_span_mm": round(max(distances), 6) if distances else 0.0,
            "mean_span_mm": round(sum(distances) / len(distances), 6) if distances else 0.0,
            "pairs": measurements,
        })
    return result


def _surface_signed_clearance(points, source_shape, collision_surface, proximity_mesh=None):
    unsigned = None
    if proximity_mesh is not None:
        try:
            import numpy as np
            import trimesh  # noqa: F401
            if points:
                _, distances, _ = proximity_mesh.nearest.on_surface(
                    np.asarray(points, dtype=float)
                )
                unsigned = float(np.min(distances)) if len(distances) else float("inf")
        except (ImportError, RuntimeError, TypeError, ValueError):
            unsigned = None
    if unsigned is None:
        unsigned = _nearest_surface_distance(points, collision_surface)
    if unsigned is None:
        return None, None
    inside = False
    for point in points:
        try:
            if bool(source_shape.isInside(App.Vector(*point), 1e-6, True)):
                inside = True
                break
        except (AttributeError, TypeError, ValueError):
            break
    return float(-unsigned if inside else unsigned), float(unsigned)


def _checkpoint_record(step, image, positions, panel_triangles, source_shape, collision_surface, base, proximity_mesh):
    finite = all(math.isfinite(float(c)) for point in positions for c in point)
    signed_clearance, unsigned_clearance = _surface_signed_clearance(
        positions,
        source_shape,
        collision_surface,
        proximity_mesh,
    )
    seam_geometry = _seam_geometry(base.backend, base.seam_stitch_pairs)
    return {
        "step": int(step),
        "image": image,
        "finite": bool(finite),
        "components": _connected_components(positions, panel_triangles),
        "max_seam_gap_mm": round(
            max((entry["max_span_mm"] for entry in seam_geometry), default=0.0), 6
        ),
        "target_clearance_mm": signed_clearance,
        "target_unsigned_clearance_mm": unsigned_clearance,
        "contact_state": "diagnostic-only-avatar",
        "seam_world_spans_mm": seam_geometry,
    }


def _build_avatar_scene(doc):
    scene = _build_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    if avatar is None:
        raise RuntimeError("diagnostic avatar scene has no production ClothAvatar")
    if str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("diagnostic avatar target is not the production ClothAvatar")
    target = getattr(scene, "DrapeTarget", None)
    if target is None or getattr(target, "SourceObject", None) is not avatar:
        raise RuntimeError("diagnostic avatar scene DrapeTarget does not reference production ClothAvatar")
    status = __import__("freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]).target_status(target)
    if status["state"] != "ready":
        raise RuntimeError("diagnostic avatar DrapeTarget is not ready: %s" % status)
    avatar.ViewObject.Visibility = True
    try:
        avatar.ViewObject.Transparency = 70
    except (AttributeError, TypeError, ValueError):
        pass
    doc.recompute()
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    def arrangement_world(name):
        raw = next((value for value in getattr(avatar, "ArrangementPoints", ()) if str(value).split("|", 1)[0] == name), None)
        if raw is None:
            raise RuntimeError("diagnostic avatar is missing arrangement point %s" % name)
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))
    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    target_mesh = getattr(avatar, "Mesh", None)
    target_vertices = []
    topology = getattr(target_mesh, "Topology", None) if target_mesh is not None else None
    if topology is not None:
        raw_vertices, _raw_faces = topology
        target_vertices = [App.Vector(v.x, v.y, v.z) for v in raw_vertices]
    if not target_vertices:
        box = getattr(getattr(avatar, "Shape", None), "BoundBox", None)
        if box is None:
            raise RuntimeError("diagnostic avatar has no mesh or shape bounds")
        target_y = float(box.YMin)
    else:
        target_y_candidates = [
            float(point.y)
            for point in target_vertices
            if abs(float(point.x) - float((shoulder_left.x + shoulder_right.x) / 2.0)) <= max(
                40.0, abs(float(shoulder_right.x - shoulder_left.x)) * 0.9
            )
            and float(hip_point.z) - 100.0 <= float(point.z) <= float(shoulder_left.z) + 100.0
        ]
        target_y = min(target_y_candidates) if target_y_candidates else min(float(point.y) for point in target_vertices)
    body_depth = max(120.0, min(260.0, abs(float(max(point.y for point in target_vertices)) - float(min(point.y for point in target_vertices)))) if target_vertices else 180.0)
    clearance = max(20.0, 0.08 * body_depth)
    x_mid = (float(shoulder_left.x) + float(shoulder_right.x)) / 2.0
    z_mid = (float(shoulder_left.z) + float(hip_point.z)) / 2.0
    panel_y = target_y - clearance
    return scene, avatar, {
        "x_mid": x_mid,
        "z_mid": z_mid,
        "panel_y": panel_y,
    }


def _add_seam(doc, piece_a, piece_b, seam_id="avatar-seam"):
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam

    seam = Seam(
        piece_a=str(piece_a.PieceId),
        edge_a=1,
        piece_b=str(piece_b.PieceId),
        edge_b=3,
        id=seam_id,
        alignment="endpoints",
        stitch_group=seam_id,
        kind="plain",
    )
    return add_seam(doc, seam)


def _case_spec(case_id):
    table = {
        "rung-6-avatar-pinned": {
            "rung": 6,
            "piece_count": 1,
            "pin_mode": "Automatic",
            "seam_mode": "none",
            "right_offset": None,
        },
        "rung-7-avatar-unpinned": {
            "rung": 7,
            "piece_count": 1,
            "pin_mode": "None",
            "seam_mode": "none",
            "right_offset": None,
        },
        "rung-8-avatar-two-piece-no-seam": {
            "rung": 8,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "none",
            "right_offset": 0.5,
        },
        "rung-9-avatar-two-piece-small-seam": {
            "rung": 9,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "small",
            "right_offset": 0.5,
        },
        "rung-10-avatar-two-piece-large-seam": {
            "rung": 10,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "large",
            "right_offset": 80.0,
        },
    }
    return dict(table[case_id])


def _run_ladder_case(case_id):
    _boot(f"case-start={case_id}")
    spec = _case_spec(case_id)
    doc = App.newDocument("TissuAvatarLadder" + case_id.replace("-", "").title())
    started = time.perf_counter()
    try:
        scene, avatar, frame = _build_avatar_scene(doc)
        panel_width = 120.0
        panel_height = 120.0
        rotation = App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0)

        def make_piece(name, x_offset):
            placement = App.Placement(
                App.Vector(
                    float(frame["x_mid"] + x_offset),
                    float(frame["panel_y"]),
                    float(frame["z_mid"] - panel_height / 2.0),
                ),
                rotation,
            )
            piece = _build_piece(doc, name, placement, width=panel_width, height=panel_height)
            return piece

        left = make_piece("AvatarLeft", -120.0)
        pieces = [left]
        if spec["piece_count"] == 2:
            right = make_piece("AvatarRight", float(spec["right_offset"] or 0.0))
            pieces.append(right)
            if spec["seam_mode"] in {"small", "large"}:
                _add_seam(doc, left, right)
        scene.ClothPieces = pieces
        scene.SeamSelection = []
        scene.PinMode = str(spec["pin_mode"])
        scene.PinSelection = []
        scene.StitchSamples = 8
        scene.Steps = 0
        doc.recompute()

        base = scene.Proxy._base_or_restore()
        if base.backend is None:
            raise RuntimeError("%s did not build a Tissu backend" % case_id)
        collision_surface = getattr(
            base.backend,
            "solver_collision_surface",
            getattr(base, "collision_surface", None),
        )
        if collision_surface is None:
            raise RuntimeError("%s did not expose a collision surface" % case_id)
        solver_triangles = len(getattr(collision_surface, "triangles", ()) or ())
        if solver_triangles <= 0:
            raise RuntimeError("%s has no solver collision triangles" % case_id)
        positions = _positions_tuple(base.backend)
        panel_triangles = tuple(
            triangle
            for panel_triangles in base.panel_triangles.values()
            for triangle in panel_triangles
        )
        target_sig = _target_signature(scene.DrapeTarget)
        source_shape = getattr(avatar, "Shape", None)
        if source_shape is None or source_shape.isNull():
            raise RuntimeError("%s production avatar source shape is invalid" % case_id)

        seam_pre = _seam_geometry(base.backend, base.seam_stitch_pairs)
        proximity_mesh = None
        try:
            import numpy as np
            import trimesh
            proximity_mesh = trimesh.Trimesh(
                vertices=np.asarray(getattr(collision_surface, "vertices", ()), dtype=float),
                faces=np.asarray(getattr(collision_surface, "triangles", ()), dtype=int),
                process=False,
            )
        except (ImportError, RuntimeError, TypeError, ValueError):
            proximity_mesh = None
        signed_before, unsigned_before = _surface_signed_clearance(
            positions, source_shape, collision_surface, proximity_mesh
        )
        bounds = {
            "x_min": min(point[0] for point in positions),
            "x_max": max(point[0] for point in positions),
            "y_min": min(point[1] for point in positions),
            "y_max": max(point[1] for point in positions),
            "z_min": min(point[2] for point in positions),
            "z_max": max(point[2] for point in positions),
        }
        _progress(
            "%s: pieces=%d pin=%s seam=%s source_triangles=%d solver_triangles=%d pre_clearance=%.6f max_seam=%.6f"
            % (
                case_id,
                spec["piece_count"],
                spec["pin_mode"],
                spec["seam_mode"],
                target_sig["source_triangles"],
                solver_triangles,
                float(signed_before if signed_before is not None else float("nan")),
                max((item["max_span_mm"] for item in seam_pre), default=0.0),
            )
        )

        view = Gui.activeDocument().activeView()
        if view is None:
            raise RuntimeError("%s has no active FreeCAD view" % case_id)
        images = {}
        checkpoints = []
        for step in CHECKPOINTS:
            _boot(f"checkpoint-before-recompute case={case_id} step={step}")
            scene.Steps = int(step)
            doc.recompute()
            _boot(f"checkpoint-after-recompute case={case_id} step={step}")
            _events()
            image = OUT / "avatar-ladder" / case_id / ("step-%03d.png" % int(step))
            image.parent.mkdir(parents=True, exist_ok=True)
            view.viewAxonometric()
            _events()
            _boot(f"checkpoint-before-screenshot case={case_id} step={step}")
            _screenshot(view, image)
            _boot(f"checkpoint-after-screenshot case={case_id} step={step}")
            positions = _positions_tuple(base.backend)
            checkpoints.append(
                _checkpoint_record(
                    step,
                    str(image.relative_to(OUT)),
                    positions,
                    panel_triangles,
                    source_shape,
                    collision_surface,
                    base,
                    proximity_mesh,
                )
            )
            images[int(step)] = str(image.relative_to(OUT))
            _progress("%s: checkpoint=%d" % (case_id, step))

        final = checkpoints[-1]
        finite = all(item["finite"] for item in checkpoints)
        seam_world_spans = [entry for entry in seam_pre]
        record = {
            "case_id": case_id,
            "predecessor_case_id": None,
            "case": {
                "rung": int(spec["rung"]),
                "id": case_id,
                "target": "avatar",
                "piece_count": int(spec["piece_count"]),
                "pin_mode": spec["pin_mode"],
                "seam_mode": spec["seam_mode"],
            },
            "solver": {
                "backend": "tissu",
                "particle_distance_mm": float(getattr(scene, "ParticleDistance", 0.0)),
                "iterations": int(getattr(scene, "SolverIterations", 0)),
                "substeps": int(getattr(scene, "SolverSubsteps", 0)),
                "timestep_s": float(getattr(scene, "TimeStep", 0.0)),
                "gravity_z_mm_s2": float(getattr(scene, "GravityZ", 0.0)),
            },
            "collision": {
                "source_signature": target_sig,
                "source_triangles": int(target_sig["source_triangles"]),
                "solver_triangles": int(solver_triangles),
                "target_bounds": {
                    "x_min": float(avatar.Shape.BoundBox.XMin), "x_max": float(avatar.Shape.BoundBox.XMax),
                    "y_min": float(avatar.Shape.BoundBox.YMin), "y_max": float(avatar.Shape.BoundBox.YMax),
                    "z_min": float(avatar.Shape.BoundBox.ZMin), "z_max": float(avatar.Shape.BoundBox.ZMax),
                },
                "target_topology_summary": {
                    "vertices": int(target_sig["source_vertices"]),
                    "triangles": int(target_sig["source_triangles"]),
                    "solver_triangles": int(solver_triangles),
                },
            },
            "pre_step": {
                "piece_bounds": [list(bounds.values())],
                "unsigned_clearance_mm": unsigned_before,
                "signed_clearance_mm": signed_before,
                "seam_pairs": [
                    [int(left), int(right)]
                    for seam in base.seam_stitch_pairs.values()
                    for left, right in seam
                ],
                "seam_world_spans_mm": seam_world_spans,
            },
            "checkpoints": checkpoints,
            "finite": bool(finite),
            "connected_components": int(final["components"]),
            "max_seam_gap_mm": float(final["max_seam_gap_mm"]),
            "final_clearance_mm": final["target_clearance_mm"],
            "runtime_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "first_contact_step": next(
                (
                    checkpoint["step"]
                    for checkpoint in checkpoints
                    if checkpoint["target_clearance_mm"] is not None
                    and checkpoint["target_clearance_mm"] < 0.0
                ),
                None,
            ),
            "contact_mode": "avatar-diagnostic",
            "control": {
                "placement_offsets_mm": {
                    "left_x": -120.0,
                    "right_x": spec["right_offset"],
                },
                "pre_step_seam_count": len(base.seam_stitch_pairs),
                "pre_step_seam_pair_count": sum(
                    len(pairs) for pairs in base.seam_stitch_pairs.values()
                ),
                "pre_step_bounds_mm": bounds,
                "arrangement_frame": frame,
            },
            "images": [images[step] for step in CHECKPOINTS],
            "notes": (
                "diagnostic-only avatar ladder; exact production ClothAvatar/DrapeTarget; "
                "fixed Tissu backend; solver/collision budgets unchanged; release gate unaffected"
            ),
        }
        _boot("case-complete=%s runtime_ms=%.3f" % (case_id, record["runtime_ms"]))
        return record
    finally:
        try:
            _boot(f"case-finally={case_id}")
        finally:
            App.closeDocument(doc.Name)



def _structural_ladder_checks(records):
    by_id = {record["case"]["id"]: record for record in records}
    checks = []
    ordered = [
        ("rung-6-avatar-pinned", 6),
        ("rung-7-avatar-unpinned", 7),
        ("rung-8-avatar-two-piece-no-seam", 8),
        ("rung-9-avatar-two-piece-small-seam", 9),
        ("rung-10-avatar-two-piece-large-seam", 10),
    ]
    for case_id, rung in ordered:
        record = by_id[case_id]
        ok = (
            bool(record["finite"])
            and record["case"]["rung"] == rung
            and record["solver"]["backend"] == "tissu"
            and record["solver"]["iterations"] == 1
            and record["solver"]["substeps"] == 1
            and abs(float(record["solver"]["timestep_s"]) - (1.0 / 120.0)) < 1e-12
            and float(record["solver"]["gravity_z_mm_s2"]) == 0.0
            and record["collision"]["solver_triangles"] > 0
            and len(record["checkpoints"]) == len(CHECKPOINTS)
            and [item["step"] for item in record["checkpoints"]] == list(CHECKPOINTS)
        )
        if rung <= 7:
            ok = ok and record["case"]["piece_count"] == 1 and record["pre_step"]["seam_pairs"] == []
        elif rung == 8:
            ok = ok and record["case"]["piece_count"] == 2 and record["pre_step"]["seam_pairs"] == []
        else:
            seam_count = len(record["pre_step"]["seam_world_spans_mm"])
            ok = ok and record["case"]["piece_count"] == 2 and seam_count == 1
        checks.append({"rung": rung, "case_id": case_id, "passed": bool(ok)})
        if not ok:
            break
    first_failure = next(
        (item["rung"] for item in checks if not item["passed"]),
        None,
    )
    return {
        "checks": checks,
        "first_failing_rung": first_failure,
        "stop_interpretation_at_first_failure": True,
    }


def main():
    _boot("main-entered")
    _progress("avatar-ladder: start")
    records = []
    for case_id in (
        "rung-1-avatar-pinned",
        "rung-2-avatar-unpinned",
        "rung-3-avatar-two-piece-no-seam",
        "rung-4-avatar-two-piece-small-seam",
        "rung-5-avatar-two-piece-large-seam",
    ):
        records.append(_run_ladder_case(case_id))
    manifest = {
        "schema": 1,
        "purpose": "diagnostic-only-avatar-complexity-ladder",
        "release_gate_effect": "none",
        "source_head_sha": os.environ.get("CLOTH_HEAD_SHA", ""),
        "solver_settings_frozen": {
            "backend_requested": os.environ.get("CLOTH_SIMULATION_BACKEND", "tissu"),
            "particle_distance_mm": 24.0,
            "iterations": 1,
            "substeps": 1,
            "timestep_s": 1.0 / 120.0,
            "gravity_z_mm_s2": 0.0,
            "gravity_mm_s2": [0.0, 0.0, 0.0],
        },
        "checkpoint_steps": list(CHECKPOINTS),
        "stop_rule": {
            "first_failing_rung": True,
            "human_visual_review_required": True,
            "strongest_alternative": "target/contact behavior is sound; seam/rest-state integration is causal",
        },
        "cases": records,
        "structural_validation": _structural_ladder_checks(records),
    }
    path = OUT / "avatar-ladder-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _boot("all-cases-complete")
    _progress("avatar-ladder: manifest-written")
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    return 0


def _run_and_shutdown():
    status = 1
    try:
        status = int(main() or 0)
    except BaseException as exc:
        _progress("avatar-ladder: main-failed=%r" % (exc,))
    finally:
        _boot(f"shutdown-status={status}")
        _shutdown_gui()
        faulthandler.cancel_dump_traceback_later()
    os._exit(status)


_boot("entrypoint-name=%r" % __name__)
_boot("entrypoint-argv0=%r" % (sys.argv[0] if sys.argv else ""))
_freecad_entrypoint_name = Path(__file__).stem
_freecad_gui_hosted = bool(getattr(App, "GuiUp", False))


def _schedule_freecad_main():
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    _boot("freecad-hosted-entrypoint")
    _boot("entrypoint:schedule-main")
    QtCore.QTimer.singleShot(0, _run_and_shutdown)


if __name__ == "__main__":
    _boot("direct-entrypoint")
    _run_and_shutdown()
elif _freecad_gui_hosted or __name__ == _freecad_entrypoint_name:
    _schedule_freecad_main()
