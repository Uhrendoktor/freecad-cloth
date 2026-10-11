"""Measure sustained cadence of the production FreeCAD realtime-preview callback."""

from __future__ import annotations

import contextlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(os.environ.get("CLOTH_REALTIME_DIR", "artifacts/freecad-realtime"))
OUT.mkdir(parents=True, exist_ok=True)

TARGET_FPS = 30.0
FRAME_BUDGET_MS = 1000.0 / TARGET_FPS
FRAMES = int(os.environ.get("CLOTH_REALTIME_FRAMES", "120"))
WARMUP_FRAMES = int(os.environ.get("CLOTH_REALTIME_WARMUP_FRAMES", "30"))
TIMEOUT_MS = int(os.environ.get("CLOTH_REALTIME_TIMEOUT_MS", "20000"))


def _add_tunic_preview_fixture(doc, scene) -> None:
    """Build two authored, sewn tunic panels so preview timing covers garment-scale meshes."""
    import Part
    import Sketcher

    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam

    avatar = getattr(getattr(scene, "AvatarProxy", None), "SourceObject", None)
    if avatar is None or not hasattr(avatar, "Mesh"):
        raise RuntimeError("Realtime preview fixture requires the production avatar mesh")
    bounds = avatar.Mesh.BoundBox
    body_width = float(bounds.XMax - bounds.XMin)
    body_depth = float(bounds.YMax - bounds.YMin)
    body_height = float(bounds.ZMax - bounds.ZMin)
    panel_width = max(420.0, body_width + 100.0)
    hem_width = panel_width + 80.0
    garment_height = max(600.0, body_height * 0.40)
    hem_z = float(bounds.ZMin) + body_height * 0.28
    center_x = 0.5 * (float(bounds.XMin) + float(bounds.XMax))
    center_y = 0.5 * (float(bounds.YMin) + float(bounds.YMax))
    clearance = max(60.0, 0.75 * body_depth)
    rotation = App.Rotation(App.Vector(1, 0, 0), 90.0)
    neckline_z = 0.90 * garment_height
    points = (
        (0.0, 0.0),
        (hem_width, 0.0),
        (panel_width, 0.82 * garment_height),
        (0.86 * panel_width, 0.97 * garment_height),
        (0.64 * panel_width, neckline_z),
        (0.36 * panel_width, neckline_z),
        (0.14 * panel_width, 0.97 * garment_height),
        (0.0, 0.82 * garment_height),
    )

    def make_piece(name: str, y: float):
        sketch = doc.addObject("Sketcher::SketchObject", f"{name}SourceSketch")
        sketch.addGeometry(
            [
                Part.LineSegment(
                    App.Vector(points[index][0], points[index][1], 0.0),
                    App.Vector(points[(index + 1) % len(points)][0],
                               points[(index + 1) % len(points)][1], 0.0),
                )
                for index in range(len(points))
            ],
            False,
        )
        sketch.addConstraint(
            [
                Sketcher.Constraint("Coincident", index, 2, (index + 1) % len(points), 1)
                for index in range(len(points))
            ]
        )
        doc.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sketch)
        piece = create_pattern_piece_from_selected_sketch(
            name=name,
            allowance=10.0,
            grainline=0.0,
        )
        piece.Label = name
        piece.Placement = App.Placement(
            App.Vector(center_x - hem_width / 2.0, y, hem_z),
            rotation,
        )
        piece.Sketch.Placement = piece.Placement
        piece.Sketch.ViewObject.Visibility = False
        return piece

    front = make_piece("RealtimeTunicFront", center_y - clearance)
    back = make_piece("RealtimeTunicBack", center_y + clearance)
    for edge_a, edge_b, seam_id in (
        (1, 1, "RealtimeRightSide"),
        (3, 3, "RealtimeRightShoulder"),
        (5, 5, "RealtimeLeftShoulder"),
        (7, 7, "RealtimeLeftSide"),
    ):
        add_seam(
            doc,
            Seam(
                str(front.PieceId),
                edge_a,
                str(back.PieceId),
                edge_b,
                id=seam_id,
                alignment="uniform",
                stitch_group="RealtimePreviewBenchmark",
            ),
        )
    Gui.Selection.clearSelection()
    scene.PinMode = "None"
    scene.PinSelection = []
    scene.ClothPieces = [front, back]
    scene.StartHeight = 0.0
    scene.TimeStep = 1.0 / 60.0


def _percentile(values: list[float], fraction: float) -> float | None:
    """Return a nearest-rank percentile, or None when no samples were collected."""
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(fraction * len(ordered)) - 1
    return ordered[max(0, min(len(ordered) - 1, rank))]


def main() -> None:
    """Exercise the real Qt preview timer and gate its sustained frame interval."""
    if FRAMES < 120:
        raise ValueError("CLOTH_REALTIME_FRAMES must be at least 120")
    if WARMUP_FRAMES < 30:
        raise ValueError("CLOTH_REALTIME_WARMUP_FRAMES must be at least 30")
    if TIMEOUT_MS < 1000:
        raise ValueError("CLOTH_REALTIME_TIMEOUT_MS must be at least 1000")

    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide import QtWidgets

    from freecad_cloth.simulation.RealtimePreview import _Preview, _prepare, _qt
    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene

    qt_core = _qt()
    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("Realtime benchmark requires the FreeCAD Qt application")

    doc = App.newDocument("ClothRealtimeBenchmark")
    preview = None
    deadline = None
    try:
        init_gui = ROOT / "InitGui.py"
        exec(
            compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"),
            globals(),
            globals(),
        )
        Gui.updateGui()
        scene = create_quality_simulation_scene(doc)
        _add_tunic_preview_fixture(doc, scene)
        _prepare(scene)

        proxy = scene.Proxy
        backend = proxy._base_or_restore().backend
        if backend is None:
            raise RuntimeError("Realtime preview did not initialize its solver backend")

        active_preview = _Preview(scene)
        preview = active_preview
        timer = active_preview.timer
        # This fresh timer has only the production tick connected; replace it with an instrumented call.
        try:
            timer.timeout.disconnect()
        except (RuntimeError, TypeError) as exc:
            raise RuntimeError("Could not instrument the production preview timer") from exc

        event_loop = qt_core.QEventLoop()
        tick_count = 0
        last_tick_at: float | None = None
        frame_intervals_ms: list[float] = []
        callback_costs_ms: list[float] = []
        initial_steps = int(scene.Steps)
        timed_out = False

        def timed_tick() -> None:
            started_at = time.perf_counter()
            active_preview.tick()
            callback_cost_ms = 1000.0 * (time.perf_counter() - started_at)
            if tick_count >= WARMUP_FRAMES:
                callback_costs_ms.append(callback_cost_ms)

        def observe_tick() -> None:
            nonlocal tick_count, last_tick_at
            now = time.perf_counter()
            tick_count += 1
            if last_tick_at is not None and tick_count > WARMUP_FRAMES:
                frame_intervals_ms.append(1000.0 * (now - last_tick_at))
            last_tick_at = now
            if len(frame_intervals_ms) >= FRAMES:
                event_loop.quit()

        def on_deadline() -> None:
            nonlocal timed_out
            timed_out = True
            event_loop.quit()

        # Signal ordering: observe only after the complete production callback has returned.
        timer.timeout.connect(timed_tick)
        timer.timeout.connect(observe_tick)
        deadline = qt_core.QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(on_deadline)

        started = time.perf_counter()
        deadline.start(TIMEOUT_MS)
        active_preview.start()
        execute_loop = getattr(event_loop, "exec", None) or event_loop.exec_
        execute_loop()
        elapsed = time.perf_counter() - started
        deadline.stop()

        mean_interval_ms = (
            sum(frame_intervals_ms) / len(frame_intervals_ms) if frame_intervals_ms else None
        )
        p95_interval_ms = _percentile(frame_intervals_ms, 0.95)
        max_interval_ms = max(frame_intervals_ms) if frame_intervals_ms else None
        mean_callback_ms = (
            sum(callback_costs_ms) / len(callback_costs_ms) if callback_costs_ms else None
        )
        p95_callback_ms = _percentile(callback_costs_ms, 0.95)
        max_callback_ms = max(callback_costs_ms) if callback_costs_ms else None
        frames_advanced = int(scene.Steps) - initial_steps
        backend_finite = bool(backend.finite())
        published_state_finite = bool(getattr(scene, "FiniteState", False))
        expected_ticks = WARMUP_FRAMES + FRAMES
        panels = tuple(getattr(scene, "DrapePanels", ()))
        collision_surface = getattr(backend, "solver_collision_surface", None)
        particle_count = len(backend.positions())
        collision_triangles = len(getattr(collision_surface, "triangles", ()))
        profile = {
            "quality_preset": str(scene.QualityPreset),
            "particle_distance_mm": float(scene.ParticleDistance),
            "solver_iterations": int(scene.SolverIterations),
            "solver_substeps": int(scene.SolverSubsteps),
            "pbd_substeps": int(getattr(backend, "_substeps", 1)),
        }
        fixture_pass = (
            particle_count >= 100
            and len(panels) == 2
            and collision_triangles > 0
        )
        profile_pass = (
            profile["quality_preset"] == "Fast"
            and profile["particle_distance_mm"] >= 40.0
            and profile["solver_iterations"] == 1
            and profile["solver_substeps"] == 1
            and profile["pbd_substeps"] == 1
        )
        cadence_pass = (
            mean_interval_ms is not None
            and p95_interval_ms is not None
            and mean_interval_ms <= FRAME_BUDGET_MS
            and p95_interval_ms <= FRAME_BUDGET_MS
            and len(frame_intervals_ms) == FRAMES
        )
        accounting_pass = tick_count == expected_ticks and frames_advanced == tick_count
        finite_pass = backend_finite and published_state_finite
        passed = (
            not timed_out
            and fixture_pass
            and profile_pass
            and cadence_pass
            and accounting_pass
            and finite_pass
        )

        try:
            freecad_version = ".".join(str(part) for part in App.Version())
        except (AttributeError, TypeError):
            freecad_version = "unknown"

        result = {
            "schema_version": 1,
            "backend": getattr(backend, "name", "unknown"),
            "fixture": "two-panel-tunic-pattern",
            "particles": particle_count,
            "panel_count": len(panels),
            "collision_triangles": collision_triangles,
            "target_fps": TARGET_FPS,
            "frame_budget_ms": FRAME_BUDGET_MS,
            "frames_requested": FRAMES,
            "warmup_frames_requested": WARMUP_FRAMES,
            "measured_intervals": len(frame_intervals_ms),
            "observed_ticks": tick_count,
            "expected_ticks": expected_ticks,
            "frames_advanced": frames_advanced,
            "timer_interval_ms": int(timer.interval()),
            "elapsed_s": elapsed,
            "mean_frame_interval_ms": mean_interval_ms,
            "p95_frame_interval_ms": p95_interval_ms,
            "max_frame_interval_ms": max_interval_ms,
            "fps_mean": 1000.0 / mean_interval_ms if mean_interval_ms else None,
            "mean_callback_ms": mean_callback_ms,
            "p95_callback_ms": p95_callback_ms,
            "max_callback_ms": max_callback_ms,
            "backend_finite": backend_finite,
            "published_state_finite": published_state_finite,
            "timed_out": timed_out,
            "profile": profile,
            "runtime": {
                "platform": platform.platform(),
                "python_version": sys.version.split()[0],
                "freecad_version": freecad_version,
                "cpu_count": os.cpu_count(),
                "libgl_always_software": os.environ.get("LIBGL_ALWAYS_SOFTWARE", "unset"),
            },
            "pass": passed,
        }
        (OUT / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, sort_keys=True), flush=True)
        if not passed:
            raise SystemExit(2)
    finally:
        if deadline is not None:
            with contextlib.suppress(Exception):
                deadline.stop()
        if preview is not None:
            with contextlib.suppress(Exception):
                preview.stop(restore=False)
        with contextlib.suppress(Exception):
            App.closeDocument(doc.Name)
        with contextlib.suppress(Exception):
            window = Gui.getMainWindow()
            if window is not None:
                window.close()
        with contextlib.suppress(Exception):
            app.quit()


main()
