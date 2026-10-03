"""Production Tissu C++ XPBD backend.

Tissu is the only runtime cloth solver. This adapter converts the headless
ClothSystem and persistent DrapeTarget into Tissu inputs.
"""

import os
from collections.abc import Iterable, Sequence
from copy import deepcopy
from math import isfinite

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_TISSU_SUBSTEPS_DEFAULT = 1
_TISSU_COLLISION_TRIANGLES_DEFAULT = 0


def _tissu_substeps() -> int:
    value = int(os.environ.get("CLOTH_TISSU_SUBSTEPS", str(_TISSU_SUBSTEPS_DEFAULT)))
    if value < 1:
        raise ValueError("CLOTH_TISSU_SUBSTEPS must be >= 1")
    return value


def _tissu_collision_triangle_limit() -> int:
    value = int(
        os.environ.get(
            "CLOTH_TISSU_COLLISION_TRIANGLES",
            str(_TISSU_COLLISION_TRIANGLES_DEFAULT),
        )
    )
    if value < 0:
        raise ValueError("CLOTH_TISSU_COLLISION_TRIANGLES must be >= 0")
    return value


def _to_tissu_position(position) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _from_tissu_position(position) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) * _MM, float(z) * _MM, float(y) * _MM)


def _to_tissu_mesh(surface: CollisionSurface):
    """Convert collision data to Tissu's pybind-friendly containers."""
    import numpy as np

    vertices = [np.asarray(_to_tissu_position(v), dtype=np.float64) for v in surface.vertices]
    triangles = [[int(a), int(c), int(b)] for a, b, c in surface.triangles]
    return vertices, triangles


def _collision_envelope(surface: CollisionSurface):
    """Build a coarse torso envelope for explicitly requested preview collision."""
    if not surface.vertices:
        return ()
    xs = [float(v[0]) for v in surface.vertices]
    ys = [float(v[1]) for v in surface.vertices]
    zs = [float(v[2]) for v in surface.vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    height = max(1.0, max_z - min_z)
    width = max(1.0, max_x - min_x)
    depth = max(1.0, max_y - min_y)
    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)
    radius = max(90.0, min(170.0, 0.16 * width, 0.48 * depth))
    bottom = min_z + 0.38 * height
    top = min_z + 0.76 * height
    return tuple(
        ((center_x, center_y, bottom + (top - bottom) * fraction), radius)
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
    )


class TissuBackend(ClothSimulationBackend):
    """Production backend using the optional pytissu package."""

    name = "tissu"

    def __init__(
        self,
        system: ClothSystem,
        triangles: Sequence[tuple[int, int, int]],
        pins: Iterable[int] = (),
        stitches: Iterable[tuple[int, int]] = (),
        collision_surface: CollisionSurface | None = None,
        collision_mode: str = "mesh",
    ):
        try:
            from tissu import Simulation
        except ImportError as exc:
            raise RuntimeError("simulation requires the 'pytissu' package") from exc

        collision_mode = (
            str(os.environ.get("CLOTH_TISSU_COLLISION_MODE", collision_mode))
            .strip()
            .lower()
        )
        if collision_mode not in {"mesh", "torso-envelope"}:
            raise ValueError("unsupported Tissu collision mode")

        self._simulation_type = Simulation
        self._initial = deepcopy(system)
        self._triangles = tuple(tuple(int(i) for i in triangle) for triangle in triangles)
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in pins))
        self._stitches = tuple((int(a), int(b)) for a, b in stitches)
        self._stitch_compliance = 0.0
        self._source_collision_surface = collision_surface
        collision_limit = _tissu_collision_triangle_limit()

        if collision_surface is not None and collision_mode == "mesh" and collision_limit:
            collision_surface = coarsen_collision_surface(collision_surface, collision_limit)
            print(
                "cloth-tissu-collision "
                f"source_triangles={len(self._source_collision_surface.triangles)} "
                f"solver_triangles={len(collision_surface.triangles)} "
                f"limit={collision_limit}",
                flush=True,
            )

        self._collision_surface = collision_surface
        self._collision_mode = collision_mode
        self._time = 0.0
        self._substeps = _tissu_substeps()
        self._build()

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the exact surface registered with Tissu."""
        return self._collision_surface

    @property
    def time(self) -> float:
        """Return elapsed simulation time in seconds."""
        return self._time

    def _add_collision(self) -> None:
        import numpy as np

        if self._collision_surface is None:
            return
        if self._collision_mode == "torso-envelope":
            for index, (center, radius_mm) in enumerate(
                _collision_envelope(self._collision_surface)
            ):
                self._sim.add_sphere(
                    f"drape-torso-{index}",
                    np.asarray(_to_tissu_position(center), dtype=np.float64),
                    float(radius_mm) / _MM,
                    friction=0.5,
                )
            return

        vertices, triangles = _to_tissu_mesh(self._collision_surface)
        self._sim.add_mesh_from_arrays(
            "drape-target",
            vertices,
            triangles,
            friction=0.5,
        )

    def _build(self) -> None:
        import numpy as np

        positions = [_to_tissu_position(p.position()) for p in self._initial.particles]
        triangles = np.asarray(self._triangles, dtype=np.int32)
        vertices = np.asarray(positions, dtype=np.float64)
        self._sim = self._simulation_type(
            substeps=self._substeps,
            iterations=8,
            gravity=-9.81,
            thickness=0.002,
        )
        self._fabric = self._sim.create_from_arrays(
            "cloth",
            vertices,
            triangles,
            material="cotton",
        )
        global_ids = np.asarray(
            self._fabric.instance.get_particle_indices(),
            dtype=np.int32,
        )
        if len(global_ids) != len(positions) or not np.array_equal(
            global_ids,
            np.arange(len(positions)),
        ):
            raise RuntimeError("Tissu did not preserve cloth particle ordering")
        for index in self._pin_indices:
            self._sim.solver.add_pin(
                int(index),
                np.asarray(positions[index], dtype=np.float64),
                0.0,
            )
        for a, b in self._stitches:
            self._sim.solver.add_stitch(a, b, self._stitch_compliance)
        self._add_collision()

    def step(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 8,
        gravity=(0.0, 0.0, -9810.0),
        surface: CollisionSurface | None = None,
    ) -> None:
        """Advance Tissu by one time step."""
        if dt <= 0.0 or iterations < 1:
            raise ValueError("dt must be positive and iterations must be >= 1")
        if surface is not None and surface is not self._collision_surface:
            raise RuntimeError("Tissu collision surface is immutable after construction")
        self._sim.solver.set_iterations(int(iterations))
        _gx, _gy, gz = gravity
        self._sim.gravity = float(gz) / _MM
        self._sim.step(float(dt))
        self._time += float(dt)

    def reset(self) -> None:
        """Rebuild Tissu from the original input model."""
        self._time = 0.0
        self._build()

    def pin(self, indices: Iterable[int]) -> None:
        """Replace solver pins and rebuild from the original input model."""
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in indices))
        self._time = 0.0
        self._build()

    def set_stitches(
        self,
        pairs: Iterable[tuple[int, int]],
        compliance: float = 0.0,
    ) -> None:
        """Replace sewing constraints and rebuild from the original input model."""
        if compliance < 0.0:
            raise ValueError("compliance must be non-negative")
        self._stitches = tuple((int(a), int(b)) for a, b in pairs)
        self._stitch_compliance = float(compliance)
        self._time = 0.0
        self._build()

    def positions(self) -> tuple[tuple[float, float, float], ...]:
        """Return current particle positions in FreeCAD millimetres."""
        return tuple(_from_tissu_position(position) for position in self._sim.positions)

    def finite(self) -> bool:
        """Return whether all solver coordinates remain finite and bounded."""
        return all(
            isfinite(value) and abs(value) < 1e12
            for position in self.positions()
            for value in position
        )
