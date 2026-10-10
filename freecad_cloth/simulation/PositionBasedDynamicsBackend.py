"""Production PositionBasedDynamics XPBD backend.

This adapter translates the headless FreeCAD cloth model and persistent
DrapeTarget collision surface into the native pyPBD runtime.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable, Sequence
from copy import deepcopy
from math import isfinite
from typing import Protocol, TypeAlias, cast

import numpy as np
import numpy.typing as npt

from freecad_cloth.common.ValidationModels import (
    CollisionSurfaceInput,
    MeshArrays,
    PBDCollisionConfig,
    PBDStepInput,
    ParticleIndexInput,
    ParticlePairInput,
    validate_finite_number,
)
from freecad_cloth.shared.collision import CollisionSurface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_PBD_SUBSTEPS_DEFAULT = 1
_PBD_ITERATIONS_DEFAULT = 8
_PBD_COLLISION_TOLERANCE_DEFAULT_MM = 1.0
_PBD_STITCH_STIFFNESS_DEFAULT = 100000.0
_PBD_CLOTH_STIFFNESS_DEFAULT = 100000.0
_PBD_BENDING_STIFFNESS_DEFAULT = 50.0


FloatArray: TypeAlias = npt.NDArray[np.float64]


class _NativePBDParticles(Protocol):
    def getNumberOfParticles(self) -> int: ...
    def setMass(self, index: int, _mass: float) -> None: ...
    def getMass(self, index: int) -> float: ...
    def getVelocity(self, index: int) -> Sequence[float]: ...
    def setVelocity(self, index: int, velocity: FloatArray) -> None: ...
    def getVertices(self) -> object: ...


class _NativePBDRigidBody(Protocol):
    def setMass(self, _mass: float) -> None: ...
    def setFrictionCoeff(self, _friction: float) -> None: ...


class _NativePBDCollisionDetection(Protocol):
    def cleanup(self) -> None: ...
    def setTolerance(self, _tolerance: float) -> None: ...


class _NativePBDTimeStep(Protocol):
    def getCollisionDetection(self) -> _NativePBDCollisionDetection: ...
    def setValueUInt(self, _parameter: int, _value: int) -> None: ...
    def step(self, model: _NativePBDModel) -> None: ...


class _NativePBDModel(Protocol):
    def cleanup(self) -> None: ...
    def addTriangleModel(
        self, points: Sequence[Sequence[float]], indices: Sequence[int], *, testMesh: bool
    ) -> object:
        _ = testMesh
        ...
    def getParticles(self) -> _NativePBDParticles: ...
    def addClothConstraints(self, _triangle_model: object, *_args: float | bool) -> None: ...
    def addBendingConstraints(
        self, _triangle_model: object, iterations: int, _stiffness: float
    ) -> None: ...
    def getConstraints(self) -> Sequence[object]: ...
    def addDistanceConstraint_XPBD(self, a: int, b: int, _stiffness: float) -> bool: ...
    def addRigidBody(
        self,
        _mass: float,
        vertex_data: object,
        mesh: object,
        *,
        testMesh: bool,
        sdf: object,
    ) -> _NativePBDRigidBody:
        _ = testMesh, sdf
        ...


class _NativePBDSimulation(Protocol):
    def getModel(self) -> _NativePBDModel: ...
    def reset(self) -> None: ...
    def initDefault(self) -> None: ...
    def getTimeStep(self) -> _NativePBDTimeStep: ...


class _NativePBDClock(Protocol):
    def setTime(self, _time: float) -> None: ...
    def setTimeStepSize(self, _step: float) -> None: ...


class _NativePBDSimulationRegistry(Protocol):
    @staticmethod
    def getCurrent() -> _NativePBDSimulation: ...


class _NativePBDClockRegistry(Protocol):
    @staticmethod
    def getCurrent() -> _NativePBDClock: ...


class _NativePBDVertexData(Protocol):
    def addVertex(self, vertex: tuple[float, float, float]) -> None: ...


class _NativePBDIndexedFaceMesh(Protocol):
    def initMesh(self, _vertex_count: int, _edge_count: int, _face_count: int) -> None: ...
    def addFace(self, face: Sequence[int]) -> None: ...
    def buildNeighbors(self) -> None: ...


class _NativePBDSDFFactory(Protocol):
    @staticmethod
    def generateSDF(
        _vertex_data: _NativePBDVertexData,
        _mesh: _NativePBDIndexedFaceMesh,
        _resolution: Sequence[int],
    ) -> object | None: ...


class _NativePBDStitchConstraint(Protocol):
    restLength: float


class _NativePBDStepConstants(Protocol):
    NUM_SUB_STEPS: int
    MAX_ITERATIONS: int
    MAX_ITERATIONS_V: int


class _NativePBDAPI(Protocol):
    Simulation: _NativePBDSimulationRegistry
    TimeManager: _NativePBDClockRegistry
    VertexData: Callable[[], _NativePBDVertexData]
    IndexedFaceMesh: Callable[[], _NativePBDIndexedFaceMesh]
    CubicSDFCollisionDetection: _NativePBDSDFFactory
    DistanceConstraint_XPBD: type[_NativePBDStitchConstraint]
    TimeStepController: _NativePBDStepConstants


def _pbd_collision_config() -> PBDCollisionConfig:
    """Parse and validate all numeric PBD environment settings together."""
    return PBDCollisionConfig.model_validate(
        {
            "substeps": int(os.environ.get("CLOTH_PBD_SUBSTEPS", str(_PBD_SUBSTEPS_DEFAULT))),
            "collision_tolerance_mm": float(
                os.environ.get(
                    "CLOTH_PBD_COLLISION_TOLERANCE_MM",
                    str(_PBD_COLLISION_TOLERANCE_DEFAULT_MM),
                )
            ),
            "collision_voxel_mm": float(os.environ.get("CLOTH_PBD_COLLISION_VOXEL_MM", "12.0")),
        }
    )


def _pbd_substeps() -> int:
    """Return validated solver substep count from runtime configuration."""
    return _pbd_collision_config().substeps


def _pbd_collision_tolerance_mm() -> float:
    """Return finite non-negative collision tolerance in millimetres."""
    return _pbd_collision_config().collision_tolerance_mm


def _pbd_collision_voxel_mm() -> float:
    """Return finite collision voxel dimension in millimetres."""
    return _pbd_collision_config().collision_voxel_mm


def _pbd_collision_effective_tolerance_mm(
    surface: CollisionSurface,
) -> float:
    configured = _pbd_collision_tolerance_mm()
    thickness = float(getattr(surface, "thickness", 0.0))
    representation_margin = 0.5 * _pbd_collision_voxel_mm()
    return max(configured, thickness, representation_margin)


def _pbd_collision_resolution(surface: CollisionSurface) -> list[int]:
    voxel_mm = _pbd_collision_voxel_mm()
    spans = []
    for axis in range(3):
        values = [float(vertex[axis]) for vertex in surface.vertices]
        if not values:
            spans.append(16)
            continue
        span_mm = max(values) - min(values)
        cells = int(np.ceil((span_mm + 200.0) / voxel_mm))
        spans.append(max(16, min(256, cells)))
    return spans


def _pbd_stitch_stiffness(compliance: float) -> float:
    value = validate_finite_number(compliance)
    if value < 0.0:
        raise ValueError("stitch compliance must be finite and non-negative")
    if value == 0.0:
        return _PBD_STITCH_STIFFNESS_DEFAULT
    return max(1.0, min(_PBD_STITCH_STIFFNESS_DEFAULT, 1.0 / value))


def _to_pbd_position(position: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _from_pbd_position(position: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = position
    return (float(x) * _MM, float(z) * _MM, float(y) * _MM)


_PBD_COLLISION_SDF_CACHE_KEY: bytes | None = None
_PBD_COLLISION_SDF_CACHE: object | None = None


def _pbd_collision_sdf_cache_key(surface: CollisionSurface, resolution: list[int]) -> bytes:
    """Hash canonical numeric buffers without constructing huge tuple repr strings."""
    digest = hashlib.sha256()
    vertices = np.asarray(surface.vertices, dtype="<f8")
    triangles = np.asarray(surface.triangles, dtype="<i8")
    resolution_data = np.asarray(tuple(int(value) for value in resolution), dtype="<i8")
    digest.update(b"vertices-f64le\0")
    digest.update(np.asarray(vertices.shape, dtype="<u8").tobytes())
    digest.update(vertices.tobytes(order="C"))
    digest.update(b"triangles-i64le\0")
    digest.update(np.asarray(triangles.shape, dtype="<u8").tobytes())
    digest.update(triangles.tobytes(order="C"))
    digest.update(b"thickness-f64le\0")
    digest.update(np.asarray((float(surface.thickness),), dtype="<f8").tobytes())
    digest.update(b"resolution-i64le\0")
    digest.update(resolution_data.tobytes(order="C"))
    return digest.digest()


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
    ) -> None:
        try:
            import pypbd
        except ImportError as exc:
            raise RuntimeError("simulation requires the 'pyPBD' package") from exc

        collision_mode = (
            str(os.environ.get("CLOTH_PBD_COLLISION_MODE", collision_mode)).strip().lower()
        )
        if collision_mode != "mesh":
            raise ValueError("PositionBasedDynamics supports only mesh collision mode")

        self._pbd = cast(_NativePBDAPI, pypbd)
        self._initial = deepcopy(system)
        validated_mesh = MeshArrays.model_validate(
            {
                "vertices": [particle.position() for particle in system.particles],
                "triangles": triangles,
            }
        )
        self._triangles = validated_mesh.triangles
        system_pins = tuple(
            i for i, particle in enumerate(system.particles) if particle.inv_mass == 0.0
        )
        self._pin_indices = tuple(
            dict.fromkeys(ParticleIndexInput.model_validate({"index": i}).index for i in pins)
        ) or system_pins
        self._stitches = tuple(
            (
                pair.a,
                pair.b,
            )
            for pair in (
                ParticlePairInput.model_validate({"a": a, "b": b}) for a, b in stitches
            )
        )
        self._stitch_compliance = 0.0
        if collision_surface is not None:
            CollisionSurfaceInput.model_validate(
                {
                    "vertices": collision_surface.vertices,
                    "triangles": collision_surface.triangles,
                    "region": collision_surface.region,
                    "thickness": collision_surface.thickness,
                }
            )
        self._source_collision_surface = collision_surface
        self._collision_surface = collision_surface
        if collision_surface is not None:
            print(
                "cloth-pbd-collision-mesh "
                f"source_triangles={len(collision_surface.triangles)} solver_triangles={len(collision_surface.triangles)}",
                flush=True,
            )
        self._collision_mode = collision_mode
        self._collision_sdf: object | None = None
        self._time = 0.0
        self._substeps = _pbd_substeps()
        self._particle_count = len(self._initial.particles)
        self._simulation_initialized = False
        self._build()

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the exact collision surface registered with PositionBasedDynamics."""
        return self._collision_surface

    @property
    def time(self) -> float:
        """Return elapsed simulation time in seconds."""
        return self._time

    def _new_simulation(self) -> tuple[_NativePBDSimulation, _NativePBDModel]:
        sim = self._pbd.Simulation.getCurrent()
        if self._simulation_initialized:
            model = sim.getModel()
            sim.reset()
            model.cleanup()
            sim.getTimeStep().getCollisionDetection().cleanup()
        sim.initDefault()
        self._simulation_initialized = True
        return sim, sim.getModel()

    def _add_collision_body(self, sim: _NativePBDSimulation, model: _NativePBDModel) -> None:
        collision_surface = self._collision_surface
        if self._source_collision_surface is None or collision_surface is None:
            return
        vertex_data = self._pbd.VertexData()
        for vertex in collision_surface.vertices:
            vertex_data.addVertex(_to_pbd_position(vertex))

        mesh = self._pbd.IndexedFaceMesh()
        faces = collision_surface.triangles
        mesh.initMesh(len(collision_surface.vertices), len(faces) * 2, len(faces))
        for triangle in faces:
            a, b, c = (int(i) for i in triangle)
            mesh.addFace([a, c, b])
        mesh.buildNeighbors()

        resolution = _pbd_collision_resolution(collision_surface)
        cache_key = _pbd_collision_sdf_cache_key(collision_surface, resolution)
        global _PBD_COLLISION_SDF_CACHE_KEY, _PBD_COLLISION_SDF_CACHE
        if self._collision_sdf is None and cache_key == _PBD_COLLISION_SDF_CACHE_KEY:
            self._collision_sdf = _PBD_COLLISION_SDF_CACHE
            print(
                "cloth-pbd-collision-sdf cache-hit "
                f"source_triangles={len(faces)} resolution={resolution}",
                flush=True,
            )
        elif self._collision_sdf is None:
            print(
                "cloth-pbd-collision-sdf build "
                f"source_triangles={len(faces)} resolution={resolution}",
                flush=True,
            )
            self._collision_sdf = self._pbd.CubicSDFCollisionDetection.generateSDF(
                vertex_data,
                mesh,
                resolution,
            )
            if self._collision_sdf is None:
                raise RuntimeError("PositionBasedDynamics failed to generate collision SDF")
            _PBD_COLLISION_SDF_CACHE_KEY = cache_key
            _PBD_COLLISION_SDF_CACHE = self._collision_sdf
        else:
            print(
                "cloth-pbd-collision-sdf reuse "
                f"source_triangles={len(faces)} resolution={resolution}",
                flush=True,
            )

        if self._collision_sdf is None:
            raise RuntimeError("PositionBasedDynamics collision SDF is unavailable")
        rigid_body = model.addRigidBody(
            1.0,
            vertex_data,
            mesh,
            testMesh=True,
            sdf=self._collision_sdf,
        )
        rigid_body.setMass(0.0)
        rigid_body.setFrictionCoeff(0.5)

        collision_detection = sim.getTimeStep().getCollisionDetection()
        collision_detection.setTolerance(
            _pbd_collision_effective_tolerance_mm(collision_surface) / _MM
        )

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
        pin_indices = set(self._pin_indices)
        invalid_pins = [
            index for index in pin_indices if index < 0 or index >= self._particle_count
        ]
        if invalid_pins:
            raise ValueError(f"pin index outside system: {invalid_pins!r}")
        for index in range(self._particle_count):
            particles.setMass(index, 0.0 if index in pin_indices else 1.0)

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
        constraints = self._model.getConstraints()
        for a, b in self._stitches:
            before = len(constraints)
            if not self._model.addDistanceConstraint_XPBD(a, b, stitch_stiffness):
                raise RuntimeError(f"PositionBasedDynamics rejected stitch constraint {(a, b)!r}")
            constraints = self._model.getConstraints()
            if len(constraints) != before + 1:
                raise RuntimeError("PositionBasedDynamics stitch constraint was not registered")
            stitch_constraint = constraints[-1]
            if not isinstance(stitch_constraint, self._pbd.DistanceConstraint_XPBD):
                raise RuntimeError(
                    "PositionBasedDynamics returned an unexpected stitch constraint type"
                )
            # Tissu stitches have zero rest length; PBD otherwise initializes the
            # distance constraint rest length from the endpoints' starting distance.
            stitch_constraint.restLength = 0.0

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
        timestep.setValueUInt(
            self._pbd.TimeStepController.MAX_ITERATIONS_V,
            _PBD_ITERATIONS_DEFAULT,
        )

    def step(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 8,
        gravity: Sequence[float] = (0.0, 0.0, -9810.0),
        surface: CollisionSurface | None = None,
    ) -> None:
        """Advance PositionBasedDynamics by one time step."""
        step_input = PBDStepInput.model_validate(
            {"dt": dt, "iterations": iterations, "gravity": gravity}
        )
        dt, iterations, gravity = step_input.dt, step_input.iterations, step_input.gravity
        if surface is not None and surface is not self._collision_surface:
            raise RuntimeError(
                "PositionBasedDynamics collision surface is immutable after construction"
            )

        gx, gy, gz = (float(value) for value in gravity)
        gravity_pbd = np.asarray((gx / _MM, gz / _MM, gy / _MM), dtype=np.float64)
        # PositionBasedDynamics resets particle accelerations from its global
        # Simulation gravitation parameter at the start of every timestep. The
        # Python binding does not expose the vector-parameter setter, so retain
        # the library default and apply only the difference as a velocity kick.
        default_gravity = np.asarray((0.0, -9.81, 0.0), dtype=np.float64)
        gravity_delta_velocity = (gravity_pbd - default_gravity) * float(dt)
        if np.any(gravity_delta_velocity):
            particles = self._model.getParticles()
            for index in range(self._particle_count):
                if particles.getMass(index) == 0.0:
                    continue
                velocity = np.asarray(particles.getVelocity(index), dtype=np.float64)
                particles.setVelocity(index, velocity + gravity_delta_velocity)

        self._pbd.TimeManager.getCurrent().setTimeStepSize(float(dt))
        timestep = self._sim.getTimeStep()
        timestep.setValueUInt(
            self._pbd.TimeStepController.MAX_ITERATIONS,
            int(iterations),
        )
        timestep.setValueUInt(
            self._pbd.TimeStepController.MAX_ITERATIONS_V,
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
        self._pin_indices = tuple(
            dict.fromkeys(ParticleIndexInput.model_validate({"index": i}).index for i in indices)
        )
        self._time = 0.0
        self._build()

    def set_stitches(
        self,
        pairs: Iterable[tuple[int, int]],
        compliance: float = 0.0,
    ) -> None:
        """Replace the sewing constraints and rebuild from the original input model."""
        compliance = validate_finite_number(compliance)
        if compliance < 0.0:
            raise ValueError("compliance must be finite and non-negative")
        self._stitches = tuple(
            (pair.a, pair.b)
            for pair in (
                ParticlePairInput.model_validate({"a": a, "b": b}) for a, b in pairs
            )
        )
        self._stitch_compliance = compliance
        self._time = 0.0
        self._build()

    def positions(self) -> tuple[tuple[float, float, float], ...]:
        """Return current cloth particle positions in FreeCAD millimetres."""
        particles = self._model.getParticles()
        vertices = np.asarray(particles.getVertices())
        if vertices.size == 0:
            return ()
        converted = vertices[:, (0, 2, 1)] * _MM
        return tuple(tuple(row) for row in converted.tolist())

    def finite(self) -> bool:
        """Return whether all solver coordinates remain finite and bounded."""
        vertices = np.asarray(self._model.getParticles().getVertices())
        if vertices.size == 0:
            return True
        return bool(np.isfinite(vertices).all() and np.all(np.abs(vertices) < 1e9))
