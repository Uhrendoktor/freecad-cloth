from types import SimpleNamespace

import pytest

from freecad_cloth.simulation.SimulationQuality import FabricMaterial, preset
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QUALITY_NAMES, apply_quality_preset, quality_discretization


def test_quality_names_and_discretization_are_materially_distinct():
    assert QUALITY_NAMES == ("Fast", "Balanced", "Final")
    counts = [quality_discretization(4, 400.0, preset(name).particle_distance) for name in QUALITY_NAMES]
    assert counts[0] < counts[1] < counts[2]


def test_quality_preset_updates_solver_controls():
    scene = SimpleNamespace(
        QualityPreset="Balanced", ParticleDistance=4.0,
        SolverIterations=8, SolverSubsteps=1,
        FabricDensity=150.0, FabricThickness=0.5,
        FabricStretch=0.02, FabricShear=0.02,
        FabricBend=0.01, FabricFriction=0.5,
        FabricColor=(0.72, 0.34, 0.46), FabricSpecular=0.25,
        FabricRoughness=0.65, FabricTransparency=0,
        AvatarSkinOffset=0.0,
    )
    quality = apply_quality_preset(scene, "Final")
    assert quality == preset("Final")
    assert scene.QualityPreset == "Final"
    assert scene.ParticleDistance == 2.0
    assert scene.SolverIterations == 16
    assert scene.SolverSubsteps == 2


def test_material_defaults_match_persisted_contract():
    material = FabricMaterial()
    assert material.validate() is material
    assert material.density_g_m2 == 150.0
    assert material.thickness_mm == 0.5
    assert material.friction == 0.5


@pytest.mark.parametrize("distance", [0.0, -2.0])
def test_discretization_clamps_invalid_spacing(distance):
    assert quality_discretization(4, 100.0, distance) >= 4


def test_tissu_step_uses_backend_owned_collision_surface_without_changing_authority():
    from freecad_cloth.simulation.SimulationObjects import _collision_surface_for_step

    authoritative = object()
    solver_surface = object()
    proxy = SimpleNamespace(
        collision_surface=authoritative,
        backend=SimpleNamespace(name="tissu", solver_collision_surface=solver_surface),
    )

    assert _collision_surface_for_step(proxy) is solver_surface
    assert proxy.collision_surface is authoritative


def test_non_tissu_step_uses_authoritative_collision_surface():
    from freecad_cloth.simulation.SimulationObjects import _collision_surface_for_step

    authoritative = object()
    proxy = SimpleNamespace(
        collision_surface=authoritative,
        backend=SimpleNamespace(name="xpbd-cpu", solver_collision_surface=object()),
    )

    assert _collision_surface_for_step(proxy) is authoritative


def test_both_simulation_step_paths_use_the_collision_surface_handoff_helper():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    simulation_source = (root / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    quality_source = (root / "freecad_cloth" / "simulation" / "SimulationQualityRuntimeV2.py").read_text(encoding="utf-8")

    assert "_collision_surface_for_step(self)" in simulation_source
    assert "_collision_surface_for_step(base)" in quality_source
    assert "self.collision_surface = collision_surface" in simulation_source
