"""Small adapter contract for the production PositionBasedDynamics cloth solver.

FreeCAD document code depends on this boundary instead of importing PositionBasedDynamics APIs.
PositionBasedDynamics is the only runtime solver; the headless ClothSystem is only input data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from freecad_cloth.shared.collision import CollisionSurface

PINNED_STITCH_EPSILON_MM = 1.0e-9
type Position = tuple[float, float, float]


@runtime_checkable
class PositionProvider(Protocol):
    """Expose a position-like value through a method."""

    def position(self) -> Sequence[float]:
        """Return the three-dimensional position."""
        ...


type PositionInput = Sequence[float] | PositionProvider
type StitchRecord = tuple[str, str, str, Iterable[tuple[int, int]]]


def _position_tuple(value: PositionInput) -> Position:
    """Normalize a tuple-like or provider-backed position into three floats."""
    position = value.position() if isinstance(value, PositionProvider) else value
    values = tuple(float(component) for component in position)
    if len(values) != 3:
        raise ValueError("simulation stitch positions must be three-dimensional")
    return (values[0], values[1], values[2])


def validate_pinned_stitch_pairs(
    positions: Iterable[PositionInput],
    pinned_indices: Iterable[int],
    seam_pair_records: Iterable[StitchRecord] = (),
    *,
    epsilon: float = PINNED_STITCH_EPSILON_MM,
) -> None:
    """Reject impossible non-zero stitches between already pinned particles."""
    normalized_positions = tuple(_position_tuple(value) for value in positions)
    pinned = frozenset(int(index) for index in pinned_indices)
    if epsilon < 0.0:
        raise ValueError("stitch validation epsilon must be non-negative")
    candidates = ((record[0], pair) for record in tuple(seam_pair_records) for pair in record[3])
    seen: set[tuple[int, int]] = set()
    for seam_id, pair in candidates:
        a, b = int(pair[0]), int(pair[1])
        if a < 0 or b < 0 or a >= len(normalized_positions) or b >= len(normalized_positions):
            raise ValueError(
                "stitch pair is outside the simulation particle set: "
                f"seam={seam_id} particle_a={a} particle_b={b}"
            )
        pair_key = (a, b)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        if a not in pinned or b not in pinned:
            continue
        pa, pb = normalized_positions[a], normalized_positions[b]
        separation = sum((pa[index] - pb[index]) ** 2 for index in range(3)) ** 0.5
        if separation > epsilon:
            raise ValueError(
                "impossible pinned-pinned sewing constraint: "
                f"seam={seam_id} particle_a={a} particle_b={b} "
                f"initial_separation={separation:.9f} mm"
            )


class ClothSimulationBackend(ABC):
    """Runtime contract implemented by the production solver backend."""

    name = "abstract"

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the collision surface registered with the backend."""
        return None

    @abstractmethod
    def step(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 8,
        gravity: Position = (0.0, 0.0, -9810.0),
        surface: CollisionSurface | None = None,
    ) -> None:
        """Advance the simulation by one time step."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Reset solver state to its last constructed input."""
        raise NotImplementedError

    @abstractmethod
    def pin(self, indices: Iterable[int]) -> None:
        """Replace the set of pinned particle indices."""
        raise NotImplementedError

    @abstractmethod
    def set_stitches(
        self,
        pairs: Iterable[tuple[int, int]],
        compliance: float = 0.0,
    ) -> None:
        """Replace the sewing constraints."""
        raise NotImplementedError

    @abstractmethod
    def positions(self) -> tuple[Position, ...]:
        """Return current particle positions in FreeCAD millimetres."""
        raise NotImplementedError

    @abstractmethod
    def finite(self) -> bool:
        """Report whether all solver positions are within the accepted finite bound."""
        raise NotImplementedError

    @property
    @abstractmethod
    def time(self) -> float:
        """Return elapsed simulation time in seconds."""
        raise NotImplementedError
