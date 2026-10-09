"""Headless model used to assemble deterministic inputs for PositionBasedDynamics.

This module deliberately contains no physics integration or collision solver.
Keeping the input model separate from the native runtime solver makes it safe
for tests and adapters while leaving one production simulation implementation.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import dist, isfinite

from freecad_cloth.common.ValidationModels import (
    DistanceConstraintInput, GridInput, ParticleIndexInput, ParticleInput,
    ParticlePairInput, validate_finite_number,
)


@dataclass
class Particle:
    """Mutable particle input expressed in FreeCAD millimetres."""

    x: float
    y: float
    z: float
    inv_mass: float = 1.0

    def __post_init__(self) -> None:
        validated = ParticleInput.model_validate(
            {"x": self.x, "y": self.y, "z": self.z, "inv_mass": self.inv_mass}
        )
        self.x, self.y, self.z, self.inv_mass = (
            validated.x, validated.y, validated.z, validated.inv_mass
        )

    def position(self) -> tuple[float, float, float]:
        """Return the particle position."""
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class DistanceConstraint:
    """Distance constraint input passed to the native solver."""

    a: int
    b: int
    rest: float
    compliance: float = 0.0

    def __post_init__(self) -> None:
        validated = DistanceConstraintInput.model_validate(
            {"a": self.a, "b": self.b, "rest": self.rest, "compliance": self.compliance}
        )
        object.__setattr__(self, "a", validated.a)
        object.__setattr__(self, "b", validated.b)
        object.__setattr__(self, "rest", validated.rest)
        object.__setattr__(self, "compliance", validated.compliance)


def distance(a: Particle, b: Particle) -> float:
    """Return a finite Euclidean distance between two particles."""
    result = dist(a.position(), b.position())
    if not isfinite(result):
        raise ValueError("particle distance must be finite")
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
        self.particles: list[Particle] = list(particles)
        if any(not isinstance(particle, Particle) for particle in self.particles):
            raise TypeError("particles must be Particle instances")
        # Particle is mutable; revalidate when crossing into a solver system.
        for particle in self.particles:
            ParticleInput.model_validate(
                {"x": particle.x, "y": particle.y, "z": particle.z, "inv_mass": particle.inv_mass}
            )
        self.constraints: list[DistanceConstraint] = list(constraints)
        if any(not isinstance(item, DistanceConstraint) for item in self.constraints):
            raise TypeError("constraints must be DistanceConstraint instances")
        for constraint in self.constraints:
            self._validate_constraint_indices(constraint)
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
        """Build a deterministic rectangular solver-input mesh."""
        spec = GridInput.model_validate(
            {"width": width, "height": height, "nx": nx, "ny": ny, "origin": origin}
        )
        width, height, nx, ny, (ox, oy, oz) = (
            spec.width, spec.height, spec.nx, spec.ny, spec.origin
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
        """Append sewing constraints, deriving zero-rest length from particle positions."""
        compliance = validate_finite_number(compliance)
        if compliance < 0.0:
            raise ValueError("compliance must be non-negative")
        for pair in pairs:
            if isinstance(pair, DistanceConstraint):
                constraint = pair
            else:
                values = tuple(pair)
                if len(values) != 2:
                    raise ValueError("stitch pairs must contain exactly two particle indices")
                validated = ParticlePairInput.model_validate({"a": values[0], "b": values[1]})
                constraint = DistanceConstraint(validated.a, validated.b, 0.0, compliance)
            self._validate_constraint_indices(constraint)
            self.stitches.append(constraint)

    def pin(self, indices: Iterable[int]) -> None:
        """Record pinned particles and set their inverse mass to zero."""
        for raw_index in indices:
            index = ParticleIndexInput.model_validate({"index": raw_index}).index
            if index >= len(self.particles):
                raise ValueError("pin index outside system")
            self.pins[index] = self.particles[index].position()
            self.particles[index].inv_mass = 0.0

    def _validate_constraint_indices(self, constraint: DistanceConstraint) -> None:
        """Reject constraints that reference missing particles."""
        count = len(self.particles)
        if constraint.a >= count or constraint.b >= count:
            raise ValueError("constraint particle index outside system")

    def finite(self) -> bool:
        """Return whether particle state and constraint parameters remain finite."""
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
