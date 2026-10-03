"""Headless model used to assemble deterministic inputs for Tissu.

This module deliberately contains no physics integration or collision solver.
Keeping the input model separate from the native runtime solver makes it safe
for tests and adapters while leaving one production simulation implementation.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt


@dataclass
class Particle:
    """Mutable particle input expressed in FreeCAD millimetres."""

    x: float
    y: float
    z: float
    inv_mass: float = 1.0

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


def distance(a: Particle, b: Particle) -> float:
    """Return Euclidean distance between two particles."""
    return sqrt(
        (a.x - b.x) ** 2 +
        (a.y - b.y) ** 2 +
        (a.z - b.z) ** 2
    )


class ClothSystem:
    """Solver-input model containing particles, structural constraints, seams and pins."""

    def __init__(
        self,
        particles: Iterable[Particle],
        constraints: Iterable[DistanceConstraint] = (),
        stitches: Iterable[DistanceConstraint] = (),
        pins: Iterable[int] = (),
    ):
        self.particles = list(particles)
        self.constraints = list(constraints)
        self.stitches = list(stitches)
        self.pins = {}
        self.add_stitches(())
        self.pin(pins)
        if stitches:
            self.add_stitches(stitches)

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
        if width <= 0.0 or height <= 0.0:
            raise ValueError("grid dimensions must be positive")
        if nx < 2 or ny < 2:
            raise ValueError("grid resolution must be at least 2 by 2")

        ox, oy, oz = (float(value) for value in origin)
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

        constraints = []
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
        pairs: Iterable[tuple[int, int]] | Iterable[DistanceConstraint],
        compliance: float = 0.0,
    ) -> None:
        """Append sewing constraints, deriving zero-rest length from particle positions."""
        if compliance < 0.0:
            raise ValueError("compliance must be non-negative")
        for pair in pairs:
            if isinstance(pair, DistanceConstraint):
                constraint = pair
            else:
                a, b = (int(pair[0]), int(pair[1]))
                if a < 0 or b < 0 or a >= len(self.particles) or b >= len(self.particles):
                    raise ValueError("stitch particle index outside system")
                constraint = DistanceConstraint(a, b, 0.0, compliance)
            self.stitches.append(constraint)

    def pin(self, indices: Iterable[int]) -> None:
        """Record pinned particles and set their inverse mass to zero."""
        for index in indices:
            index = int(index)
            if index < 0 or index >= len(self.particles):
                raise ValueError("pin index outside system")
            self.pins[index] = self.particles[index].position()
            self.particles[index].inv_mass = 0.0

    def finite(self) -> bool:
        """Return whether all input particle coordinates are finite."""
        return all(
            isfinite(value)
            for particle in self.particles
            for value in particle.position()
        )
