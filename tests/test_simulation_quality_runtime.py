from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQuality import FabricMaterial, preset
from freecad_cloth.simulation.SimulationQualityRuntime import (
    QUALITY_NAMES,
    apply_quality_preset,
    quality_discretization,
)

ROOT = Path(__file__).resolve().parents[1]


def test_quality_names_and_discretization_are_materially_distinct():
    assert QUALITY_NAMES == ("Fast", "Balanced", "Final")
    counts = [
        quality_discretization(4, 400.0, preset(name).particle_distance) for name in QUALITY_NAMES
    ]
    assert counts[0] < counts[1] < counts[2]


def test_quality_preset_updates_solver_controls():
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

    quality = apply_quality_preset(scene, "Final")

    assert quality == preset("Final")
    assert scene.QualityPreset == "Final"
    assert scene.ParticleDistance == 2.0
    assert scene.SolverIterations == 16
    assert scene.SolverSubsteps == 2


def test_material_defaults_are_document_metadata():
    material = FabricMaterial()
    assert material.validate() is material
    assert material.density_g_m2 == 150.0
    assert material.thickness_mm == 0.5
    assert material.friction == 0.5


def test_advance_preview_frame_advances_backend_once_without_document_recompute():
    from freecad_cloth.simulation import SimulationQualityRuntime as runtime

    class Backend:
        name = "position-based-dynamics"
        time = 0.25

        def __init__(self):
            self.calls = []

        def step(self, dt, iterations, gravity, surface):
            self.calls.append((dt, iterations, gravity, surface))

        def positions(self):
            raise AssertionError("preview publication should be stubbed in this focused test")

        def finite(self):
            return True

    scene = SimpleNamespace(
        QualityPreset="Fast",
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
    proxy = runtime.QualitySimulationProxy()
    base = proxy._base_or_restore()
    backend = Backend()
    base.backend = backend
    base.collision_surface = "collision"
    base.last_steps = 0
    published = []
    proxy._publish_state = lambda obj, state: published.append((obj, state))

    proxy.advance_preview_frame(scene)

    assert backend.calls == [
        (
            scene.TimeStep,
            scene.SolverIterations,
            (scene.GravityX, scene.GravityY, scene.GravityZ),
            "collision",
        )
    ]
    assert published == [(scene, base)]
    assert base.last_steps == 1


def test_quality_proxy_keeps_solver_stitch_provenance():
    from freecad_cloth.simulation import SimulationQualityRuntime as runtime

    class Base:
        seam_stitch_pairs = {"seam-2": ((2, 3), (4, 5))}

    proxy = runtime.QualitySimulationProxy()
    proxy._sync_seam_stitch_provenance(Base())

    assert proxy.seam_stitch_pairs == {"seam-2": ((2, 3), (4, 5))}


