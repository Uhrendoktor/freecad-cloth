"""Canonical FreeCAD boundary integration for simulation quality and fabric controls.

This module owns the quality-aware runtime wrapper around the canonical simulation
proxy. It is the only quality runtime implementation.
"""

import weakref
from math import ceil

from freecad_cloth.simulation.SimulationObjects import PIN_MODE_NAMES, resolve_pin_indices
from freecad_cloth.simulation.SimulationQuality import QUALITY_PRESETS, normalize_color_rgb, preset

QUALITY_NAMES = tuple(QUALITY_PRESETS)
_RUNTIME_BASES = weakref.WeakKeyDictionary()


def ensure_quality_properties(scene):
    """Create and validate persistent simulation-quality properties on a scene."""
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
        if not hasattr(scene, name):
            scene.addProperty(type_name, name, group)
            if values is not None:
                setattr(scene, name, values)
            setattr(scene, name, default)
    _validate_properties(scene)
    return scene


def _validate_properties(scene):
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
    """Apply a named quality preset and return its normalized profile."""
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
    """Return the sample count required by the requested particle spacing."""
    if int(point_count) < 3:
        raise ValueError("point_count must be at least three")
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
        """Recreate non-serializable solver state after FreeCAD reloads the proxy."""
        self._restore_base()
        self.seam_stitch_pairs = {}

    @staticmethod
    def _signature(obj):
        from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

        pieces = [
            p
            for p in getattr(obj, "ClothPieces", ())
            if getattr(p, "PatternType", "") == "PatternPiece"
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
        positions = base.backend.positions()
        from freecad_cloth.simulation.SimulationObjects import _write_mesh

        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, base.panel_triangles.get(panel.Name, ()))
        self._apply_presentation(obj)
        obj.Steps = int(base.last_steps)
        obj.SimulatedTime = base.backend.time
        obj.ParticleCount = len(positions)
        obj.FiniteState = base.backend.finite()

    def execute(self, obj):
        """Recompute the FreeCAD object from its current source properties."""
        ensure_quality_properties(obj)
        base = self._base_or_restore()
        signature = self._signature(obj)
        pieces = [
            p
            for p in getattr(obj, "ClothPieces", ())
            if getattr(p, "PatternType", "") == "PatternPiece"
        ]
        if (
            base.backend is None
            or signature != base.source_signature
            or int(obj.Steps) < base.last_steps
        ):
            if pieces:
                self._build_pattern_scene(obj, pieces, signature)
            else:
                self._build_demo(obj, signature)
            self._sync_seam_stitch_provenance(base)
        steps = int(obj.Steps)
        if steps > base.last_steps:
            self._advance(obj, base, steps - base.last_steps)
        self._publish_state(obj, base)

    def advance_preview_frame(self, obj):
        """Advance one interactive frame without triggering a document recompute."""
        ensure_quality_properties(obj)
        base = self._base_or_restore()
        if base.backend is None:
            self.execute(obj)
            base = self._base_or_restore()
        self._advance(obj, base, 1)
        self._publish_state(obj, base)

    def _build_pattern_scene(self, obj, pieces, signature):
        """Use the authoritative base scene builder with quality tessellation."""
        from freecad_cloth.simulation import SimulationObjects
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
        """Reset the runtime state to its initial values."""
        self._base_or_restore().reset(obj)
