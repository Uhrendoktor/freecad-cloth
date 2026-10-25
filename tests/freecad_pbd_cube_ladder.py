# Copyright (C) 2026 FreeCAD Cloth contributors
"""Screenshot-backed cube complexity ladder for the diagnostic harness.
# Exact-head validation note: this source is exercised only from its PR head.
# Validation note: this diagnostic consumes the shared schema-1 cube ladder manifest.

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

from freecad_pbd_ladder_bootstrap import bootstrap_ladder, dispatch_ladder_entrypoint

_BOOTSTRAP = bootstrap_ladder(__file__, "cube")
OUT = _BOOTSTRAP.output_directory
_boot = _BOOTSTRAP.boot
App = _BOOTSTRAP.app
Gui = _BOOTSTRAP.gui
Part = _BOOTSTRAP.part

import pbd_contact_helpers as _ladder

_progress = _ladder.make_progress_logger(OUT / "progress.log")
_shutdown_gui = _ladder.make_shutdown_gui(_progress)
_boot("after-support-helper-import")

CHECKPOINTS = (0, 1, 5, 15, 45, 90)


def _surface_signed_clearance(
    points: Sequence[Sequence[float]],
    source_shape: object | None,
    collision_surface: object,
    proximity_mesh: object | None = None,
) -> tuple[float | None, float | None]:
    """Measure signed surface clearance through the shared geometry helper.

    Args:
        points: Particle coordinates to test against the target surface.
        source_shape: Native FreeCAD target shape when available.
        collision_surface: Collision surface used by spatial-index fallback queries.
        proximity_mesh: Optional Trimesh query object.

    Returns:
        Signed and unsigned target clearance in millimetres, or (None, None) when unavailable.
    """
    return _ladder.surface_signed_clearance(
        points,
        source_shape,
        collision_surface,
        proximity_mesh,
        vector_factory=App.Vector,
    )


def _checkpoint_record(
    step, image, positions, panel_triangles, source_shape, collision_surface, base, proximity_mesh
):
    """Add cube-specific clearance observations to the shared checkpoint record."""
    signed_clearance, unsigned_clearance = _surface_signed_clearance(
        positions, source_shape, collision_surface, proximity_mesh
    )
    return _ladder.checkpoint_record(
        step,
        image,
        positions,
        panel_triangles,
        signed_clearance,
        unsigned_clearance,
        base,
        _ladder.connected_components,
        "diagnostic-only-cube",
    )


def _build_cube_scene(doc):
    """Build the cube fixture and bind it to the canonical collision target."""
    scene = _ladder.build_scene(doc)
    cube = _ladder.configure_diagnostic_cube_target(doc, scene, App, Part)
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
        left = _ladder.build_piece(
            doc,
            "CubeLeft",
            App.Placement(App.Vector(-180.0, -180.0, 58.5), App.Rotation()),
        )
        pieces = [left]

        def create_right_piece() -> object:
            """Build the optional right cube-ladder cloth panel."""
            return _ladder.build_piece(
                doc,
                "CubeRight",
                App.Placement(
                    App.Vector(float(spec["right_x"]), -180.0, 58.5),
                    App.Rotation(),
                ),
            )

        _ladder.append_optional_ladder_piece(
            spec=spec,
            pieces=pieces,
            create_right_piece=create_right_piece,
            add_seam=lambda first, second: _add_seam(doc, first, second),
        )
        _ladder.configure_ladder_scene(scene, pieces, spec)
        doc.recompute()

        measurements = _ladder.prepare_ladder_case(
            scene=scene,
            source_object=cube,
            positions_converter=_ladder.positions_tuple,
            case_id=case_id,
            require_source_shape=True,
            clearance_measure=_surface_signed_clearance,
        )
        runtime = measurements.runtime
        _progress(
            "%s: pieces=%d pin=%s seam=%s solver_triangles=%d pre_clearance=%.6f max_seam=%.6f"
            % (
                case_id,
                spec["piece_count"],
                spec["pin_mode"],
                spec["seam_mode"],
                runtime.solver_triangles,
                float(
                    measurements.signed_before
                    if measurements.signed_before is not None
                    else float("nan")
                ),
                max((item["max_span_mm"] for item in measurements.seam_pre), default=0.0),
            )
        )

        view = Gui.activeDocument().activeView()
        if view is None:
            msg = f"{case_id} has no active FreeCAD view"
            raise RuntimeError(msg)
        capture = _ladder.LadderCheckpointCapture(
            scene=scene,
            document=doc,
            view=view,
            case_id=case_id,
            boot=_boot,
            process_events=_ladder.events,
            orient_view=view.viewAxonometric,
            reveal_objects=lambda: None,
            capture_image=_ladder.screenshot,
        )
        images = {}
        checkpoints = []
        for step in CHECKPOINTS:
            image = OUT / "cube-ladder" / case_id / ("step-%03d.png" % int(step))
            capture.capture(step, image)
            positions = _ladder.positions_tuple(runtime.base.backend)
            checkpoints.append(
                _checkpoint_record(
                    step,
                    str(image.relative_to(OUT)),
                    positions,
                    runtime.panel_triangles,
                    runtime.source_shape,
                    runtime.collision_surface,
                    runtime.base,
                    measurements.proximity_mesh,
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
        seam_world_spans = [entry for entry in measurements.seam_pre]
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
                "source_signature": runtime.target_signature,
                "source_triangles": int(runtime.target_signature["source_triangles"]),
                "solver_triangles": int(runtime.solver_triangles),
                "target_bounds": {
                    "x_min": -90.0,
                    "x_max": 90.0,
                    "y_min": -90.0,
                    "y_max": 90.0,
                    "z_min": 0.0,
                    "z_max": 60.0,
                },
                "target_topology_summary": {
                    "vertices": int(runtime.target_signature["source_vertices"]),
                    "triangles": int(runtime.target_signature["source_triangles"]),
                    "solver_triangles": int(runtime.solver_triangles),
                },
            },
            "pre_step": {
                "piece_bounds": [list(measurements.bounds.values())],
                "unsigned_clearance_mm": measurements.unsigned_before,
                "signed_clearance_mm": measurements.signed_before,
                "seam_pairs": [
                    [int(left), int(right)]
                    for seam in runtime.base.seam_stitch_pairs.values()
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
                "pre_step_seam_count": len(runtime.base.seam_stitch_pairs),
                "pre_step_seam_pair_count": sum(
                    len(pairs) for pairs in runtime.base.seam_stitch_pairs.values()
                ),
                "pre_step_bounds_mm": measurements.bounds,
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
    records = [
        _run_ladder_case(case_id)
        for case_id in (
            "rung-1-cube-pinned",
            "rung-2-cube-unpinned",
            "rung-3-cube-two-piece-no-seam",
            "rung-4-cube-two-piece-small-seam",
            "rung-5-cube-two-piece-large-seam",
        )
    ]
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


dispatch_ladder_entrypoint(
    __file__,
    __name__,
    _run_and_shutdown,
    _boot,
    App,
    _ladder.schedule_freecad_main,
)
