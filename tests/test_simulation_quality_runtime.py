# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for simulation-quality presets and preview-runtime state."""

from collections.abc import Callable
from math import isclose
from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar, cast

from freecad_cloth.simulation.SimulationQuality import FabricMaterial, preset
from freecad_cloth.simulation.SimulationQualityRuntime import (
    QUALITY_NAMES,
    QualitySimulationProxy,
    apply_quality_preset,
    quality_discretization,
)
from tests.support.assertions import require

if TYPE_CHECKING:
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

_EXPECTED_QUALITY_NAMES = ("Fast", "Balanced", "Final")
_DISCRETIZATION_RESOLUTION = 4
_DISCRETIZATION_WIDTH_MM = 400.0
_FINAL_PRESET = "Final"
_FINAL_PARTICLE_DISTANCE_MM = 2.0
_FINAL_SOLVER_ITERATIONS = 16
_FINAL_SOLVER_SUBSTEPS = 2
_DEFAULT_DENSITY_G_M2 = 150.0
_DEFAULT_THICKNESS_MM = 0.5
_DEFAULT_FRICTION = 0.5
_EXPECTED_PREVIEW_STEPS = 1
_COLLISION_SENTINEL = "collision"
_SEAM_PROVENANCE = {"seam-2": ((2, 3), (4, 5))}


def _private_callable(target: object, name: str) -> Callable[..., object]:
    """Return one named callable used by the focused runtime contract tests.

    Args:
        target: Runtime object exposing the operation to inspect.
        name: Name of the private method required by this test.

    Returns:
        The named callable, typed as an opaque callable at the test boundary.

    Raises:
        TypeError: If the named attribute does not resolve to a callable.
    """
    attribute = getattr(target, name)
    if not callable(attribute):
        msg = f"Expected {name!r} to reference a callable."
        raise TypeError(msg)
    return cast("Callable[..., object]", attribute)


def test_quality_names_and_discretization_are_materially_distinct() -> None:
    """Keep named quality levels distinct and ordered by mesh discretization."""
    require(
        condition=QUALITY_NAMES == _EXPECTED_QUALITY_NAMES,
        message="Quality names must remain Fast, Balanced, and Final in order.",
    )
    counts = [
        quality_discretization(
            _DISCRETIZATION_RESOLUTION,
            _DISCRETIZATION_WIDTH_MM,
            preset(name).particle_distance,
        )
        for name in QUALITY_NAMES
    ]
    require(
        condition=counts[0] < counts[1] < counts[2],
        message="Higher quality presets must increase mesh discretization.",
    )


def test_quality_preset_updates_solver_controls() -> None:
    """Verify the Final preset updates particle distance and solver budgets."""
    scene = SimpleNamespace(
        QualityPreset="Balanced",
        ParticleDistance=4.0,
        PinMode="Automatic",
        SolverIterations=8,
        SolverSubsteps=1,
        FabricDensity=150.0,
        FabricThickness=0.5,
        FabricStretch=0.02,
        FabricShear=0.02,
        FabricBend=0.01,
        FabricFriction=0.5,
        FabricColor=(0.72, 0.34, 0.46),
        FabricSpecular=0.25,
        FabricRoughness=0.65,
        FabricTransparency=0,
        AvatarSkinOffset=0.0,
    )

    quality = apply_quality_preset(scene, _FINAL_PRESET)

    require(
        condition=quality == preset(_FINAL_PRESET),
        message="The returned quality object must match the selected preset.",
    )
    require(
        condition=scene.QualityPreset == _FINAL_PRESET,
        message="The scene must retain the selected quality preset.",
    )
    require(
        condition=isclose(
            float(scene.ParticleDistance),
            _FINAL_PARTICLE_DISTANCE_MM,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="The Final preset must set the canonical particle distance.",
    )
    require(
        condition=scene.SolverIterations == _FINAL_SOLVER_ITERATIONS,
        message="The Final preset must set the canonical solver iteration count.",
    )
    require(
        condition=scene.SolverSubsteps == _FINAL_SOLVER_SUBSTEPS,
        message="The Final preset must set the canonical solver substep count.",
    )


def test_material_defaults_are_document_metadata() -> None:
    """Preserve the material defaults presented as document metadata."""
    material = FabricMaterial()
    require(
        condition=material.validate() is material,
        message="Valid material metadata must preserve the validated instance.",
    )
    require(
        condition=isclose(
            material.density_g_m2,
            _DEFAULT_DENSITY_G_M2,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="Material density must retain its documented default.",
    )
    require(
        condition=isclose(
            material.thickness_mm,
            _DEFAULT_THICKNESS_MM,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="Material thickness must retain its documented default.",
    )
    require(
        condition=isclose(
            material.friction,
            _DEFAULT_FRICTION,
            rel_tol=0.0,
            abs_tol=0.0,
        ),
        message="Material friction must retain its documented default.",
    )


def test_advance_preview_frame_advances_backend_once_without_document_recompute() -> None:
    """Advance exactly one preview step and publish the resulting proxy state once."""

    class Backend:
        """Record preview backend calls without advancing a native simulation."""

        name: ClassVar[str] = "position-based-dynamics"
        time: ClassVar[float] = 0.25

        def __init__(self) -> None:
            """Initialize the call log and publication-read count."""
            self.calls: list[tuple[float, int, tuple[float, float, float], object]] = []
            self.position_reads = 0

        def step(
            self,
            dt: float,
            iterations: int,
            gravity: tuple[float, float, float],
            surface: object,
        ) -> None:
            """Record a step request without running solver work.

            Args:
                dt: Requested simulation time increment.
                iterations: Requested solver iteration count.
                gravity: Requested acceleration vector.
                surface: Collision surface passed from the scene.
            """
            self.calls.append((dt, iterations, gravity, surface))

        def positions(self) -> tuple[tuple[float, float, float], ...]:
            """Return no vertices while recording the publication read.

            Returns:
                An empty position sequence because the scene has no display panels.
            """
            self.position_reads += 1
            return ()

        @staticmethod
        def finite() -> bool:
            """Report finite state because this test double has no solver state.

            Returns:
                True because the fake backend contains no non-finite particle values.
            """
            return True

    scene = SimpleNamespace(
        QualityPreset="Fast",
        PinMode="Automatic",
        ParticleDistance=40.0,
        SolverIterations=1,
        SolverSubsteps=1,
        FabricDensity=150.0,
        FabricThickness=0.5,
        FabricStretch=0.02,
        FabricShear=0.02,
        FabricBend=0.01,
        FabricFriction=0.5,
        FabricColor=(0.72, 0.34, 0.46),
        FabricSpecular=0.25,
        FabricRoughness=0.65,
        FabricTransparency=0,
        AvatarSkinOffset=0.0,
        TimeStep=1.0 / 60.0,
        GravityX=0.0,
        GravityY=0.0,
        GravityZ=-9810.0,
        DrapePanels=(),
    )
    proxy = QualitySimulationProxy()
    base = cast("SimulationProxy", _private_callable(proxy, "_base_or_restore")())
    backend = Backend()
    base.backend = cast("PositionBasedDynamicsBackend", backend)
    base.collision_surface = _COLLISION_SENTINEL
    base.last_steps = 0
    proxy.advance_preview_frame(scene)

    require(
        condition=backend.calls
        == [
            (
                scene.TimeStep,
                scene.SolverIterations,
                (scene.GravityX, scene.GravityY, scene.GravityZ),
                _COLLISION_SENTINEL,
            )
        ],
        message="A preview frame must advance the backend once with the authoritative surface.",
    )
    require(
        condition=backend.position_reads == 1,
        message="A preview frame must publish the solved state exactly once.",
    )
    require(
        condition=base.last_steps == _EXPECTED_PREVIEW_STEPS,
        message="A preview frame must advance the recorded step count by one.",
    )


def test_quality_proxy_keeps_solver_stitch_provenance() -> None:
    """Preserve seam stitch provenance when the quality proxy delegates to its base."""
    proxy = QualitySimulationProxy()
    base = SimpleNamespace(seam_stitch_pairs=_SEAM_PROVENANCE.copy())
    _private_callable(proxy, "_sync_seam_stitch_provenance")(base)

    require(
        condition=proxy.seam_stitch_pairs == _SEAM_PROVENANCE,
        message="The quality proxy must retain the base proxy's seam stitch provenance.",
    )
