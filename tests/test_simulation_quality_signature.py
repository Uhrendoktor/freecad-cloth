"""Regression coverage for quality/material/collision rebuild signatures."""

from types import SimpleNamespace

from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy


def _scene():
    scene = SimpleNamespace(
        QualityPreset="Balanced",
        ParticleDistance=4.0,
        SolverIterations=8,
        SolverSubsteps=1,
        FabricDensity=150.0,
        FabricThickness=0.5,
        FabricStretch=0.02,
        FabricShear=0.02,
        FabricBend=0.01,
        FabricFriction=0.5,
        AvatarSkinOffset=0.0,
        AutoPinning=True,
        ClothPieces=(),
        Document=SimpleNamespace(Objects=()),
    )
    return scene


def test_signature_changes_for_every_derived_simulation_control():
    scene = _scene()
    baseline = QualitySimulationProxy._signature(scene)
    controls = (
        ("QualityPreset", "Final"),
        ("ParticleDistance", 2.0),
        ("SolverIterations", 16),
        ("SolverSubsteps", 2),
        ("FabricDensity", 300.0),
        ("FabricThickness", 0.8),
        ("FabricStretch", 0.04),
        ("FabricShear", 0.04),
        ("FabricBend", 0.02),
        ("FabricFriction", 0.8),
        ("AvatarSkinOffset", 3.0),
        ("AutoPinning", False),
    )
    for name, value in controls:
        changed = _scene()
        setattr(changed, name, value)
        assert QualitySimulationProxy._signature(changed) != baseline, name


def test_identical_quality_signature_is_deterministic():
    first = QualitySimulationProxy._signature(_scene())
    second = QualitySimulationProxy._signature(_scene())
    assert first == second
