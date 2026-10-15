"""Production PositionBasedDynamics XPBD backend.

This adapter translates the headless FreeCAD cloth model and persistent
DrapeTarget collision surface into the native pyPBD runtime.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Protocol, TypeAlias, cast

import numpy as np
import numpy.typing as npt

from freecad_cloth.common.ValidationModels import (
    CollisionSurfaceInput,
    MeshArrays,
    ParticleIndexInput,
    ParticlePairInput,
    PBDCollisionConfig,
    PBDStepInput,
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
    def setPosition(self, index: int, position: FloatArray) -> None: ...
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
        raise NotImplementedError


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
    def addFace(self, _face: Sequence[int]) -> None: ...
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


def _pbd_collision_config(environ: Mapping[str, str] | None = None) -> PBDCollisionConfig:
    """Parse and validate all numeric PBD environment settings together."""
    settings = os.environ if environ is None else environ
    return PBDCollisionConfig.model_validate(
        {
            "substeps": int(settings.get("CLOTH_PBD_SUBSTEPS", str(_PBD_SUBSTEPS_DEFAULT))),
            "collision_tolerance_mm": float(
                settings.get(
                    "CLOTH_PBD_COLLISION_TOLERANCE_MM",
                    str(_PBD_COLLISION_TOLERANCE_DEFAULT_MM),
                )
            ),
            "collision_voxel_mm": float(settings.get("CLOTH_PBD_COLLISION_VOXEL_MM", "12.0")),
        }
    )


def _pbd_substeps(environ: Mapping[str, str] | None = None) -> int:
    """Return validated solver substep count from runtime configuration."""
    return _pbd_collision_config(environ).substeps


def _pbd_collision_tolerance_mm(environ: Mapping[str, str] | None = None) -> float:
    """Return finite non-negative collision tolerance in millimetres."""
    return _pbd_collision_config(environ).collision_tolerance_mm


def _pbd_collision_voxel_mm(environ: Mapping[str, str] | None = None) -> float:
    """Return finite collision voxel dimension in millimetres."""
    return _pbd_collision_config(environ).collision_voxel_mm


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
    """Hash binary mesh arrays without allocating their large textual representations."""
    digest = hashlib.sha256()
    digest.update(b"cloth-pbd-collision-sdf-key-v2\0")

    vertices = np.ascontiguousarray(surface.vertices, dtype=np.dtype("<f8"))
    triangles = np.ascontiguousarray(surface.triangles, dtype=np.dtype("<i8")).reshape((-1, 3))
    voxel_resolution = np.ascontiguousarray(resolution, dtype=np.dtype("<i8"))
    thickness = np.asarray((surface.thickness,), dtype=np.dtype("<f8"))

    digest.update(len(surface.vertices).to_bytes(8, "little"))
    digest.update(memoryview(vertices).cast("B"))
    digest.update(len(surface.triangles).to_bytes(8, "little"))
    digest.update(memoryview(triangles).cast("B"))
    digest.update(memoryview(thickness).cast("B"))
    digest.update(len(resolution).to_bytes(8, "little"))
    digest.update(memoryview(voxel_resolution).cast("B"))
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
        self._pin_indices = (
            tuple(
                dict.fromkeys(ParticleIndexInput.model_validate({"index": i}).index for i in pins)
            )
            or system_pins
        )
        self._stitches = tuple(
            (
                pair.a,
                pair.b,
            )
            for pair in (ParticlePairInput.model_validate({"a": a, "b": b}) for a, b in stitches)
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
        self._collision_sdf_resolution: tuple[int, ...] | None = None
        self._collision_voxel_mm: float | None = None
        self._collision_configured_tolerance_mm: float | None = None
        self._collision_effective_tolerance_mm: float | None = None
        self._collision_projector: object | None = None
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
        collision_voxel_mm = _pbd_collision_voxel_mm()
        configured_tolerance_mm = _pbd_collision_tolerance_mm()
        effective_tolerance_mm = _pbd_collision_effective_tolerance_mm(collision_surface)
        self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)
        self._collision_voxel_mm = collision_voxel_mm
        self._collision_configured_tolerance_mm = configured_tolerance_mm
        self._collision_effective_tolerance_mm = effective_tolerance_mm
        print(
            "cloth-pbd-collision-config "
            f"target_thickness_mm={float(collision_surface.thickness):.2f} "
            f"configured_tolerance_mm={configured_tolerance_mm:.2f} "
            f"voxel_mm={collision_voxel_mm:.2f} "
            f"effective_tolerance_mm={effective_tolerance_mm:.2f} "
            f"resolution={list(self._collision_sdf_resolution)}",
            flush=True,
        )
        # The position-level projection pass is required for high-detail avatar
        # meshes where native PBD contact resolution leaves residual penetration.
        # Simple blockers (for example the blanket's 12-triangle cube) already
        # resolve reliably through native contacts; projecting them can overcorrect
        # deeply intersecting points and create long mesh spikes.
        if self._collision_projector is None and len(collision_surface.triangles) >= 1000:
            try:
                from freecad_cloth.simulation.MeshCollisionProjector import MeshCollisionProjector

                projector_candidate_count = 2 if self._substeps <= 1 else 4
                self._collision_projector = MeshCollisionProjector(
                    collision_surface,
                    clearance_mm=effective_tolerance_mm,
                    candidate_count=projector_candidate_count,
                )
                print(
                    "cloth-pbd-position-projection ready "
                    f"clearance_mm={effective_tolerance_mm:.2f} "
                    f"candidate_triangles={min(projector_candidate_count, len(collision_surface.triangles))}",
                    flush=True,
                )
            except ValueError as exc:
                # An open or inconsistently oriented target still uses the native
                # collision path; signed position projection requires a closed mesh.
                print(f"cloth-pbd-position-projection disabled reason={exc}", flush=True)

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
        collision_detection.setTolerance(effective_tolerance_mm / _MM)

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

    def _project_collision_positions(self) -> None:
        """Resolve residual position-level mesh contacts after the native PBD pass."""
        projector = self._collision_projector
        if projector is None:
            return
        from freecad_cloth.simulation.MeshCollisionProjector import MeshCollisionProjector

        if not isinstance(projector, MeshCollisionProjector):
            return

        particles = self._model.getParticles()
        native_vertices = np.asarray(particles.getVertices(), dtype=np.float64)
        if native_vertices.size == 0:
            return
        positions_mm = native_vertices[:, (0, 2, 1)] * _MM
        corrected_mm, outward_normals = projector.project(positions_mm)
        # Stitch reconciliation also handles close pairs whose endpoints already
        # sit safely outside the shell. Do not return just because no single point
        # needed contact correction; distant stitch groups are filtered below.
        from freecad_cloth.simulation.MeshCollisionProjector import project_stitched_pairs

        corrected_mm, outward_normals = project_stitched_pairs(
            projector,
            corrected_mm,
            outward_normals,
            self._stitches,
            self._pin_indices,
        )
        moved_indices = np.flatnonzero(np.linalg.norm(corrected_mm - positions_mm, axis=1) > 1e-7)
        pinned = set(self._pin_indices)
        for raw_index in moved_indices:
            index = int(raw_index)
            if index in pinned:
                continue
            position = corrected_mm[index]
            particles.setPosition(
                index,
                np.asarray(
                    (position[0] / _MM, position[2] / _MM, position[1] / _MM),
                    dtype=np.float64,
                ),
            )
            # Velocity coordinates use the same PBD (X, Z, Y) axis permutation.
            normal = outward_normals[index]
            normal_pbd = np.asarray((normal[0], normal[2], normal[1]), dtype=np.float64)
            velocity = np.asarray(particles.getVelocity(index), dtype=np.float64)
            inward_speed = float(np.dot(velocity, normal_pbd))
            if inward_speed < 0.0:
                particles.setVelocity(index, velocity - inward_speed * normal_pbd)

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
        self._project_collision_positions()
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
            for pair in (ParticlePairInput.model_validate({"a": a, "b": b}) for a, b in pairs)
        )
        self._stitch_compliance = compliance
        self._time = 0.0
        self._build()

    def _positions_snapshot(self) -> tuple[tuple[tuple[float, float, float], ...], bool]:
        """Read native positions once and validate the same snapshot for publication."""
        vertices = np.asarray(self._model.getParticles().getVertices(), dtype=np.float64)
        if vertices.size == 0:
            return (), True
        converted = vertices[:, (0, 2, 1)] * _MM
        positions = tuple(tuple(row) for row in converted.tolist())
        finite = bool(np.isfinite(vertices).all() and np.all(np.abs(vertices) < 1e9))
        return positions, finite

    def positions_and_finite(self) -> tuple[tuple[tuple[float, float, float], ...], bool]:
        """Return display positions and the finite-state flag from one native snapshot."""
        return self._positions_snapshot()

    def positions(self) -> tuple[tuple[float, float, float], ...]:
        """Return current cloth particle positions in FreeCAD millimetres."""
        return self._positions_snapshot()[0]

    def finite(self) -> bool:
        """Return whether all solver coordinates remain finite and bounded."""
        return self._positions_snapshot()[1]
