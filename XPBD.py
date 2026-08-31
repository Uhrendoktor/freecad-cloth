"""PositionBasedDynamics-backed cloth simulation adapter."""
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, List, Sequence, Tuple

from PatternMesh import TriangleMesh
from SewingConstraints import Stitch
from SimulationBackend import ClothState, Vec3

try:
    import pypbd
except ImportError as exc:  # pragma: no cover
    pypbd = None
    _PYPBD_IMPORT_ERROR = exc
else:
    _PYPBD_IMPORT_ERROR = None


@dataclass(frozen=True)
class DistanceConstraint:
    a: int
    b: int
    rest_length: float
    compliance: float = 0.0

    @property
    def rest(self) -> float:
        return self.rest_length


@dataclass(frozen=True)
class ShearConstraint(DistanceConstraint):
    pass


@dataclass(frozen=True)
class BendingConstraint:
    a: int
    b: int
    c: int
    d: int
    compliance: float = 0.0


@dataclass(frozen=True)
class SphereCollider:
    center: Vec3
    radius: float
    thickness: float = 0.0

    def validate(self) -> None:
        if self.radius <= 0 or self.thickness < 0:
            raise ValueError("sphere radius must be positive and thickness non-negative")


@dataclass(frozen=True)
class CapsuleCollider:
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
    _validate_compliance(compliance)
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


def shear_constraints(mesh: TriangleMesh, compliance: float = 0.0) -> Tuple[ShearConstraint, ...]:
    _validate_compliance(compliance)
    edge_faces = {}
    for face in mesh.triangles:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(face)
    result = []
    seen = set()
    for edge, faces in edge_faces.items():
        if len(faces) != 2:
            continue
        opposite = [next(v for v in face if v not in edge) for face in faces]
        pair = (min(opposite), max(opposite))
        if pair in seen:
            continue
        seen.add(pair)
        result.append(ShearConstraint(pair[0], pair[1], _distance(mesh.vertices[pair[0]], mesh.vertices[pair[1]]), compliance))
    return tuple(result)


def bending_constraints(mesh: TriangleMesh, compliance: float = 0.0) -> Tuple[BendingConstraint, ...]:
    _validate_compliance(compliance)
    edge_faces = {}
    for face in mesh.triangles:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(face)
    result = []
    for edge, faces in edge_faces.items():
        if len(faces) != 2:
            continue
        c = next(v for v in faces[0] if v not in edge)
        d = next(v for v in faces[1] if v not in edge)
        result.append(BendingConstraint(edge[0], edge[1], c, d, compliance))
    return tuple(result)


def stitches_to_constraints(stitches: Iterable[Stitch], positions: Sequence[Vec3], compliance: float = 0.0) -> Tuple[DistanceConstraint, ...]:
    _validate_compliance(compliance)
    return tuple(DistanceConstraint(s.vertex_a, s.vertex_b, s.rest_length, compliance) for s in stitches)


def _require_pypbd():
    if pypbd is None:
        raise RuntimeError("pyPBD==2.2.2 is required for cloth simulation") from _PYPBD_IMPORT_ERROR
    return pypbd


def _stiffness(compliance: float) -> float:
    _validate_compliance(compliance)
    return 1.0e9 if compliance == 0.0 else 1.0 / compliance


def _validate_compliance(compliance: float) -> None:
    if compliance < 0:
        raise ValueError("compliance must be non-negative")


class XPBDClothSolver:
    """Thin state adapter around InteractiveComputerGraphics/PositionBasedDynamics."""

    backend_name = "PositionBasedDynamics/pyPBD"

    def __init__(self, constraints=(), gravity=(0.0, 0.0, -9810.0), iterations=8, pinned=(), colliders=(), shear=(), bending=(), self_collision_radius=0.0):
        if iterations < 1:
            raise ValueError("iterations must be positive")
        if colliders:
            raise NotImplementedError("primitive colliders are not yet wired to pyPBD; use the PBD mesh collision scene")
        if self_collision_radius:
            raise NotImplementedError("particle-only self collision is not a pyPBD model; provide the cloth triangle mesh to the PBD collision scene")
        self.constraints = tuple(constraints)
        self.shear = tuple(shear)
        self.bending = tuple(bending)
        self.gravity = tuple(gravity)
        self.iterations = int(iterations)
        self.pinned = frozenset(int(i) for i in pinned)
        self.colliders = tuple(colliders)
        self.self_collision_radius = float(self_collision_radius)
        self._simulation = None
        self._model = None
        self._particle_count = None
        self._signature = None

    def _build(self, state: ClothState) -> None:
        pbd = _require_pypbd()
        if not pbd.TimeManager.hasCurrent():
            pbd.TimeManager.setCurrent(pbd.TimeManager())
        if not pbd.Simulation.hasCurrent():
            pbd.Simulation.setCurrent(pbd.Simulation())
        simulation = pbd.Simulation.getCurrent()
        simulation.initDefault()
        model = simulation.getModel()
        particles = model.getParticles()
        for index, position in enumerate(state.positions):
            particles.addVertex(list(position))
            inv_mass = state.inverse_masses[index]
            particles.setMass(index, 0.0 if index in self.pinned or inv_mass == 0.0 else 1.0 / inv_mass)
            particles.setAcceleration(index, list(self.gravity))
        for constraint in self.constraints:
            model.addDistanceConstraint_XPBD(constraint.a, constraint.b, _stiffness(constraint.compliance))
        for constraint in self.shear:
            model.addDistanceConstraint_XPBD(constraint.a, constraint.b, _stiffness(constraint.compliance))
        for constraint in self.bending:
            model.addIsometricBendingConstraint_XPBD(constraint.a, constraint.b, constraint.c, constraint.d, _stiffness(constraint.compliance))
        model.initConstraintGroups()
        timestep = simulation.getTimeStep()
        timestep.setValueUInt(pbd.TimeStepController.NUM_SUB_STEPS, 1)
        timestep.setValueUInt(pbd.TimeStepController.MAX_ITERATIONS, self.iterations)
        self._simulation = simulation
        self._model = model
        self._particle_count = len(state.positions)
        self._signature = self._constraint_signature()

    def _constraint_signature(self):
        return (
            tuple((c.a, c.b, c.compliance) for c in self.constraints),
            tuple((c.a, c.b, c.compliance) for c in self.shear),
            tuple((c.a, c.b, c.c, c.d, c.compliance) for c in self.bending),
            tuple(sorted(self.pinned)),
        )

    def step(self, state: ClothState, dt: float) -> ClothState:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        if not state.positions or dt == 0.0:
            return state
        pbd = _require_pypbd()
        if self._model is None or self._particle_count != len(state.positions) or self._signature != self._constraint_signature():
            self._build(state)
        particles = self._model.getParticles()
        pbd.TimeManager.getCurrent().setTimeStepSize(float(dt))
        for index, position in enumerate(state.positions):
            particles.setPosition(index, list(position))
            particles.setVelocity(index, list(state.velocities[index]))
            particles.setAcceleration(index, list(self.gravity))
            if index in self.pinned or state.inverse_masses[index] == 0.0:
                particles.setMass(index, 0.0)
            else:
                particles.setMass(index, 1.0 / state.inverse_masses[index])
        self._simulation.getTimeStep().step(self._model)
        state.positions = [tuple(particles.getPosition(i)) for i in range(len(state.positions))]
        state.velocities = [tuple(particles.getVelocity(i)) for i in range(len(state.positions))]
        return state


def _distance(a, b):
    dims = min(len(a), len(b))
    return sqrt(sum((a[i] - b[i]) ** 2 for i in range(dims)))
