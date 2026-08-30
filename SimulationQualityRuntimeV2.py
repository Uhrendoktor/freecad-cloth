"""FreeCAD boundary integration for simulation quality and fabric controls."""
from math import ceil

from SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset

QUALITY_NAMES = tuple(QUALITY_PRESETS)


def ensure_quality_properties(scene):
    specs = (
        ("QualityPreset", "App::PropertyEnumeration", "Quality", list(QUALITY_NAMES), "Balanced"),
        ("ParticleDistance", "App::PropertyFloat", "Quality", None, 4.0),
        ("SolverIterations", "App::PropertyInteger", "Quality", None, 8),
        ("SolverSubsteps", "App::PropertyInteger", "Quality", None, 1),
        ("FabricDensity", "App::PropertyFloat", "Fabric", None, 150.0),
        ("FabricThickness", "App::PropertyFloat", "Fabric", None, 0.5),
        ("FabricStretch", "App::PropertyFloat", "Fabric", None, 0.02),
        ("FabricShear", "App::PropertyFloat", "Fabric", None, 0.02),
        ("FabricBend", "App::PropertyFloat", "Fabric", None, 0.01),
        ("FabricFriction", "App::PropertyFloat", "Fabric", None, 0.5),
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
    for name in ("FabricStretch", "FabricShear", "FabricBend", "FabricFriction"):
        setattr(scene, name, min(1.0, max(0.0, float(getattr(scene, name)))))
    scene.AvatarSkinOffset = max(0.0, float(scene.AvatarSkinOffset))


def apply_quality_preset(scene, name=None):
    ensure_quality_properties(scene)
    quality = preset(name or scene.QualityPreset)
    scene.QualityPreset = quality.name
    scene.ParticleDistance = quality.particle_distance
    scene.SolverIterations = quality.solver_iterations
    scene.SolverSubsteps = quality.substeps
    return quality


def quality_discretization(point_count, perimeter, particle_distance):
    if int(point_count) < 3:
        raise ValueError("point_count must be at least three")
    return max(int(point_count), int(ceil(float(perimeter) / max(0.25, float(particle_distance)))))


def _material(scene):
    return FabricMaterial(
        density_g_m2=float(scene.FabricDensity),
        thickness_mm=float(scene.FabricThickness),
        stretch=float(scene.FabricStretch),
        shear=float(scene.FabricShear),
        bend=float(scene.FabricBend),
        friction=float(scene.FabricFriction),
    ).validate()


class QualitySimulationProxy:
    """Wrap the existing deterministic proxy without duplicating document plumbing."""

    Type = "ClothSimulation"

    def __init__(self):
        from SimulationObjects import SimulationProxy
        self._base = SimulationProxy()

    def __getattr__(self, name):
        return getattr(self._base, name)

    def onChanged(self, obj, prop):
        """Rebuild immediately when semantic simulation inputs are edited."""
        if prop == "ClothPieces":
            try:
                self.execute(obj)
            except (AttributeError, RuntimeError, ValueError):
                obj.touch()
            return
        if prop in {
            "DrapeTarget", "AvatarProxy", "QualityPreset", "ParticleDistance",
            "SolverIterations", "SolverSubsteps", "FabricDensity", "FabricThickness",
            "FabricStretch", "FabricShear", "FabricBend", "FabricFriction",
            "AvatarSkinOffset", "StitchSamples", "StartHeight", "Steps", "TimeStep",
        }:
            try:
                obj.touch()
            except (AttributeError, RuntimeError):
                pass

    @staticmethod
    def _signature(obj):
        from SimulationObjects import _simulation_source_signature
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        material = _material(obj)
        return (
            _simulation_source_signature(obj, pieces),
            preset(obj.QualityPreset),
            float(obj.ParticleDistance), int(obj.SolverIterations), int(obj.SolverSubsteps),
            material, float(obj.AvatarSkinOffset),
        )

    def execute(self, obj):
        ensure_quality_properties(obj)
        signature = self._signature(obj)
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        if self._base.backend is None or signature != self._base.source_signature or int(obj.Steps) < self._base.last_steps:
            if pieces:
                self._base._build_pattern_scene(obj, pieces, signature)
            else:
                self._build_demo(obj, signature)
            self._apply_material(obj)
            self._apply_collision(obj)
        steps = int(obj.Steps)
        if steps > self._base.last_steps:
            material = _material(obj)
            dt = float(obj.TimeStep) / int(obj.SolverSubsteps)
            damping = 1.0 - 0.05 * material.friction
            for _ in range(steps - self._base.last_steps):
                for _ in range(int(obj.SolverSubsteps)):
                    self._base.backend.step(
                        dt, int(obj.SolverIterations),
                        (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ)),
                        (float(obj.CollisionX), float(obj.CollisionY), float(obj.CollisionZ), float(obj.CollisionRadius)),
                        self._base.collision_surface,
                    )
                    system = getattr(self._base.backend, "system", None)
                    for particle in getattr(system, "particles", ()):
                        particle.x = particle.px + (particle.x - particle.px) * damping
                        particle.y = particle.py + (particle.y - particle.py) * damping
                        particle.z = particle.pz + (particle.z - particle.pz) * damping
                self._base.last_steps += 1
        positions = self._base.backend.positions()
        from SimulationObjects import _write_mesh
        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, self._base.panel_triangles.get(panel.Name, ()))
        obj.SimulatedTime = self._base.backend.time
        obj.ParticleCount = len(positions)
        obj.FiniteState = self._base.backend.finite()

    def _build_demo(self, obj, signature):
        from ClothBackend import default_backend_registry
        from ClothSolver import ClothSystem
        from SimulationObjects import _parse_pair_list, _parse_int_list, _write_grid_mesh
        spacing = max(0.25, float(obj.ParticleDistance))
        width, height = 100.0, 60.0
        nx = max(3, int(round(width / spacing)) + 1)
        ny = max(3, int(round(height / spacing)) + 1)
        left = ClothSystem.grid(width, height, nx, ny, origin=(-100.0, -30.0, float(obj.StartHeight)))
        right = ClothSystem.grid(width, height, nx, ny, origin=(0.0, -30.0, float(obj.StartHeight)))
        offset = len(left.particles)
        particles = left.particles + right.particles
        constraints = list(left.constraints) + [type(c)(c.a + offset, c.b + offset, c.rest, c.compliance) for c in right.constraints]
        system = ClothSystem(particles, constraints)
        system.add_stitches(_parse_pair_list(getattr(obj, "SeamSelection", ()), len(particles)) or tuple((j * nx + nx - 1, offset + j * nx) for j in range(ny)))
        pins = _parse_int_list(getattr(obj, "PinSelection", ()), len(particles)) or (0, nx - 1, offset, offset + nx - 1)
        system.pin(pins)
        self._base.backend = default_backend_registry().create("xpbd-cpu", system)
        tris = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = j * nx + i; b = a + 1; c = (j + 1) * nx + i + 1; d = (j + 1) * nx + i
                tris.extend(((a, b, c), (a, c, d)))
        self._base.panel_indices = {"DrapePanelA": tuple(range(offset)), "DrapePanelB": tuple(range(offset, offset * 2))}
        self._base.panel_triangles = {"DrapePanelA": tuple(tris), "DrapePanelB": tuple((a + offset, b + offset, c + offset) for a, b, c in tris)}
        self._base.source_signature = signature
        self._base.last_steps = 0
        self._base.collision_surface = None
        positions = self._base.backend.positions()
        for panel, key in zip(getattr(obj, "DrapePanels", ()), ("DrapePanelA", "DrapePanelB")):
            _write_grid_mesh(panel, positions, self._base.panel_indices[key], nx, ny)

    def _apply_material(self, obj):
        material = _material(obj)
        system = getattr(self._base.backend, "system", None)
        if system is None:
            return
        mass_factor = 150.0 / material.density_g_m2
        for particle in system.particles:
            particle.inv_mass *= mass_factor
        rest_factor = 1.0 + 0.01 * material.stretch + 0.005 * material.shear + 0.002 * material.bend
        system.constraints = [type(c)(c.a, c.b, c.rest * rest_factor, c.compliance) for c in system.constraints]

    def _apply_collision(self, obj):
        avatar = getattr(obj, "AvatarProxy", None)
        source = getattr(avatar, "SourceObject", None) if avatar is not None else None
        if source is None:
            return
        from AvatarCollision import surface_from_freecad
        thickness = float(getattr(avatar, "CollisionThickness", 0.0)) + float(obj.FabricThickness) + float(obj.AvatarSkinOffset)
        self._base.collision_surface = surface_from_freecad(source, float(getattr(avatar, "CollisionDeflection", 1.0)), thickness)

    def reset(self, obj):
        self._base.reset(obj)


def create_quality_simulation_scene(doc):
    from SimulationObjects import create_simulation_scene
    scene = create_simulation_scene(doc)
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.Document.recompute()
    return scene

# CI retrigger marker: keep this file as the canonical quality-simulation boundary.
