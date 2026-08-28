"""Small, deterministic XPBD particle solver for cloth prototyping.

This is intentionally a reference backend rather than a production-quality
solver. It provides the numerical contract needed by the workbench while
leaving collision, bending and GPU implementations replaceable.
"""
from dataclasses import dataclass, field
from math import sqrt
from typing import Iterable, List, Sequence, Tuple

from PatternMesh import TriangleMesh
from SewingConstraints import Stitch
from SimulationBackend import ClothState, Vec3


@dataclass(frozen=True)
class DistanceConstraint:
    a: int
    b: int
    rest_length: float
    compliance: float = 0.0


def structural_constraints(mesh: TriangleMesh, compliance: float = 0.0) -> Tuple[DistanceConstraint, ...]:
    """Create one distance constraint for every unique mesh edge."""
    if compliance < 0:
        raise ValueError("compliance must be non-negative")
    edges = set()
    result: List[DistanceConstraint] = []
    for triangle in mesh.triangles:
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edge = (min(a, b), max(a, b))
            if edge in edges:
                continue
            edges.add(edge)
            result.append(DistanceConstraint(edge[0], edge[1], _distance(mesh.vertices[edge[0]], mesh.vertices[edge[1]]), compliance))
    return tuple(result)


def stitches_to_constraints(stitches: Iterable[Stitch], positions: Sequence[Vec3], compliance: float = 0.0) -> Tuple[DistanceConstraint, ...]:
    if compliance < 0:
        raise ValueError("compliance must be non-negative")
    return tuple(DistanceConstraint(s.vertex_a, s.vertex_b, s.rest_length, compliance) for s in stitches)


class XPBDClothSolver:
    """CPU XPBD distance-constraint solver with gravity and optional pins."""
    def __init__(self, constraints: Iterable[DistanceConstraint] = (), gravity: Vec3 = (0.0, 0.0, -9810.0), iterations: int = 8, pinned: Iterable[int] = ()):
        if iterations < 1:
            raise ValueError("iterations must be positive")
        self.constraints = tuple(constraints)
        self.gravity = gravity
        self.iterations = iterations
        self.pinned = frozenset(pinned)

    def step(self, state: ClothState, dt: float) -> ClothState:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        n = len(state.positions)
        if n == 0 or dt == 0:
            return state
        velocities = list(getattr(state, "velocities", [(0.0, 0.0, 0.0)] * n))
        if len(velocities) != n:
            raise ValueError("velocity count must match position count")
        positions = [tuple(p) for p in state.positions]
        inv_masses = list(getattr(state, "inverse_masses", [1.0] * n))
        if len(inv_masses) != n:
            raise ValueError("inverse mass count must match position count")
        for i in self.pinned:
            if i < 0 or i >= n:
                raise ValueError("pinned vertex index outside state")
            inv_masses[i] = 0.0
        previous = positions[:]
        for i, (p, v) in enumerate(zip(positions, velocities)):
            if inv_masses[i] == 0.0:
                continue
            velocities[i] = _add(v, _scale(self.gravity, dt))
            positions[i] = _add(p, _scale(velocities[i], dt))
        alpha_scale = dt * dt
        for _ in range(self.iterations):
            for constraint in self.constraints:
                _project(constraint, positions, inv_masses, alpha_scale)
        for i in range(n):
            if inv_masses[i] == 0.0:
                velocities[i] = (0.0, 0.0, 0.0)
            else:
                velocities[i] = _scale(_sub(positions[i], previous[i]), 1.0 / dt)
        state.positions = positions
        state.velocities = velocities
        return state


def _project(c: DistanceConstraint, positions, inv_masses, dt2):
    if c.a < 0 or c.b < 0 or c.a >= len(positions) or c.b >= len(positions):
        raise ValueError("constraint vertex index outside state")
    wa, wb = inv_masses[c.a], inv_masses[c.b]
    w = wa + wb
    if w == 0:
        return
    delta = _sub(positions[c.a], positions[c.b])
    length = sqrt(sum(x * x for x in delta))
    if length < 1e-12:
        return
    correction = (length - c.rest_length) / (w + c.compliance / dt2 if dt2 else w)
    direction = _scale(delta, 1.0 / length)
    positions[c.a] = _sub(positions[c.a], _scale(direction, correction * wa))
    positions[c.b] = _add(positions[c.b], _scale(direction, correction * wb))


def _distance(a, b):
    return sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))) if len(a) == 3 else sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _scale(a, scalar):
    return tuple(x * scalar for x in a)
