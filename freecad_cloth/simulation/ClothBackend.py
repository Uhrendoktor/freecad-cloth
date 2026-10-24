# Copyright (C) 2026 FreeCAD Cloth contributors
"""Small adapter contract for the production PositionBasedDynamics cloth solver.

FreeCAD document code depends on this boundary instead of importing PositionBasedDynamics APIs.
PositionBasedDynamics is the only runtime solver; the headless ClothSystem is only input data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from freecad_cloth.shared.collision import CollisionSurface

PINNED_STITCH_EPSILON_MM = 1.0e-9
POSITION_COMPONENT_COUNT = 3
type Position = tuple[float, float, float]


@runtime_checkable
class PositionProvider(Protocol):
    """Expose a position-like value through a method."""

    def position(self) -> Sequence[float]:
        """Return the three-dimensional position.

        Returns:
            The position coordinates in the provider's native length units.
        """
        ...


type PositionInput = Sequence[float] | PositionProvider
type StitchRecord = tuple[str, str, str, Iterable[tuple[int, int]]]


def _position_tuple(value: PositionInput) -> Position:
    """Normalize an input position to three floating-point coordinates.

    Args:
        value: Coordinates or a provider object exposing a position method.

    Returns:
        Three floating-point coordinates in FreeCAD millimetres.

    Raises:
        ValueError: If the supplied coordinates do not contain exactly three values.
    """
    position = value.position() if isinstance(value, PositionProvider) else value
    values = tuple(float(component) for component in position)
    if len(values) != POSITION_COMPONENT_COUNT:
        msg = "simulation stitch positions must be three-dimensional"
        raise ValueError(msg)
    return (values[0], values[1], values[2])


def validate_pinned_stitch_pairs(
    positions: Iterable[PositionInput],
    pinned_indices: Iterable[int],
    seam_pair_records: Iterable[StitchRecord] = (),
    *,
    epsilon: float = PINNED_STITCH_EPSILON_MM,
) -> None:
    """Reject impossible non-zero stitches between already pinned particles.

    Args:
        positions: Initial particle positions used to measure seam-pair separation.
        pinned_indices: Particle indices that are constrained to remain stationary.
        seam_pair_records: Seam identities and particle pairs supplied to the solver.
        epsilon: Maximum accepted initial separation for pinned pairs, in millimetres.

    Raises:
        ValueError: If epsilon is negative, a pair index is invalid, or pinned particles violate
            the maximum permitted separation.
    """
    normalized_positions = tuple(_position_tuple(value) for value in positions)
    pinned = frozenset(int(index) for index in pinned_indices)
    if epsilon < 0.0:
        msg = "stitch validation epsilon must be non-negative"
        raise ValueError(msg)
    candidates = ((record[0], pair) for record in tuple(seam_pair_records) for pair in record[3])
    seen: set[tuple[int, int]] = set()
    for seam_id, pair in candidates:
        a, b = int(pair[0]), int(pair[1])
        if a < 0 or b < 0 or a >= len(normalized_positions) or b >= len(normalized_positions):
            msg = (
                "stitch pair is outside the simulation particle set: "
                f"seam={seam_id} particle_a={a} particle_b={b}"
            )
            raise ValueError(msg)
        pair_key = (a, b)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        if a not in pinned or b not in pinned:
            continue
        pa, pb = normalized_positions[a], normalized_positions[b]
        separation = sum((pa[index] - pb[index]) ** 2 for index in range(3)) ** 0.5
        if separation > epsilon:
            msg = (
                "impossible pinned-pinned sewing constraint: "
                f"seam={seam_id} particle_a={a} particle_b={b} "
                f"initial_separation={separation:.9f} mm"
            )
            raise ValueError(msg)


class ClothSimulationBackend(ABC):
    """Runtime contract implemented by the production solver backend."""

    name = "abstract"

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the collision surface registered with the backend.

        Returns:
            The registered collision surface, or None when no surface is configured.
        """
        return None

    @abstractmethod
    def step(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 8,
        gravity: Position = (0.0, 0.0, -9810.0),
        surface: CollisionSurface | None = None,
    ) -> None:
        """Advance the simulation by one time step.

        Args:
            dt: Duration of the simulation step in seconds.
            iterations: Number of solver iterations for this step.
            gravity: Gravity vector in FreeCAD millimetres per second squared.
            surface: Optional collision surface to use for this step.

        Raises:
            NotImplementedError: If a concrete backend does not implement simulation stepping.
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Reset solver state to its last constructed input.

        Raises:
            NotImplementedError: If a concrete backend does not implement solver reset.
        """
        raise NotImplementedError

    @abstractmethod
    def pin(self, indices: Iterable[int]) -> None:
        """Replace the set of pinned particle indices.

        Args:
            indices: Particle indices that the backend should hold fixed.

        Raises:
            NotImplementedError: If a concrete backend does not implement particle pinning.
        """
        raise NotImplementedError

    @abstractmethod
    def set_stitches(
        self,
        pairs: Iterable[tuple[int, int]],
        compliance: float = 0.0,
    ) -> None:
        """Replace the sewing constraints.

        Args:
            pairs: Particle-index pairs that define sewing constraints.
            compliance: Constraint compliance value used by the backend.

        Raises:
            NotImplementedError: If a concrete backend does not implement sewing constraints.
        """
        raise NotImplementedError

    @abstractmethod
    def positions(self) -> tuple[Position, ...]:
        """Return current particle positions in FreeCAD millimetres.

        Returns:
            Particle coordinates in solver order, expressed in FreeCAD millimetres.

        Raises:
            NotImplementedError: If a concrete backend cannot provide particle positions.
        """
        raise NotImplementedError

    @abstractmethod
    def finite(self) -> bool:
        """Report whether all solver positions are within the accepted finite bound.

        Returns:
            True when all solver positions satisfy the backend's finite-value contract.

        Raises:
            NotImplementedError: If a concrete backend does not implement the finite-state check.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def time(self) -> float:
        """Return elapsed simulation time in seconds.

        Returns:
            Elapsed simulation time since the backend's input state was constructed.

        Raises:
            NotImplementedError: If a concrete backend does not expose simulation time.
        """
        raise NotImplementedError
