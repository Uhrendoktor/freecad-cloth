"""Benchmark the production FreeCAD realtime preview loop at interactive quality."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freecad_cloth.simulation.RealtimePreview import _prepare, _select_preview_backend
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene

OUT = Path(os.environ.get("CLOTH_REALTIME_DIR", "artifacts/freecad-realtime"))
OUT.mkdir(parents=True, exist_ok=True)
FRAME_BUDGET_MS = 1000.0 / 30.0
FRAMES = int(os.environ.get("CLOTH_REALTIME_FRAMES", "30"))
TRACE = OUT / "benchmark-trace.log"


def trace(message):
    with TRACE.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    TRACE.write_text("", encoding="utf-8")
    run_started = time.perf_counter()
    trace("stage=process-start")
    doc = App.newDocument("ClothRealtimeBenchmark")
    try:
        trace("stage=document-created elapsed_ms=%.3f" % (1000.0 * (time.perf_counter() - run_started)))
        scene = create_quality_simulation_scene(doc)
        trace("stage=scene-created particles=%d elapsed_ms=%.3f" % (int(getattr(scene, "ParticleCount", 0)), 1000.0 * (time.perf_counter() - run_started)))
        _prepare(scene)
        trace("stage=prepared elapsed_ms=%.3f" % (1000.0 * (time.perf_counter() - run_started)))
        backend = _select_preview_backend(scene)
        trace("stage=backend-selected backend=%s particles=%d elapsed_ms=%.3f" % (getattr(backend, "name", "unknown"), len(backend.positions()), 1000.0 * (time.perf_counter() - run_started)))
        # _prepare builds the realtime-quality system; avoid an extra GUI panel entirely.
        view = Gui.activeDocument().activeView() if Gui.activeDocument() else None
        times = []
        started = time.perf_counter()
        for frame in range(FRAMES):
            frame_start = time.perf_counter()
            trace("stage=frame-start frame=%d elapsed_ms=%.3f" % (frame + 1, 1000.0 * (frame_start - run_started)))
            scene.Steps = int(scene.Steps) + 1
            doc.recompute()
            if view is not None:
                view.redraw()
            frame_time = time.perf_counter() - frame_start
            times.append(frame_time)
            trace("stage=frame-end frame=%d frame_ms=%.3f elapsed_ms=%.3f" % (frame + 1, 1000.0 * frame_time, 1000.0 * (time.perf_counter() - run_started)))
        elapsed = time.perf_counter() - started
        ordered = sorted(times)
        p95 = ordered[max(0, min(len(ordered) - 1, int(0.95 * len(ordered)) - 1))]
        result = {
            "backend": getattr(backend, "name", "unknown"),
            "frames": FRAMES,
            "particles": int(getattr(scene, "ParticleCount", 0)),
            "particle_distance_mm": float(getattr(scene, "ParticleDistance", 0.0)),
            "solver_iterations": int(getattr(scene, "SolverIterations", 0)),
            "solver_substeps": int(getattr(scene, "SolverSubsteps", 0)),
            "tissu_substeps": int(getattr(backend, "_substeps", 1)),
            "elapsed_s": elapsed,
            "mean_frame_ms": 1000.0 * sum(times) / len(times),
            "p95_frame_ms": 1000.0 * p95,
            "max_frame_ms": 1000.0 * max(times),
            "fps_mean": 1.0 / (sum(times) / len(times)),
            "finite": bool(backend.finite()),
            "frame_budget_ms": FRAME_BUDGET_MS,
        }
        (OUT / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        trace("stage=metrics-written elapsed_ms=%.3f mean_frame_ms=%.3f p95_frame_ms=%.3f max_frame_ms=%.3f" % (1000.0 * (time.perf_counter() - run_started), result["mean_frame_ms"], result["p95_frame_ms"], result["max_frame_ms"]))
        print(json.dumps(result, sort_keys=True), flush=True)
        if not result["finite"] or result["mean_frame_ms"] > FRAME_BUDGET_MS or result["p95_frame_ms"] > 50.0:
            raise SystemExit(2)
    finally:
        trace("stage=cleanup-start elapsed_ms=%.3f" % (1000.0 * (time.perf_counter() - run_started)))
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass
        try:
            App.exit()
            trace("stage=app-exit-returned elapsed_ms=%.3f" % (1000.0 * (time.perf_counter() - run_started)))
        except Exception as exc:
            trace("stage=app-exit-exception type=%s elapsed_ms=%.3f" % (type(exc).__name__, 1000.0 * (time.perf_counter() - run_started)))


if __name__ == "__main__":
    main()
