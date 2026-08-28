"""Solver-neutral adapter API for cloth simulation backends.

FreeCAD document code should depend on this module rather than directly on a
specific solver.  The bundled XPBD backend wraps ``ClothSystem`` unchanged.
"""
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Callable, Iterable, Mapping, Sequence, Tuple

from ClothSolver import ClothSystem
from SeamGraph import SeamGraph


class ClothSimulationBackend(ABC):
    """Small stable interface consumed by simulation/document objects."""

    name = "abstract"

    @abstractmethod
    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None):
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
    """Adapter for the repository's deterministic CPU XPBD-style solver."""

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

    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None):
        self.system.step(dt=dt, iterations=iterations, gravity=gravity, sphere=sphere)

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

    def set_seams(
        self,
        graph: SeamGraph,
        edge_vertices: Mapping[Tuple[str, int], Sequence[int]],
        seam_ids: Iterable[str] = (),
        compliance=0.0,
    ):
        """Generate solver stitches from semantic seam metadata."""
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

    def register(self, name: str, factory: Callable[[ClothSystem], ClothSimulationBackend]):
        key = str(name).strip()
        if not key:
            raise ValueError("backend name must not be empty")
        if key in self._factories:
            raise ValueError(f"backend already registered: {key}")
        self._factories[key] = factory

    def create(self, name: str, system: ClothSystem):
        try:
            factory = self._factories[name]
        except KeyError:
            raise ValueError(f"unknown cloth backend: {name}") from None
        backend = factory(system)
        if not isinstance(backend, ClothSimulationBackend):
            raise TypeError("backend factory must return ClothSimulationBackend")
        return backend


def default_backend_registry() -> BackendRegistry:
    registry = BackendRegistry()
    registry.register(XPBDBackend.name, XPBDBackend)
    return registry
