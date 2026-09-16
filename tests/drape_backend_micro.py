"""Realtime backend smoke/performance check without FreeCAD GUI overhead."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.simulation.ClothBackend import default_backend_registry
from freecad_cloth.simulation.ClothSolver import ClothSystem

OUT = Path(os.environ.get("CLOTH_MICRO_DIR", "artifacts/drape-backend-micro"))
OUT.mkdir(parents=True, exist_ok=True)
FRAME_BUDGET_MS = 1000.0 / 30.0


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


def make_collision_surface():
    # Small closed torso-like box: enough collision work to exercise the same code path
    # without importing or tessellating the full FreeCAD avatar in the performance test.
    x0, x1 = -105.0, 105.0
    y0, y1 = -55.0, 55.0
    z0, z1 = 105.0, 225.0
    vertices = (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
    )
    return CollisionSurface(vertices, triangles, "micro-torso", 2.0)


def main():
    requested = os.environ.get("CLOTH_SIMULATION_BACKEND", "xpbd-cpu")
    registry = default_backend_registry()
    backend_name = requested if requested in registry._factories else "xpbd-cpu"
    system, triangles, stitches = make_system()
    collision = make_collision_surface()
    if backend_name == "tissu":
        backend = registry.create(
            "tissu",
            system,
            triangles=triangles,
            pins=(0, 11, 216, 227),
            stitches=stitches,
            collision_surface=collision,
        )
    else:
        backend = registry.create("xpbd-cpu", system)
        backend.pin((0, 11, 216, 227))
        backend.set_stitches(stitches, compliance=0.0)

    iterations = int(os.environ.get("CLOTH_MICRO_ITERATIONS", "1"))
    steps = int(os.environ.get("CLOTH_MICRO_STEPS", "60"))
    dt = 1.0 / 60.0
    times = []
    started = time.perf_counter()
    for _ in range(steps):
        start = time.perf_counter()
        backend.step(
            dt=dt,
            iterations=iterations,
            gravity=(0.0, 0.0, -9810.0),
            surface=collision,
        )
        times.append(time.perf_counter() - start)
    elapsed = time.perf_counter() - started
    ordered = sorted(times)
    p95 = ordered[max(0, min(len(ordered) - 1, int(0.95 * len(ordered)) - 1))]
    result = {
        "backend": backend_name,
        "steps": steps,
        "iterations": iterations,
        "particles": len(backend.positions()),
        "stitches": len(stitches),
        "collision_triangles": len(collision.triangles),
        "substeps": int(os.environ.get("CLOTH_TISSU_SUBSTEPS", "1")) if backend_name == "tissu" else 1,
        "elapsed_s": elapsed,
        "mean_step_ms": 1000.0 * sum(times) / len(times),
        "p95_step_ms": 1000.0 * p95,
        "max_step_ms": 1000.0 * max(times),
        "fps_mean": 1.0 / (sum(times) / len(times)),
        "finite": bool(backend.finite()),
        "frame_budget_ms": FRAME_BUDGET_MS,
    }
    (OUT / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, sort_keys=True), flush=True)
    if not result["finite"] or result["mean_step_ms"] > FRAME_BUDGET_MS or result["p95_step_ms"] > 50.0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
