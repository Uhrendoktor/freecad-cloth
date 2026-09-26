"""Optional Tissu C++ XPBD backend.

The reference solver remains the deterministic fallback. Tissu is imported lazily
so installations without the optional wheel keep the existing backend usable.
"""
from copy import deepcopy
from typing import Iterable, Sequence, Tuple
import os

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_TISSU_SUBSTEPS_DEFAULT = 1
_TISSU_COLLISION_TRIANGLES_DEFAULT = 0
_TISSU_COLLIDER_FRICTION_DEFAULT = 0.5


def _tissu_substeps():
    value = int(os.environ.get("CLOTH_TISSU_SUBSTEPS", str(_TISSU_SUBSTEPS_DEFAULT)))
    if value < 1:
        raise ValueError("CLOTH_TISSU_SUBSTEPS must be >= 1")
    return value


def _tissu_collider_friction():
    raw = os.environ.get(
        "CLOTH_TISSU_COLLIDER_FRICTION",
        str(_TISSU_COLLIDER_FRICTION_DEFAULT),
    ).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("CLOTH_TISSU_COLLIDER_FRICTION must be a number in [0, 1]") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError("CLOTH_TISSU_COLLIDER_FRICTION must be in [0, 1]")
    return value


def _tissu_collision_triangle_limit():
    value = int(os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", str(_TISSU_COLLISION_TRIANGLES_DEFAULT)))
    if value < 0:
        raise ValueError("CLOTH_TISSU_COLLISION_TRIANGLES must be >= 0")
    return value


def _to_tissu_position(position):
    x, y, z = position
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _from_tissu_position(position):
    x, y, z = position
    return (float(x) * _MM, float(z) * _MM, float(y) * _MM)


def _to_tissu_mesh(surface):
    """Convert FreeCAD collision data to Tissu's pybind-friendly containers."""
    import numpy as np

    vertices = [np.asarray(_to_tissu_position(v), dtype=np.float64) for v in surface.vertices]
    triangles = [[int(a), int(c), int(b)] for a, b, c in surface.triangles]
    return vertices, triangles


def _collision_envelope(surface):
    """Derive a stable torso envelope from the authored avatar collision data."""
    if surface is None or not surface.vertices:
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

    radius = max(120.0, min(240.0, 0.245 * width, 0.70 * depth))
    bottom = min_z + 0.38 * height
    top = min_z + 0.76 * height
    samples = (0.0, 0.25, 0.50, 0.75, 1.0)
    return tuple(
        (
            (center_x, center_y, bottom + (top - bottom) * t),
            radius,
        )
        for t in samples
    )


class TissuBackend(ClothSimulationBackend):
    """C++ XPBD backend with selectable Tissu collision paths."""

    name = "tissu"

    def __init__(
        self,
        system: ClothSystem,
        triangles: Sequence[Tuple[int, int, int]],
        pins: Iterable[int] = (),
        stitches: Iterable[Tuple[int, int]] = (),
        collision_surface: CollisionSurface | None = None,
        collision_mode: str = "torso-envelope",
    ):
        try:
            from tissu import Simulation
        except ImportError as exc:
            raise RuntimeError("Tissu backend requires the optional 'pytissu' package") from exc
        collision_mode = str(os.environ.get("CLOTH_TISSU_COLLISION_MODE", collision_mode)).strip().lower()
        if collision_mode not in {"mesh", "torso-envelope"}:
            raise ValueError("unsupported Tissu collision mode")
        self._initial = deepcopy(system)
        self._triangles = tuple(tuple(int(i) for i in tri) for tri in triangles)
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in pins))
        self._stitches = tuple((int(a), int(b)) for a, b in stitches)
        self._source_collision_surface = collision_surface
        collision_limit = _tissu_collision_triangle_limit()
        if collision_surface is not None and collision_mode == "mesh" and collision_limit:
            collision_surface = coarsen_collision_surface(collision_surface, collision_limit)
            print(
                "cloth-tissu-collision source_triangles=%d solver_triangles=%d limit=%d"
                % (
                    len(self._source_collision_surface.triangles),
                    len(collision_surface.triangles),
                    collision_limit,
                ),
                flush=True,
            )
        self._collision_surface = collision_surface
        self._collision_mode = collision_mode
        self._time = 0.0
        self._iterations = 8
        self._substeps = _tissu_substeps()
        self._build(Simulation)

    @property
    def solver_collision_surface(self):
        """Return the exact surface registered with Tissu's solver."""
        return self._collision_surface

    @property
    def time(self):
        return self._time

    def _add_collision(self):
        import numpy as np
        if self._collision_surface is None:
            return
        if self._collision_mode == "torso-envelope":
            for index, (center, radius_mm) in enumerate(_collision_envelope(self._collision_surface)):
                self._sim.add_sphere(
                    f"drape-torso-{index}",
                    np.asarray(_to_tissu_position(center), dtype=np.float64),
                    float(radius_mm) / _MM,
                    friction=0.5,
                )
            return
        vtx, idx = _to_tissu_mesh(self._collision_surface)
        self._sim.add_mesh_from_arrays(
            "drape-target",
            vtx,
            idx,
            friction=_tissu_collider_friction(),
        )

    def _build(self, Simulation):
        import numpy as np
        positions = [_to_tissu_position(p.position()) for p in self._initial.particles]
        triangles = np.asarray(self._triangles, dtype=np.int32)
        vertices = np.asarray(positions, dtype=np.float64)
        self._sim = Simulation(substeps=self._substeps, iterations=self._iterations, gravity=-9.81, thickness=0.002)
        self._fabric = self._sim.create_from_arrays("cloth", vertices, triangles, material="cotton")
        global_ids = np.asarray(self._fabric.instance.get_particle_indices(), dtype=np.int32)
        if len(global_ids) != len(positions) or not np.array_equal(global_ids, np.arange(len(positions))):
            raise RuntimeError("Tissu did not preserve cloth particle ordering")
        for index in self._pin_indices:
            self._sim.solver.add_pin(int(index), np.asarray(positions[index], dtype=np.float64), 0.0)
        for a, b in self._stitches:
            self._sim.solver.add_stitch(int(a), int(b), 0.0)
        self._add_collision()

    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        if dt <= 0 or iterations < 1:
            raise ValueError("dt and iterations must be positive")
        if surface is not None and surface is not self._collision_surface:
            raise RuntimeError("TissuBackend collision surface is immutable after construction")
        if sphere is not None:
            raise RuntimeError("TissuBackend does not support sphere fallback collision")
        self._sim.solver.set_iterations(max(1, int(iterations)))
        _gx, _gy, gz = gravity
        self._sim.gravity = float(gz) / _MM
        self._sim.step(float(dt))
        self._iterations = int(iterations)
        self._time += float(dt)

    def reset(self):
        from tissu import Simulation
        self._time = 0.0
        self._build(Simulation)

    def pin(self, indices: Iterable[int]):
        import numpy as np
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in indices))
        for index in self._pin_indices:
            position = self.positions()[index]
            self._sim.solver.add_pin(int(index), np.asarray(_to_tissu_position(position), dtype=np.float64), 0.0)

    def set_stitches(self, pairs: Iterable[Tuple[int, int]], compliance=0.0):
        self._stitches = tuple((int(a), int(b)) for a, b in pairs)
        for a, b in self._stitches:
            self._sim.solver.add_stitch(int(a), int(b), float(compliance))

    def positions(self):
        return tuple(_from_tissu_position(p) for p in self._sim.positions)

    def finite(self):
        return all(abs(v) < 1e12 for p in self.positions() for v in p)
