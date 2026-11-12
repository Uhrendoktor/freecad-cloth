# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical FreeCAD boundary integration for simulation quality and fabric controls.

This module owns the quality-aware runtime wrapper around the canonical simulation
proxy. It is the only quality runtime implementation.
"""

import weakref
from collections.abc import Sequence
from math import ceil
from typing import Protocol, cast

from freecad_cloth.simulation.SimulationObjects import PIN_MODE_NAMES, resolve_pin_indices
from freecad_cloth.simulation.SimulationQuality import QUALITY_PRESETS, normalize_color_rgb, preset

QUALITY_NAMES = tuple(QUALITY_PRESETS)
_RUNTIME_BASES = weakref.WeakKeyDictionary()


class _QualityScene(Protocol):
    """Dynamic FreeCAD feature fields owned by the quality runtime."""

    QualityPreset: str
    ParticleDistance: float
    SolverIterations: int
    SolverSubsteps: int
    PinMode: str
    FabricDensity: float
    FabricThickness: float
    FabricStretch: float
    FabricShear: float
    FabricBend: float
    FabricFriction: float
    FabricColor: tuple[float, float, float]
    FabricSpecular: float
    FabricRoughness: float
    FabricTransparency: int
    AvatarSkinOffset: float
    Steps: int
    ClothPieces: Sequence[object]

    def addProperty(self, type_name: str, name: str, group: str) -> object:
        """Register one persistent property on the FreeCAD feature.

        Args:
            type_name: Native FreeCAD property type.
            name: Property name to add.
            group: Property group displayed by FreeCAD.

        Returns:
            The FreeCAD feature on which the property was registered.
        """
        ...


def ensure_quality_properties(scene: object) -> _QualityScene:
    """Create and validate persistent simulation-quality properties on a scene.

    Args:
        scene: FreeCAD simulation feature receiving quality and fabric properties.

    Returns:
        The same feature after its quality properties have been initialized and clamped.
    """
    typed_scene = cast("_QualityScene", scene)
    specs = (
        ("QualityPreset", "App::PropertyEnumeration", "Quality", list(QUALITY_NAMES), "Balanced"),
        ("ParticleDistance", "App::PropertyFloat", "Quality", None, 4.0),
        ("SolverIterations", "App::PropertyInteger", "Quality", None, 8),
        ("SolverSubsteps", "App::PropertyInteger", "Quality", None, 1),
        ("PinMode", "App::PropertyEnumeration", "Quality", list(PIN_MODE_NAMES), "Automatic"),
        ("FabricDensity", "App::PropertyFloat", "Fabric", None, 150.0),
        ("FabricThickness", "App::PropertyFloat", "Fabric", None, 0.5),
        ("FabricStretch", "App::PropertyFloat", "Fabric", None, 0.02),
        ("FabricShear", "App::PropertyFloat", "Fabric", None, 0.02),
        ("FabricBend", "App::PropertyFloat", "Fabric", None, 0.01),
        ("FabricFriction", "App::PropertyFloat", "Fabric", None, 0.5),
        ("FabricColor", "App::PropertyColor", "Fabric", None, (0.72, 0.34, 0.46)),
        ("FabricSpecular", "App::PropertyFloat", "Fabric", None, 0.25),
        ("FabricRoughness", "App::PropertyFloat", "Fabric", None, 0.65),
        ("FabricTransparency", "App::PropertyInteger", "Fabric", None, 0),
        ("AvatarSkinOffset", "App::PropertyFloat", "Collision", None, 0.0),
    )
    for name, type_name, group, values, default in specs:
        if not hasattr(typed_scene, name):
            typed_scene.addProperty(type_name, name, group)
            if values is not None:
                setattr(typed_scene, name, values)
            setattr(typed_scene, name, default)
    _validate_properties(typed_scene)
    return typed_scene


def _validate_properties(scene: _QualityScene) -> None:
    """Clamp persisted quality and fabric properties to their supported ranges.

    Args:
        scene: Simulation feature whose saved values are normalized in place.
    """
    scene.ParticleDistance = max(0.25, float(scene.ParticleDistance))
    scene.SolverIterations = max(1, int(scene.SolverIterations))
    scene.SolverSubsteps = max(1, int(scene.SolverSubsteps))
    scene.FabricDensity = max(1e-9, float(scene.FabricDensity))
    scene.FabricThickness = max(1e-9, float(scene.FabricThickness))
    for name in (
        "FabricStretch",
        "FabricShear",
        "FabricBend",
        "FabricFriction",
        "FabricSpecular",
        "FabricRoughness",
    ):
        setattr(scene, name, min(1.0, max(0.0, float(getattr(scene, name)))))
    scene.FabricTransparency = min(100, max(0, int(scene.FabricTransparency)))
    scene.FabricColor = normalize_color_rgb(getattr(scene, "FabricColor", (0.72, 0.34, 0.46)))
    scene.AvatarSkinOffset = max(0.0, float(scene.AvatarSkinOffset))


def apply_quality_preset(scene, name=None):
    """Apply a named quality preset and return its normalized profile.

    Args:
        scene: Persistent FreeCAD simulation feature receiving the profile values.
        name: Optional preset name; the scene's stored selection is used by default.

    Returns:
        The selected immutable profile after its persisted values have been updated.

    Raises:
        ValueError: If the requested preset name is not supported.
    """
    ensure_quality_properties(scene)
    quality = preset(name or scene.QualityPreset)
    scene.QualityPreset = quality.name
    scene.ParticleDistance = quality.particle_distance
    scene.SolverIterations = quality.solver_iterations
    scene.SolverSubsteps = quality.substeps
    touch = getattr(scene, "touch", None)
    if callable(touch):
        touch()
    return quality


def quality_discretization(point_count, perimeter, particle_distance):
    """Return the sample count required by the requested particle spacing.

    Args:
        point_count: Minimum sample count required by the authored boundary.
        perimeter: Total boundary length in model units.
        particle_distance: Requested maximum particle spacing in model units.

    Returns:
        An integer sample count no smaller than the supplied boundary minimum.

    Raises:
        ValueError: If the boundary minimum contains fewer than three points.
    """
    if int(point_count) < 3:
        msg = "point_count must be at least three"
        raise ValueError(msg)
    return max(int(point_count), int(ceil(float(perimeter) / max(0.25, float(particle_distance)))))


class QualitySimulationProxy:
    """Wrap the deterministic simulation proxy with quality/material behavior."""

    Type = "ClothSimulation"

    def __init__(self):
        self._restore_base()

    @staticmethod
    def _new_base():
        from freecad_cloth.simulation.SimulationObjects import SimulationProxy

        return SimulationProxy()

    def _restore_base(self):
        base = self._new_base()
        _RUNTIME_BASES[self] = base
        return base

    def _base_or_restore(self):
        base = _RUNTIME_BASES.get(self)
        if base is None:
            base = self._restore_base()
        return base

    def __getattr__(self, name):
        if name == "_base":
            raise AttributeError(name)
        return getattr(self._base_or_restore(), name)

    def _sync_seam_stitch_provenance(self, base):
        """Keep exact solver stitch-pair provenance on the authoritative document proxy."""
        self.seam_stitch_pairs = {
            str(seam_id): tuple(stitch_pairs)
            for seam_id, stitch_pairs in getattr(base, "seam_stitch_pairs", {}).items()
        }

    def onDocumentRestored(self, obj):
        """Recreate non-serializable solver state after FreeCAD reloads the proxy.

Args:
    obj: Persisted simulation-quality feature restored by the FreeCAD document loader."""
        self._restore_base()
        self.seam_stitch_pairs = {}

    @staticmethod
    def _signature(obj: _QualityScene) -> tuple[object, ...]:
        """Return the deterministic inputs that invalidate the derived simulation.

        Args:
            obj: Simulation feature whose persisted source and quality values are read.

        Returns:
            Immutable source, preset, solver, and fabric controls for scene rebuilding.
        """
        from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

        pieces = [
            piece
            for piece in obj.ClothPieces
            if getattr(piece, "PatternType", "") == "PatternPiece"
        ]
        return (
            _simulation_source_signature(obj, pieces),
            preset(obj.QualityPreset),
            float(obj.ParticleDistance),
            int(obj.SolverIterations),
            int(obj.SolverSubsteps),
            float(obj.FabricDensity),
            float(obj.FabricThickness),
            float(obj.FabricStretch),
            float(obj.FabricShear),
            float(obj.FabricBend),
            float(obj.FabricFriction),
            float(obj.AvatarSkinOffset),
        )

    def _advance(self, obj, base, step_count):
        """Advance the persistent backend without entering FreeCAD recompute."""
        steps = max(0, int(step_count))
        if steps <= 0:
            return
        dt = float(obj.TimeStep) / int(obj.SolverSubsteps)
        gravity = (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ))
        for _ in range(steps):
            for _ in range(int(obj.SolverSubsteps)):
                base.backend.step(
                    dt,
                    int(obj.SolverIterations),
                    gravity,
                    base.collision_surface,
                )
            base.last_steps += 1

    def _publish_state(self, obj, base):
        """Write the already-solved particle state to the display objects."""
        snapshot = getattr(base.backend, "positions_and_finite", None)
        if callable(snapshot):
            snapshot_result = snapshot()
            positions, finite_state = cast(
                "tuple[tuple[tuple[float, float, float], ...], bool]",
                snapshot_result,
            )
        else:
            positions = base.backend.positions()
            finite_state = base.backend.finite()
        from freecad_cloth.simulation.SimulationObjects import _write_mesh

        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, base.panel_triangles.get(panel.Name, ()))
        self._apply_presentation(obj)
        obj.Steps = int(base.last_steps)
        obj.SimulatedTime = base.backend.time
        obj.ParticleCount = len(positions)
        obj.FiniteState = finite_state

    def execute(self, obj: object) -> None:
        """Recompute the FreeCAD object from its current source properties.

        Args:
            obj: Native FreeCAD simulation feature receiving the derived scene state.
        """
        scene = ensure_quality_properties(obj)
        base = self._base_or_restore()
        signature = self._signature(scene)
        pieces = [
            piece
            for piece in scene.ClothPieces
            if getattr(piece, "PatternType", "") == "PatternPiece"
        ]
        if (
            base.backend is None
            or signature != base.source_signature
            or int(scene.Steps) < base.last_steps
        ):
            if pieces:
                self._build_pattern_scene(scene, pieces, signature)
            else:
                self._build_demo(scene, signature)
            self._sync_seam_stitch_provenance(base)
        steps = int(scene.Steps)
        if steps > base.last_steps:
            self._advance(scene, base, steps - base.last_steps)
        self._publish_state(scene, base)

    def advance_preview_frame(self, obj):
        """Advance one interactive frame without triggering a document recompute.

        Args:
            obj: Persistent quality-simulation feature whose preview state is advanced.
        """
        ensure_quality_properties(obj)
        base = self._base_or_restore()
        if base.backend is None:
            self.execute(obj)
            base = self._base_or_restore()
        self._advance(obj, base, 1)
        self._publish_state(obj, base)

    def _build_pattern_scene(self, obj, pieces, signature):
        """Use the authoritative base scene builder with quality tessellation."""
        from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

        base = self._base_or_restore()
        return base._build_pattern_scene(
            obj,
            pieces,
            signature,
            piece_mesh=lambda piece, start_height, piece_ir=None: quality_piece_mesh(
                piece,
                start_height,
                float(obj.ParticleDistance),
                piece_ir=piece_ir,
            ),
        )

    def _build_demo(self, obj, signature):
        from freecad_cloth.simulation.ClothSolver import ClothSystem
        from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
            PositionBasedDynamicsBackend,
        )
        from freecad_cloth.simulation.SimulationObjects import (
            _collision_for_scene,
            _parse_pair_list,
            _write_grid_mesh,
        )

        base = self._base_or_restore()
        spacing = max(0.25, float(obj.ParticleDistance))
        width, height = 100.0, 60.0
        nx = max(3, int(round(width / spacing)) + 1)
        ny = max(3, int(round(height / spacing)) + 1)
        left = ClothSystem.grid(
            width, height, nx, ny, origin=(-100.0, -30.0, float(obj.StartHeight))
        )
        right = ClothSystem.grid(width, height, nx, ny, origin=(0.0, -30.0, float(obj.StartHeight)))
        offset = len(left.particles)
        particles = left.particles + right.particles
        constraints = list(left.constraints) + [
            type(c)(c.a + offset, c.b + offset, c.rest, c.compliance) for c in right.constraints
        ]
        system = ClothSystem(particles, constraints)
        system.add_stitches(
            _parse_pair_list(getattr(obj, "SeamSelection", ()), len(particles))
            or tuple((j * nx + nx - 1, offset + j * nx) for j in range(ny))
        )
        pins = resolve_pin_indices(
            obj,
            len(particles),
            (0, nx - 1, offset, offset + nx - 1),
        )
        if pins:
            system.pin(pins)
        tris = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = j * nx + i
                b = a + 1
                c = (j + 1) * nx + i + 1
                d = (j + 1) * nx + i
                tris.extend(((a, b, c), (a, c, d)))
        base.panel_indices = {
            "DrapePanelA": tuple(range(offset)),
            "DrapePanelB": tuple(range(offset, offset * 2)),
        }
        base.panel_triangles = {
            "DrapePanelA": tuple(tris),
            "DrapePanelB": tuple((a + offset, b + offset, c + offset) for a, b, c in tris),
        }
        collision_surface = _collision_for_scene(obj)
        base.backend = PositionBasedDynamicsBackend(
            system,
            tuple(tris),
            pins=pins,
            stitches=tuple((stitch.a, stitch.b) for stitch in system.stitches),
            collision_surface=collision_surface,
        )
        base.source_signature = signature
        base.last_steps = 0
        base.collision_surface = getattr(
            base.backend, "solver_collision_surface", collision_surface
        )
        positions = base.backend.positions()
        for panel, key in zip(
            getattr(obj, "DrapePanels", ()), ("DrapePanelA", "DrapePanelB"), strict=False
        ):
            _write_grid_mesh(panel, positions, base.panel_indices[key], nx, ny)

    def _apply_presentation(self, obj):
        color = tuple(float(value) for value in getattr(obj, "FabricColor", (0.72, 0.34, 0.46)))
        transparency = int(getattr(obj, "FabricTransparency", 0))
        for panel in getattr(obj, "DrapePanels", ()):
            try:
                view = panel.ViewObject
                if hasattr(view, "DisplayMode"):
                    view.DisplayMode = "Shaded"
                view.ShapeColor = color
                view.Transparency = transparency
                if hasattr(view, "SpecularColor"):
                    view.SpecularColor = (float(getattr(obj, "FabricSpecular", 0.25)),) * 3
                if hasattr(view, "Shininess"):
                    view.Shininess = float(
                        max(
                            0.0,
                            min(
                                100.0, (1.0 - float(getattr(obj, "FabricRoughness", 0.65))) * 100.0
                            ),
                        )
                    )
            except (AttributeError, TypeError, ValueError):
                pass

    def reset(self, obj):
        """Reset the runtime state to its initial values.

        Args:
            obj: Persistent quality-simulation feature whose runtime state is reset.
        """
        self._base_or_restore().reset(obj)
