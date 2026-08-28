"""Simulation backend interface and shared cloth state."""
from dataclasses import dataclass, field
from typing import Callable, Dict, Protocol, Tuple

Vec3 = Tuple[float, float, float]


@dataclass
class ClothState:
    """Mutable solver state; positions are always present, dynamics are optional."""
    positions: list[Vec3]
    velocities: list[Vec3] = field(default_factory=list)
    inverse_masses: list[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.velocities:
            self.velocities = [(0.0, 0.0, 0.0) for _ in self.positions]
        if not self.inverse_masses:
            self.inverse_masses = [1.0 for _ in self.positions]
        if len(self.velocities) != len(self.positions):
            raise ValueError("velocity count must match position count")
        if len(self.inverse_masses) != len(self.positions):
            raise ValueError("inverse mass count must match position count")
        if any(mass < 0 for mass in self.inverse_masses):
            raise ValueError("inverse masses cannot be negative")


class ClothSolver(Protocol):
    def step(self, state: ClothState, dt: float) -> ClothState:
        ...


class NullSolver:
    """Deterministic no-op backend used for workbench plumbing."""
    def step(self, state: ClothState, dt: float) -> ClothState:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        return state


BackendFactory = Callable[[], ClothSolver]


class BackendRegistry:
    """Small named backend registry; external solvers remain optional."""

    def __init__(self):
        self._factories: Dict[str, BackendFactory] = {}

    def register(self, name: str, factory: BackendFactory) -> None:
        key = str(name).strip().lower()
        if not key:
            raise ValueError("backend name must not be empty")
        if key in self._factories:
            raise ValueError(f"backend already registered: {key}")
        self._factories[key] = factory

    def create(self, name: str) -> ClothSolver:
        key = str(name).strip().lower()
        try:
            factory = self._factories[key]
        except KeyError as exc:
            raise KeyError(f"unknown cloth backend: {key}") from exc
        solver = factory()
        if not hasattr(solver, "step"):
            raise TypeError(f"backend {key} does not provide step(state, dt)")
        return solver

    def names(self):
        return tuple(sorted(self._factories))


def default_backend_registry() -> BackendRegistry:
    """Return a fresh registry containing only the dependency-free default."""
    registry = BackendRegistry()
    registry.register("null", NullSolver)
    return registry
