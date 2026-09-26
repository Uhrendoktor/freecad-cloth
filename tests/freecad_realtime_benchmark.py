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

OUT = Path(os.environ.get("CLOTH_REALTIME_DIR", "artifacts/freecad-realtime"))
OUT.mkdir(parents=True, exist_ok=True)
FRAME_BUDGET_MS = 1000.0 / 30.0
FRAMES = int(os.environ.get("CLOTH_REALTIME_FRAMES", "30"))


def main():
    doc = App.newDocument("ClothRealtimeBenchmark")
    try:
        init_gui = ROOT / "InitGui.py"
        exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), globals(), globals())
        Gui.updateGui()
        from freecad_cloth.simulation.RealtimePreview import _prepare, _select_preview_backend
        from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
        scene = create_quality_simulation_scene(doc)
        _prepare(scene)
        backend = _select_preview_backend(scene)
        # _prepare builds the realtime-quality system; avoid an extra GUI panel entirely.
        view = Gui.activeDocument().activeView() if Gui.activeDocument() else None
        times = []
        started = time.perf_counter()
        for _ in range(FRAMES):
            t0 = time.perf_counter()
            scene.Steps = int(scene.Steps) + 1
            doc.recompute()
            if view is not None:
                view.redraw()
            times.append(time.perf_counter() - t0)
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
        print(json.dumps(result, sort_keys=True), flush=True)
        if not result["finite"] or result["mean_frame_ms"] > FRAME_BUDGET_MS or result["p95_frame_ms"] > 50.0:
            raise SystemExit(2)
    finally:
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass
        try:
            window = Gui.getMainWindow()
            if window is not None:
                window.close()
        except Exception:
            pass
        try:
            try:
                from PySide6 import QtWidgets
            except ImportError:
                from PySide import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass


main()
