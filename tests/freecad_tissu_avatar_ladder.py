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
import struct
import time
import zlib

_boot("script-start")
_boot("before-import-FreeCAD")
import FreeCAD as App

_boot("import-FreeCAD-complete")
import contextlib

import FreeCADGui as Gui

_boot("import-FreeCADGui-complete")
_boot("import-Part-complete")
try:
    faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)
    faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)
    _boot("diagnostic-faulthandler-ready")
except (AttributeError, OSError, RuntimeError, ValueError) as exc:
    _boot(f"diagnostic-faulthandler-unavailable={exc!r}")

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
    if source_shape is not None:
        for point in points:
            try:
                if bool(source_shape.isInside(App.Vector(*point), 1e-6, True)):
                    inside = True
                    break
            except (AttributeError, TypeError, ValueError):
                break
    if not inside and proximity_mesh is not None and points:
        try:
            import numpy as np

            inside = bool(np.any(proximity_mesh.contains(np.asarray(points, dtype=float))))
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
            pass
    return float(-unsigned if inside else unsigned), float(unsigned)


def _avatar_png_has_visible_content(path, minimum_pixels=128):
    """Return True when an 8-bit RGB/RGBA PNG contains visible non-background pixels."""

    data = Path(path).read_bytes()
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        return False
    offset = len(signature)
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            return False
        payload = data[payload_start:payload_end]
        offset = payload_end + 4
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, _inter = struct.unpack(
                ">IIBBBBB", payload
            )
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth != 8 or color_type not in (2, 6) or not idat:
        return False

    raw = zlib.decompress(bytes(idat))
    channels = 3 if color_type == 2 else 4
    row_bytes = int(width) * channels
    stride = row_bytes + 1
    if len(raw) < int(height) * stride:
        return False

    def paeth(a, b, c):
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    previous = bytearray(row_bytes)
    visible = 0
    for row in range(int(height)):
        base = row * stride
        filter_type = raw[base]
        encoded = raw[base + 1 : base + stride]
        decoded = bytearray(row_bytes)
        for i, value in enumerate(encoded):
            left = decoded[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 0:
                decoded[i] = value
            elif filter_type == 1:
                decoded[i] = (value + left) & 0xFF
            elif filter_type == 2:
                decoded[i] = (value + up) & 0xFF
            elif filter_type == 3:
                decoded[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                decoded[i] = (value + paeth(left, up, up_left)) & 0xFF
            else:
                return False
        for i in range(0, row_bytes, channels):
            if color_type == 2:
                pixel_visible = any(decoded[i + c] < 250 for c in range(3))
            else:
                alpha = decoded[i + 3]
                pixel_visible = alpha > 8 and any(decoded[i + c] < 250 for c in range(3))
            if pixel_visible:
                visible += 1
                if visible >= int(minimum_pixels):
                    return True
        previous = decoded
    return False


def _avatar_screenshot(view, path):
    view.setCameraType("Orthographic")
    view.fitAll()
    _events()
    view.redraw()
    time.sleep(0.05)
    _events()
    _screenshot(view, path)
    if _avatar_png_has_visible_content(path):
        return
    _progress(f"png-capture=retry path={path}")
    view.redraw()
    time.sleep(0.10)
    _events()
    _screenshot(view, path)
    if not _avatar_png_has_visible_content(path):
        raise RuntimeError(f"PNG capture contains no visible rendered content: {path}")


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
        raise RuntimeError(
            "diagnostic avatar scene DrapeTarget does not reference production ClothAvatar"
        )
    status = __import__(
        "freecad_cloth.simulation.DrapeTarget", fromlist=["target_status"]
    ).target_status(target)
    if status["state"] != "ready":
        raise RuntimeError(f"diagnostic avatar DrapeTarget is not ready: {status}")
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
            raise RuntimeError(f"diagnostic avatar is missing arrangement point {name}")
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
    target_vertices = [App.Vector(*vertex) for vertex in getattr(target_surface, "vertices", ())]
    if not target_vertices:
        raise RuntimeError(
            "diagnostic avatar DrapeTarget has no authoritative world-space vertices"
        )
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
                    float(frame["panel_y"] + 120.0),
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
            raise RuntimeError(f"{case_id} did not build a Tissu backend")
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
        source_shape = getattr(avatar, "Shape", None)
        if source_shape is not None:
            try:
                if source_shape.isNull():
                    source_shape = None
            except (AttributeError, TypeError, ValueError):
                source_shape = None

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
            raise RuntimeError(f"{case_id} has no active FreeCAD view")
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
            view.viewFront()
            _events()
            avatar.ViewObject.Visibility = True
            for panel in getattr(scene, "DrapePanels", ()):
                panel.ViewObject.Visibility = True
            _boot(f"checkpoint-before-screenshot case={case_id} step={step}")
            _avatar_screenshot(view, image)
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
    records = []
    for case_id in (
        "rung-6-avatar-pinned",
        "rung-7-avatar-unpinned",
        "rung-8-avatar-two-piece-no-seam",
        "rung-9-avatar-two-piece-small-seam",
        "rung-10-avatar-two-piece-large-seam",
    ):
        records.append(_run_ladder_case(case_id))
    manifest = {
        "schema": 1,
        "purpose": "diagnostic-only-avatar-complexity-ladder",
        "release_gate_effect": "none",
        "source_head_sha": os.environ.get("CLOTH_HEAD_SHA", ""),
        "solver_settings_frozen": {
            "backend_requested": "tissu",
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
