"""Simulation backend interface; concrete solvers can be plugged in later."""
from dataclasses import dataclass
from typing import Protocol, Sequence, Tuple

Vec3 = Tuple[float, float, float]


@dataclass
class ClothState:
    positions: list[Vec3]


class ClothSolver(Protocol):
    def step(self, state: ClothState, dt: float) -> ClothState:
        ...


class NullSolver:
    """Deterministic no-op backend used by the initial workbench."""
    def step(self, state: ClothState, dt: float) -> ClothState:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        return state
