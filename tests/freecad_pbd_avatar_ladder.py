# Copyright (C) 2026 FreeCAD Cloth contributors
"""Screenshot-backed avatar complexity ladder for the diagnostic harness.
# Exact-head validation note: this source is exercised only from its PR head.
# Validation note: this diagnostic consumes the shared schema-1 avatar ladder manifest.

This module is a progressive simulation gate. It reuses the existing PositionBasedDynamics/FreeCAD runtime and
frozen solver settings; it does not participate in release acceptance.
"""

from __future__ import annotations


import contextlib
import faulthandler
import json
import os
import sys
import time
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from freecad_pbd_ladder_bootstrap import bootstrap_ladder

(
    _REPO_ROOT,
    _HELPER_DIR,
    OUT,
    _BOOT_LOG,
    _TRACE_HANDLE,
    _boot,
    App,
    Gui,
    Part,
) = bootstrap_ladder(__file__, "avatar")

from itertools import starmap

import pbd_contact_helpers as _ladder

_progress = _ladder.make_progress_logger(OUT / "progress.log")
_shutdown_gui = _ladder.make_shutdown_gui(_progress)
_boot("after-support-helper-import")

CHECKPOINTS = (0, 1, 5, 15, 45, 90)


def _surface_signed_clearance(
    points, source_shape, collision_surface, proximity_mesh=None, trace_context=""
):
    """Measure target clearance through shared spatial queries with optional tracing.

    Args:
        points: Particle coordinates to test against the target surface.
        source_shape: Native FreeCAD target shape, when available.
        collision_surface: Collision surface used by spatial-index fallback queries.
        proximity_mesh: Optional Trimesh query object.
        trace_context: Stable diagnostic context; tracing is enabled only for the
            named avatar stress checkpoint.

    Returns:
        Signed and unsigned target clearance in millimetres, or (None, None) when unavailable.
    """
    trace_enabled = trace_context == "rung-10-avatar-two-piece-large-seam step=45"

    def trace(message: str) -> None:
        if trace_enabled:
            _boot(f"{trace_context}:clearance:{message}")

    return _ladder.surface_signed_clearance(
        points,
        source_shape,
        collision_surface,
        proximity_mesh,
        vector_factory=App.Vector,
        trace=trace if trace_enabled else None,
    )


def _checkpoint_record(
    step,
    image,
    positions,
    panel_triangles,
    source_shape,
    collision_surface,
    base,
    proximity_mesh,
    case_id="",
):
    """Add avatar-specific clearance observations to the shared checkpoint record."""
    context = f"{case_id} step={step}"
    _boot(f"checkpoint-record-start {context}")
    signed_clearance, unsigned_clearance = _surface_signed_clearance(
        positions, source_shape, collision_surface, proximity_mesh, trace_context=context
    )
    _boot(f"checkpoint-record-after-clearance {context}")
    _boot(f"checkpoint-record-before-common {context}")
    record = _ladder.checkpoint_record(
        step,
        image,
        positions,
        panel_triangles,
        signed_clearance,
        unsigned_clearance,
        base,
        _ladder.connected_components,
        "diagnostic-only-avatar",
    )
    _boot(f"checkpoint-record-after-common {context}")
    return record


def _build_avatar_scene(doc):
    scene = _ladder.build_scene(doc)
    avatar = getattr(getattr(scene, "DrapeTarget", None), "SourceObject", None)
    if avatar is None:
        msg = "diagnostic avatar scene has no production ClothAvatar"
        raise RuntimeError(msg)
    if str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        msg = "diagnostic avatar target is not the production ClothAvatar"
        raise RuntimeError(msg)
    target = getattr(scene, "DrapeTarget", None)
    if target is None or getattr(target, "SourceObject", None) is not avatar:
        msg = "diagnostic avatar scene DrapeTarget does not reference production ClothAvatar"
        raise RuntimeError(msg)
    status = __import__(
        "freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]
    ).target_status(target)
    if status["state"] != "ready":
        msg = f"diagnostic avatar DrapeTarget is not ready: {status}"
        raise RuntimeError(msg)
    avatar.ViewObject.Visibility = True
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        avatar.ViewObject.Transparency = 70
    doc.recompute()
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
            msg = f"diagnostic avatar is missing arrangement point {name}"
            raise RuntimeError(msg)
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))

    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    from freecad_cloth.simulation.DrapeTarget import collision_surface

    target_surface = collision_surface(
        avatar,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    target_vertices = list(starmap(App.Vector, getattr(target_surface, "vertices", ())))
    if not target_vertices:
        msg = "diagnostic avatar DrapeTarget has no authoritative world-space vertices"
        raise RuntimeError(msg)
    x_mid_target = (float(shoulder_left.x) + float(shoulder_right.x)) / 2.0
    target_y_candidates = [
        float(point.y)
        for point in target_vertices
        if abs(float(point.x) - x_mid_target)
        <= max(40.0, abs(float(shoulder_right.x - shoulder_left.x)) * 0.9)
        and float(hip_point.z) - 100.0 <= float(point.z) <= float(shoulder_left.z) + 100.0
    ]
    target_y = (
        min(target_y_candidates)
        if target_y_candidates
        else min(float(point.y) for point in target_vertices)
    )
    body_depth = max(
        120.0,
        min(
            260.0,
            float(max(point.y for point in target_vertices))
            - float(min(point.y for point in target_vertices)),
        ),
    )
    clearance = max(20.0, 0.08 * body_depth)
    x_mid = (float(shoulder_left.x) + float(shoulder_right.x)) / 2.0
    z_mid = (float(shoulder_left.z) + float(hip_point.z)) / 2.0
    panel_y = target_y - clearance
    return (
        scene,
        avatar,
        {
            "x_mid": x_mid,
            "z_mid": z_mid,
            "panel_y": panel_y,
        },
    )


def _add_seam(doc, piece_a, piece_b, seam_id="avatar-seam"):
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam

    seam = Seam(
        piece_a=str(piece_a.PieceId),
        edge_a=1,
        piece_b=str(piece_b.PieceId),
        edge_b=3,
        id=seam_id,
        reversed_b=True,
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
    doc = App.newDocument("PositionBasedDynamicsAvatarLadder" + case_id.replace("-", "").title())
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
                    float(frame["panel_y"] + 120.0),
                    float(frame["z_mid"] - panel_height / 2.0),
                ),
                rotation,
            )
            piece = _ladder.build_piece(doc, name, placement, width=panel_width, height=panel_height)
            return piece

        left = make_piece("AvatarLeft", -120.0)
        pieces = [left]
        _ladder.append_optional_ladder_piece(
            spec=spec,
            pieces=pieces,
            create_right_piece=lambda: make_piece(
                "AvatarRight", float(spec["right_offset"] or 0.0)
            ),
            add_seam=lambda first, second: _add_seam(doc, first, second),
        )
        _ladder.configure_ladder_scene(scene, pieces, spec)
        doc.recompute()

        measurements = _ladder.prepare_ladder_case(
            scene=scene,
            source_object=avatar,
            positions_converter=_ladder.positions_tuple,
            case_id=case_id,
            require_source_shape=False,
            clearance_measure=_surface_signed_clearance,
        )
        runtime = measurements.runtime
        base = runtime.base
        collision_surface = runtime.collision_surface
        solver_triangles = runtime.solver_triangles
        positions = runtime.positions
        panel_triangles = runtime.panel_triangles
        target_sig = runtime.target_signature
        source_shape = runtime.source_shape
        seam_pre = measurements.seam_pre
        proximity_mesh = measurements.proximity_mesh
        signed_before = measurements.signed_before
        unsigned_before = measurements.unsigned_before
        bounds = measurements.bounds
        _progress(
            (
                "%s: pieces=%d pin=%s seam=%s source_triangles=%d "
                "solver_triangles=%d pre_clearance=%.6f min_seam=%.6f max_seam=%.6f"
            )
            % (
                case_id,
                spec["piece_count"],
                spec["pin_mode"],
                spec["seam_mode"],
                target_sig["source_triangles"],
                solver_triangles,
                float(signed_before if signed_before is not None else float("nan")),
                min((item["min_span_mm"] for item in seam_pre), default=0.0),
                max((item["max_span_mm"] for item in seam_pre), default=0.0),
            )
        )

        view = Gui.activeDocument().activeView()
        if view is None:
            msg = f"{case_id} has no active FreeCAD view"
            raise RuntimeError(msg)
        def reveal_avatar() -> None:
            avatar.ViewObject.Visibility = True
            for panel in getattr(scene, "DrapePanels", ()):
                panel.ViewObject.Visibility = True

        capture = _ladder.LadderCheckpointCapture(
            scene=scene,
            document=doc,
            view=view,
            case_id=case_id,
            boot=_boot,
            process_events=_ladder.events,
            orient_view=view.viewFront,
            reveal_objects=reveal_avatar,
            capture_image=_avatar_screenshot,
        )
        images = {}
        checkpoints = []
        for step in CHECKPOINTS:
            image = OUT / "avatar-ladder" / case_id / ("step-%03d.png" % int(step))
            capture.capture(step, image)
            positions = _ladder.positions_tuple(base.backend)
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
                    case_id=case_id,
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
                "target": "avatar",
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
                    "x_min": float(avatar.Mesh.BoundBox.XMin),
                    "x_max": float(avatar.Mesh.BoundBox.XMax),
                    "y_min": float(avatar.Mesh.BoundBox.YMin),
                    "y_max": float(avatar.Mesh.BoundBox.YMax),
                    "z_min": float(avatar.Mesh.BoundBox.ZMin),
                    "z_max": float(avatar.Mesh.BoundBox.ZMax),
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
                "progressive mannequin simulation ladder; exact production ClothAvatar/DrapeTarget; "
                "fixed PositionBasedDynamics backend; solver/collision budgets unchanged; release gate unaffected"
            ),
        }
        _boot("case-complete={} runtime_ms={:.3f}".format(case_id, record["runtime_ms"]))
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
            and record["solver"]["backend"] == "pbd"
            and record["solver"]["iterations"] == 1
            and record["solver"]["substeps"] == 1
            and abs(float(record["solver"]["timestep_s"]) - (1.0 / 120.0)) < 1e-12
            and float(record["solver"]["gravity_z_mm_s2"]) == 0.0
            and record["collision"]["solver_triangles"] > 0
            and len(record["checkpoints"]) == len(CHECKPOINTS)
            and [item["step"] for item in record["checkpoints"]] == list(CHECKPOINTS)
        )
        if rung <= 7:
            ok = (
                ok and record["case"]["piece_count"] == 1 and record["pre_step"]["seam_pairs"] == []
            )
        elif rung == 8:
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
    _progress("avatar-ladder: start")
    records = [
        _run_ladder_case(case_id)
        for case_id in (
            "rung-6-avatar-pinned",
            "rung-7-avatar-unpinned",
            "rung-8-avatar-two-piece-no-seam",
            "rung-9-avatar-two-piece-small-seam",
            "rung-10-avatar-two-piece-large-seam",
        )
    ]
    manifest = {
        "schema": 1,
        "purpose": "simulation-avatar-ladder",
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
            "strongest_alternative": "avatar target/contact is causal; seam interaction is not",
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
        _progress(f"avatar-ladder: main-failed={exc!r}")
    finally:
        _boot(f"shutdown-status={status}")
        faulthandler.cancel_dump_traceback_later()
    os._exit(status)


_boot(f"entrypoint-name={__name__!r}")
_boot("entrypoint-argv0=%r" % (sys.argv[0] if sys.argv else ""))
_freecad_entrypoint_name = Path(__file__).stem
_freecad_gui_hosted = bool(getattr(App, "GuiUp", False))


def _schedule_freecad_main():
    """Schedule the ladder outside FreeCAD's delayed-startup import callback."""
    _boot("freecad-hosted-entrypoint")
    _boot("entrypoint:schedule-main")
    _ladder.schedule_freecad_main(_run_and_shutdown)


if __name__ == "__main__":
    _boot("direct-entrypoint")
    _run_and_shutdown()
elif _freecad_gui_hosted or __name__ == _freecad_entrypoint_name:
    _schedule_freecad_main()
