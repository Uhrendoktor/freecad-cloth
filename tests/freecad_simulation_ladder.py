"""Progressive PositionBasedDynamics collision ladder.

Each rung keeps the same cloth/cube scenario and tightens collision resolution.
The ladder is intentionally small enough for CI while detecting solver/contact
quality regressions before the full mannequin acceptance path.
"""

from __future__ import annotations

import os

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend


WIDTH = 200.0
HEIGHT = 200.0
NX = 14
NY = 14
START_Z = 105.0
CUBE_MIN = -90.0
CUBE_MAX = 90.0
CUBE_BOTTOM = 0.0
CUBE_TOP = 60.0


def cube_surface():
    vertices = (
        (CUBE_MIN, CUBE_MIN, CUBE_BOTTOM),
        (CUBE_MAX, CUBE_MIN, CUBE_BOTTOM),
        (CUBE_MAX, CUBE_MAX, CUBE_BOTTOM),
        (CUBE_MIN, CUBE_MAX, CUBE_BOTTOM),
        (CUBE_MIN, CUBE_MIN, CUBE_TOP),
        (CUBE_MAX, CUBE_MIN, CUBE_TOP),
        (CUBE_MAX, CUBE_MAX, CUBE_TOP),
        (CUBE_MIN, CUBE_MAX, CUBE_TOP),
    )
    triangles = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 7, 4),
        (3, 4, 0),
    )
    return surface_from_triangles(vertices, triangles, region="ladder-cube", thickness=2.0)


def box_signed_clearance(position) -> float:
    x, y, z = (float(value) for value in position)
    inside_x = CUBE_MIN <= x <= CUBE_MAX
    inside_y = CUBE_MIN <= y <= CUBE_MAX
    inside_z = CUBE_BOTTOM <= z <= CUBE_TOP
    if inside_x and inside_y and inside_z:
        return -min(
            x - CUBE_MIN,
            CUBE_MAX - x,
            y - CUBE_MIN,
            CUBE_MAX - y,
            z - CUBE_BOTTOM,
            CUBE_TOP - z,
        )
    dx = max(CUBE_MIN - x, 0.0, x - CUBE_MAX)
    dy = max(CUBE_MIN - y, 0.0, y - CUBE_MAX)
    dz = max(CUBE_BOTTOM - z, 0.0, z - CUBE_TOP)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def make_system() -> ClothSystem:
    system = ClothSystem.grid(
        WIDTH,
        HEIGHT,
        nx=NX,
        ny=NY,
        origin=(-WIDTH / 2.0, -HEIGHT / 2.0, START_Z),
    )
    system.pin(((NY - 1) * NX, NY * NX - 1))
    return system


def run_stage(name, *, voxel_mm=None, substeps, iterations, steps, max_penetration_mm):
    if voxel_mm is None:
        os.environ.pop("CLOTH_PBD_COLLISION_VOXEL_MM", None)
        surface = None
    else:
        os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"] = str(float(voxel_mm))
        surface = cube_surface()
    os.environ["CLOTH_PBD_SUBSTEPS"] = str(int(substeps))
    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_PBD_COLLISION_TOLERANCE_MM"] = "2.0"

    backend = PositionBasedDynamicsBackend(
        make_system(),
        tuple(
            (
                j * NX + i,
                j * NX + i + 1,
                (j + 1) * NX + i + 1,
            )
            for j in range(NY - 1)
            for i in range(NX - 1)
        )
        + tuple(
            (
                j * NX + i,
                (j + 1) * NX + i + 1,
                (j + 1) * NX + i,
            )
            for j in range(NY - 1)
            for i in range(NX - 1)
        ),
        pins=((NY - 1) * NX, NY * NX - 1),
        collision_surface=surface,
    )
    initial = backend.positions()
    for _ in range(int(steps)):
        backend.step(1.0 / 60.0, int(iterations), (0.0, 0.0, -9810.0), surface)
    final = backend.positions()
    if not backend.finite():
        raise RuntimeError(f"{name}: non-finite solver state")
    if not final:
        raise RuntimeError(f"{name}: solver returned no particles")
    displacement = max(
        sum((final[index][axis] - initial[index][axis]) ** 2 for axis in range(3)) ** 0.5
        for index in range(len(final))
    )
    signed_clearance = min(box_signed_clearance(position) for position in final)
    penetration = max(0.0, -signed_clearance)
    if voxel_mm is None:
        if displacement <= 1.0:
            raise RuntimeError(f"{name}: cloth did not materially move ({displacement:.2f} mm)")
        print(
            f"ladder-rung=passed name={name} steps={steps} displacement_mm={displacement:.2f}",
            flush=True,
        )
        return
    if penetration > float(max_penetration_mm):
        raise RuntimeError(
            f"{name}: penetration {penetration:.2f} mm exceeds {max_penetration_mm:.2f} mm"
        )
    print(
        "ladder-rung=passed "
        f"name={name} steps={steps} voxel_mm={voxel_mm:.1f} substeps={substeps} "
        f"iterations={iterations} min_signed_clearance_mm={signed_clearance:.2f} "
        f"penetration_mm={penetration:.2f} displacement_mm={displacement:.2f}",
        flush=True,
    )


def main():
    run_stage(
        "01-free-cloth",
        voxel_mm=None,
        substeps=1,
        iterations=4,
        steps=30,
        max_penetration_mm=0.0,
    )
    run_stage(
        "02-cube-contact-coarse",
        voxel_mm=24.0,
        substeps=1,
        iterations=4,
        steps=120,
        max_penetration_mm=12.0,
    )
    run_stage(
        "03-cube-contact-stable",
        voxel_mm=12.0,
        substeps=4,
        iterations=8,
        steps=120,
        max_penetration_mm=6.0,
    )
    run_stage(
        "04-cube-contact-release",
        voxel_mm=8.0,
        substeps=8,
        iterations=8,
        steps=120,
        max_penetration_mm=3.0,
    )
    print("simulation-ladder=passed rungs=4", flush=True)


if __name__ == "__main__":
    main()
