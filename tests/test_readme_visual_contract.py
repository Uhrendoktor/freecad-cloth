"""Contracts for the published README visual validation path."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_turntable_uses_real_blanket_drape_motion():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert 'Part::Feature", "BlanketTargetCube' in source
    assert 'BlanketSource' in source
    assert 'ClothPieces = [blanket]' in source
    assert 'set_avatar_collision_source(scene, cube, thickness=2.0, deflection=1.0)' in source
    assert 'blanket-motion-diagnostic' in source
    assert 'blanket-turntable-pass' in source
    assert 'if displacement < 40.0' in source
    assert 'minimum_z > cube_top + 35.0' in source


def test_readme_turntable_uses_authoritative_drape_target_api():
    turntable = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    simulation_objects = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    assert "set_avatar_collision_source(scene, cube" in turntable
    assert "scene.DrapeTarget = target" in simulation_objects
    assert "create_drape_target(doc, source_obj, target_type, deflection, thickness)" in simulation_objects
    assert "assign_drape_target(target, source_obj, target_type)" in simulation_objects


def test_canonical_workflow_fails_closed_on_turntable_quality():

    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "CLOTH_TISSU_SUBSTEPS: 10" in source
    assert "CLOTH_TISSU_COLLISION_MODE: mesh" in source
    assert "blanket-motion-diagnostic" in source
    assert "blanket-turntable-pass" in source
    assert 'test "$(find docs/images/generated/cloth-simulation-draped-turntable-frames' in source
    assert 'checkpoint-uniqueness=passed' in source
