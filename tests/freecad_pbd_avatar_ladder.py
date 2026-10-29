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
import os
import sys
import time
from functools import partial
from itertools import starmap
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from freecad_pbd_ladder_bootstrap import bootstrap_ladder, dispatch_ladder_entrypoint

_BOOTSTRAP = bootstrap_ladder(__file__, "avatar")
OUT = _BOOTSTRAP.output_directory
_boot = _BOOTSTRAP.boot
App = _BOOTSTRAP.app
Gui = _BOOTSTRAP.gui
Part = _BOOTSTRAP.part

import pbd_contact_helpers as _ladder

_progress = _ladder.make_progress_logger(OUT / "progress.log")
_shutdown_gui = _ladder.make_shutdown_gui(_progress)
_boot("after-support-helper-import")


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
            piece = _ladder.build_piece(
                doc, name, placement, width=panel_width, height=panel_height
            )
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
                runtime.target_signature["source_triangles"],
                runtime.solver_triangles,
                float(
                    measurements.signed_before
                    if measurements.signed_before is not None
                    else float("nan")
                ),
                min((item["min_span_mm"] for item in measurements.seam_pre), default=0.0),
                max((item["max_span_mm"] for item in measurements.seam_pre), default=0.0),
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
            capture_image=_ladder.screenshot,
        )
        checkpoint_callback = partial(
            _checkpoint_record,
            panel_triangles=runtime.panel_triangles,
            source_shape=runtime.source_shape,
            collision_surface=runtime.collision_surface,
            base=runtime.base,
            proximity_mesh=measurements.proximity_mesh,
            case_id=case_id,
        )
        images, checkpoints = _ladder.capture_ladder_checkpoints(
            capture=capture,
            output_directory=OUT,
            target_name="avatar",
            case_id=case_id,
            runtime=runtime,
            record_checkpoint=checkpoint_callback,
            progress=_progress,
        )

        record = _ladder.build_ladder_case_record(
            target="avatar",
            case_id=case_id,
            spec=spec,
            scene=scene,
            runtime=runtime,
            measurements=measurements,
            images=images,
            checkpoints=checkpoints,
            started=started,
            target_bounds={
                "x_min": float(avatar.Mesh.BoundBox.XMin),
                "x_max": float(avatar.Mesh.BoundBox.XMax),
                "y_min": float(avatar.Mesh.BoundBox.YMin),
                "y_max": float(avatar.Mesh.BoundBox.YMax),
                "z_min": float(avatar.Mesh.BoundBox.ZMin),
                "z_max": float(avatar.Mesh.BoundBox.ZMax),
            },
            contact_mode="avatar-diagnostic",
            extra_control={
                "placement_offsets_mm": {"left_x": -120.0, "right_x": spec["right_offset"]},
                "arrangement_frame": frame,
            },
            notes=(
                "progressive mannequin simulation ladder; exact production ClothAvatar/DrapeTarget; "
                "fixed PositionBasedDynamics backend; solver/collision budgets unchanged; release gate unaffected"
            ),
        )
        _boot("case-complete={} runtime_ms={:.3f}".format(case_id, record["runtime_ms"]))
        return record
    finally:
        try:
            _boot(f"case-finally={case_id}")
        finally:
            App.closeDocument(doc.Name)


def main() -> int:
    """Run the avatar ladder and persist its schema-1 evidence manifest."""
    return _ladder.write_ladder_manifest(
        target="avatar",
        purpose="simulation-avatar-ladder",
        manifest_name="avatar-ladder-manifest.json",
        strongest_alternative="avatar target/contact is causal; seam interaction is not",
        case_ids=(
            "rung-6-avatar-pinned",
            "rung-7-avatar-unpinned",
            "rung-8-avatar-two-piece-no-seam",
            "rung-9-avatar-two-piece-small-seam",
            "rung-10-avatar-two-piece-large-seam",
        ),
        ordered_cases=(
            ("rung-6-avatar-pinned", 6),
            ("rung-7-avatar-unpinned", 7),
            ("rung-8-avatar-two-piece-no-seam", 8),
            ("rung-9-avatar-two-piece-small-seam", 9),
            ("rung-10-avatar-two-piece-large-seam", 10),
        ),
        single_piece_rungs=(6, 7),
        no_seam_two_piece_rungs=(8,),
        run_case=_run_ladder_case,
        output_directory=OUT,
        boot=_boot,
        progress=_progress,
    )


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


dispatch_ladder_entrypoint(
    __file__,
    __name__,
    _run_and_shutdown,
    _boot,
    App,
    _ladder.schedule_freecad_main,
)
