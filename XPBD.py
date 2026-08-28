"""Small, deterministic XPBD particle solver for cloth prototyping."""
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SphereCollider:
    """Static spherical collision proxy for early avatar/body prototypes."""
    center: Vec3
    radius: float
    thickness: float = 0.0

    def validate(self) -> None:
        if self.radius <= 0 or self.thickness < 0:
            raise ValueError("sphere radius must be positive and thickness non-negative")


@dataclass(frozen=True)
class CapsuleCollider:
    """Static capsule collision proxy defined by two segment endpoints."""
    point_a: Vec3
    point_b: Vec3
    radius: float
    thickness: float = 0.0

    def validate(self) -> None:
        if self.radius <= 0 or self.thickness < 0:
            raise ValueError("capsule radius must be positive and thickness non-negative")
        if _distance(self.point_a, self.point_b) < 1e-12:
            raise ValueError("capsule endpoints must be distinct")


def structural_constraints(mesh: TriangleMesh, compliance: float = 0.0) -> Tuple[DistanceConstraint, ...]:
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
    """CPU XPBD distance-constraint solver with gravity, pins and primitive collisions."""
    def __init__(self, constraints: Iterable[DistanceConstraint] = (), gravity: Vec3 = (0.0, 0.0, -9810.0), iterations: int = 8, pinned: Iterable[int] = (), colliders: Iterable[object] = ()):
        if iterations < 1:
            raise ValueError("iterations must be positive")
        self.constraints = tuple(constraints)
        self.gravity = gravity
        self.iterations = iterations
        self.pinned = frozenset(pinned)
        self.colliders = tuple(colliders)
        for collider in self.colliders:
            collider.validate()

    def step(self, state: ClothState, dt: float) -> ClothState:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        n = len(state.positions)
        if n == 0 or dt == 0:
            return state
        velocities = list(state.velocities)
        positions = [tuple(p) for p in state.positions]
        inv_masses = list(state.inverse_masses)
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
            for collider in self.colliders:
                if isinstance(collider, SphereCollider):
                    for i in range(n):
                        _project_sphere(i, positions, inv_masses, collider)
                elif isinstance(collider, CapsuleCollider):
                    for i in range(n):
                        _project_capsule(i, positions, inv_masses, collider)
                else:
                    raise TypeError("unsupported collider type")
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


def _project_sphere(index, positions, inv_masses, collider: SphereCollider):
    if inv_masses[index] == 0.0:
        return
    delta = _sub(positions[index], collider.center)
    distance = sqrt(sum(x * x for x in delta))
    minimum = collider.radius + collider.thickness
    if distance >= minimum:
        return
    direction = (0.0, 0.0, 1.0) if distance < 1e-12 else _scale(delta, 1.0 / distance)
    positions[index] = _add(collider.center, _scale(direction, minimum))


def _project_capsule(index, positions, inv_masses, collider: CapsuleCollider):
    if inv_masses[index] == 0.0:
        return
    closest = _closest_point_on_segment(positions[index], collider.point_a, collider.point_b)
    delta = _sub(positions[index], closest)
    distance = sqrt(sum(x * x for x in delta))
    minimum = collider.radius + collider.thickness
    if distance >= minimum:
        return
    direction = _scale(delta, 1.0 / distance) if distance >= 1e-12 else _capsule_fallback_direction(positions[index], collider)
    positions[index] = _add(closest, _scale(direction, minimum))


def _closest_point_on_segment(point, a, b):
    segment = _sub(b, a)
    denominator = sum(x * x for x in segment)
    if denominator < 1e-24:
        return a
    t = sum((point[i] - a[i]) * segment[i] for i in range(3)) / denominator
    t = max(0.0, min(1.0, t))
    return _add(a, _scale(segment, t))


def _capsule_fallback_direction(point, collider):
    # A deterministic radial direction is needed when a particle lies exactly
    # on the capsule axis. Prefer the least-aligned coordinate axis.
    axis = _sub(collider.point_b, collider.point_a)
    candidates = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    direction = min(candidates, key=lambda v: abs(sum(v[i] * axis[i] for i in range(3))))
    return direction


def _distance(a, b):
    if len(a) == 3 and len(b) == 3:
        return sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _scale(a, scalar):
    return tuple(x * scalar for x in a)
