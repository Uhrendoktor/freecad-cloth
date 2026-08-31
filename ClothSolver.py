"""Compatibility facade for the PositionBasedDynamics cloth backend.

This module intentionally contains no physics implementation. Garment/domain
code can keep using ``ClothSystem`` while actual integration and constraint
projection are delegated to ``XPBD.XPBDClothSolver`` / pyPBD.
"""
from dataclasses import dataclass
from math import sqrt

from SimulationBackend import ClothState
from XPBD import DistanceConstraint as PBDDistanceConstraint
from XPBD import XPBDClothSolver


@dataclass
class Particle:
    x: float
    y: float
    z: float
    inv_mass: float = 1.0
    px: float = 0.0
    py: float = 0.0
    pz: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    def position(self):
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class DistanceConstraint:
    a: int
    b: int
    rest: float
    compliance: float = 0.0


def distance(a, b):
    return sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


class ClothSystem:
    """Legacy garment-facing state model backed by upstream pyPBD."""

    def __init__(self, particles, constraints=(), stitches=(), pins=()):
        self.particles = list(particles)
        self.constraints = list(constraints)
        self.stitches = list(stitches)
        self.pins = {int(i): tuple(p) for i, p in pins}
        self.time = 0.0
        self._solver = None

    def __getstate__(self):
        state = dict(self.__dict__)
        state["_solver"] = None
        return state

    @classmethod
    def grid(cls, width, height, nx=8, ny=5, origin=(0.0, 0.0, 0.0)):
        if nx < 2 or ny < 2:
            raise ValueError("grid dimensions must be at least 2x2")
        ox, oy, oz = origin
        particles = []
        for j in range(ny):
            for i in range(nx):
                x = ox + width * i / (nx - 1)
                y = oy + height * j / (ny - 1)
                particles.append(Particle(x, y, oz, 1.0))
        constraints = []

        def idx(i, j):
            return j * nx + i

        for j in range(ny):
            for i in range(nx):
                if i + 1 < nx:
                    constraints.append(DistanceConstraint(idx(i, j), idx(i + 1, j), distance(particles[idx(i, j)], particles[idx(i + 1, j)])))
                if j + 1 < ny:
                    constraints.append(DistanceConstraint(idx(i, j), idx(i, j + 1), distance(particles[idx(i, j)], particles[idx(i, j + 1)])))
                if i + 1 < nx and j + 1 < ny:
                    constraints.append(DistanceConstraint(idx(i, j), idx(i + 1, j + 1), distance(particles[idx(i, j)], particles[idx(i + 1, j + 1)])))
                    constraints.append(DistanceConstraint(idx(i + 1, j), idx(i, j + 1), distance(particles[idx(i + 1, j)], particles[idx(i, j + 1)])))
        return cls(particles, constraints)

    def _make_solver(self, gravity, iterations):
        constraints = [PBDDistanceConstraint(c.a, c.b, c.rest, c.compliance) for c in self.constraints + self.stitches]
        self._solver = XPBDClothSolver(constraints=constraints, gravity=gravity, iterations=iterations, pinned=self.pins.keys())

    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        if dt <= 0 or iterations < 1:
            raise ValueError("dt and iterations must be positive")
        if sphere is not None or surface is not None:
            raise NotImplementedError("use the pyPBD mesh collision scene for collision targets")
        if self._solver is None or self._solver.iterations != int(iterations) or tuple(self._solver.gravity) != tuple(gravity):
            self._make_solver(gravity, int(iterations))
        state = ClothState(
            positions=[p.position() for p in self.particles],
            velocities=[(p.vx, p.vy, p.vz) for p in self.particles],
            inverse_masses=[p.inv_mass for p in self.particles],
        )
        self._solver.step(state, dt)
        for index, particle in enumerate(self.particles):
            particle.px, particle.py, particle.pz = particle.x, particle.y, particle.z
            particle.x, particle.y, particle.z = state.positions[index]
            particle.vx, particle.vy, particle.vz = state.velocities[index]
            if state.inverse_masses[index] == 0.0 or index in self.pins:
                particle.inv_mass = 0.0
        self.time += dt

    def add_stitches(self, pairs, compliance=0.0):
        for a, b in pairs:
            pa, pb = self.particles[a], self.particles[b]
            self.stitches.append(DistanceConstraint(a, b, distance(pa, pb), compliance))
        self._solver = None

    def pin(self, indices):
        for i in indices:
            i = int(i)
            self.pins[i] = self.particles[i].position()
            self.particles[i].inv_mass = 0.0
        self._solver = None

    def finite(self):
        return all(abs(v) < 1e12 for p in self.particles for v in p.position())
