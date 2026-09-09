"""FreeCAD boundary integration for simulation quality and fabric controls."""
from math import ceil

from freecad_cloth.simulation.SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset

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
    touch = getattr(scene, "touch", None)
    if callable(touch):
        touch()
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
    """Wrap the deterministic simulation proxy with quality/material behavior."""

    Type = "ClothSimulation"

    def __init__(self):
        self._restore_base()

    @staticmethod
    def _new_base():
        from freecad_cloth.simulation.SimulationObjects import SimulationProxy
        return SimulationProxy()

    def _restore_base(self):
        self.__dict__["_base"] = self._new_base()
        return self.__dict__["_base"]

    def _base_or_restore(self):
        base = self.__dict__.get("_base")
        if base is None:
            base = self._restore_base()
        return base

    def __getattr__(self, name):
        if name == "_base":
            raise AttributeError(name)
        return getattr(self._base_or_restore(), name)

    def onDocumentRestored(self, obj):
        """Recreate non-serializable solver state after FreeCAD reloads the proxy."""
        self._restore_base()

    @staticmethod
    def _signature(obj):
        from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature
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
        base = self._base_or_restore()
        signature = self._signature(obj)
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        if base.backend is None or signature != base.source_signature or int(obj.Steps) < base.last_steps:
            if pieces:
                self._build_pattern_scene(obj, pieces, signature)
            else:
                self._build_demo(obj, signature)
            self._apply_material(obj)
            self._apply_collision(obj)
        steps = int(obj.Steps)
        if steps > base.last_steps:
            material = _material(obj)
            dt = float(obj.TimeStep) / int(obj.SolverSubsteps)
            damping = 1.0 - 0.05 * material.friction
            for _ in range(steps - base.last_steps):
                for _ in range(int(obj.SolverSubsteps)):
                    base.backend.step(
                        dt, int(obj.SolverIterations),
                        (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ)),
                        (float(obj.CollisionX), float(obj.CollisionY), float(obj.CollisionZ), float(obj.CollisionRadius)),
                        base.collision_surface,
                    )
                    system = getattr(base.backend, "system", None)
                    for particle in getattr(system, "particles", ()):
                        particle.x = particle.px + (particle.x - particle.px) * damping
                        particle.y = particle.py + (particle.y - particle.py) * damping
                        particle.z = particle.pz + (particle.z - particle.pz) * damping
                base.last_steps += 1
        positions = base.backend.positions()
        from freecad_cloth.simulation.SimulationObjects import _write_mesh
        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, base.panel_triangles.get(panel.Name, ()))
        obj.SimulatedTime = base.backend.time
        obj.ParticleCount = len(positions)
        obj.FiniteState = base.backend.finite()

    def _build_pattern_scene(self, obj, pieces, signature):
        """Use the authoritative base scene builder with quality tessellation."""
        from freecad_cloth.simulation import SimulationObjects
        from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

        base = self._base_or_restore()
        previous = SimulationObjects._piece_mesh
        SimulationObjects._piece_mesh = lambda piece, start_height: quality_piece_mesh(
            piece, start_height, float(obj.ParticleDistance)
        )
        try:
            return base._build_pattern_scene(obj, pieces, signature)
        finally:
            SimulationObjects._piece_mesh = previous

    def _build_demo(self, obj, signature):
        from freecad_cloth.simulation.ClothBackend import default_backend_registry
        from freecad_cloth.simulation.ClothSolver import ClothSystem
        from freecad_cloth.simulation.SimulationObjects import _parse_pair_list, _parse_int_list, _write_grid_mesh
        base = self._base_or_restore()
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
        base.backend = default_backend_registry().create("xpbd-cpu", system)
        tris = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = j * nx + i; b = a + 1; c = (j + 1) * nx + i + 1; d = (j + 1) * nx + i
                tris.extend(((a, b, c), (a, c, d)))
        base.panel_indices = {"DrapePanelA": tuple(range(offset)), "DrapePanelB": tuple(range(offset, offset * 2))}
        base.panel_triangles = {"DrapePanelA": tuple(tris), "DrapePanelB": tuple((a + offset, b + offset, c + offset) for a, b, c in tris)}
        base.source_signature = signature
        base.last_steps = 0
        base.collision_surface = None
        positions = base.backend.positions()
        for panel, key in zip(getattr(obj, "DrapePanels", ()), ("DrapePanelA", "DrapePanelB")):
            _write_grid_mesh(panel, positions, base.panel_indices[key], nx, ny)

    def _apply_material(self, obj):
        base = self._base_or_restore()
        material = _material(obj)
        system = getattr(base.backend, "system", None)
        if system is None:
            return
        mass_factor = 150.0 / material.density_g_m2
        for particle in system.particles:
            particle.inv_mass *= mass_factor
        rest_factor = 1.0 + 0.01 * material.stretch + 0.005 * material.shear + 0.002 * material.bend
        system.constraints = [type(c)(c.a, c.b, c.rest * rest_factor, c.compliance) for c in system.constraints]

    def _apply_collision(self, obj):
        base = self._base_or_restore()
        avatar = getattr(obj, "AvatarProxy", None)
        source = getattr(avatar, "SourceObject", None) if avatar is not None else None
        if source is None:
            return
        from freecad_cloth.avatar.AvatarCollision import surface_from_freecad
        thickness = float(getattr(avatar, "CollisionThickness", 0.0)) + float(obj.FabricThickness) + float(obj.AvatarSkinOffset)
        base.collision_surface = surface_from_freecad(source, float(getattr(avatar, "CollisionDeflection", 1.0)), thickness)

    def reset(self, obj):
        self._base_or_restore().reset(obj)


def create_quality_simulation_scene(doc):
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene, set_avatar_collision_source
    from freecad_cloth.avatar.AvatarCommands import create_avatar

    scene = create_simulation_scene(doc)

    legacy = doc.getObject("HumanoidAvatar")
    if legacy is not None and hasattr(legacy, "ViewObject"):
        legacy.ViewObject.Visibility = False

    avatar = create_avatar(attach_collision=False, doc=doc)
    avatar.Label = "Cloth Human Avatar (MakeHuman)"
    avatar.ViewObject.Visibility = True

    set_avatar_collision_source(
        scene,
        avatar,
        float(getattr(avatar, "SkinOffset", 3.0)),
        1.0,
    )
    scene.AvatarProxy.SourceObject = avatar
    scene.DrapeTarget = doc.getObject("DrapeTarget")
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.Document.recompute()
    return scene
