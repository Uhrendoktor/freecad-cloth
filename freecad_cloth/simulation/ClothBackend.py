"""Solver-neutral adapter API for cloth simulation backends.

FreeCAD document code should depend on this module rather than directly on a
specific solver. The bundled XPBD backend is the deterministic fallback;
Tissu is an optional C++ XPBD backend with broad-phase collision support.
"""
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Callable, Iterable, Mapping, Sequence, Tuple

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.sewing.SeamGraph import SeamGraph


PINNED_STITCH_EPSILON_MM = 1.0e-9


def _position_tuple(value):
    position = value.position() if callable(getattr(value, "position", None)) else value
    values = tuple(float(component) for component in position)
    if len(values) != 3:
        raise ValueError("simulation stitch positions must be three-dimensional")
    return values


def validate_pinned_stitch_pairs(
    positions,
    pinned_indices,
    seam_pair_records=(),
    *,
    epsilon=PINNED_STITCH_EPSILON_MM,
):
    """Reject physically impossible zero-rest stitches between pinned particles."""
    positions = tuple(_position_tuple(value) for value in positions)
    pinned = frozenset(int(index) for index in pinned_indices)
    if epsilon < 0.0:
        raise ValueError("stitch validation epsilon must be non-negative")

    records = tuple(seam_pair_records)
    if records:
        candidates = (
            (str(record[0]), pair)
            for record in records
            for pair in record[3]
        )
    else:
        candidates = (("unattributed", pair) for pair in ())

    seen = set()
    for seam_id, pair in candidates:
        a, b = (int(pair[0]), int(pair[1]))
        if a < 0 or b < 0 or a >= len(positions) or b >= len(positions):
            raise ValueError(
                "stitch pair is outside the simulation particle set: "
                f"seam={seam_id} particle_a={a} particle_b={b}"
            )
        if (a, b) in seen:
            continue
        seen.add((a, b))
        if a not in pinned or b not in pinned:
            continue
        pa, pb = positions[a], positions[b]
        separation = sum((pa[index] - pb[index]) ** 2 for index in range(3)) ** 0.5
        if separation > epsilon:
            raise ValueError(
                "impossible pinned-pinned sewing constraint: "
                f"seam={seam_id} particle_a={a} particle_b={b} "
                f"initial_separation={separation:.9f} mm"
            )



class ClothSimulationBackend(ABC):
    name = "abstract"

    @property
    def solver_collision_surface(self):
        """Return the backend-facing collision surface, if the backend derives one."""
        return None

    @abstractmethod
    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        raise NotImplementedError

    @abstractmethod
    def reset(self):
        raise NotImplementedError

    @abstractmethod
    def pin(self, indices: Iterable[int]):
        raise NotImplementedError

    @abstractmethod
    def set_stitches(self, pairs: Iterable[Tuple[int, int]], compliance=0.0):
        raise NotImplementedError

    @abstractmethod
    def positions(self):
        raise NotImplementedError

    @abstractmethod
    def finite(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def time(self):
        raise NotImplementedError


class XPBDBackend(ClothSimulationBackend):
    name = "xpbd-cpu"

    def __init__(self, system: ClothSystem):
        if not isinstance(system, ClothSystem):
            raise TypeError("XPBDBackend requires a ClothSystem")
        self._initial = deepcopy(system)
        self.system = system
        self._stitches = ()
        self._stitch_compliance = 0.0
        self._pins = ()

    @property
    def time(self):
        return self.system.time

    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        if surface is not None and not isinstance(surface, CollisionSurface):
            raise TypeError("surface must be a CollisionSurface")
        self.system.step(dt=dt, iterations=iterations, gravity=gravity, sphere=sphere, surface=surface)

    def reset(self):
        self.system = deepcopy(self._initial)
        if self._stitches:
            self.system.add_stitches(self._stitches, self._stitch_compliance)
        if self._pins:
            self.system.pin(self._pins)

    def pin(self, indices: Iterable[int]):
        self._pins = tuple(dict.fromkeys(int(i) for i in indices))
        self.system.pin(self._pins)

    def set_stitches(self, pairs: Iterable[Tuple[int, int]], compliance=0.0):
        self._stitches = tuple((int(a), int(b)) for a, b in pairs)
        self._stitch_compliance = float(compliance)
        self.system.stitches = []
        if self._stitches:
            self.system.add_stitches(self._stitches, self._stitch_compliance)

    def set_seams(self, graph: SeamGraph, edge_vertices: Mapping[Tuple[str, int], Sequence[int]], seam_ids: Iterable[str] = (), compliance=0.0):
        graph.validate()
        self.set_stitches(graph.stitch_pairs(edge_vertices, seam_ids), compliance)

    def positions(self):
        return tuple(p.position() for p in self.system.particles)

    def finite(self):
        return self.system.finite()


class BackendRegistry:
    """Deterministic named backend registry for dependency injection/tests."""

    def __init__(self):
        self._factories = {}

    def register(self, name: str, factory: Callable):
        key = str(name).strip()
        if not key:
            raise ValueError("backend name must not be empty")
        if key in self._factories:
            raise ValueError(f"backend already registered: {key}")
        self._factories[key] = factory

    def create(self, name: str, system: ClothSystem, **kwargs):
        requested = str(name).strip()
        try:
            factory = self._factories[requested]
        except KeyError:
            raise ValueError(f"unknown cloth backend: {requested}") from None
        backend = factory(system, **kwargs) if kwargs else factory(system)
        if not isinstance(backend, ClothSimulationBackend):
            raise TypeError("backend factory must return ClothSimulationBackend")
        return backend


def default_backend_registry() -> BackendRegistry:
    registry = BackendRegistry()
    registry.register(XPBDBackend.name, XPBDBackend)
    try:
        import tissu  # noqa: F401
        from freecad_cloth.simulation.TissuBackend import TissuBackend
    except ImportError:
        pass
    else:
        registry.register(TissuBackend.name, TissuBackend)
    return registry


def preferred_backend_name(registry=None) -> str:
    """Prefer Tissu when installed; retain XPBD as a deterministic fallback."""
    import os
    registry = registry or default_backend_registry()
    requested = str(os.environ.get("CLOTH_SIMULATION_BACKEND", "auto")).strip().lower()
    if requested in registry._factories:
        return requested
    if requested not in ("", "auto"):
        raise ValueError(f"unknown cloth backend: {requested}")
    return "tissu" if "tissu" in registry._factories else XPBDBackend.name
