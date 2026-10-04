"""Production PositionBasedDynamics XPBD backend.

This adapter translates the headless FreeCAD cloth model and persistent
DrapeTarget collision surface into the native pyPBD runtime.
"""

import os
from collections.abc import Iterable, Sequence
from copy import deepcopy
from math import isfinite

import numpy as np

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_PBD_SUBSTEPS_DEFAULT = 1
_PBD_ITERATIONS_DEFAULT = 8
_PBD_COLLISION_TRIANGLES_DEFAULT = 0
_PBD_COLLISION_TOLERANCE_DEFAULT_MM = 1.0
_PBD_STITCH_STIFFNESS_DEFAULT = 100000.0
_PBD_CLOTH_STIFFNESS_DEFAULT = 100000.0
_PBD_BENDING_STIFFNESS_DEFAULT = 50.0


def _pbd_substeps() -> int:
    value = int(os.environ.get("CLOTH_PBD_SUBSTEPS", str(_PBD_SUBSTEPS_DEFAULT)))
    if value < 1:
        raise ValueError("CLOTH_PBD_SUBSTEPS must be >= 1")
    return value


def _pbd_collision_triangle_limit() -> int:
    value = int(
        os.environ.get(
            "CLOTH_PBD_COLLISION_TRIANGLES",
            str(_PBD_COLLISION_TRIANGLES_DEFAULT),
        )
    )
    if value < 0:
        raise ValueError("CLOTH_PBD_COLLISION_TRIANGLES must be >= 0")
    return value


def _pbd_collision_tolerance_mm() -> float:
    value = float(
        os.environ.get(
            "CLOTH_PBD_COLLISION_TOLERANCE_MM",
            str(_PBD_COLLISION_TOLERANCE_DEFAULT_MM),
        )
    )
    if value < 0.0:
        raise ValueError("CLOTH_PBD_COLLISION_TOLERANCE_MM must be >= 0")
    return value


def _pbd_stitch_stiffness(compliance: float) -> float:
    value = float(compliance)
    if value < 0.0:
        raise ValueError("stitch compliance must be non-negative")
    if value == 0.0:
        return _PBD_STITCH_STIFFNESS_DEFAULT
    return max(1.0, min(_PBD_STITCH_STIFFNESS_DEFAULT, 1.0 / value))


def _to_pbd_position(position) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) / _MM, float(y) / _MM, float(z) / _MM)


def _from_pbd_position(position) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) * _MM, float(y) * _MM, float(z) * _MM)


class PositionBasedDynamicsBackend(ClothSimulationBackend):
    """Production backend using the native PositionBasedDynamics Python bindings."""

    name = "position-based-dynamics"

    def __init__(
        self,
        system: ClothSystem,
        triangles: Sequence[tuple[int, int, int]],
        pins: Iterable[int] = (),
        stitches: Iterable[tuple[int, int]] = (),
        collision_surface: CollisionSurface | None = None,
        collision_mode: str = "mesh",
    ):
        try:
            import pypbd
        except ImportError as exc:
            raise RuntimeError("simulation requires the 'pyPBD' package") from exc

        collision_mode = (
            str(os.environ.get("CLOTH_PBD_COLLISION_MODE", collision_mode)).strip().lower()
        )
        if collision_mode != "mesh":
            raise ValueError("PositionBasedDynamics supports only mesh collision mode")

        self._pbd = pypbd
        self._initial = deepcopy(system)
        self._triangles = tuple(tuple(int(i) for i in triangle) for triangle in triangles)
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in pins))
        self._stitches = tuple((int(a), int(b)) for a, b in stitches)
        self._stitch_compliance = 0.0
        self._source_collision_surface = collision_surface
        collision_limit = _pbd_collision_triangle_limit()
        if collision_surface is not None and collision_limit:
            collision_surface = coarsen_collision_surface(collision_surface, collision_limit)
            print(
                "cloth-pbd-collision "
                f"source_triangles={len(self._source_collision_surface.triangles)} "
                f"solver_triangles={len(collision_surface.triangles)} "
                f"limit={collision_limit}",
                flush=True,
            )

        self._collision_surface = collision_surface
        self._collision_mode = collision_mode
        self._time = 0.0
        self._substeps = _pbd_substeps()
        self._particle_count = len(self._initial.particles)
        self._build()

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the exact collision surface registered with PositionBasedDynamics."""
        return self._collision_surface

    @property
    def time(self) -> float:
        """Return elapsed simulation time in seconds."""
        return self._time

    def _new_simulation(self):
        sim = self._pbd.Simulation.getCurrent()
        model = sim.getModel()
        sim.reset()
        model.cleanup()
        sim.initDefault()
        return sim, sim.getModel()

    def _add_collision_body(self, sim, model) -> None:
        if self._collision_surface is None:
            return

        vertex_data = self._pbd.VertexData()
        for vertex in self._collision_surface.vertices:
            vertex_data.addVertex(_to_pbd_position(vertex))

        mesh = self._pbd.IndexedFaceMesh()
        faces = self._collision_surface.triangles
        mesh.initMesh(len(self._collision_surface.vertices), len(faces) * 2, len(faces))
        for triangle in faces:
            mesh.addFace([int(i) for i in triangle])
        mesh.buildNeighbors()

        rigid_body = model.addRigidBody(
            1.0,
            vertex_data,
            mesh,
            testMesh=True,
            generateCollisionObject=True,
            resolution=[30, 30, 30],
        )
        rigid_body.setMass(0.0)
        rigid_body.setFrictionCoeff(0.5)

        collision_detection = sim.getTimeStep().getCollisionDetection()
        collision_detection.setTolerance(_pbd_collision_tolerance_mm() / _MM)

    def _build(self) -> None:
        self._sim, self._model = self._new_simulation()
        points = [_to_pbd_position(p.position()) for p in self._initial.particles]
        indices = [index for triangle in self._triangles for index in triangle]
        tri_model = self._model.addTriangleModel(
            points,
            indices,
            testMesh=self._collision_surface is not None,
        )
        self._tri_model = tri_model

        particles = self._model.getParticles()
        if particles.getNumberOfParticles() != self._particle_count:
            raise RuntimeError("PositionBasedDynamics did not preserve cloth particle ordering")
        for index, particle in enumerate(self._initial.particles):
            particles.setMass(index, 0.0 if particle.inv_mass == 0.0 else 1.0)

        cloth_stiffness = float(
            os.environ.get(
                "CLOTH_PBD_CLOTH_STIFFNESS",
                str(_PBD_CLOTH_STIFFNESS_DEFAULT),
            )
        )
        bending_stiffness = float(
            os.environ.get(
                "CLOTH_PBD_BENDING_STIFFNESS",
                str(_PBD_BENDING_STIFFNESS_DEFAULT),
            )
        )
        if cloth_stiffness <= 0.0 or bending_stiffness <= 0.0:
            raise ValueError("PositionBasedDynamics cloth stiffness values must be positive")

        self._model.addClothConstraints(
            tri_model,
            4,
            cloth_stiffness,
            cloth_stiffness,
            cloth_stiffness,
            cloth_stiffness,
            0.3,
            0.3,
            False,
            False,
        )
        self._model.addBendingConstraints(tri_model, 3, bending_stiffness)

        stitch_stiffness = _pbd_stitch_stiffness(self._stitch_compliance)
        for a, b in self._stitches:
            self._model.addDistanceConstraint_XPBD(a, b, stitch_stiffness)

        self._add_collision_body(self._sim, self._model)

        time_manager = self._pbd.TimeManager.getCurrent()
        time_manager.setTime(0.0)
        time_manager.setTimeStepSize(1.0 / 60.0)
        timestep = self._sim.getTimeStep()
        timestep.setValueUInt(self._pbd.TimeStepController.NUM_SUB_STEPS, self._substeps)
        timestep.setValueUInt(
            self._pbd.TimeStepController.MAX_ITERATIONS,
            _PBD_ITERATIONS_DEFAULT,
        )

    def step(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 8,
        gravity=(0.0, 0.0, -9810.0),
        surface: CollisionSurface | None = None,
    ) -> None:
        """Advance PositionBasedDynamics by one time step."""
        if dt <= 0.0 or iterations < 1:
            raise ValueError("dt must be positive and iterations must be >= 1")
        if surface is not None and surface is not self._collision_surface:
            raise RuntimeError(
                "PositionBasedDynamics collision surface is immutable after construction"
            )

        gx, gy, gz = (float(value) for value in gravity)
        gravity_pbd = (gx / _MM, gy / _MM, gz / _MM)
        particles = self._model.getParticles()
        for index in range(self._particle_count):
            if particles.getMass(index) == 0.0:
                continue
            particles.setAcceleration(index, np.asarray(gravity_pbd, dtype=np.float64))

        self._pbd.TimeManager.getCurrent().setTimeStepSize(float(dt))
        timestep = self._sim.getTimeStep()
        timestep.setValueUInt(
            self._pbd.TimeStepController.MAX_ITERATIONS,
            int(iterations),
        )
        timestep.step(self._model)
        self._time += float(dt)

    def reset(self) -> None:
        """Rebuild PositionBasedDynamics from the original input model."""
        self._time = 0.0
        self._build()

    def pin(self, indices: Iterable[int]) -> None:
        """Replace the set of pinned particle indices and rebuild from the original input model."""
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in indices))
        self._time = 0.0
        self._build()

    def set_stitches(
        self,
        pairs: Iterable[tuple[int, int]],
        compliance: float = 0.0,
    ) -> None:
        """Replace the sewing constraints and rebuild from the original input model."""
        if compliance < 0.0:
            raise ValueError("compliance must be non-negative")
        self._stitches = tuple((int(a), int(b)) for a, b in pairs)
        self._stitch_compliance = float(compliance)
        self._time = 0.0
        self._build()

    def positions(self) -> tuple[tuple[float, float, float], ...]:
        """Return current cloth particle positions in FreeCAD millimetres."""
        particles = self._model.getParticles()
        return tuple(
            _from_pbd_position(particles.getPosition(index))
            for index in range(self._particle_count)
        )

    def finite(self) -> bool:
        """Return whether all solver coordinates remain finite and bounded."""
        return all(
            isfinite(value) and abs(value) < 1e12
            for position in self.positions()
            for value in position
        )
