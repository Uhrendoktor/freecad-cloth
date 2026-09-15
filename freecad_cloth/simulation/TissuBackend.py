"""Optional Tissu C++ XPBD backend.

The reference solver remains the deterministic fallback. Tissu is imported lazily
so installations without the optional wheel keep the existing backend usable.
"""
from copy import deepcopy
from typing import Iterable, Sequence, Tuple

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_TISSU_SUBSTEPS = 10


def _to_tissu_position(position):
    x, y, z = position
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _from_tissu_position(position):
    x, y, z = position
    return (float(x) * _MM, float(z) * _MM, float(y) * _MM)


def _to_tissu_mesh(surface):
    """Convert FreeCAD collision data to Tissu's pybind-friendly containers.

    FreeCAD is RH-Z-up while Tissu is RH-Y-up. The coordinate mapping swaps
    Y and Z, an odd permutation with determinant -1, so it reverses handedness.
    Every authored triangle is therefore reversed exactly once to preserve the
    authored outward orientation. A per-face center heuristic is incorrect for
    a concave humanoid surface because its global center is not a reliable
    inside/outside test for each local face.
    """
    import numpy as np

    vertices = [np.asarray(_to_tissu_position(v), dtype=np.float64) for v in surface.vertices]
    triangles = [[int(a), int(c), int(b)] for a, b, c in surface.triangles]
    return vertices, triangles


def _collision_envelope(surface):
    """Derive a stable torso envelope from the authored avatar collision data.

    Tissu's sphere collider resolves with a radial normal, which is substantially
    more stable for this canonical torso drape than nearest-triangle contact on
    a highly concave human render mesh. The centers are still derived directly
    from the real avatar bounds; no FreeCAD proxy object is created.
    """
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
        collision_mode: str = "mesh",
    ):
        try:
            from tissu import Simulation
        except ImportError as exc:
            raise RuntimeError("Tissu backend requires the optional 'pytissu' package") from exc
        if collision_mode not in {"mesh", "torso-envelope"}:
            raise ValueError("unsupported Tissu collision mode")
        self._initial = deepcopy(system)
        self._triangles = tuple(tuple(int(i) for i in tri) for tri in triangles)
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in pins))
        self._stitches = tuple((int(a), int(b)) for a, b in stitches)
        self._collision_surface = collision_surface
        self._collision_mode = collision_mode
        self._time = 0.0
        self._iterations = 8
        self._build(Simulation)

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
            friction=0.5,
        )

    def _build(self, Simulation):
        import numpy as np
        positions = [_to_tissu_position(p.position()) for p in self._initial.particles]
        triangles = np.asarray(self._triangles, dtype=np.int32)
        vertices = np.asarray(positions, dtype=np.float64)
        self._sim = Simulation(substeps=_TISSU_SUBSTEPS, iterations=self._iterations, gravity=-9.81, thickness=0.002)
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
