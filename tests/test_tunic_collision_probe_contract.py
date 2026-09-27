from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_research_tunic_collision_probe_is_parameter_read_only():
    source = (ROOT / "tests" / "freecad_tunic_collision_probe.py").read_text(encoding="utf-8")
    assert "scene.Proxy.backend" in source
    assert "scene.Proxy.seam_stitch_pairs" in source
    assert "solver_collision_surface" in source
    assert "CLOTH_TISSU_COLLISION_TRIANGLES" in source
    assert "ProbeComplete" in source
    forbidden = (
        "ParticleDistance =",
        "SolverIterations =",
        "SolverSubsteps =",
        "PinSelection =",
        "FabricFriction =",
    )
    assert not any(token in source for token in forbidden)


def test_research_tunic_collision_probe_persists_31_states():
    source = (ROOT / "tests" / "freecad_tunic_collision_probe.py").read_text(encoding="utf-8")
    assert 'len(states) != 31' in source
    assert '"step": int(step)' in source
    assert '"contact_band_count_le_2mm"' in source
    assert '"signed_distance_min_mm"' in source
    assert '"stitch_lengths_mm"' in source


def test_research_tunic_collision_probe_is_scoped_to_its_pr_branch():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "Run tunic collision/stitch probe" in workflow
    assert "startsWith(github.head_ref, 'agent/1986-')" in workflow
    assert "tunic-collision-probe" in workflow
