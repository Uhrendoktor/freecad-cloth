"""Screenshot-backed cube complexity ladder for the diagnostic harness.
# Exact-head validation note: this source is exercised only from its PR head.
# Validation note: this diagnostic consumes the shared schema-1 cube ladder manifest.

This module is a progressive simulation gate. It reuses the existing PositionBasedDynamics/FreeCAD runtime and
frozen solver settings; it does not participate in release acceptance.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

OUT = Path(os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/pbd-contact-diagnostics"))
OUT.mkdir(parents=True, exist_ok=True)
_BOOT_LOG = OUT / "cube-ladder-bootstrap.log"
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
    _boot(f"diagnostic-faulthandler-unavailable={exc!r}")

_boot("before-shared-helper-runpath")
_shared = runpy.run_path(
    str(Path(__file__).with_name("freecad_pbd_contact_diagnostics.py")),
    run_name="freecad_pbd_contact_diagnostics",
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
            measurements.append(
                {
                    "particle_a": int(left),
                    "particle_b": int(right),
                    "a_world_mm": [round(value, 6) for value in a],
                    "b_world_mm": [round(value, 6) for value in b],
                    "distance_mm": round(distance, 6),
                }
            )
        distances = [item["distance_mm"] for item in measurements]
        result.append(
            {
                "seam_id": str(seam_id),
                "pair_count": len(measurements),
                "min_span_mm": round(min(distances), 6) if distances else 0.0,
                "max_span_mm": round(max(distances), 6) if distances else 0.0,
                "mean_span_mm": round(sum(distances) / len(distances), 6) if distances else 0.0,
                "pairs": measurements,
            }
        )
    return result


def _surface_signed_clearance(points, source_shape, collision_surface, proximity_mesh=None):
    unsigned = None
    if proximity_mesh is not None:
        try:
            import numpy as np
            import trimesh  # noqa: F401

            if points:
                _, distances, _ = proximity_mesh.nearest.on_surface(np.asarray(points, dtype=float))
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


def _checkpoint_record(
    step, image, positions, panel_triangles, source_shape, collision_surface, base, proximity_mesh
):
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
        "penetration_mm": (
            round(max(0.0, -float(signed_clearance)), 6) if signed_clearance is not None else None
        ),
        "contact_state": "diagnostic-only-cube",
        "seam_world_spans_mm": seam_geometry,
    }


def _build_cube_scene(doc):
    scene = _build_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    cube = doc.addObject("Part::Feature", "DiagnosticCube")
    cube.Label = "Diagnostic Collision Cube"
    cube.Shape = Part.makeBox(180.0, 180.0, 60.0, App.Vector(-90.0, -90.0, 0.0))
    doc.recompute()

    from freecad_cloth.simulation.SimulationObjects import set_avatar_collision_source

    set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)
    if avatar is not None and hasattr(avatar, "ViewObject"):
        avatar.ViewObject.Visibility = False
    cube.ViewObject.Visibility = True
    doc.recompute()
    return scene, cube


def _add_seam(doc, piece_a, piece_b, seam_id="cube-seam"):
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
        "rung-1-cube-pinned": {
            "rung": 1,
            "piece_count": 1,
            "pin_mode": "Automatic",
            "seam_mode": "none",
            "right_x": None,
        },
        "rung-2-cube-unpinned": {
            "rung": 2,
            "piece_count": 1,
            "pin_mode": "None",
            "seam_mode": "none",
            "right_x": None,
        },
        "rung-3-cube-two-piece-no-seam": {
            "rung": 3,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "none",
            "right_x": -60.0,
        },
        "rung-4-cube-two-piece-small-seam": {
            "rung": 4,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "small",
            "right_x": -59.5,
        },
        "rung-5-cube-two-piece-large-seam": {
            "rung": 5,
            "piece_count": 2,
            "pin_mode": "None",
            "seam_mode": "large",
            "right_x": 20.0,
        },
    }
    return dict(table[case_id])


def _run_ladder_case(case_id):
    _boot(f"case-start={case_id}")
    spec = _case_spec(case_id)
    doc = App.newDocument("PositionBasedDynamicsCubeLadder" + case_id.replace("-", "").title())
    started = time.perf_counter()
    try:
        scene, cube = _build_cube_scene(doc)
        left = _build_piece(
            doc,
            "CubeLeft",
            App.Placement(App.Vector(-180.0, -180.0, 58.5), App.Rotation()),
        )
        pieces = [left]
        if spec["piece_count"] == 2:
            right = _build_piece(
                doc,
                "CubeRight",
                App.Placement(App.Vector(float(spec["right_x"]), -180.0, 58.5), App.Rotation()),
            )
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
            raise RuntimeError(f"{case_id} did not build a PositionBasedDynamics backend")
        collision_surface = getattr(
            base.backend,
            "solver_collision_surface",
            getattr(base, "collision_surface", None),
        )
        if collision_surface is None:
            raise RuntimeError(f"{case_id} did not expose a collision surface")
        solver_triangles = len(getattr(collision_surface, "triangles", ()) or ())
        if solver_triangles <= 0:
            raise RuntimeError(f"{case_id} has no solver collision triangles")
        positions = _positions_tuple(base.backend)
        panel_triangles = tuple(
            triangle
            for panel_triangles in base.panel_triangles.values()
            for triangle in panel_triangles
        )
        target_sig = _target_signature(scene.DrapeTarget)
        source_shape = getattr(cube, "Shape", None)
        if source_shape is None or source_shape.isNull():
            raise RuntimeError(f"{case_id} cube source shape is invalid")

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
            "%s: pieces=%d pin=%s seam=%s solver_triangles=%d pre_clearance=%.6f max_seam=%.6f"
            % (
                case_id,
                spec["piece_count"],
                spec["pin_mode"],
                spec["seam_mode"],
                solver_triangles,
                float(signed_before if signed_before is not None else float("nan")),
                max((item["max_span_mm"] for item in seam_pre), default=0.0),
            )
        )

        view = Gui.activeDocument().activeView()
        if view is None:
            raise RuntimeError(f"{case_id} has no active FreeCAD view")
        images = {}
        checkpoints = []
        for step in CHECKPOINTS:
            _boot(f"checkpoint-before-recompute case={case_id} step={step}")
            scene.Steps = int(step)
            doc.recompute()
            _boot(f"checkpoint-after-recompute case={case_id} step={step}")
            _events()
            image = OUT / "cube-ladder" / case_id / ("step-%03d.png" % int(step))
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
        max_penetration = max(
            (
                float(item["penetration_mm"])
                for item in checkpoints
                if item["penetration_mm"] is not None
            ),
            default=0.0,
        )
        seam_world_spans = [entry for entry in seam_pre]
        record = {
            "case_id": case_id,
            "predecessor_case_id": None,
            "case": {
                "rung": int(spec["rung"]),
                "id": case_id,
                "target": "cube",
                "piece_count": int(spec["piece_count"]),
                "pin_mode": spec["pin_mode"],
                "seam_mode": spec["seam_mode"],
            },
            "solver": {
                "backend": "pbd",
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
                    "x_min": -90.0,
                    "x_max": 90.0,
                    "y_min": -90.0,
                    "y_max": 90.0,
                    "z_min": 0.0,
                    "z_max": 60.0,
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
            "max_penetration_mm": round(max_penetration, 6),
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
            "contact_mode": "cube-diagnostic",
            "control": {
                "pre_step_seam_count": len(base.seam_stitch_pairs),
                "pre_step_seam_pair_count": sum(
                    len(pairs) for pairs in base.seam_stitch_pairs.values()
                ),
                "pre_step_bounds_mm": bounds,
            },
            "images": [images[step] for step in CHECKPOINTS],
            "notes": (
                "progressive cube simulation ladder; fixed PositionBasedDynamics backend; "
                "solver/collision budgets unchanged; release gate unaffected"
            ),
        }
        _boot(f"case-complete={case_id} runtime_ms={record['runtime_ms']}")
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
        ("rung-1-cube-pinned", 1),
        ("rung-2-cube-unpinned", 2),
        ("rung-3-cube-two-piece-no-seam", 3),
        ("rung-4-cube-two-piece-small-seam", 4),
        ("rung-5-cube-two-piece-large-seam", 5),
    ]
    for case_id, rung in ordered:
        record = by_id[case_id]
        ok = (
            bool(record["finite"])
            and record["case"]["rung"] == rung
            and record["solver"]["backend"] == "pbd"
            and record["solver"]["iterations"] == 1
            and record["solver"]["substeps"] == 1
            and abs(float(record["solver"]["timestep_s"]) - (1.0 / 120.0)) < 1e-12
            and float(record["solver"]["gravity_z_mm_s2"]) == 0.0
            and record["collision"]["solver_triangles"] > 0
            and len(record["checkpoints"]) == len(CHECKPOINTS)
            and [item["step"] for item in record["checkpoints"]] == list(CHECKPOINTS)
        )
        if rung <= 2:
            ok = (
                ok and record["case"]["piece_count"] == 1 and record["pre_step"]["seam_pairs"] == []
            )
        elif rung == 3:
            ok = (
                ok and record["case"]["piece_count"] == 2 and record["pre_step"]["seam_pairs"] == []
            )
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
    _progress("cube-ladder: start")
    records = []
    for case_id in (
        "rung-1-cube-pinned",
        "rung-2-cube-unpinned",
        "rung-3-cube-two-piece-no-seam",
        "rung-4-cube-two-piece-small-seam",
        "rung-5-cube-two-piece-large-seam",
    ):
        records.append(_run_ladder_case(case_id))
    manifest = {
        "schema": 1,
        "purpose": "simulation-collision-ladder",
        "release_gate_effect": "gate",
        "source_head_sha": os.environ.get("CLOTH_HEAD_SHA", ""),
        "solver_settings_frozen": {
            "backend_requested": "pbd",
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
    path = OUT / "cube-ladder-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _boot("all-cases-complete")
    _progress("cube-ladder: manifest-written")
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    return 0


def _run_and_shutdown():
    status = 1
    try:
        status = int(main() or 0)
    except BaseException as exc:
        _progress(f"cube-ladder: main-failed={exc!r}")
    finally:
        _boot(f"shutdown-status={status}")
        _shutdown_gui()
        faulthandler.cancel_dump_traceback_later()
    os._exit(status)


_boot(f"entrypoint-name={__name__!r}")
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
