"""Simulation backend interface and shared cloth state."""
from dataclasses import dataclass, field
from typing import Protocol, Tuple

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
