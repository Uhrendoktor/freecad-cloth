# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless model used to assemble deterministic inputs for PositionBasedDynamics.

This module deliberately contains no physics integration or collision solver.
Keeping the input model separate from the native runtime solver makes it safe
for tests and adapters while leaving one production simulation implementation.
"""

from collections.abc import Iterable
from math import dist, isfinite

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.ValidationModels import (
    DistanceConstraintInput,
    GridInput,
    ParticleIndexInput,
    ParticleInput,
    ParticlePairInput,
    validate_finite_number,
)


@pydantic_dataclass
class Particle:
    """Mutable particle input expressed in FreeCAD millimetres."""

    x: float
    y: float
    z: float
    inv_mass: float = 1.0

    def __post_init__(self) -> None:
        """Validate coordinates and inverse mass at particle construction."""
        validated = ParticleInput.model_validate(
            {"x": self.x, "y": self.y, "z": self.z, "inv_mass": self.inv_mass}
        )
        self.x, self.y, self.z, self.inv_mass = (
            validated.x,
            validated.y,
            validated.z,
            validated.inv_mass,
        )

    def position(self) -> tuple[float, float, float]:
        """Return the particle position.

        Returns:
            Particle coordinates as an ordered x, y, z tuple in millimetres.
        """
        return (self.x, self.y, self.z)


@pydantic_dataclass(frozen=True)
class DistanceConstraint:
    """Distance constraint input passed to the native solver."""

    a: int
    b: int
    rest: float
    compliance: float = 0.0

    def __post_init__(self) -> None:
        """Validate endpoint indices and physical constraint parameters."""
        validated = DistanceConstraintInput.model_validate(
            {"a": self.a, "b": self.b, "rest": self.rest, "compliance": self.compliance}
        )
        object.__setattr__(self, "a", validated.a)
        object.__setattr__(self, "b", validated.b)
        object.__setattr__(self, "rest", validated.rest)
        object.__setattr__(self, "compliance", validated.compliance)


def distance(a: Particle, b: Particle) -> float:
    """Return the finite Euclidean distance between two particles.

    Args:
        a: First particle endpoint.
        b: Second particle endpoint.

    Returns:
        Euclidean distance between particle positions in millimetres.

    Raises:
        ValueError: If the computed particle distance is not finite.
    """
    result = dist(a.position(), b.position())
    if not isfinite(result):
        msg = "particle distance must be finite"
        raise ValueError(msg)
    return result


class ClothSystem:
    """Solver-input model containing particles, structural constraints, seams and pins."""

    def __init__(
        self,
        particles: Iterable[Particle],
        constraints: Iterable[DistanceConstraint] = (),
        stitches: Iterable[DistanceConstraint] = (),
        pins: Iterable[int] = (),
    ) -> None:
        """Create the solver input with validated particles, constraints, stitches, and pins.

        Args:
            particles: Initial particle collection.
            constraints: Structural distance constraints to validate and retain.
            stitches: Optional sewing constraints between particle pairs.
            pins: Optional particle indices whose initial positions remain fixed.

        Raises:
            TypeError: If a particle or constraint entry has an unsupported type.
            ValueError: If particle indices or physical parameters are invalid.
        """
        raw_particles: list[object] = list(particles)
        self.particles: list[Particle] = []
        for particle in raw_particles:
            if not isinstance(particle, Particle):
                msg = "particles must be Particle instances"
                raise TypeError(msg)
            # Particle is mutable; revalidate at the solver-system boundary.
            ParticleInput.model_validate(
                {"x": particle.x, "y": particle.y, "z": particle.z, "inv_mass": particle.inv_mass}
            )
            self.particles.append(particle)

        raw_constraints: list[object] = list(constraints)
        self.constraints: list[DistanceConstraint] = []
        for constraint in raw_constraints:
            if not isinstance(constraint, DistanceConstraint):
                msg = "constraints must be DistanceConstraint instances"
                raise TypeError(msg)
            self._validate_constraint_indices(constraint)
            self.constraints.append(constraint)
        self.stitches: list[DistanceConstraint] = []
        self.pins: dict[int, tuple[float, float, float]] = {}
        self.add_stitches(stitches)
        self.pin(pins)

    @classmethod
    def grid(
        cls,
        width: float,
        height: float,
        nx: int = 8,
        ny: int = 5,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> "ClothSystem":
        """Build a deterministic rectangular solver-input mesh.

        Args:
            width: Mesh width in millimetres.
            height: Mesh height in millimetres.
            nx: Number of particle columns; at least two are required.
            ny: Number of particle rows; at least two are required.
            origin: Lower-left-front coordinate of the grid.

        Returns:
            A cloth system with generated particles and structural constraints.
        """
        spec = GridInput.model_validate(
            {"width": width, "height": height, "nx": nx, "ny": ny, "origin": origin}
        )
        width, height, nx, ny, (ox, oy, oz) = (
            spec.width,
            spec.height,
            spec.nx,
            spec.ny,
            spec.origin,
        )
        particles = [
            Particle(
                ox + width * i / (nx - 1),
                oy + height * j / (ny - 1),
                oz,
            )
            for j in range(ny)
            for i in range(nx)
        ]

        def index(i: int, j: int) -> int:
            """Map one grid coordinate to its row-major particle index.

            Args:
                i: Column index in the grid.
                j: Row index in the grid.

            Returns:
                Flat particle index for the supplied grid coordinate.
            """
            return j * nx + i

        constraints: list[DistanceConstraint] = []
        for j in range(ny):
            for i in range(nx):
                if i + 1 < nx:
                    a, b = index(i, j), index(i + 1, j)
                    constraints.append(
                        DistanceConstraint(a, b, distance(particles[a], particles[b]))
                    )
                if j + 1 < ny:
                    a, b = index(i, j), index(i, j + 1)
                    constraints.append(
                        DistanceConstraint(a, b, distance(particles[a], particles[b]))
                    )
                if i + 1 < nx and j + 1 < ny:
                    diagonal_a = (index(i, j), index(i + 1, j + 1))
                    diagonal_b = (index(i + 1, j), index(i, j + 1))
                    constraints.extend(
                        DistanceConstraint(a, b, distance(particles[a], particles[b]))
                        for a, b in (diagonal_a, diagonal_b)
                    )

        return cls(particles, constraints)

    def add_stitches(
        self,
        pairs: Iterable[tuple[int, int] | DistanceConstraint],
        compliance: float = 0.0,
    ) -> None:
        """Append sewing constraints, deriving zero-rest length from particle positions.

        Args:
            pairs: Endpoint-index pairs or fully specified distance constraints.
            compliance: Non-negative compliance applied to newly created constraints.

        Raises:
            ValueError: If compliance is negative, a pair is malformed, or an index is invalid.
        """
        compliance = validate_finite_number(compliance)
        if compliance < 0.0:
            msg = "compliance must be non-negative"
            raise ValueError(msg)
        for pair in pairs:
            if isinstance(pair, DistanceConstraint):
                constraint = pair
            else:
                values = tuple(pair)
                if len(values) != 2:
                    msg = "stitch pairs must contain exactly two particle indices"
                    raise ValueError(msg)
                validated = ParticlePairInput.model_validate({"a": values[0], "b": values[1]})
                constraint = DistanceConstraint(validated.a, validated.b, 0.0, compliance)
            self._validate_constraint_indices(constraint)
            self.stitches.append(constraint)

    def pin(self, indices: Iterable[int]) -> None:
        """Pin selected particles by setting their inverse mass to zero.

        Args:
            indices: Particle indices that should remain fixed during solving.

        Raises:
            ValueError: If an index is outside the particle collection.
        """
        for raw_index in indices:
            index = ParticleIndexInput.model_validate({"index": raw_index}).index
            if index >= len(self.particles):
                msg = "pin index outside system"
                raise ValueError(msg)
            self.pins[index] = self.particles[index].position()
            self.particles[index].inv_mass = 0.0

    def _validate_constraint_indices(self, constraint: DistanceConstraint) -> None:
        """Reject constraints that reference missing particles.

        Args:
            constraint: Distance constraint whose endpoints are checked.

        Raises:
            ValueError: If either endpoint index is outside the particle collection.
        """
        count = len(self.particles)
        if constraint.a >= count or constraint.b >= count:
            msg = "constraint particle index outside system"
            raise ValueError(msg)

    def finite(self) -> bool:
        """Return whether particle state and constraint parameters remain finite.

        Returns:
            True if all particle coordinates, inverse masses, rest lengths, and compliance
            values are finite and non-negative where required.
        """
        return all(
            isfinite(value) and isfinite(particle.inv_mass) and particle.inv_mass >= 0.0
            for particle in self.particles
            for value in particle.position()
        ) and all(
            isfinite(constraint.rest)
            and isfinite(constraint.compliance)
            and constraint.rest >= 0.0
            and constraint.compliance >= 0.0
            for constraint in (*self.constraints, *self.stitches)
        )
