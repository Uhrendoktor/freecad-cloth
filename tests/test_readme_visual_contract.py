"""Contracts for the published README visual validation path."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_turntable_uses_solver_boundary_provenance():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert "panel_boundary_edges" in source
    assert "resolve_simulation_pattern" in source
    assert "Edge%sId" in source
    assert "semantic-provenance=true" in source
    assert "if seam_gap > 35.0" in source


def test_readme_turntable_uses_validated_tunics_profile():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert 'chest = 860.0; hip = 880.0; ease = 10.0' in source
    assert 'ParticleDistance", "24.0' in source or 'ParticleDistance = float(os.environ.get("CLOTH_TUNIC_PARTICLE_DISTANCE_MM", "24.0"))' in source
    assert 'SolverIterations", "64' in source or 'SolverIterations = int(os.environ.get("CLOTH_TUNIC_SOLVER_ITERATIONS", "64"))' in source
    assert 'FabricFriction = 0.85' in source


def test_canonical_workflow_fails_closed_on_turntable_quality():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "CLOTH_TISSU_SUBSTEPS: 10" in source
    assert "semantic-provenance=true" in source
    assert "simulation-seam-diagnostic" in source
    assert "checkpoint-uniqueness=passed" in source
    assert "test $unique -eq 4" in source
