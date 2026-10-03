from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQuality import FabricMaterial, preset
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import (
    QUALITY_NAMES,
    apply_quality_preset,
    quality_discretization,
)

ROOT = Path(__file__).resolve().parents[1]


def test_quality_names_and_discretization_are_materially_distinct():
    assert QUALITY_NAMES == ("Fast", "Balanced", "Final")
    counts = [
        quality_discretization(4, 400.0, preset(name).particle_distance)
        for name in QUALITY_NAMES
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


def test_runtime_has_no_legacy_backend_or_damping_path():
    source = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationQualityRuntimeV2.py"
    ).read_text(encoding="utf-8")

    assert "default_backend_registry" not in source
    assert "preferred_backend_name" not in source
    assert "_collision_surface_for_step" not in source
    assert "_apply_material" not in source
    assert "damping =" not in source
    assert 'name="xpbd-cpu"' not in source
    assert "TissuBackend" in source


def test_quality_proxy_keeps_solver_stitch_provenance():
    from freecad_cloth.simulation import SimulationQualityRuntimeV2 as runtime

    class Base:
        seam_stitch_pairs = {"seam-2": ((2, 3), (4, 5))}

    proxy = runtime.QualitySimulationProxy()
    proxy._sync_seam_stitch_provenance(Base())

    assert proxy.seam_stitch_pairs == {"seam-2": ((2, 3), (4, 5))}
