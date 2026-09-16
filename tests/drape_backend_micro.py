"""Sub-minute backend smoke/performance check without FreeCAD GUI overhead."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freecad_cloth.simulation.ClothBackend import default_backend_registry
from freecad_cloth.simulation.ClothSolver import ClothSystem

OUT = Path(os.environ.get("CLOTH_MICRO_DIR", "artifacts/drape-backend-micro"))
OUT.mkdir(parents=True, exist_ok=True)


def make_system():
    nx, ny = 12, 18
    left = ClothSystem.grid(180.0, 260.0, nx=nx, ny=ny, origin=(-185.0, -130.0, 210.0))
    right = ClothSystem.grid(180.0, 260.0, nx=nx, ny=ny, origin=(5.0, -130.0, 210.0))
    offset = len(left.particles)
    particles = left.particles + right.particles
    constraints = list(left.constraints) + [
        type(c)(c.a + offset, c.b + offset, c.rest, c.compliance)
        for c in right.constraints
    ]
    system = ClothSystem(particles, constraints)
    top = tuple(range(nx - 1, -1, -1))
    right_top = tuple(offset + i for i in range(nx))
    stitches = tuple((a, b) for a, b in zip(top, right_top))
    system.add_stitches(stitches)
    system.pin((0, nx - 1, offset, offset + nx - 1))
    triangles = []
    for panel_offset in (0, offset):
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = panel_offset + j * nx + i
                b = a + 1
                c = panel_offset + (j + 1) * nx + i + 1
                d = panel_offset + (j + 1) * nx + i
                triangles.extend(((a, b, c), (a, c, d)))
    return system, tuple(triangles), stitches


def main():
    requested = os.environ.get("CLOTH_SIMULATION_BACKEND", "xpbd-cpu")
    registry = default_backend_registry()
    backend_name = requested if requested in registry._factories else "xpbd-cpu"
    system, triangles, stitches = make_system()
    backend = registry.create(
        backend_name,
        system,
        triangles=triangles,
        pins=(0, 11, 216, 227) if backend_name == "tissu" else (),
        stitches=stitches if backend_name == "tissu" else (),
        collision_surface=None,
    ) if backend_name == "tissu" else registry.create("xpbd-cpu", system)
    if backend_name == "xpbd-cpu":
        backend.pin((0, 11, 216, 227))
        backend.set_stitches(stitches, compliance=0.0)

    iterations = int(os.environ.get("CLOTH_MICRO_ITERATIONS", "4"))
    steps = int(os.environ.get("CLOTH_MICRO_STEPS", "6"))
    dt = 1.0 / 60.0
    times = []
    t0 = time.perf_counter()
    for _ in range(steps):
        start = time.perf_counter()
        backend.step(dt=dt, iterations=iterations, gravity=(0.0, 0.0, -9810.0), surface=None)
        times.append(time.perf_counter() - start)
    elapsed = time.perf_counter() - t0
    result = {
        "backend": backend_name,
        "steps": steps,
        "iterations": iterations,
        "particles": len(backend.positions()),
        "stitches": len(stitches),
        "substeps": int(os.environ.get("CLOTH_TISSU_SUBSTEPS", "10")) if backend_name == "tissu" else 1,
        "elapsed_s": elapsed,
        "mean_step_ms": 1000.0 * sum(times) / len(times),
        "max_step_ms": 1000.0 * max(times),
        "finite": bool(backend.finite()),
    }
    (OUT / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, sort_keys=True), flush=True)
    # Keep the CI contract explicit: the micro path must remain comfortably sub-minute.
    if not result["finite"] or elapsed > 45.0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
